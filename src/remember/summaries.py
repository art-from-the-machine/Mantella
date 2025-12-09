import logging
import os
import time
from src.config.config_loader import ConfigLoader
from src.games.gameable import Gameable
from src.llm.llm_client import LLMClient
from src.llm.message_thread import message_thread
from src.llm.messages import UserMessage
from src.characters_manager import Characters
from src.character_manager import Character
from src.remember.remembering import Remembering
from src import utils

class Summaries(Remembering):
    """ Stores a conversation as a summary in a text file.
        Loads the latest summary from disk for a prompt text.
    """
    def __init__(self, game: Gameable, config: ConfigLoader, client: LLMClient, language_name: str, summary_limit_pct: float = 0.3) -> None:
        super().__init__()
        self.loglevel = 28
        self.__config = config
        self.__game: Gameable = game
        self.__summary_limit_pct: float = summary_limit_pct
        self.__client: LLMClient = client
        self.__language_name: str = language_name
        self.__memory_prompt: str = config.memory_prompt
        self.__resummarize_prompt:str = config.resummarize_prompt

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
                conversation_summary_file = self.__get_latest_conversation_summary_file_path(character.name, character.ref_id, world_id)      
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
    def save_conversation_state(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, is_reload=False, pending_shares: list[tuple[str, str, str]] | None = None, end_timestamp: float | None = None):
        summary = ''
        
        for npc in npcs_in_conversation.get_all_characters():
            if not npc.is_player_character:
                if len(summary) < 1: # if a summary has not already been generated, make one
                    summary = self.__create_new_conversation_summary(messages, npc.name, end_timestamp)
                if len(summary) > 0 or is_reload: # if a summary has been generated, give the same summary to all NPCs
                    self.__append_new_conversation_summary(summary, npc.name, npc.ref_id, world_id)
        
        # Handle pending shares: write summary with prefix to recipient folders
        if pending_shares and len(summary) > 0:
            for sharer_name, recipient_name, recipient_ref_id in pending_shares:
                # Build participant names list, excluding the sharer and annotating the player
                participant_names = []
                for npc in npcs_in_conversation.get_all_characters():
                    if npc.name == sharer_name:
                        continue  # Exclude sharer from participant list
                    if npc.is_player_character:
                        participant_names.append(f"{npc.name} (the player)")
                    else:
                        participant_names.append(npc.name)
                
                # Create prefixed summary
                participants_text = ", ".join(participant_names) if participant_names else "others"
                prefixed_summary = f"{sharer_name} shared with {recipient_name} a conversation with {participants_text}:\n{summary}"
                
                self.__append_new_conversation_summary(prefixed_summary, recipient_name, recipient_ref_id, world_id)
                logging.info(f"Shared conversation summary with {recipient_name}")

    @utils.time_it
    def __get_latest_conversation_summary_file_path(self, npc_name: str, npc_ref_id: str, world_id: str) -> str:
        """
        Get the path to the latest conversation summary file, prioritizing name_ref folders over legacy name folders.
        
        Args:
            npc_name: Name of the NPC
            npc_ref_id: The ref_id of the NPC
            world_id: ID of the game world
        
        Returns:
            str: Path to the latest conversation summary file
        """
        # Remove trailing numbers from character names (e.g., "Whiterun Guard 1" -> "Whiterun Guard")
        base_name: str = utils.remove_trailing_number(npc_name)
        name_ref: str = f'{base_name} - {npc_ref_id}'
        
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
    def __create_new_conversation_summary(self, messages: message_thread, npc_name: str, end_timestamp: float | None = None) -> str:
        prompt = self.__memory_prompt.format(
                    name=npc_name,
                    language=self.__language_name,
                    game=self.__game.game_name_in_filepath
                )
        while True:
            try:
                if len(messages) >= 5:
                    summary = self.summarize_conversation(messages.transform_to_dict_representation(messages.get_talk_only()), prompt, npc_name)
                    # Prepend timestamp to summary if available
                    if summary and end_timestamp is not None and self.__config.memory_prompt_datetime_prefix:
                        timestamp_prefix = self.__format_timestamp(end_timestamp)
                        summary = f"{timestamp_prefix}\n{summary}"
                    return summary
                else:
                    logging.info(f"Conversation summary not saved. Not enough dialogue spoken.")
                break
            except:
                logging.error('Failed to summarize conversation. Retrying...')
                time.sleep(5)
                continue
        return ""

    @utils.time_it
    def __append_new_conversation_summary(self, new_summary: str, npc_name: str, npc_ref_id: str, world_id: str):
        # if this is not the first conversation
        conversation_summary_file = self.__get_latest_conversation_summary_file_path(npc_name, npc_ref_id, world_id)
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
                        name=npc_name,
                        language=self.__language_name,
                        game=self.__game.game_name_in_filepath
                    )
                    long_conversation_summary = self.summarize_conversation(conversation_summaries, prompt, npc_name)
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
    def __format_timestamp(self, game_days: float) -> str:
        """Formats a game timestamp into readable format: [Day X, Y in the evening]
        
        Args:
            game_days: Game time as days passed (eg 42.75 = Day 42, 6pm)
        
        Returns:
            str: Formatted timestamp like "[Day 42, 6 in the evening]"
        """
        days = int(game_days)
        hours = int((game_days - days) * 24)
        in_game_time_twelve_hour = hours - 12 if hours > 12 else hours
        
        return f"[Day {days}, {in_game_time_twelve_hour} {utils.get_time_group(hours)}]"
    
    @utils.time_it
    def summarize_conversation(self, text_to_summarize: str, prompt: str, npc_name: str) -> str:
        summary = ''
        if len(text_to_summarize) > 5:
            messages = message_thread(self.__config, prompt)
            messages.add_message(UserMessage(self.__config, text_to_summarize))
            summary = self.__client.request_call(messages)
            if not summary:
                logging.error(f"Summarizing conversation failed.")
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