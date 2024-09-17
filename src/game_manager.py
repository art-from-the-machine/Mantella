import logging
import re
from typing import Any, Hashable
import regex
from collections import deque
from threading import Thread
import random
import time
from src.games.equipment import Equipment, EquipmentItem
from src.games.external_character_info import external_character_info
from src.games.gameable import gameable
from src.conversation.action import action
from src.llm.sentence import sentence
from src.output_manager import ChatManager
from src.remember.remembering import remembering
from src.remember.summaries import summaries
from src.config.config_loader import ConfigLoader
from src.llm.openai_client import openai_client
from src.conversation.conversation import conversation
from src.conversation.context import context
from src.character_manager import Character
import src.utils as utils
from src.http.communication_constants import communication_constants as comm_consts

class CharacterDoesNotExist(Exception):
    """Exception raised when NPC name cannot be found in skyrim_characters.csv/fallout4_characters.csv"""
    pass


class GameStateManager:
    TOKEN_LIMIT_PERCENT: float = 0.45  # not used?
    WORLD_ID_CLEANSE_REGEX: regex.Pattern = regex.compile('[^A-Za-z0-9]+')

    def __init__(self, game: gameable, chat_manager: ChatManager, config: ConfigLoader, language_info: dict[Hashable, str], client: openai_client):        
        self.__game: gameable = game
        self.__config: ConfigLoader = config
        self.__language_info: dict[Hashable, str] = language_info 
        self.__client: openai_client = client
        self.__chat_manager: ChatManager = chat_manager
        self.__rememberer: remembering = summaries(game, config.memory_prompt, config.resummarize_prompt, client, language_info['language'])
        self.__talk: conversation | None = None
        self.__actions: list[action] = [
            action(comm_consts.ACTION_NPC_OFFENDED, config.offended_npc_response, "The player offended the NPC"),
            action(comm_consts.ACTION_NPC_FORGIVEN, config.forgiven_npc_response, "The player made up with the NPC"),
            action(comm_consts.ACTION_NPC_FOLLOW, config.follow_npc_response, "The NPC is willing to follow the player"),
            action(comm_consts.ACTION_NPC_INVENTORY, config.inventory_npc_response, "The NPC is willing to show their inventory to the player")
        ]
        
        #Inner Thoughts
        self.inner_thoughts_prompt = self.__config.inner_thoughts_prompt
        self.multiple_inner_thoughts_prompt = self.__config.multiple_inner_thoughts_prompt
        self.command_memory = None  # Variable to store the temp thoughts
        self.thought_input = None  # Variable to store the injected thought
        self.intent_thoughts_length = self.__config.intent_thoughts_length  # Retrieve from config
        self.intent_thoughts = deque(maxlen=self.intent_thoughts_length)  # Use configurable length
        self.__temperature_i: float = self.__config.temperature_i
        self.__top_p_i: float = self.__config.top_p_i
        self.__frequency_penalty_i: float = self.__config.frequency_penalty_i
        self.__presence_penalty_i: float = self.__config.presence_penalty_i
        self.__max_tokens_i: int = self.__config.max_tokens_i

        # Start monitoring in a separate thread
        self.start_instruction_monitoring()      

    ###### React to calls from the game #######
    def start_conversation(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if self.__talk:  # This should only happen if game and server are out of sync due to some previous error -> close conversation and start a new one
            self.__talk.end()
            self.__talk = None
        world_id = "default"
        if input_json.__contains__(comm_consts.KEY_STARTCONVERSATION_WORLDID):
            world_id = input_json[comm_consts.KEY_STARTCONVERSATION_WORLDID]
            world_id = self.WORLD_ID_CLEANSE_REGEX.sub("", world_id)
        context_for_conversation = context(world_id, self.__config, self.__client, self.__rememberer, self.__language_info, self.__client.is_text_too_long)
        self.__talk = conversation(context_for_conversation, self.__chat_manager, self.__rememberer, self.__client, self.__actions)
        self.__update_context(input_json)
        self.__talk.start_conversation()
        
        return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTTYPE_STARTCONVERSATIONCOMPLETED}
    
    def continue_conversation(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if not self.__talk:
            return self.error_message("No running conversation.")
        
        if input_json.__contains__(comm_consts.KEY_REQUEST_EXTRA_ACTIONS):
            extra_actions: list[str] = input_json[comm_consts.KEY_REQUEST_EXTRA_ACTIONS]
            if extra_actions.__contains__(comm_consts.ACTION_RELOADCONVERSATION):
                self.__talk.reload_conversation()

        replyType, sentence_to_play = self.__talk.continue_conversation()
        reply: dict[str, Any] = {comm_consts.KEY_REPLYTYPE: replyType}
        if sentence_to_play:
            if not sentence_to_play.error_message:
                self.__game.prepare_sentence_for_game(sentence_to_play, self.__talk.context, self.__config)            
                reply[comm_consts.KEY_REPLYTYPE_NPCTALK] = self.sentence_to_json(sentence_to_play)
            else:
                self.__talk.end()
                return self.error_message(sentence_to_play.error_message)
        return reply

    def player_input(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if not self.__talk:
            return self.error_message("No running conversation.")
        
        player_text: str = input_json[comm_consts.KEY_REQUESTTYPE_PLAYERINPUT]
        self.__update_context(input_json)
        self.__talk.process_player_input(player_text)

        cleaned_player_text = utils.clean_text(player_text)
        npcs_in_conversation = self.__talk.context.npcs_in_conversation
        if not npcs_in_conversation.contains_multiple_npcs():  # Actions are only enabled in 1-1 conversations
            for action in self.__actions:
                # If the player response is just the name of an action, force the action to trigger
                if action.keyword.lower() == cleaned_player_text.lower():
                    return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_NPCACTION,
                            comm_consts.KEY_REPLYTYPE_NPCACTION: {
                                'mantella_actor_speaker': npcs_in_conversation.last_added_character.name,
                                'mantella_actor_actions': [action.game_action_identifier],
                                }
                            }
        
        # If the player response is not an action command, return a regular player reply type
        return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_NPCTALK}

    def end_conversation(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if self.__talk:
            self.__talk.end()
            self.__talk = None

        logging.log(24, '\nConversations not starting when you select an NPC? See here:')
        logging.log(25, 'https://art-from-the-machine.github.io/Mantella/pages/issues_qna')
        logging.log(24, '\nWaiting for player to select an NPC...')
        return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_ENDCONVERSATION}

    ####### JSON constructions #########

    def character_to_json(self, character_to_jsonfy: Character) -> dict[str, Any]:
        return {
            comm_consts.KEY_ACTOR_BASEID: character_to_jsonfy.base_id,
            comm_consts.KEY_ACTOR_NAME: character_to_jsonfy.name,
        }
    
    def sentence_to_json(self, sentence_to_prepare: sentence) -> dict[str, Any]:
        return {
            comm_consts.KEY_ACTOR_SPEAKER: sentence_to_prepare.speaker.name,
            comm_consts.KEY_ACTOR_LINETOSPEAK: sentence_to_prepare.sentence.strip(),
            comm_consts.KEY_ACTOR_VOICEFILE: sentence_to_prepare.voice_file,
            comm_consts.KEY_ACTOR_DURATION: sentence_to_prepare.voice_line_duration,
            comm_consts.KEY_ACTOR_ACTIONS: sentence_to_prepare.actions
        }

    ##### Utilities #######

    def __update_context(self, json: dict[str, Any]):
        if self.__talk:
            actors_in_json: list[Character] = []
            for actorJson in json[comm_consts.KEY_ACTORS]:
                actor: Character | None = self.load_character(actorJson)                
                if actor:
                    actors_in_json.append(actor)
            
            self.__talk.add_or_update_character(actors_in_json)
            location: str = json[comm_consts.KEY_CONTEXT].get(comm_consts.KEY_CONTEXT_LOCATION, None)
            time: int = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_TIME]
            ingame_events: list[str] = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_INGAMEEVENTS]
            custom_context_values: dict[str, Any] = {}
            weather = ""
            if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_WEATHER):
                weather = self.__game.get_weather_description(json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_WEATHER])
            if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_CUSTOMVALUES):
                custom_context_values = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_CUSTOMVALUES]
            self.__talk.update_context(location, time, ingame_events, weather, custom_context_values)

    @utils.time_it
    def load_character(self, json: dict[str, Any]) -> Character | None:
        try:
            base_id: str = utils.convert_to_skyrim_hex_format(str(json[comm_consts.KEY_ACTOR_BASEID]))
            ref_id: str = utils.convert_to_skyrim_hex_format(str(json[comm_consts.KEY_ACTOR_REFID]))
            ref_id = ref_id[-6:].upper()  # Ignore plugin ID at the start of the ref ID as this can vary by load order
            character_name: str = str(json[comm_consts.KEY_ACTOR_NAME])
            gender: int = int(json[comm_consts.KEY_ACTOR_GENDER])
            race: str = str(json[comm_consts.KEY_ACTOR_RACE])
            actor_voice_model: str = str(json[comm_consts.KEY_ACTOR_VOICETYPE])
            ingame_voice_model: str = actor_voice_model.split('<')[1].split(' ')[0]
            is_in_combat: bool = bool(json[comm_consts.KEY_ACTOR_ISINCOMBAT])
            is_enemy: bool = bool(json[comm_consts.KEY_ACTOR_ISENEMY])
            relationship_rank: int = int(json[comm_consts.KEY_ACTOR_RELATIONSHIPRANK])
            custom_values: dict[str, Any] = {}
            if json.__contains__(comm_consts.KEY_ACTOR_CUSTOMVALUES):
                custom_values = json[comm_consts.KEY_ACTOR_CUSTOMVALUES]
                if not custom_values:
                    custom_values: dict[str, Any] = {}
            equipment = Equipment({})
            if json.__contains__(comm_consts.KEY_ACTOR_EQUIPMENT):
                equipment = Equipment(self.__convert_to_equipment_item_dictionary(json[comm_consts.KEY_ACTOR_EQUIPMENT]))
            is_generic_npc: bool = False
            bio: str = ""
            tts_voice_model: str = ""
            csv_in_game_voice_model: str = ""
            advanced_voice_model: str = ""
            voice_accent: str = ""
            is_player_character: bool = bool(json[comm_consts.KEY_ACTOR_ISPLAYER])
            if self.__talk and self.__talk.contains_character(ref_id):
                already_loaded_character: Character | None = self.__talk.get_character(ref_id)
                if already_loaded_character:
                    bio = already_loaded_character.bio
                    tts_voice_model = already_loaded_character.tts_voice_model
                    csv_in_game_voice_model = already_loaded_character.csv_in_game_voice_model
                    advanced_voice_model = already_loaded_character.advanced_voice_model
                    voice_accent = already_loaded_character.voice_accent
                    is_generic_npc = already_loaded_character.is_generic_npc
            elif self.__talk and not is_player_character:  # If this is not the player and the character has not already been loaded
                external_info: external_character_info = self.__game.load_external_character_info(base_id, character_name, race, gender, actor_voice_model)
                
                bio = external_info.bio
                tts_voice_model = external_info.tts_voice_model
                csv_in_game_voice_model = external_info.csv_in_game_voice_model
                advanced_voice_model = external_info.advanced_voice_model
                voice_accent = external_info.voice_accent
                is_generic_npc = external_info.is_generic_npc
                if is_generic_npc:
                    character_name = external_info.name
                    ingame_voice_model = external_info.ingame_voice_model
            elif self.__talk and is_player_character and self.__config.voice_player_input:
                if custom_values.__contains__(comm_consts.KEY_ACTOR_PC_VOICEMODEL):
                    tts_voice_model = self.__get_player_voice_model(str(custom_values[comm_consts.KEY_ACTOR_PC_VOICEMODEL]))
                else:
                    tts_voice_model = self.__get_player_voice_model(None)

            return Character(base_id,
                            ref_id,
                            character_name,
                            gender,
                            race,
                            is_player_character,
                            bio,
                            is_in_combat,
                            is_enemy,
                            relationship_rank,
                            is_generic_npc,
                            ingame_voice_model,
                            tts_voice_model,
                            csv_in_game_voice_model,
                            advanced_voice_model,
                            voice_accent,
                            equipment,
                            custom_values)
        except CharacterDoesNotExist:                 
            logging.log(23, 'Restarting...')
            return None 
        
    def error_message(self, message: str) -> dict[str, Any]:
        return {
                comm_consts.KEY_REPLYTYPE: "error",
                "mantella_message": message
            }
    
    def __get_player_voice_model(self, game_value: str | None) -> str:
        if game_value is None:
            return self.__config.player_voice_model
        return game_value
    
    def __convert_to_equipment_item_dictionary(self, input_dict: dict[str, Any]) -> dict[str, EquipmentItem]:
        result: dict[str, EquipmentItem] = {}
        if input_dict:
            for slot, itemname in input_dict.items():
                result[slot] = EquipmentItem(itemname)
        return result

    ###### Inner Thoughts #######
    def start_instruction_monitoring(self):
        """Starts a background thread to monitor the instruction file."""
        thread = Thread(target=self.monitor_thoughts)
        thread.daemon = True
        thread.start()

    def monitor_thoughts(self):
        """Continuously monitors new thoughts."""
        logging.info("Starting creation of thoughts.")

        # Checks if the "Inner Thoughts" feature is enabled
        if not self.__config.auto_inner_thoughts:
            logging.info("Inner Thoughts feature is disabled. Monitoring stopped.")
            return

        while True:
            try:
				# Checks if a conversation is active
                if self.__talk is None:
                    logging.info("No active conversation. Monitoring paused.")
                    time.sleep(30)  # Wait a while before checking again
                    continue  # Continue the loop to check again

                # Check if the NPC is generating a response
                if not self.__chat_manager.is_generating():  # Verificação direta da variável de estado
                    # Get the latest conversations using the existing function
                    last_conversations = self.get_last_conversations()

                    assistant_message_type = self.get_thread_assistant_message
                    user_message_type = self.get_thread_user_message

                    # Prepare a JSON of conversations with 'role' and 'content'
                    conversations_json = []
                    if isinstance(last_conversations, list):
                        for msg in last_conversations:
                            if isinstance(msg, assistant_message_type):
                                role = "assistant"
                            elif isinstance(msg, user_message_type):
                                role = "user"
                            else:
                                continue  # Ignore messages of unexpected types

                            # Extract formatted content
                            content = msg.get_formatted_content()
                            if not isinstance(content, str):
                                logging.warning(f"Formatted content is not a string: {content}")
                                content = str(content)

                            # Add to JSON
                            conversations_json.append({'role': role, 'content': content})

                    if conversations_json:
                        # Creates behavioral summary based on formatted conversations
                        prompt = self.create_behavior_summary([conversations_json])
						
                        # Check if the prompt is not empty or only contains whitespace
                        if not prompt.strip():
                            logging.warning("Behavioral summary prompt is empty or contains only whitespace.")
                        else:
                            # Get behavior instruction only if prompt is valid
                            thought = self.get_behavior_instruction(prompt)
							
                            # Check if the thought is not empty or only contains whitespace
                            if not thought.strip():
                                logging.warning("Generated thought is empty or contains only whitespace. Not storing the thought.")
                            else:
                                # If the thought is valid, store it
                                self.create_thought(thought)
                                logging.info(f"Generated and Stored thought: {thought}")

                    else:
                        logging.info("No recent conversations found.")
                else:
                    logging.info("NPC is still speaking. Waiting for the NPC to finish.")

                # Attempt to retrieve any stored thought command after checking generation status
                data = self.retrieve_thought_command()
                if data:
					# Verificar se o NPC terminou de falar
                    if not self.__chat_manager.is_generating():  # Verificação direta da variável de estado
                        logging.info(f"Detected thought found: {data}")
                        # Stores the detected command for later use
                        self.thought_input = data
                        logging.info(f"Stored thought input: {self.thought_input}")
                    else:
                        logging.info("NPC is still speaking. Waiting for the NPC to finish.")
                else:
                    logging.info("No thought found.")


				# Determines wait time based on user configuration
                if self.__config.interval_type == "Random":
                    sleep_time = random.uniform(60, 180)
                else:
                    sleep_time = self.__config.fixed_interval  # Use user-defined fixed interval

                logging.info(f"Waiting {sleep_time:.2f} seconds before checking again.")
                time.sleep(sleep_time)

            except Exception as e:
                logging.error(f"Error on monitoring: {e}")
                time.sleep(120)


    def get_last_conversations(self, count: int = None) -> list[str]:
        
        # Use the configured default count if none is provided
        if count is None:
            count = self.__config.conversation_retrieval_count  # Retrieve from config
		
        message_thread = self.get_message_thread()  # Use the correct method to access the message_thread

        if message_thread:
            # Directly access the get_talk_only() method from message_thread
            messages = message_thread.get_talk_only()
            
            # Check for assistant messages directly using message_thread
            assistant_message_type = self.get_thread_assistant_message
            
            # Maybe filter here message type
            assistant_messages = [msg for msg in messages if isinstance(msg, assistant_message_type)]
            
            # Return the latest assistant conversations, limited by the specified amount
            return assistant_messages[-count:]
        else:
            print("Error: 'message_thread' not found")
            return []

    def get_current_npc_name(self) -> str:
        """Retrieve the current NPC's name from the conversation context."""
        if self.__talk and self.__talk.context and self.__talk.context.npcs_in_conversation:
            npcs_in_conversation = self.__talk.context.npcs_in_conversation
            if not npcs_in_conversation.contains_multiple_npcs():  # Ensure only one NPC is involved
                return npcs_in_conversation.last_added_character.name
        return "NPC"  # Default value if no specific NPC is identified


	
    def create_behavior_summary(self, conversations):
        """Create a behavioral and emotional summary of an NPC, based on recent conversations."""
		
        # Get the current NPC's name dynamically
        name = self.get_current_npc_name()
		
        # Check if there are recent conversations
        if not conversations:
            return f"{name} has no recent interactions to analyze. {name} remains neutral and attentive, awaiting their Thane's command."
		
        # Determine if multiple NPCs are involved
        npcs_in_conversation = self.__talk.context.npcs_in_conversation
        if not npcs_in_conversation.contains_multiple_npcs():  # 1-1 conversations
            # Use single NPC prompt
            prompt = self.inner_thoughts_prompt.replace("{name}", name)
        else:
            # Use multiple NPCs prompt
            names = ', '.join(npcs_in_conversation.get_all_names())  # Get the list of NPCs involved
            prompt = self.multiple_inner_thoughts_prompt.replace("{names}", names)

        # Append recent interactions to the prompt
        for conversation in conversations:
            for entry in conversation:
                role = entry['role']
                content = entry['content']
                # Format interaction in the style required by the prompt
                prompt += f"{role}: {content}\n"

        prompt += "\nYour Response:"

        return prompt


    def get_behavior_instruction(self, prompt):
        """Generate a behavior instruction using llm client."""
        try:
            # Generate a synchronous client and make the API call
            sync_client = self.__client.generate_sync_client()

            response = sync_client.chat.completions.create(
                model=self.__client.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.__max_tokens_i,
                temperature=self.__temperature_i,
                top_p=self.__top_p_i,
                frequency_penalty=self.__frequency_penalty_i,
                presence_penalty= self.__presence_penalty_i
            )

            sync_client.close()

            instruction = response.choices[0].message.content.strip()

            # Check whether the statement is empty or only contains special characters
            if not instruction:
                logging.warning("LLM - Inner Thought response is empty or contains only whitespace.")
                return "remain silent"

            # Check whether the statement contains at least one letter or number
            if not re.search(r'\w', instruction):
                logging.warning("LLM - Inner Thought response does not contain valid content.")
                return "remain silent"

            # Return the instruction directly
            return instruction

        except Exception as e:
            logging.error(f"Error calling the Mantella API: {e}")
            return "remain silent"


    def create_thought(self, instruction):
        """Create a command for Mantella based on the generated instruction."""
        
        # Replace the use of files with an instance variable
        if "remain silent" in instruction.lower():
            # Remove the command if NPC decides to remain silent
            if self.command_memory is not None:
                self.clear_thought_command()
                logging.info("No instruction was recorded as NPC decides to remain silent.")
            else:
                logging.info("NPC decides to remain silent; no command exists to be removed.")
        elif instruction.strip():  # Check if 'instruction' is not empty
            content = f"**{instruction}**"
            logging.info(f"Creating command for Mantella: {content}")
            try:
                # Store the command in the instance variable
                self.store_thought_command(content)
                logging.info(f"Instruction created and stored in the variable: {instruction}")
            except Exception as e:
                logging.error(f"Error storing the command in the variable: {e}")

    def get_thought_input(self):
        """Retrieve the thought input variable."""
        return self.thought_input  

    def clean_thought_input(self):
        """Clear the thought input variable."""
        self.thought_input = None
    
    def store_thought_command(self, command: str):
        """Store thought command variable."""
        self.command_memory = command  # Store the command in the variable
    
    def retrieve_thought_command(self):
        """Retrieve the thought command variable."""
        return self.command_memory  # Return the stored command
    
    def clear_thought_command(self):
        """Clear the thought command variable."""
        self.command_memory = None  # Clear the variable after use

    def get_message_thread(self):
        """Return the message_thread of the current conversation."""
        if self.__talk:
            return self.__talk.messages  # Access the message_thread via the getter method
        return None
        
    @property
    def get_thread_user_message(self):
        """Return the user_message message_thread of the current conversation."""
        if self.__talk:
            return self.__talk.user_message  # Access the message_thread via the getter method
        return None    

    @property
    def get_thread_assistant_message(self):
        """Return the assistant_message message_thread of the current conversation."""
        if self.__talk:
            return self.__talk.assistant_message  # Access the message_thread via the getter method
        return None    
