from collections import defaultdict
import logging
import os
import time
from typing import Dict, List
from src.games.gameable import gameable
from src.llm.llm_client import LLMClient
from src.llm.message_thread import message_thread
from src.llm.messages import assistant_message, join_message, leave_message, user_message
from src.characters_manager import Characters
from src.character_manager import Character
from src.remember.remembering import remembering
from src import utils

class batch_summaries(remembering):
    """ Stores a conversation as a summary in a text file.
        Loads the latest summary from disk for a prompt text.
    """
    def __init__(self, game: gameable, memory_prompt: str, resummarize_prompt: str, client: LLMClient, language_name: str, summary_limit_pct: float = 0.3) -> None:
        super().__init__()
        self.loglevel = 28
        self.__game: gameable = game
        self.__summary_limit_pct: float = summary_limit_pct
        self.__client: LLMClient = client
        self.__language_name: str = language_name
        self.__memory_prompt: str = memory_prompt
        self.__resummarize_prompt:str = resummarize_prompt

    @utils.time_it
    def get_prompt_text(self, npcs_in_conversation: Characters, world_id: str) -> str:
        """Load the conversation summaries for all NPCs in the conversation and returns them as one string

        Args:
            npcs_in_conversation (Characters): the npcs to load the summaries for

        Returns:
            str: a concatenation of the summaries as a single string
        """
        paragraphs = []
        for character in npcs_in_conversation.get_all_characters():
            if not character.is_player_character:          
                conversation_summary_file = self.__get_latest_conversation_summary_file_path(character, world_id)      
                if os.path.exists(conversation_summary_file):
                    with open(conversation_summary_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and line not in paragraphs:
                                paragraphs.append(line.strip())
        if paragraphs:
            result = "\n".join(paragraphs)
            return f"Below is a summary of past events:\n{result}"
        else:
            return ""

    @utils.time_it
    def save_conversation_state(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, is_reload=False):
        summary = ''
        characters = self.get_character_lookup_dict(messages)
        npc_message_threads = self.get_threads_for_summarization(messages)
        npcs_with_shared_threads = self.group_shared_threads(npc_message_threads)
        for thread, npc_names in npcs_with_shared_threads.items():
            summary = self.__create_new_conversation_summary(thread, npc_names[0])
            for npc_name in npc_names:
                self.__append_new_conversation_summary(summary, characters[npc_name], world_id)

    def get_character_lookup_dict(self, all_messages: message_thread) -> dict[str, Character]:
        """Returns a dictionary of character names to Character objects."""
        characters = {}
        for message in all_messages.get_messages_of_type((join_message)):
            if message._character == None or message._character.is_player_character:
                continue
            characters[message._character.name] = message._character
        return characters
 
    @utils.time_it
    def get_threads_for_summarization(self, all_messages: message_thread) -> dict[str, message_thread]:
        """Returns a dictionary of message threads per character name, each containing the messages that should be summarized for that character."""
        npcs_in_conversation: dict[str, bool] = {}
        npc_messageThreads: dict[str, message_thread] = {}

        for message in all_messages.get_messages_of_type((user_message, assistant_message, join_message, leave_message)):
            if isinstance(message, join_message) and not message._character.is_player_character:
                npcs_in_conversation[message._character.name] = True

            # Loop over all NPCs in the conversation where the value is True
            for char_name, in_conversation in npcs_in_conversation.items():
                if in_conversation:
                    if char_name not in npc_messageThreads:
                        npc_messageThreads[char_name] = message_thread(None)
                    thread: message_thread = npc_messageThreads[char_name]
                    
                    # Mark passage of time, in case a character left and rejoined the conversation
                    if thread.__len__() > 0:
                        npcs_previous_message = thread.get_last_message()
                        if isinstance(npcs_previous_message, leave_message) and npcs_previous_message._character.name == char_name:
                            thread.add_message(assistant_message("* some time later *"))
                    
                    thread.add_message(message)
            
            if isinstance(message, leave_message) and not message._character.is_player_character:
                npcs_in_conversation[message._character.name] = False

        return npc_messageThreads

    def group_shared_threads(self, npc_threads: Dict[str, message_thread]) -> Dict[message_thread, List[str]]:
        """
        Groups NPC message threads if they have exactly the same messages.

        Two threads are considered identical if the sequence of messages (by text) returned by 
        thread.get_talk_only() (when converted to a tuple of strings) is exactly equal.

        Returns:
        A dictionary mapping a representative message_thread to a list of NPC names that share that thread.
        """
        # Group NPCs by the exact tuple of message texts from their thread.
        thread_groups = defaultdict(list)
        for npc_name, thread in npc_threads.items():
            messages_tuple = tuple(message.text for message in thread.get_talk_only())
            thread_groups[messages_tuple].append(npc_name)

        # Build the result: for each group, select a representative thread.
        result: Dict[message_thread, List[str]] = {}
        for messages, npc_list in thread_groups.items():
            rep_npc = npc_list[0]
            rep_thread = npc_threads[rep_npc]
            result[rep_thread] = npc_list

        return result


                        

    @utils.time_it
    def __get_latest_conversation_summary_file_path(self, character: Character, world_id: str) -> str:
        """
        Get the path to the latest conversation summary file, prioritizing name_ref folders over legacy name folders.
        
        Args:
            character: Character object containing name and ref_id
            world_id: ID of the game world
        
        Returns:
            str: Path to the latest conversation summary file
        """
        # Remove trailing numbers from character names (e.g., "Whiterun Guard 1" -> "Whiterun Guard")
        base_name: str = utils.remove_trailing_number(character.name)
        name_ref: str = f'{base_name} - {character.ref_id}'
        
        def get_folder_path(folder_name: str) -> str:
            return os.path.join(self.__game.conversation_folder_path, world_id, folder_name).replace(os.sep, '/')
        
        def get_latest_file_number(folder_path: str) -> int:
            if not os.path.exists(folder_path):
                return 1
                
            txt_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
            if not txt_files:
                return 1
                
            file_numbers = [int(os.path.splitext(f)[0].split('_')[-1]) for f in txt_files]
            return max(file_numbers)
        
        # Check folders in priority order
        name_ref_path = get_folder_path(name_ref)
        name_path = get_folder_path(base_name)
        
        # Determine which folder path to use based on existence
        if os.path.exists(name_ref_path):
            target_folder = name_ref_path
            logging.info(f"Loaded latest summary file from: {target_folder}")
        elif os.path.exists(name_path):
            target_folder = name_path
            logging.info(f"Loaded latest summary file from: {target_folder}")
        else:
            target_folder = name_ref_path  # Use name_ref format for new folders
            logging.info(f"{name_ref_path} does not exist. A new summary file will be created.")
        
        latest_file_number = get_latest_file_number(target_folder)
        return f"{target_folder}/{base_name}_summary_{latest_file_number}.txt"
    
    @utils.time_it
    def __create_new_conversation_summary(self, messages: message_thread, npc_name: str) -> str:
        prompt = self.__memory_prompt.format(
                    name=npc_name,
                    language=self.__language_name,
                    game=self.__game
                )
        while True:
            try:
                if len(messages) >= 1:
                    return self.summarize_conversation(messages.transform_to_dict_representation(messages.get_talk_only()), prompt, npc_name)
                else:
                    logging.info(f"Conversation summary not saved. Not enough dialogue spoken.")
                break
            except:
                logging.error('Failed to summarize conversation. Retrying...')
                time.sleep(5)
                continue
        return ""

    @utils.time_it
    def __append_new_conversation_summary(self, new_summary: str, npc: Character, world_id: str):
        # if this is not the first conversation
        conversation_summary_file = self.__get_latest_conversation_summary_file_path(npc, world_id)
        if os.path.exists(conversation_summary_file):
            with open(conversation_summary_file, 'r', encoding='utf-8') as f:
                previous_conversation_summaries = f.read()
        # if this is the first conversation
        else:
            directory = os.path.dirname(conversation_summary_file)
            os.makedirs(directory, exist_ok=True)
            previous_conversation_summaries = ''
       
        if len(new_summary) > 0:
            conversation_summaries = previous_conversation_summaries + new_summary
            with open(conversation_summary_file, 'w', encoding='utf-8') as f:
                f.write(conversation_summaries)
        else:
            conversation_summaries = previous_conversation_summaries
            

        summary_limit = round(self.__client.token_limit*self.__summary_limit_pct,0)

        count_tokens_summaries = self.__client.get_count_tokens(conversation_summaries)
        # if summaries token limit is reached, summarize the summaries
        if count_tokens_summaries > summary_limit:
            logging.info(f'Token limit of conversation summaries reached ({count_tokens_summaries} / {summary_limit} tokens). Creating new summary file...')
            while True:
                try:
                    prompt = self.__resummarize_prompt.format(
                        name=npc.name,
                        language=self.__language_name,
                        game=self.__game
                    )
                    long_conversation_summary = self.summarize_conversation(conversation_summaries, prompt, npc.name)
                    break
                except:
                    logging.error('Failed to summarize conversation. Retrying...')
                    time.sleep(5)
                    continue

            # Split the file path and increment the number by 1
            base_directory, filename = os.path.split(conversation_summary_file)
            file_prefix, old_number = filename.rsplit('_', 1)
            old_number = os.path.splitext(old_number)[0]
            new_number = int(old_number) + 1
            new_conversation_summary_file = os.path.join(base_directory, f"{file_prefix}_{new_number}.txt")

            with open(new_conversation_summary_file, 'w', encoding='utf-8') as f:
                f.write(long_conversation_summary)
            
            # npc.conversation_summary_file = self.__get_latest_conversation_summary_file_path(npc)

    @utils.time_it
    def summarize_conversation(self, text_to_summarize: str, prompt: str, npc_name: str) -> str:
        summary = ''
        if len(text_to_summarize) > 0:
            messages = message_thread(prompt)
            messages.add_message(user_message(text_to_summarize))
            summary = self.__client.request_call(messages)
            if not summary:
                logging.info(f"Summarizing conversation failed.")
                return ""

            summary = summary.replace('The assistant', npc_name)
            summary = summary.replace('the assistant', npc_name)
            summary = summary.replace('an assistant', npc_name)
            summary = summary.replace('an AI assistant', npc_name)
            summary = summary.replace('The user', 'The player')
            summary = summary.replace('the user', 'the player')
            summary += '\n\n'

            logging.log(self.loglevel, f'Conversation summary: {summary.strip()}')
            logging.info(f"Conversation summary saved")
        else:
            logging.info(f"Conversation summary not saved. Not enough dialogue spoken.")

        return summary