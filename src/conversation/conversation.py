from enum import Enum
import logging
from threading import Thread, Lock
import time
from typing import Any, Callable
from src.conversation.conversation_log import conversation_log
from src.conversation.action import action
from src.llm.sentence_queue import sentence_queue
from src.llm.sentence import sentence
from src.remember.remembering import remembering
from src.output_manager import ChatManager
from src.llm.messages import assistant_message, system_message, user_message
from src.conversation.context import context
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
    TOKEN_LIMIT_PERCENT: float = 0.6 # TODO: check if this is necessary as it has been removed from the main branch
    """Controls the flow of a conversation."""
    def __init__(self, context_for_conversation: context, output_manager: ChatManager, rememberer: remembering, is_conversation_too_long: Callable[[message_thread, float], bool], actions: list[action]) -> None:
        self.__context: context = context_for_conversation
        if not self.__context.npcs_in_conversation.contains_player_character(): # TODO: fix this being set to a radiant conversation because of NPCs in conversation not yet being added
            self.__conversation_type: conversation_type = radiant(context_for_conversation)
        else:
            self.__conversation_type: conversation_type = pc_to_npc(context_for_conversation.config.prompt)        
        self.__messages: message_thread = message_thread(None)
        self.__output_manager: ChatManager = output_manager
        self.__rememberer: remembering = rememberer
        self.__is_conversation_too_long: Callable[[message_thread, float], bool] = is_conversation_too_long
        self.__has_already_ended: bool = False        
        self.__sentences: sentence_queue = sentence_queue()
        self.__generation_thread: Thread | None = None
        self.__generation_start_lock: Lock = Lock()
        self.__actions: list[action] = actions

    @property
    def has_already_ended(self) -> bool:
        return self.__has_already_ended
    
    @property
    def context(self) -> context:
        return self.__context
    
    def add_or_update_character(self, new_character: Character):
        """Adds or updates a character in the conversation.

        Args:
            new_character (Character): the character to add or update
        """
        self.__context.add_or_update_character(new_character)

        # #switch to multi-npc dialog
        # if isinstance(self.__conversation_type, pc_to_npc) and len(self.__context.npcs_in_conversation) > 1:
        #     self.__switch_to_multi_npc()
        #     # add greeting from newly added NPC to help the LLM understand that this NPC has joined the conversation
        #     for npc in self.__context.npcs_in_conversation.get_all_characters():
        #         if npc != new_character: 
        #             # existing NPCs greet the new NPC
        #             self.__messages.append_text_to_last_assistant_message(f"\n{npc.name}: {self.__context.language['hello']} {new_character.name}.")
        #         else: 
        #             # new NPC greets the existing NPCs
        #             self.__messages.append_text_to_last_assistant_message(f"\n{npc.name}: {self.__context.language['hello']}.")

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

    def continue_conversation(self) -> tuple[str, sentence | None]:
        """Main workhorse of the conversation. Decides what happens next based on the state of the conversation

        Returns:
            tuple[str, sentence | None]: Returns a tuple consisting of a reply type and an optional sentence
        """
        if self.has_already_ended:
            return comm_consts.KEY_REPLYTYPE_ENDCONVERSATION, None        
        if self.__is_conversation_too_long(self.__messages, self.TOKEN_LIMIT_PERCENT):
            # Check if conversation too long and if yes initiate intermittent reload
            self.__initiate_reload_conversation()

        #Grab the next sentence from the queue
        next_sentence: sentence | None = self.retrieve_sentence_from_queue()
        if next_sentence and len(next_sentence.sentence) > 0:
            #if there is a next sentence and it actually has content, return it as something for an NPC to say 
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

    def process_player_input(self, player_text: str):
        """Submit the input of the player to the conversation

        Args:
            player_text (str): The input text / voice transcribe of what the player character is supposed to say
        """
        player_character = self.__context.npcs_in_conversation.get_player_character()
        if not player_character:
            return #If there is no player in the conversation, exit here

        with self.__generation_start_lock: #This lock makes sure no new generation by the LLM is started while we clear this
            self.__stop_generation() # Stop generation of additional sentences right now
            self.__sentences.clear() # Clear any remaining sentences from the list
            
            new_message: user_message = user_message(player_text, player_character.name, False)
            new_message.is_multi_npc_message = self.__context.npcs_in_conversation.contains_multiple_npcs()
            self.update_game_events(new_message)
            self.__messages.add_message(new_message)
            text = new_message.text
            logging.log(23, f"Text passed to NPC: {text}")

        if self.__has_conversation_ended(text):
            new_message.is_system_generated_message = True # Flag message containing goodbye as a system message to exclude from summary
            self.initiate_end_sequence()
        else:
            self.__start_generating_npc_sentences()

    def update_context(self, location: str, time: int, custom_ingame_events: list[str], custom_context_values: dict[str, Any]):
        """Updates the context with a new set of values

        Args:
            location (str): the location the characters are currently in
            time (int): the current ingame time
            custom_ingame_events (list[str]): a list of events that happend since the last update
            custom_context_values (dict[str, Any]): the current set of context values
        """
        self.__context.update_context(location, time, custom_ingame_events, custom_context_values)
        if self.__context.have_actors_changed:
            self.__update_conversation_type()
            self.__context.have_actors_changed = False

    def __update_conversation_type(self):
        """This changes between pc_to_npc, multi_npc and radiant conversation_types based on the current state of the context
        """
        # If the conversation can proceed for the first time, it starts and we add the system_message with the prompt
        if not self.__context.npcs_in_conversation.contains_player_character():
            self.__conversation_type = radiant(self.__context)
        elif self.__context.npcs_in_conversation.active_character_count() >= 3:
            self.__conversation_type = multi_npc(self.__context.config.multi_npc_prompt)
        else:
            self.__conversation_type = pc_to_npc(self.__context.config.prompt)

        new_prompt = self.__conversation_type.generate_prompt(self.__context)        
        if len(self.__messages) == 0:
            self.__messages: message_thread = message_thread(new_prompt)
        else:
            self.__conversation_type.adjust_existing_message_thread(self.__messages, self.__context)
            self.__messages.reload_message_thread(new_prompt, 8)

    @utils.time_it
    def update_game_events(self, message: user_message) -> user_message:
        """Add in-game events to player's response"""

        message.add_event(self.__context.get_context_ingame_events())
        self.__context.clear_context_ingame_events()        

        if message.count_ingame_events() > 0:            
            logging.log(28, f'In-game events since previous exchange:\n{message.get_ingame_events_text()}')

        return message

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
        
        if not next_sentence.is_system_generated_sentence:
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
            # say goodbyes
            npc = self.__context.npcs_in_conversation.last_added_character
            if npc:
                goodbye_sentence = self.__output_manager.generate_sentence(config.goodbye_npc_response, npc, True)
                if goodbye_sentence:
                    goodbye_sentence.actions.append(comm_consts.ACTION_ENDCONVERSATION)
                    self.__sentences.put(goodbye_sentence)
                    
    def contains_character(self, character_id: str) -> bool:
        for actor in self.__context.npcs_in_conversation.get_all_characters():
            if actor.id == character_id:
                return True
        return False
    
    def get_character(self, character_id: str) -> Character | None:
        for actor in self.__context.npcs_in_conversation.get_all_characters():
            if actor.id == character_id:
                return actor
        return None

    def end(self):
        """Ends a conversation
        """
        self.__has_already_ended = True
        self.__stop_generation()
        self.__sentences.clear()        
        self.__save_conversation(is_reload=False)
    
    def __start_generating_npc_sentences(self):
        """Starts a background Thread to generate sentences into the sentence_queue"""    
        with self.__generation_start_lock:
            if not self.__generation_thread:
                self.__sentences.is_more_to_come = True
                self.__generation_thread = Thread(None, self.__output_manager.generate_response, None, [self.__messages, self.__context.npcs_in_conversation, self.__sentences, self.__actions]).start()   

    def __stop_generation(self):
        """Stops the current generation of sentences if there is one
        """
        if self.__generation_thread and self.__generation_thread.is_alive():
            self.__output_manager.stop_generation()
            while self.__generation_thread and self.__generation_thread.is_alive():
                time.sleep(0.1)
            self.__generation_thread = None         

    def __save_conversation(self, is_reload: bool):
        """Saves conversation log and state for each NPC in the conversation"""
        for npc in self.__context.npcs_in_conversation.get_all_characters():
            if not npc.is_player_character:
                conversation_log.save_conversation_log(npc, self.__messages.transform_to_openai_messages(self.__messages.get_talk_only()))
        self.__rememberer.save_conversation_state(self.__messages, self.__context.npcs_in_conversation, is_reload)
        # self.__remember_thread = Thread(None, self.__rememberer.save_conversation_state, None, [self.__messages, self.__context.npcs_in_conversation]).start()

    @utils.time_it
    def __initiate_reload_conversation(self):
        """Places a "gather thoughts" sentence add the front of the queue that also prompts the game to request a reload of the conversation using an action"""
        latest_npc = self.__context.npcs_in_conversation.last_added_character
        if not latest_npc: 
            self.initiate_end_sequence()
            return
        
        # Play gather thoughts
        collecting_thoughts_text = self.__context.config.collecting_thoughts_npc_response
        collecting_thoughts_sentence = self.__output_manager.generate_sentence(collecting_thoughts_text, latest_npc, True)        
        if collecting_thoughts_sentence:
            collecting_thoughts_sentence.actions.append(comm_consts.ACTION_RELOADCONVERSATION)
            self.__sentences.put_at_front(collecting_thoughts_sentence)
    
    def reload_conversation(self):
        """Reloads the conversation
        """
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
        # transcriber = self.__stt
        config = self.__context.config
        transcript_cleaned = utils.clean_text(last_user_text)

        # check if user is ending conversation
        return Transcriber.activation_name_exists(transcript_cleaned, config.end_conversation_keyword.lower()) or (Transcriber.activation_name_exists(transcript_cleaned, 'good bye'))
            