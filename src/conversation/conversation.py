import asyncio
import logging
import sys
from src.game_manager import GameStateManager
from src.remember.remembering import remembering
from src.output_manager import ChatManager
from src.llm.messages import assistant_message, system_message, user_message
from src.conversation.context import context
from src.llm.message_thread import message_thread
from src.conversation.conversation_type import conversation_type, multi_npc, pc_to_npc, radiant
from src.character_manager import Character
from src.stt import Transcriber
from src.tts import Synthesizer
from src.tts import VoiceModelNotFound
import src.utils as utils

class conversation:
    """Controls the flow of a conversation."""
    def __init__(self, context_for_conversation: context, stt :Transcriber, tts: Synthesizer, game_manager: GameStateManager, output_manager: ChatManager, rememberer: remembering, is_radiant: bool, context_length: int = 4096, token_limit_percent: float = 0.45) -> None:
        self.__context: context = context_for_conversation
        if is_radiant:
            self.__conversation_type: conversation_type = radiant(context_for_conversation)
        else:
            self.__conversation_type: conversation_type = pc_to_npc(context_for_conversation.config.prompt)        
        self.__messages: message_thread = message_thread(None)
        self.__stt = stt
        self.__tts = tts
        self.__game_manager: GameStateManager = game_manager
        self.__output_manager: ChatManager = output_manager
        self.__rememberer: remembering = rememberer
        self.__context_length: int = context_length
        self.__token_limit_percent: float = 0.45
        self.__has_already_ended: bool = False

    def add_character(self, new_character: Character):
        """Adds a NPC character to the conversation. Turns the conversation into a multi-NPC conversation if applicable 

        Args:
            new_character (Character): the new character to add
        """
        self.__context.npcs_in_conversation.add_character(new_character)

        #switch to or continue multi-npc dialog
        if (isinstance(self.__conversation_type, pc_to_npc) and len(self.__context.npcs_in_conversation) > 1) or (isinstance(self.__conversation_type, multi_npc)):
            self.__switch_to_multi_npc()
            # add greeting from newly added NPC to help the LLM understand that this NPC has joined the conversation
            for npc in self.__context.npcs_in_conversation.get_all_characters():
                if npc != new_character: 
                    # existing NPCs greet the new NPC
                    self.__messages.append_text_to_last_assitant_message(f"\n{npc.name}: {self.__context.language['hello']} {new_character.name}.")
                else: 
                    # new NPC greets the existing NPCs
                    self.__messages.append_text_to_last_assitant_message(f"\n{npc.name}: {self.__context.language['hello']}.")            
    
    def __switch_to_multi_npc(self):
        """Switches the conversation to multi-npc
        """
        self.__conversation_type = multi_npc(self.__context.prompt_multinpc)
        self.__messages.turn_into_multi_npc_conversation(self.__conversation_type.generate_prompt(self.__context), True)
        self.__context.should_switch_to_multi_npc_conversation = False

    def proceed(self) -> bool:
        """Proceeds the conversation

        Returns:
            bool: returns True if the conversation is still ongoing, False otherwise
        """
        if self.__has_already_ended:
            return False
        
        # Check if the conversation can proceed at this moment. If not, skip this proceed and wait
        if not self.__conversation_type.can_proceed(self.__context):
            return True
        
        # If the conversation can proceed for the first time, it starts and we add the system_message with the prompt
        if len(self.__messages) == 0:
            self.__messages: message_thread = message_thread(self.__conversation_type.generate_prompt(self.__context))

        # Checks if the conversation should switch to multi-npc
        if self.__context.should_switch_to_multi_npc_conversation:
            self.__switch_to_multi_npc()
        
        # Allow the conversation_type to make changes before the user or assistant message is generated
        self.__conversation_type.pre_proceed_conversation(self.__context, self.__messages, self.__game_manager)
        
        # Add a user or assistant message based on the last message in the message_thread
        last_message = self.__messages.get_last_message()
        if isinstance(last_message, assistant_message) or isinstance(last_message, system_message):
            self.__add_user_message()
        else:
            self.__add_assistant_message()
            # After an assistant_message is generated, check if the current message exchange is about to break the context size of the LLM and if yes, reload the conversation
            if self.__output_manager.num_tokens(self.__messages) > (round(self.__context_length*self.__token_limit_percent,0)):
                self.__reload_conversation()

        # After a message has been added, check if the conversation_type decides to end the conversation 
        if self.__conversation_type.should_end(self.__context, self.__messages, self.__game_manager):
            self.end()
            return False
        
        return True

    @utils.time_it
    def end(self):
        """Sends last messages, saves the conversation, ends the conversation."""
        if not self.__has_already_ended:
            config = self.__context.config
            # say goodbyes
            npc = self.__output_manager.active_character
            if npc:
                self.__output_manager.play_sentence_ingame(config.goodbye_npc_response, npc)

            self.__messages.add_message(user_message(config.end_conversation_keyword+'.', config.player_name, is_system_generated_message=True))
            self.__messages.add_message(assistant_message(config.end_conversation_keyword+'.', self.__context.npcs_in_conversation.get_all_names(), is_system_generated_message=True))
            
            # save conversation
            self.__save_conversation(is_reload=False)
            
            self.__has_already_ended = True
            self.__game_manager.end_conversation()

    def __add_assistant_message(self):
        """Private method to get a reply from the LLM"""
        try:
            self.__messages = asyncio.run(self.__output_manager.get_response(self.__messages, self.__context.npcs_in_conversation, isinstance(self.__conversation_type,radiant)))
        except VoiceModelNotFound:
            self.__game_manager.write_game_info('_mantella_end_conversation', 'True')
            logging.info('Restarting...')
            # if debugging and character name not found, exit here to avoid endless loop
            if (self.__context.config.debug_mode == '1') & (self.__context.config.debug_character_name != 'None'):
                sys.exit(0)
            self.end()

    def __add_user_message(self):
        """Gets a user message. Either from the player or, depending on the state of the conversation, an automatic one"""
        new_message = self.__conversation_type.get_user_message(self.__context, self.__stt, self.__messages)
        self.__game_manager.update_game_events(new_message)
        self.__messages.add_message(new_message)
        text = new_message.text
        self.__game_manager.write_game_info('_mantella_player_input', text)
        logging.info(f"Text passed to NPC: {text.strip()}")
        if self.__has_conversation_ended(text):
            new_message.is_system_generated_message = True # Flag message containing goodbye as a system message to exclude from summary
            self.end()

    def __save_conversation(self, is_reload):
        """Saves conversation log and state for each NPC in the conversation"""
        for npc in self.__context.npcs_in_conversation.get_all_characters():
            npc.save_conversation_log(self.__messages)
        self.__rememberer.save_conversation_state(self.__messages, self.__context.npcs_in_conversation, is_reload)

    @utils.time_it
    def __reload_conversation(self):
        """Saves conversation and reloads it afterwards with reduced messages to reduce context length"""
        latest_npc = self.__context.npcs_in_conversation.last_added_character
        if not latest_npc: 
            self.end()
            return
        self.__tts.change_voice(latest_npc.voice_model, latest_npc.voice_accent)
        
        # Play gather thoughts
        collecting_thoughts_text = self.__context.config.collecting_thoughts_npc_response
        self.__output_manager.play_sentence_ingame(collecting_thoughts_text, latest_npc)
        # Add gather thought messages to thread
        self.__messages.add_message(user_message(latest_npc.name +'?', self.__context.config.player_name, is_system_generated_message=True))
        if len(self.__context.npcs_in_conversation) > 1:
            collecting_thoughts_response = latest_npc.name +': '+ collecting_thoughts_text +'.'
        else:
            collecting_thoughts_response = collecting_thoughts_text+'.'
        self.__messages.add_message(assistant_message(collecting_thoughts_response, self.__context.npcs_in_conversation.get_all_names(), is_system_generated_message=True))
        # Save conversation
        self.__save_conversation(is_reload=True)
        # Reload
        new_prompt = self.__conversation_type.generate_prompt(self.__context)
        self.__messages.reload_message_thread(new_prompt, 8)

    def __has_conversation_ended(self, last_user_text: str) -> bool:
        """Checks if the last player text has ended the conversation

        Args:
            last_user_text (str): the text to check

        Returns:
            bool: true if the conversation has ended, false otherwise
        """
        transcriber = self.__stt
        config = self.__context.config
        transcript_cleaned = utils.clean_text(last_user_text)
        # check if conversation has ended again after player input
        with open(f'{config.game_path}/_mantella_end_conversation.txt', 'r', encoding='utf-8') as f:
            conversation_ended = f.readline().strip()

        # check if user is ending conversation
        return transcriber.activation_name_exists(transcript_cleaned, config.end_conversation_keyword.lower()) or (transcriber.activation_name_exists(transcript_cleaned, 'good bye')) or (conversation_ended.lower() == 'true')
            