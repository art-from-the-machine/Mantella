from collections import defaultdict
import os
import time
from typing import Dict, List
from src.config.config_loader import ConfigLoader
from src.config.definitions.game_definitions import GameEnum
from src.games.gameable import Gameable
from src.llm.client_base import ClientBase
from src.llm.llm_client import LLMClient
from src.llm.summary_client import SummaryLLMClient
from src.llm.message_thread import message_thread
from src.llm.messages import UserMessage, AssistantMessage
from src.characters_manager import Characters
from src.character_manager import Character
from src.remember.remembering import Remembering
from src import utils

logger = utils.get_logger()


class CharacterSummaryParameters:
    """Encapsulates the messages and involved characters for a single NPC's summary."""
    def __init__(self, messages: message_thread, involved_characters: List[Character]) -> None:
        self.messages = messages
        self.characters = involved_characters


class Summaries(Remembering):
    """ Stores a conversation as a summary in a text file.
        Loads the latest summary from disk for a prompt text.
    """
    def __init__(self, game: Gameable, config: ConfigLoader, client: LLMClient, language_name: str, summary_client: SummaryLLMClient | None = None, summary_limit_pct: float = 0.3) -> None:
        super().__init__()
        self.loglevel = 28
        self.__config = config
        self.__game: Gameable = game
        self.__summary_limit_pct: float = summary_limit_pct
        self.__client: ClientBase = summary_client if summary_client else client
        self.__language_name: str = language_name
        self.__memory_prompt: str = config.memory_prompt
        self.__resummarize_prompt: str = config.resummarize_prompt

    def __read_summary_lines(self, file_path: str, deduplicate: bool = False) -> list[str]:
        """Read a summary file and return non-empty stripped lines.

        Args:
            file_path: Path to the summary file
            deduplicate: If True, skip lines already seen

        Returns:
            list[str]: Non-empty stripped lines from the file
        """
        if not os.path.exists(file_path):
            return []
        lines = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped and (not deduplicate or stripped not in lines):
                    lines.append(stripped)
        return lines

    @utils.time_it
    def get_prompt_text(self, characters: list[Character], world_id: str) -> str:
        """Load the conversation summaries for all NPCs in the conversation and returns them as one string

        Args:
            characters (list[Character]): the non-player NPCs to load summaries for
            world_id (str): the world identifier used to separate summary folders by player characters

        Returns:
            str: a concatenation of the summaries as a single string
        """
        multi_npc = len(characters) > 1
        character_memories = []
        for character in characters:
            conversation_summary_file = self.__get_latest_conversation_summary_file_path(character, world_id)
            paragraphs = self.__read_summary_lines(conversation_summary_file, deduplicate=True)
            if not paragraphs:
                continue
            memory = "\n".join(paragraphs)
            if multi_npc:
                memory = f"[This is the beginning of {character.name}'s memory]\n{memory}\n[This is the end of {character.name}'s memory]"
            character_memories.append(memory)

        if not character_memories:
            return ""
        return f"Below is a summary of past events:\n" + "\n\n".join(character_memories)


    @utils.time_it
    def save_conversation_state(self, messages: message_thread, npcs_to_summarize: list[Character], npcs_in_conversation: Characters, world_id: str, is_reload=False, pending_shares: list[tuple[str, str, str]] | None = None, end_timestamp: float | None = None):
        """Save conversation summaries for the requested NPCs, with per-NPC thread tracking.

        NPCs only get summaries of the messages they actually heard (based on participation log).
        NPCs with identical message histories share a single LLM summarization call.

        Args:
            messages: The full conversation message thread
            npcs_to_summarize: The NPCs to generate summaries for
            npcs_in_conversation: All NPCs with participation history (for thread building and pending shares)
            world_id: The world identifier
            is_reload: Whether this is a reload (save even if summary is empty)
            pending_shares: List of (sharer_name, recipient_name, recipient_ref_id) for memory sharing
            end_timestamp: Optional timestamp to prepend to summaries
        """
        npc_message_threads: Dict[str, CharacterSummaryParameters] = self.get_threads_for_summarization(messages, npcs_in_conversation)

        # Filter to only the NPCs the caller wants summarized
        names_to_summarize = {c.name for c in npcs_to_summarize}
        npc_message_threads = {name: params for name, params in npc_message_threads.items() if name in names_to_summarize}

        npcs_with_shared_threads = self.group_shared_threads(npc_message_threads)

        # Track per-NPC summaries for pending_shares
        npc_summaries: Dict[str, str] = {}

        # Set a lower threshold for reloads to capture brief interactions, 
        # and a higher threshold for normal saves to avoid trivial summaries (eg "Guard: Hello there. Player: Goodbye.").
        min_messages = 2 if is_reload else 5

        for npc_names in npcs_with_shared_threads:
            # Generate one summary per unique conversation experience
            summary = self.__create_new_conversation_summary(npc_message_threads[npc_names[0]], npcs_in_conversation, world_id, end_timestamp, min_messages=min_messages)

            # Write the same summary to all NPCs who heard the same messages
            for npc_name in npc_names:
                npc_summaries[npc_name] = summary
                if summary or is_reload:
                    character = next(c for c in npcs_to_summarize if c.name == npc_name)
                    self.__append_new_conversation_summary(summary, character, world_id)

        # Handle pending shares: write summary with prefix to recipient folders
        if pending_shares:
            for sharer_name, recipient_name, recipient_ref_id in pending_shares:
                sharer_summary = npc_summaries.get(sharer_name, '')
                if not sharer_summary:
                    continue

                # Build participant names list, excluding the sharer and annotating the player
                participant_names = []
                for npc in npcs_in_conversation.get_all_characters_since_start():
                    if npc.name == sharer_name:
                        continue  # Exclude sharer from participant list
                    participant_names.append(npc.name)
                # Add the player
                player_name = npcs_in_conversation.get_player_name()
                if player_name:
                    participant_names.append(f"{player_name} (the player)")

                # Create prefixed summary
                participants_text = ", ".join(participant_names) if participant_names else "others"
                prefixed_summary = f"{sharer_name} shared with {recipient_name} a conversation with {participants_text}:\n{sharer_summary}"

                # Write to recipient using name and ref_id directly
                self.__append_new_conversation_summary_by_ids(prefixed_summary, recipient_name, recipient_ref_id, world_id)
                logger.info(f"Shared conversation summary with {recipient_name}")

    @utils.time_it
    def get_threads_for_summarization(self, all_messages: message_thread, npcs_in_conversation: Characters) -> Dict[str, CharacterSummaryParameters]:
        """Returns a dictionary mapping an NPC's name to a CharacterSummaryParameters object,
        which encapsulates the NPC's message_thread and the list of Characters they interacted with.

        Uses the participation log from Characters to determine which messages each NPC heard,
        based on their join/leave message indices.
        """
        participation_log = npcs_in_conversation.get_participation_log()
        all_chars_since_start = npcs_in_conversation.get_all_characters_since_start()
        total_messages = len(all_messages)

        # Build intervals for each NPC: list of (start_index, end_index)
        npc_intervals: Dict[str, list[tuple[int, int]]] = {}
        open_joins: Dict[str, int] = {}

        for event, name, msg_index in participation_log:
            if event == "join":
                open_joins[name] = msg_index
            elif event == "leave" and name in open_joins:
                start = open_joins.pop(name)
                npc_intervals.setdefault(name, []).append((start, msg_index))

        # Close any open joins (NPCs still in conversation at save time)
        for name, start in open_joins.items():
            npc_intervals.setdefault(name, []).append((start, total_messages))

        # Build per-NPC threads
        result: Dict[str, CharacterSummaryParameters] = {}
        for npc_name, intervals in npc_intervals.items():
            start, end = intervals[-1]

            thread = message_thread(self.__config, None)
            for idx in range(start, min(end, total_messages)):
                msg = all_messages[idx]
                if isinstance(msg, (UserMessage, AssistantMessage)):
                    thread.add_message(msg)

            # Find other NPCs who were present during this NPC's latest interval
            involved: set[str] = {npc_name}
            for other_name, other_intervals in npc_intervals.items():
                if other_name == npc_name:
                    continue
                for other_start, other_end in other_intervals:
                    if start < other_end and other_start < end:
                        involved.add(other_name)
                        break

            involved_chars = [c for c in all_chars_since_start if c.name in involved]
            result[npc_name] = CharacterSummaryParameters(thread, involved_chars)

        return result

    def group_shared_threads(self, npc_threads: Dict[str, CharacterSummaryParameters]) -> list[list[str]]:
        """Groups NPC message threads if they have exactly the same messages.
        Two threads are considered identical if the sequence of messages (by text) returned by
        thread.get_talk_only() (when converted to a tuple of strings) is exactly equal.

        Returns:
            A list of lists, where each inner list contains NPC names that share the same thread.
        """
        thread_groups = defaultdict(list)
        for npc_name, summary_params in npc_threads.items():
            messages_tuple = tuple(message.text for message in summary_params.messages.get_talk_only())
            thread_groups[messages_tuple].append(npc_name)

        return list(thread_groups.values())

    @utils.time_it
    def __get_latest_conversation_summary_file_path(self, character: Character, world_id: str) -> str:
        """Get the path to the latest conversation summary file, prioritizing name_ref folders over legacy name folders.

        Args:
            character: The Character object
            world_id: ID of the game world

        Returns:
            str: Path to the latest conversation summary file
        """
        return self.__get_latest_conversation_summary_file_path_by_ids(character.name, character.ref_id, world_id)

    def __get_latest_conversation_summary_file_path_by_ids(self, npc_name: str, npc_ref_id: str, world_id: str) -> str:
        """Get the path to the latest conversation summary file, prioritizing name_ref folders over legacy name folders.

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
            logger.debug(f"Resolved summary folder: {target_folder}")
        elif os.path.exists(name_path):
            target_folder = name_path
            logger.debug(f"Resolved summary folder (legacy): {target_folder}")
        else:
            target_folder = name_ref_path  # Use name_ref format for new folders
            logger.info(f"{name_ref_path} does not exist. A new summary file will be created.")
        
        latest_file_number = get_latest_file_number(target_folder)
        return f"{target_folder}/{base_name}_summary_{latest_file_number}.txt"
    
    @utils.time_it
    def __create_new_conversation_summary(self, npc_info: CharacterSummaryParameters, npcs_in_conversation: Characters, world_id: str, end_timestamp: float | None = None, min_messages: int = 5) -> str:
        if self.__config.game.base_game == GameEnum.FALLOUT4:
            location: str = 'the Commonwealth'
        else:
            location: str = "Skyrim"

        bios = '\n\n'.join([f"{c.name}: {c.bio}" for c in npc_info.characters])
        names = ', '.join([c.name for c in npc_info.characters])

        player_name = npcs_in_conversation.get_player_name() or "the player"

        prompt = self.__memory_prompt.format(
                    name=names,
                    names=names,
                    language=self.__language_name,
                    game=location,
                    bios=bios,
                    conversation_summaries=self.get_prompt_text(npc_info.characters, world_id),
                    player_name=player_name
                )
        while True:
            try:
                if len(npc_info.messages) >= min_messages:
                    summary = self.summarize_conversation(npc_info.messages.transform_to_dict_representation(npc_info.messages.get_talk_only()), prompt)
                    # Prepend timestamp to summary if available
                    if summary and end_timestamp is not None and self.__config.memory_prompt_datetime_prefix:
                        timestamp_prefix = self.__format_timestamp(end_timestamp)
                        summary = f"{timestamp_prefix}\n{summary}"
                    return summary
                else:
                    logger.info(f"Conversation summary not saved. Not enough dialogue spoken.")
                break
            except Exception:
                logger.error('Failed to summarize conversation. Retrying...')
                time.sleep(5)
                continue
        return ""

    @utils.time_it
    def __append_new_conversation_summary(self, new_summary: str, character: Character, world_id: str):
        """Append a new conversation summary for a character."""
        self.__append_new_conversation_summary_by_ids(new_summary, character.name, character.ref_id, world_id)

    @utils.time_it
    def __append_new_conversation_summary_by_ids(self, new_summary: str, npc_name: str, npc_ref_id: str, world_id: str):
        """Append a new conversation summary using name and ref_id directly."""
        conversation_summary_file = self.__get_latest_conversation_summary_file_path_by_ids(npc_name, npc_ref_id, world_id)
        logger.info(f"Saving conversation summary for {npc_name} to: {conversation_summary_file}")
        if os.path.exists(conversation_summary_file):
            with open(conversation_summary_file, 'r', encoding='utf-8') as f:
                previous_conversation_summaries = f.read()
        else:
            directory = os.path.dirname(conversation_summary_file)
            os.makedirs(directory, exist_ok=True)
            previous_conversation_summaries = ''
       
        if len(new_summary) > 0:
            new_summary = new_summary.strip() + '\n\n'

            conversation_summaries = previous_conversation_summaries + new_summary
            with open(conversation_summary_file, 'w', encoding='utf-8') as f:
                f.write(conversation_summaries)
        else:
            conversation_summaries = previous_conversation_summaries

        summary_limit = int(self.__client.token_limit * self.__summary_limit_pct)

        count_tokens_summaries = self.__client.get_count_tokens(conversation_summaries)
        # if summaries token limit is reached, summarize the summaries
        if count_tokens_summaries > summary_limit:
            logger.info(f'Token limit of conversation summaries reached ({count_tokens_summaries} / {summary_limit} tokens). Creating new summary file...')
            while True:
                try:
                    prompt = self.__resummarize_prompt.format(
                        name=npc_name,
                        language=self.__language_name,
                        game=self.__game.game_name_in_filepath
                    )
                    long_conversation_summary = self.summarize_conversation(conversation_summaries, prompt)
                    break
                except Exception:
                    logger.error('Failed to summarize conversation. Retrying...')
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
    def summarize_conversation(self, text_to_summarize: str, prompt: str) -> str:
        summary = ''
        if len(text_to_summarize) > 5:
            logger.log(23, f'Summary prompt sent to LLM: {prompt.strip()}')
            messages = message_thread(self.__config, prompt)
            messages.add_message(UserMessage(self.__config, text_to_summarize))
            summary = self.__client.request_call(messages)
            if not summary:
                logger.error(f"Summarizing conversation failed.")
                return ""

            summary = summary.replace('The assistant', 'Someone')
            summary = summary.replace('the assistant', 'Someone')
            summary = summary.replace('an assistant', 'Someone')
            summary = summary.replace('an AI assistant', 'Someone')
            summary = summary.replace('The user', 'The player')
            summary = summary.replace('the user', 'the player')
            summary += '\n\n'

            logger.log(self.loglevel, f'Conversation summary: {summary.strip()}')
            logger.info(f"Conversation summary saved")
        else:
            logger.info(f"Conversation summary not saved. Not enough dialogue spoken.")

        return summary
