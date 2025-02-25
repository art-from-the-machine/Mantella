from enum import Enum
import logging
from threading import Thread, Lock
import time
from typing import Any
from src.llm.ai_client import AIClient
from src.llm.sentence_content import SentenceTypeEnum, sentence_content
from src.characters_manager import Characters
from src.conversation.conversation_log import conversation_log
from src.conversation.action import action
from src.llm.sentence_queue import sentence_queue
from src.llm.sentence import sentence
from src.remember.remembering import remembering
from src.output_manager import ChatManager
from src.llm.messages import assistant_message, join_message, leave_message, system_message, user_message
from src.conversation.context import add_or_update_result, context
from src.llm.message_thread import message_thread
from src.conversation.conversation_type import conversation_type, multi_npc, pc_to_npc, radiant
from src.character_manager import Character
from src.http.communication_constants import communication_constants as comm_consts
from src.stt import Transcriber
import src.utils as utils

class conversation_continue_type(Enum):
    NPC_TALK = 1
    PLAYER_TALK = 2
    END_CONVERSATION = 3

class conversation:
    TOKEN_LIMIT_PERCENT: float = 0.9
    TOKEN_LIMIT_RELOAD_MESSAGES: float = 0.1
    """Controls the flow of a conversation."""
    def __init__(self, context_for_conversation: context, output_manager: ChatManager, rememberer: remembering, llm_client: AIClient, stt: Transcriber | None, mic_input: bool, mic_ptt: bool) -> None:
        
        self.__context: context = context_for_conversation
        self.__mic_input: bool = mic_input
        self.__mic_ptt: bool = mic_ptt
        self.__allow_interruption: bool = context_for_conversation.config.allow_interruption # allow mic interruption
        self.__is_player_interrupting = False
        self.__stt: Transcriber | None = stt
        self.__events_refresh_time: float = context_for_conversation.config.events_refresh_time  # Time in seconds before events are considered stale
        self.__transcribed_text: str | None = None
        if not self.__context.npcs_in_conversation.contains_player_character(): # TODO: fix this being set to a radiant conversation because of NPCs in conversation not yet being added
            self.__conversation_type: conversation_type = radiant(context_for_conversation.config)
        else:
            self.__conversation_type: conversation_type = pc_to_npc(context_for_conversation.config)        
        self.__messages: message_thread = message_thread(None)
        self.__output_manager: ChatManager = output_manager
        self.__rememberer: remembering = rememberer
        self.__llm_client = llm_client
        self.__has_already_ended: bool = False
        self.__allow_mic_input: bool = True # this flag ensures mic input is disabled on conversation end
        self.__sentences: sentence_queue = sentence_queue()
        self.__generation_thread: Thread | None = None
        self.__generation_start_lock: Lock = Lock()
        # self.__actions: list[action] = actions
        self.last_sentence_audio_length = 0
        self.last_sentence_start_time = time.time()
        self.__end_conversation_keywords = utils.parse_keywords(context_for_conversation.config.end_conversation_keyword)

    @property
    def has_already_ended(self) -> bool:
        return self.__has_already_ended
    
    @property
    def context(self) -> context:
        return self.__context
    
    @property
    def output_manager(self) -> ChatManager:
        return self.__output_manager
    
    @property
    def transcribed_text(self) -> str | None:
        return self.__transcribed_text
    
    @property
    def stt(self) -> Transcriber | None:
        return self.__stt
    
    @utils.time_it
    def add_or_update_character(self, new_character: list[Character]):
        """Adds or updates a character in the conversation.

        Args:
            new_character (Character): the character to add or update
        """
        update_result = self.__context.add_or_update_characters(new_character)
        if len(update_result.removed_npcs) > 0:
            all_characters = self.__context.npcs_in_conversation.get_all_characters()
            all_characters.extend(update_result.removed_npcs)
            self.__save_conversation_log_for_characters(all_characters)
            
        # mark the joining / leaving of an npc in the message_thread
        for update_message in self.generate_add_or_remove_messages(update_result):
            self.__messages.add_message(update_message)

    @utils.time_it
    def generate_add_or_remove_messages(self, update_result: add_or_update_result) -> list[str]:
        add_or_remove_messages = []
        for npc in update_result.added_npcs:
            if not npc.is_player_character:
                add_or_remove_messages.append(join_message(npc))
        for npc in update_result.removed_npcs:
            if not npc.is_player_character:
                add_or_remove_messages.append(leave_message(npc))
        return add_or_remove_messages

    @utils.time_it
    def start_conversation(self) -> tuple[str, sentence | None]:
        """Starts a new conversation.

        Returns:
            tuple[str, sentence | None]: Returns a tuple consisting of a reply type and an optional sentence
        """
        greeting: user_message | None = self.__conversation_type.get_user_message(self.__context, self.__messages)
        if greeting:
            self.__messages.add_message(greeting)
            self.__start_generating_npc_sentences()
            return comm_consts.KEY_REPLYTYPE_NPCTALK, None
        else:
            return comm_consts.KEY_REPLYTYPE_PLAYERTALK, None

    @utils.time_it
    def continue_conversation(self) -> tuple[str, sentence | None]:
        """Main workhorse of the conversation. Decides what happens next based on the state of the conversation

        Returns:
            tuple[str, sentence | None]: Returns a tuple consisting of a reply type and an optional sentence
        """
        if self.has_already_ended:
            return comm_consts.KEY_REPLYTYPE_ENDCONVERSATION, None        
        if self.__llm_client.is_too_long(self.__messages, self.TOKEN_LIMIT_PERCENT):
            # Check if conversation too long and if yes initiate intermittent reload
            self.__initiate_reload_conversation()

        # interrupt response if player has spoken
        if self.__stt and self.__stt.has_player_spoken:
            self.__stop_generation()
            self.__sentences.clear()
            self.__is_player_interrupting = True
            return comm_consts.KEY_REQUESTTYPE_TTS, None
        
        # restart mic listening as soon as NPC's first sentence is processed
        if self.__mic_input and self.__allow_interruption and not self.__mic_ptt and not self.__stt.is_listening and self.__allow_mic_input and not isinstance(self.__conversation_type, radiant):
            mic_prompt = self.__get_mic_prompt()
            self.__stt.start_listening(mic_prompt)
        
        #Grab the next sentence from the queue
        next_sentence: sentence | None = self.retrieve_sentence_from_queue()
        
        if next_sentence and len(next_sentence.text) > 0:
            if comm_consts.ACTION_REMOVECHARACTER in next_sentence.actions:
                self.__context.remove_character(next_sentence.speaker)
            #if there is a next sentence and it actually has content, return it as something for an NPC to say
            if self.last_sentence_audio_length > 0:
                logging.debug(f'Waiting {round(self.last_sentence_audio_length, 1)} seconds for last voiceline to play')
            # before immediately sending the next voiceline, give the player the chance to interrupt
            while time.time() - self.last_sentence_start_time < self.last_sentence_audio_length:
                if self.__stt and self.__stt.has_player_spoken:
                    self.__stop_generation()
                    self.__sentences.clear()
                    self.__is_player_interrupting = True
                    return comm_consts.KEY_REQUESTTYPE_TTS, None
                time.sleep(0.01)
            self.last_sentence_audio_length = next_sentence.voice_line_duration + self.__context.config.wait_time_buffer
            self.last_sentence_start_time = time.time()
            return comm_consts.KEY_REPLYTYPE_NPCTALK, next_sentence
        else:
            #Ask the conversation type here, if we should end the conversation
            if self.__conversation_type.should_end(self.__context, self.__messages):
                self.initiate_end_sequence()
                return comm_consts.KEY_REPLYTYPE_NPCTALK, None
            else:
                #If not ended, ask the conversation type for an automatic user message. If there is None, signal the game that the player must provide it 
                new_user_message = self.__conversation_type.get_user_message(self.__context, self.__messages)
                if new_user_message:
                    self.__messages.add_message(new_user_message)
                    self.__start_generating_npc_sentences()
                    return comm_consts.KEY_REPLYTYPE_NPCTALK, None
                else:
                    return comm_consts.KEY_REPLYTYPE_PLAYERTALK, None

    @utils.time_it
    def process_player_input(self, player_text: str) -> tuple[str, bool, sentence|None]:
        """Submit the input of the player to the conversation

        Args:
            player_text (str): The input text / voice transcribe of what the player character is supposed to say. Can be empty if mic input has not yet been parsed

        Returns:
            tuple[str, bool]: Returns a tuple consisting of updated player text (if using mic input) and whether or not in-game events need to be refreshed (depending on how much time has passed)
        """
        player_character = self.__context.npcs_in_conversation.get_player_character()
        if not player_character:
            return '', False, None # If there is no player in the conversation, exit here
        
        events_need_updating: bool = False

        with self.__generation_start_lock: #This lock makes sure no new generation by the LLM is started while we clear this
            self.__stop_generation() # Stop generation of additional sentences right now
            self.__sentences.clear() # Clear any remaining sentences from the list

            # If the player's input does not already exist, parse mic input if mic is enabled
            if self.__mic_input and len(player_text) == 0:
                player_text = None
                if not self.__stt.is_listening and self.__allow_mic_input:
                    self.__stt.start_listening(self.__get_mic_prompt())
                
                # Start tracking how long it has taken to receive a player response
                input_wait_start_time = time.time()
                while not player_text:
                    player_text = self.__stt.get_latest_transcription()
                if time.time() - input_wait_start_time >= self.__events_refresh_time:
                    # If too much time has passed, in-game events need to be updated
                    events_need_updating = True
                    logging.debug('Updating game events...')
                    return player_text, events_need_updating, None
                
                # Stop listening once input has been detected to give the NPC a chance to speak
                # This also needs to apply when interruptions are allowed, 
                # otherwise the player could constantly speak over the NPC and never hear a response
                self.__stt.stop_listening()
            
            new_message: user_message = user_message(player_text, player_character.name, False)
            new_message.is_multi_npc_message = self.__context.npcs_in_conversation.contains_multiple_npcs()
            new_message = self.update_game_events(new_message)
            self.__messages.add_message(new_message)
            player_voiceline = self.__get_player_voiceline(player_character, player_text)
            text = new_message.text
            logging.log(23, f"Text passed to NPC: {text}")

        ejected_npc = self.__does_dismiss_npc_from_conversation(text)
        if ejected_npc:
            self.__prepare_eject_npc_from_conversation(ejected_npc)
        elif self.__has_conversation_ended(text):
            new_message.is_system_generated_message = True # Flag message containing goodbye as a system message to exclude from summary
            self.initiate_end_sequence()
        else:
            self.__start_generating_npc_sentences()

        return player_text, events_need_updating, player_voiceline

    def __get_mic_prompt(self):
        mic_prompt = f"This is a conversation with {self.__context.get_character_names_as_text(False)} in {self.__context.location}."
        #logging.log(23, f'Context for mic transcription: {mic_prompt}')
        return mic_prompt
    
    @utils.time_it
    def __get_player_voiceline(self, player_character: Character | None, player_text: str) -> sentence | None:
        """Synthesizes the player's input if player voice input is enabled, or else returns None
        """
        player_character_voiced_sentence: sentence | None = None
        if self.__should_voice_player_input(player_character):
            player_character_voiced_sentence = self.__output_manager.generate_sentence(sentence_content(player_character, player_text, SentenceTypeEnum.SPEECH, False))
            if player_character_voiced_sentence.error_message:
                player_message_content: sentence_content = sentence_content(player_character, player_text, SentenceTypeEnum.SPEECH, False)
                player_character_voiced_sentence = sentence(player_message_content, "" , 2.0)

        return player_character_voiced_sentence

    @utils.time_it
    def update_context(self, location: str | None, time: int, custom_ingame_events: list[str], weather: str, custom_context_values: dict[str, Any]):
        """Updates the context with a new set of values

        Args:
            location (str): the location the characters are currently in
            time (int): the current ingame time
            custom_ingame_events (list[str]): a list of events that happend since the last update
            custom_context_values (dict[str, Any]): the current set of context values
        """
        self.__context.update_context(location, time, custom_ingame_events, weather, custom_context_values)
        if self.__context.have_actors_changed:
            self.__update_conversation_type()
            self.__context.have_actors_changed = False

    @utils.time_it
    def __update_conversation_type(self):
        """This changes between pc_to_npc, multi_npc and radiant conversation_types based on the current state of the context
        """
        # If the conversation can proceed for the first time, it starts and we add the system_message with the prompt
        if not self.__has_already_ended:
            self.__stop_generation()
            self.__sentences.clear()
            
            if not self.__context.npcs_in_conversation.contains_player_character():
                self.__conversation_type = radiant(self.__context.config)
            elif self.__context.npcs_in_conversation.active_character_count() >= 3:
                self.__conversation_type = multi_npc(self.__context.config)
            else:
                self.__conversation_type = pc_to_npc(self.__context.config)

            new_prompt = self.__conversation_type.generate_prompt(self.__context)        
            if len(self.__messages) == 0:
                self.__messages: message_thread = message_thread(new_prompt)
            else:
                self.__conversation_type.adjust_existing_message_thread(new_prompt, self.__messages)
                self.reload_and_cull_thread(new_prompt)

    @utils.time_it
    def reload_and_cull_thread(self, new_prompt):
        """Reloads the message thread and removes old messages if getting close to context limits"""
        removed_messages = self.__messages.reload_message_thread(new_prompt, self.__llm_client.is_too_long, self.TOKEN_LIMIT_RELOAD_MESSAGES)
        if len(removed_messages) > 0:
            removed_messages_thread = message_thread(None)
            for message in removed_messages:
                removed_messages_thread.add_message(message)
            # Summarize the removed messages
            self.__save_summary_for_characters(removed_messages_thread, self.__context.npcs_in_conversation.get_all_characters(), true)
            conversation_log.save_conversation_log(self.__context.npcs_in_conversation.get_all_characters(), removed_messages, self.__context.world_id)
        

    @utils.time_it
    def update_game_events(self, message: user_message) -> user_message:
        """Add in-game events to player's response"""

        all_ingame_events = self.__context.get_context_ingame_events()
        if self.__is_player_interrupting:
            all_ingame_events.append('Interrupting...')
            self.__is_player_interrupting = False
        max_events = min(len(all_ingame_events) ,self.__context.config.max_count_events)
        message.add_event(all_ingame_events[-max_events:])
        self.__context.clear_context_ingame_events()        

        if message.count_ingame_events() > 0:            
            logging.log(28, f'In-game events since previous exchange:\n{message.get_ingame_events_text()}')

        return message

    @utils.time_it
    def retrieve_sentence_from_queue(self) -> sentence | None:
        """Retrieves the next sentence from the queue.
        If there is a sentence, adds the sentence to the last assistant_message of the message_thread.
        If the last message is not an assistant_message, a new one will be added.

        Returns:
            sentence | None: The next sentence from the queue or None if the queue is empty
        """
        next_sentence: sentence | None = self.__sentences.get_next_sentence() #This is a blocking call. Execution will wait here until queue is filled again
        if not next_sentence:
            return None
        
        if not next_sentence.is_system_generated_sentence and not next_sentence.speaker.is_player_character:
            last_message = self.__messages.get_last_message()
            if not isinstance(last_message, assistant_message):
                last_message = assistant_message()
                last_message.is_multi_npc_message = self.__context.npcs_in_conversation.contains_multiple_npcs()
                self.__messages.add_message(last_message)
            last_message.add_sentence(next_sentence)
        return next_sentence
   
    @utils.time_it
    def initiate_end_sequence(self):
        """Replaces all remaining sentences with a "goodbye" sentence that also prompts the game to request a stop to the conversation using an action
        """
        if not self.__has_already_ended:
            config = self.__context.config            
            self.__stop_generation()
            self.__sentences.clear()
            if self.__stt:
                self.__stt.stop_listening()
                self.__allow_mic_input = False
            # say goodbyes
            npc = self.__context.npcs_in_conversation.last_added_character
            if npc:
                goodbye_sentence = self.__output_manager.generate_sentence(sentence_content(npc, config.goodbye_npc_response, SentenceTypeEnum.SPEECH, True))
                if goodbye_sentence:
                    goodbye_sentence.actions.append(comm_consts.ACTION_ENDCONVERSATION)
                    self.__sentences.put(goodbye_sentence)
                    
    @utils.time_it
    def contains_character(self, ref_id: str) -> bool:
        for actor in self.__context.npcs_in_conversation.get_all_characters():
            if actor.ref_id == ref_id:
                return True
        return False
    
    @utils.time_it
    def get_character(self, ref_id: str) -> Character | None:
        for actor in self.__context.npcs_in_conversation.get_all_characters():
            if actor.ref_id == ref_id:
                return actor
        return None

    @utils.time_it
    def end(self):
        """Ends a conversation
        """
        self.__has_already_ended = True
        self.__stop_generation()
        self.__sentences.clear()
        self.__save_summary()
    
    @utils.time_it
    def __start_generating_npc_sentences(self):
        """Starts a background Thread to generate sentences into the sentence_queue"""    
        with self.__generation_start_lock:
            if not self.__generation_thread:
                self.__sentences.is_more_to_come = True
                self.__generation_thread = Thread(None, self.__output_manager.generate_response, None, [self.__messages, self.__context.npcs_in_conversation, self.__sentences, self.context.config.actions]).start()   

    @utils.time_it
    def __stop_generation(self):
        """Stops the current generation of sentences if there is one
        """
        self.__output_manager.stop_generation()
        while self.__generation_thread and self.__generation_thread.is_alive():
            time.sleep(0.1)
        self.__generation_thread = None

    @utils.time_it
    def __prepare_eject_npc_from_conversation(self, npc: Character):
        if not self.__has_already_ended:            
            self.__stop_generation()
            self.__sentences.clear()            
            # say goodbye
            goodbye_sentence = self.__output_manager.generate_sentence(sentence_content(npc, self.__context.config.goodbye_npc_response, SentenceTypeEnum.SPEECH, False))
            if goodbye_sentence:
                goodbye_sentence.actions.append(comm_consts.ACTION_REMOVECHARACTER)
                self.__sentences.put(goodbye_sentence)        

    @utils.time_it
    def __save_summary(self):
        """Saves conversation log and state for each NPC in the conversation"""
        self.__save_summary_for_characters(self.__messages, self.__context.npcs_in_conversation.get_all_characters())

    @utils.time_it
    def __save_conversation_log_for_characters(self, characters_to_save_for: list[Character] ):
        for npc in characters_to_save_for:
            if not npc.is_player_character:
                conversation_log.save_conversation_log(npc, self.__messages.transform_to_openai_messages(self.__messages.get_talk_only()), self.__context.world_id)
                
    @utils.time_it
    def __save_summary_for_characters(self, messages_to_summarize:message_thread, characters_to_save_for: list[Character], is_reload=False):
        characters_object = Characters()
        for npc in characters_to_save_for:
            if not npc.is_player_character:
                characters_object.add_or_update_character(npc)
        # Save the summary
        self.__rememberer.save_conversation_state(messages_to_summarize, characters_object, self.__context.world_id, is_reload)
        # Save the log
        self.__save_conversation_log_for_characters(characters_to_save_for)

    @utils.time_it
    def __initiate_reload_conversation(self):
        """Places a "gather thoughts" sentence add the front of the queue that also prompts the game to request a reload of the conversation using an action"""
        latest_npc = self.__context.npcs_in_conversation.last_added_character
        if not latest_npc: 
            self.initiate_end_sequence()
            return
        
        # Play gather thoughts
        collecting_thoughts_text = self.__context.config.collecting_thoughts_npc_response
        collecting_thoughts_sentence = self.__output_manager.generate_sentence(sentence_content(latest_npc, collecting_thoughts_text, SentenceTypeEnum.SPEECH, True))
        if collecting_thoughts_sentence:
            collecting_thoughts_sentence.actions.append(comm_consts.ACTION_RELOADCONVERSATION)
            self.__sentences.put_at_front(collecting_thoughts_sentence)
    
    @utils.time_it
    def reload_conversation(self):
        """Reloads the conversation
        """
        new_prompt = self.__conversation_type.generate_prompt(self.__context)
        self.__messages.reload_message_thread(new_prompt, self.__llm_client.is_too_long, self.TOKEN_LIMIT_RELOAD_MESSAGES)

    @utils.time_it
    def __has_conversation_ended(self, last_user_text: str) -> bool:
        """Checks if the last player text has ended the conversation

        Args:
            last_user_text (str): the text to check

        Returns:
            bool: true if the conversation has ended, false otherwise
        """
        # transcriber = self.__stt
        config = self.__context.config
        transcript_cleaned = utils.clean_text(last_user_text)

        # check if user is ending conversation
        return Transcriber.activation_name_exists(transcript_cleaned, self.__end_conversation_keywords)

    @utils.time_it
    def __does_dismiss_npc_from_conversation(self, last_user_text: str) -> Character | None:
        """Checks if the last player text dismisses an NPC from the conversation

        Args:
            last_user_text (str): the text to check

        Returns:
            bool: true if the conversation has ended, false otherwise
        """
        transcript_cleaned = utils.clean_text(last_user_text)

        words = transcript_cleaned.split()
        for i, word in enumerate(words):
            if word in self.__end_conversation_keywords:
                if i < (len(words) - 1):
                    next_word = words[i + 1]
                    for npc_name in self.__context.npcs_in_conversation.get_all_names():
                        if next_word in npc_name.lower().split():
                            return self.__context.npcs_in_conversation.get_character_by_name(npc_name)
        return None
    
    @utils.time_it
    def __should_voice_player_input(self, player_character: Character) -> bool:
        game_value: Any = player_character.get_custom_character_value(comm_consts.KEY_ACTOR_PC_VOICEPLAYERINPUT)
        if game_value == None:
            return self.__context.config.voice_player_input
        return game_value