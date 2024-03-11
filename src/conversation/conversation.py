from enum import Enum
import logging
from threading import Thread, Lock
import time
from typing import Any, Callable
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
    """Controls the flow of a conversation."""
    def __init__(self, context_for_conversation: context, output_manager: ChatManager, rememberer: remembering, is_conversation_too_long: Callable[[message_thread], bool], actions: list[action]) -> None:
        self.__context: context = context_for_conversation
        if not self.__context.npcs_in_conversation.contains_player_character():
            self.__conversation_type: conversation_type = radiant(context_for_conversation)
        else:
            self.__conversation_type: conversation_type = pc_to_npc(context_for_conversation.config.prompt)        
        self.__messages: message_thread = message_thread(None)
        self.__output_manager: ChatManager = output_manager
        self.__rememberer: remembering = rememberer
        self.__is_conversation_too_long: Callable[[message_thread], bool] = is_conversation_too_long
        self.__has_already_ended: bool = False        
        self.__sentences: sentence_queue = sentence_queue()
        self.__generation_thread: Thread | None = None
        self.__generation_start_lock: Lock = Lock()
        self.__actions: list[action] = actions

    @property
    def Has_already_ended(self) -> bool:
        return self.__has_already_ended
    
    def add_or_update_character(self, new_character: Character):
        """Adds a NPC character to the conversation. Turns the conversation into a multi-NPC conversation if applicable 

        Args:
            new_character (Character): the new character to add
        """
        self.__context.add_or_update_character(new_character)

        # #switch to multi-npc dialog
        # if isinstance(self.__conversation_type, pc_to_npc) and len(self.__context.npcs_in_conversation) > 1:
        #     self.__switch_to_multi_npc()
        #     # add greeting from newly added NPC to help the LLM understand that this NPC has joined the conversation
        #     for npc in self.__context.npcs_in_conversation.get_all_characters():
        #         if npc != new_character: 
        #             # existing NPCs greet the new NPC
        #             self.__messages.append_text_to_last_assitant_message(f"\n{npc.Name}: {self.__context.language['hello']} {new_character.Name}.")
        #         else: 
        #             # new NPC greets the existing NPCs
        #             self.__messages.append_text_to_last_assitant_message(f"\n{npc.Name}: {self.__context.language['hello']}.")
  
    # def __switch_to_multi_npc(self):
    #     """Switches the conversation to multi-npc
    #     """
    #     self.__conversation_type = multi_npc(self.__context.prompt_multinpc)
    #     self.__messages.turn_into_multi_npc_conversation(self.__conversation_type.generate_prompt(self.__context), True)
    #     self.__context.Have_actors_changed = False

    def start_conversation(self) -> tuple[str, sentence | None]:
        greeting: user_message | None = self.__conversation_type.get_user_message(self.__context, self.__messages)
        if greeting:
            self.__messages.add_message(greeting)
            self.__start_generating_npc_sentences()
            return comm_consts.KEY_REPLYTYPE_NPCTALK, None
        else:
            return comm_consts.KEY_REPLYTYPE_PLAYERTALK, None

    def continue_conversation(self) -> tuple[str, sentence | None]:
        if self.Has_already_ended:
            return comm_consts.KEY_REPLYTYPE_ENDCONVERSATION, None        
        if self.__is_conversation_too_long(self.__messages):
            # Check if conversation too long and if yes initiate intermittent reload
            self.__initiate_reload_conversation()

        next_sentence: sentence | None = self.retrieve_sentence_from_queue()
        if next_sentence and len(next_sentence.Sentence) > 0:
            return comm_consts.KEY_REPLYTYPE_NPCTALK, next_sentence
        else:
            if self.__conversation_type.should_end(self.__context, self.__messages):
                self.initiate_end_sequence()
                return comm_consts.KEY_REPLYTYPE_NPCTALK, None
            else:    
                new_user_message = self.__conversation_type.get_user_message(self.__context, self.__messages)
                if new_user_message:
                    self.__messages.add_message(new_user_message)
                    self.__start_generating_npc_sentences()
                    return comm_consts.KEY_REPLYTYPE_NPCTALK, None
                else:
                    return comm_consts.KEY_REPLYTYPE_PLAYERTALK, None

    def process_player_input(self, player_text: str):
        player_character = self.__context.npcs_in_conversation.get_player_character()
        if not player_character:
            return

        with self.__generation_start_lock:
            self.__stop_generation() # Stop generation of additional sentences right now
            self.__sentences.clear() # Clear any remaining sentences from the list

            # New spot for checking if a conversation needs to reload: right before a new player input is added
            # This makes sure, there is no more generation running at this point and thanks to the lock we are sure that no new generation is started while doing this
            
            new_message: user_message = user_message(player_text, player_character.Name )
            self.update_game_events(new_message)
            self.__messages.add_message(new_message)
            text = new_message.text
            logging.info(f"Text passed to NPC: {text}")

        if self.__has_conversation_ended(text):
            new_message.is_system_generated_message = True # Flag message containing goodbye as a system message to exclude from summary
            self.initiate_end_sequence()
        else:
            self.__start_generating_npc_sentences()

    def update_context(self, location: str, time: int, custom_ingame_events: list[str]):
        self.__context.update_context(location, time, custom_ingame_events)
        if self.__context.Have_actors_changed:
            self.__update_system_message()
            self.__context.Have_actors_changed = False

    def __update_system_message(self):
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
            self.__messages.reload_message_thread(new_prompt, 8)

    @utils.time_it
    def update_game_events(self, message: user_message) -> user_message:
        """Add in-game events to player's response"""

        message.add_event(self.__context.get_context_ingame_events())
        self.__context.clear_context_ingame_events()        

        if message.count_ingame_events() > 0:            
            logging.info(f'In-game events since previous exchange:\n{message.get_ingame_events_text()}')

        return message

    def retrieve_sentence_from_queue(self) -> sentence | None:
        next_sentence: sentence | None = self.__sentences.get_next_sentence() #This is a blocking call. Execution will wait here until queue is filled again
        if not next_sentence:
            return None
        
        if not next_sentence.Is_system_generated_sentence:
            last_message = self.__messages.get_last_message()
            if not isinstance(last_message, assistant_message):
                last_message = assistant_message("")
                self.__messages.add_message(last_message)
            last_message.add_sentence(next_sentence)
        return next_sentence
   
    @utils.time_it
    def initiate_end_sequence(self):
        """Sends last messages, saves the conversation, ends the conversation."""
        if not self.__has_already_ended:
            config = self.__context.config            
            self.__stop_generation()
            self.__sentences.clear()            
            # say goodbyes
            npc = self.__context.npcs_in_conversation.last_added_character
            if npc:
                goodbye_sentence = self.__output_manager.generate_sentence(config.goodbye_npc_response, npc, True)
                if goodbye_sentence:
                    goodbye_sentence.Actions.append(comm_consts.ACTION_ENDCONVERSATION)
                    self.__sentences.put(goodbye_sentence)
            # self.__has_already_ended = True

            # self.__messages.add_message(user_message(config.end_conversation_keyword+'.', config.player_name, is_system_generated_message=True))
            # self.__messages.add_message(assistant_message(config.end_conversation_keyword+'.', self.__context.npcs_in_conversation.get_all_names(), is_system_generated_message=True))
            
            # save conversation
            
            
            
            # self.__game_manager.end_conversation()

    def end(self):
        self.__has_already_ended = True
        self.__stop_generation()
        self.__sentences.clear()        
        self.__save_conversation()
    
    def __start_generating_npc_sentences(self):
        """Private method to get a reply from the LLM"""    
        with self.__generation_start_lock:
            if not self.__generation_thread:
                self.__sentences.Is_more_to_come = True
                self.__generation_thread = Thread(None, self.__output_manager.generate_response, None, [self.__messages, self.__context.npcs_in_conversation, self.__sentences, self.__actions]).start()   

    def __stop_generation(self):
        if self.__generation_thread and self.__generation_thread.is_alive():
            self.__output_manager.stop_generation()
            while self.__generation_thread and self.__generation_thread.is_alive():
                time.sleep(0.1)                

    def __save_conversation(self):
        """Saves conversation log and state for each NPC in the conversation"""
        if self.__context.npcs_in_conversation.contains_player_character():
            for npc in self.__context.npcs_in_conversation.get_all_characters():
                npc.save_conversation_log(self.__messages.transform_to_openai_messages(self.__messages.get_talk_only()))
            self.__rememberer.save_conversation_state(self.__messages, self.__context.npcs_in_conversation)
        # self.__remember_thread = Thread(None, self.__rememberer.save_conversation_state, None, [self.__messages, self.__context.npcs_in_conversation]).start()

    @utils.time_it
    def __initiate_reload_conversation(self):
        """Saves conversation and reloads it afterwards with reduced messages to reduce context length"""
        latest_npc = self.__context.npcs_in_conversation.last_added_character
        if not latest_npc: 
            self.initiate_end_sequence()
            return
        
        # Play gather thoughts
        collecting_thoughts_text = self.__context.config.collecting_thoughts_npc_response
        collecting_thoughts_sentence = self.__output_manager.generate_sentence(collecting_thoughts_text, latest_npc, True)        
        if collecting_thoughts_sentence:
            collecting_thoughts_sentence.Actions.append(comm_consts.ACTION_RELOADCONVERSATION)
            self.__sentences.put_at_front(collecting_thoughts_sentence)
    
    def reload_conversation(self):
        self.__save_conversation()
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
            