from collections import defaultdict
import logging
import os
import time
from typing import Dict, List
from src.config.config_loader import ConfigLoader
from src.games.gameable import Gameable
from src.llm.summary_client import SummaryLLMCLient
from src.llm.client_base import ClientBase
from src.llm.llm_client import LLMClient
from src.llm.message_thread import message_thread
from src.llm.messages import assistant_message, join_message, leave_message, UserMessage
from src.characters_manager import Characters
from src.character_manager import Character
from src.remember.remembering import Remembering
from src import utils


class CharacterSummaryParameters:
    def __init__(self, messages: message_thread, involved_characters: List[Character]) -> None:
        self.messages = messages
        self.characters = involved_characters


class CharacterSummaryParameters:
    def __init__(self, messages: message_thread, involved_characters: List[Character]) -> None:
        self.messages = messages
        self.characters = involved_characters


class Summaries(Remembering): 
    """ Stores a conversation as a summary in a text file.
        Loads the latest summary from disk for a prompt text.
    """
    def __init__(self, game: Gameable, config: ConfigLoader, client: LLMClient, language_name: str, summary_client: ClientBase | None = None, summary_limit_pct: float = 0.3) -> None:
        super().__init__()
        self.loglevel = 28
        self.__config = config
        self.__game: Gameable = game
        self.__summary_limit_pct: float = summary_limit_pct
        self.__client: LLMClient = client
        self.__summary_client: ClientBase = summary_client if summary_client else client  # Use separate client for summaries if provided
        self.__language_name: str = language_name
        self.__memory_prompt: str = config.memory_prompt
        self.__resummarize_prompt:str = config.resummarize_prompt

    @utils.time_it
    def get_prompt_text(self, npcs_in_conversation: Characters, world_id: str) -> str:
        """Load the conversation summaries for all NPCs in the conversation and returns them as one string

        Args:
            npcs_in_conversation (Characters): the npcs to load the summaries for
            world_id (str): the world identifier

        Returns:
            str: a concatenation of the summaries as a single string
        """
        # Get all non-player characters
        non_player_characters = [char for char in npcs_in_conversation.get_all_characters() if not char.is_player_character]
        
        if len(non_player_characters) == 1:
            # Single NPC conversation - no delimiters needed
            paragraphs = []
            character = non_player_characters[0]
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
        else:
            # Multi-NPC conversation - add delimiters around each character's memories
            character_memories = []
            for character in non_player_characters:
                character_paragraphs = []
                conversation_summary_file = self.__get_latest_conversation_summary_file_path(character, world_id)      
                if os.path.exists(conversation_summary_file):
                    with open(conversation_summary_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                character_paragraphs.append(line.strip())
                
                if character_paragraphs:
                    # Add delimiters around this character's memories
                    memory_with_delimiters = f"[This is the beginning of {character.name}'s memory]\n" + \
                                           "\n".join(character_paragraphs) + \
                                           f"\n[This is the end of {character.name}'s memory]"
                    character_memories.append(memory_with_delimiters)
            
            if character_memories:
                result = "\n\n".join(character_memories)
                return f"Below is a summary of past events:\n{result}"
            else:
                return ""

    @utils.time_it
    def get_character_summary(self, character: Character, world_id: str) -> str:
        """ Gets the summary for a specific character
        
        Args:
            character (Character): the character to get the summary for
            world_id (str): the world ID
            
        Returns:
            str: the summary text for this character, or empty string if no summary exists
        """
        conversation_summary_file = self.__get_latest_conversation_summary_file_path(character, world_id)      
        if os.path.exists(conversation_summary_file):
            paragraphs = []
            with open(conversation_summary_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        paragraphs.append(line.strip())
            if paragraphs:
                return "\n".join(paragraphs)
        return ""
    
    @utils.time_it
    def may_add_missing_join_leave_messages(self, messages: message_thread) -> bool:
        """ Adds missing join and leave messages to the beginning / end of the message thread."""
        hadMissingMessages = False
        characters_found = {}
        characters_joined = {}
        characters_left = {}
    
        # check if every join message has a leave message and vice versa
        for message in messages.get_messages_of_type((join_message)):
            if not message.character.is_player_character:
                name = message.character.name
                characters_joined[name] = message.character
                characters_found[name] = message.character
        
        for message in messages.get_messages_of_type((leave_message)):
            if not message.character.is_player_character:
                name = message.character.name
                characters_left[name] = message.character
                characters_found[name] = message.character

    
        # Insert the missing messages at the appropriate places
        if len(characters_joined) < len(characters_found):
            for name, character in characters_found.items():
                if name not in characters_joined:
                    messages.insert_after_system_messages(join_message(character, self.__config))
                    hadMissingMessages = True
        if len(characters_left) < len(characters_found):
            for name, character in characters_found.items():
                if name not in characters_left:
                    messages.add_message(leave_message(character, self.__config))
                    hadMissingMessages = True
        return hadMissingMessages

    @utils.time_it
    def save_conversation_state(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, is_reload=False):
        summary = ''
        # If we truncated the conversation due to running out of context, join and leave messages may be missing
        self.may_add_missing_join_leave_messages(messages)
        
        characters = self.get_character_lookup_dict(messages)
        npc_message_threads: Dict[str, CharacterSummaryParameters] = self.get_threads_for_summarization(messages, characters)
        npcs_with_shared_threads = self.group_shared_threads(npc_message_threads)
        
        for npc_names in npcs_with_shared_threads:
           summary = self.__create_new_conversation_summary(npc_message_threads[npc_names[0]], world_id)
           for npc_name in npc_names:
               self.__append_new_conversation_summary(summary, characters[npc_name], world_id)
        
        
                

    def get_character_lookup_dict(self, all_messages: message_thread) -> Dict[str, Character]:
        """Returns a dictionary of character names to Character objects."""
        characters = {}
        for message in all_messages.get_messages_of_type((join_message)):
            if not isinstance(message, (join_message, leave_message)) or message.character == None or message.character.is_player_character:
                continue
            characters[message.character.name] = message.character
        return characters

    @utils.time_it
    def get_threads_for_summarization(self, all_messages: message_thread, characters:Dict[str, Character]) -> Dict[str, CharacterSummaryParameters]:
        """
        Returns a dictionary mapping an NPC's name to a CharacterSummaryParameters object,
        which encapsulates the npc's message_thread and the list of Characters they've seen.
        """
        npcs_in_conversation: Dict[str, bool] = {}
        def set_in_conversation(npc: Character, in_conversation: bool):
            npcs_in_conversation[npc.name] = in_conversation
        
        npc_messageThreads: Dict[str, message_thread] = {}
        npc_has_seen_npcs: Dict[str, Dict[str, Character]] = {}

        for message in all_messages.get_persistent_messages():
            # Mark npc as present when they join
            if isinstance(message, join_message) and not message.character.is_player_character:
                set_in_conversation(message.character, True)

            # Add the message for each npc that was in the conversation to hear this message
            for npc_name, in_conversation in npcs_in_conversation.items():
                # For each npc we extract a list of all the other npcs that have been in the conversation with them at the same time
                for npc_name2, in_conversation2 in npcs_in_conversation.items():
                    if in_conversation and in_conversation2:
                        if npc_has_seen_npcs.get(npc_name) is None:
                            npc_has_seen_npcs[npc_name] = {}
                        npc_has_seen_npcs[npc_name][npc_name2] = characters[npc_name2]  # Assuming message.character represents the Character.
                
                # We also store the message for the npc if they are in the conversation for it
                if in_conversation:
                    if npc_name not in npc_messageThreads:
                        npc_messageThreads[npc_name] = message_thread(self.__config, None)
                    thread: message_thread = npc_messageThreads[npc_name]
                    
                    # Mark passage of time, in case a character left and rejoined the conversation
                    if len(thread) > 0:
                        npcs_previous_message = thread.get_last_message()
                        if isinstance(npcs_previous_message, leave_message) and npcs_previous_message.character.name == npc_name:
                            narration_start, narration_end = self.__config.get_narration_indicators()
                            thread.add_message(user_message(self.__config, narration_start + "some time later*" + narration_end))
                    
                    thread.add_message(message)
            
            # Mark npc as absent when they leave 
            if isinstance(message, leave_message) and not message.character.is_player_character:
                set_in_conversation(message.character, False)

        # Prepare the result
        result: Dict[str, CharacterSummaryParameters] = {}
        for npc_name, seen_npcs_dict in npc_has_seen_npcs.items():
            if npc_name not in npc_messageThreads:
                continue
            seen_npcs = [seen_npcs_dict[key] for key in seen_npcs_dict]
            thread = npc_messageThreads[npc_name]
            result[npc_name] = CharacterSummaryParameters(thread, seen_npcs)
            
        return result

    def group_shared_threads(self, npc_threads: Dict[str, CharacterSummaryParameters]) -> list[list[str]]:
        """
        Groups NPC message threads if they have exactly the same messages.

        Two threads are considered identical if the sequence of messages (by text) returned by 
        thread.get_talk_only() (when converted to a tuple of strings) is exactly equal.

        Returns:
        A dictionary mapping a representative message_thread to a list of NPC names that share that thread.
        """
        # Group NPCs by the exact tuple of message texts from their thread.
        thread_groups = defaultdict(list)
        for npc_name, summary_params in npc_threads.items():
            messages_tuple = tuple(message.text for message in summary_params.messages.get_talk_only())
            thread_groups[messages_tuple].append(npc_name)

        # Build the result: for each group, select a representative thread.
        result: list[list[str]] = []
        for messages, npc_list in thread_groups.items():
            result.append(npc_list)

        return result

                        

    @utils.time_it
    def __get_latest_conversation_summary_file_path(self, character: Character, world_id: str, log_file_info) -> str:
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
            if log_file_info:
                logging.info(f"Loaded latest summary file from: {target_folder}")
        elif os.path.exists(name_path):
            target_folder = name_path
            if log_file_info:
                logging.info(f"Loaded latest summary file from: {target_folder}")
        else:
            target_folder = name_ref_path  # Use name_ref format for new folders
            logging.info(f"{name_ref_path} does not exist. A new summary file will be created.")
        
        latest_file_number = get_latest_file_number(target_folder)
        return f"{target_folder}/{base_name}_summary_{latest_file_number}.txt"
    
    @utils.time_it
    def __create_new_conversation_summary(self, npcInfo:CharacterSummaryParameters, world_id: str) -> str:
        if self.__config.game == "Fallout4" or self.__config.game == "Fallout4VR":
            location: str = 'the Commonwealth'
        else:
            location: str = "Skyrim"
        
        bios = '\n\n'.join([f"{c.name}: {c.bio}" for c in npcInfo.characters])
        names = ', '.join([c.name for c in npcInfo.characters])
        # Try to extract player name from the latest user message; default to 'the player'
        player_name = "the player"
        try:
            talk_messages = messages.get_talk_only()
            for m in reversed(talk_messages):
                if isinstance(m, UserMessage):
                    pn = m.player_character_name if hasattr(m, 'player_character_name') else ""
                    if pn:
                        player_name = pn
                        break
        except Exception:
            pass

        prompt = self.__memory_prompt.format(
                    name=names,
                    names=names,
                    language=self.__language_name,
                    game=location, 
                    bios=bios,
                    conversation_summaries=self.__get_prompt_text(npcInfo.characters, world_id, False),
                    player_name=player_name
                )
        while True:
            try:
                if len(npcInfo.messages) >= 5:
                    return self.summarize_conversation(npcInfo.messages.transform_to_dict_representation(npcInfo.messages.get_talk_only()), prompt)
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
        conversation_summary_file = self.__get_latest_conversation_summary_file_path(npc, world_id,False)
        if os.path.exists(conversation_summary_file):
            with open(conversation_summary_file, 'r', encoding='utf-8') as f:
                previous_conversation_summaries = f.read()
        # if this is the first conversation
        else:
            directory = os.path.dirname(conversation_summary_file)
            os.makedirs(directory, exist_ok=True)
            previous_conversation_summaries = ''
       
        if len(new_summary) > 0:
            # Add dash prefix to new summary if it doesn't already have one
            if not new_summary.strip().startswith('-'):
                new_summary = '- ' + new_summary.strip() + '\n\n'
            else:
                new_summary = new_summary.strip() + '\n\n'
                
            conversation_summaries = previous_conversation_summaries + new_summary
            with open(conversation_summary_file, 'w', encoding='utf-8') as f:
                f.write(conversation_summaries)
        else:
            conversation_summaries = previous_conversation_summaries
            

        summary_limit = round(self.__summary_client.token_limit*self.__summary_limit_pct,0)

        count_tokens_summaries = self.__summary_client.get_count_tokens(conversation_summaries)
        # if summaries token limit is reached, summarize the summaries
        if count_tokens_summaries > summary_limit:
            logging.info(f'Token limit of conversation summaries reached ({count_tokens_summaries} / {summary_limit} tokens). Creating new summary file...')
            while True:
                try:
                    # Try to extract player name from existing summaries if present is not needed here; default to last known from recent talks
                    player_name = "the player"
                    try:
                        # Attempt to infer from latest user talk messages in current session
                        # Note: we cannot access original conversation messages here, so fallback remains 'the player'
                        pass
                    except Exception:
                        pass

                    prompt = self.__resummarize_prompt.format(
                        name=npc.name,
                        language=self.__language_name,
                        game=self.__game,
                        player_name=player_name
                    )
                    long_conversation_summary = self.summarize_conversation(conversation_summaries, prompt)
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
            
    @utils.time_it
    def summarize_conversation(self, text_to_summarize: str, prompt: str) -> str:
        summary = ''
        if len(text_to_summarize) > 5:
            messages = message_thread(self.__config, prompt)
            messages.add_message(UserMessage(self.__config, text_to_summarize))

            # Log the summary prompt being sent
            logging.log(23, f'Summary prompt sent to LLM: {prompt.strip()}')

            summary = self.__summary_client.request_call(messages)
            if not summary:
                logging.info(f"Summarizing conversation failed.")
                return ""

            npc_name = "Someone"
            summary = summary.replace('The assistant', npc_name)
            summary = summary.replace('the assistant', npc_name)
            summary = summary.replace('an assistant', npc_name)
            summary = summary.replace('an AI assistant', npc_name)
            summary = summary.replace('The user', 'The player')
            summary = summary.replace('the user', 'the player')
            summary += '\n\n'

            # Log which LLM is being used for the summary
            summary_llm_info = f"local model ({self.__summary_client.model_name})" if self.__summary_client.is_local else self.__summary_client.model_name
            logging.log(self.loglevel, f'Creating conversation summary using: {summary_llm_info}')
            logging.log(self.loglevel, f'Conversation summary: {summary.strip()}')
            logging.info(f"Conversation summary saved")
        else:
            logging.info(f"Conversation summary not saved. Not enough dialogue spoken.")

        return summary