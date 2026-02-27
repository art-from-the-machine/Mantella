from collections import defaultdict
import os
import time
from typing import Dict, List
from src.config.config_loader import ConfigLoader
from src.games.gameable import Gameable
from src.llm.client_base import ClientBase
from src.llm.llm_client import LLMClient
from src.llm.message_thread import message_thread
from src.llm.messages import AssistantMessage, join_message, leave_message, UserMessage
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
        self.__resummarize_prompt: str = config.resummarize_prompt

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
        """Gets the summary for a specific character

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
    def may_add_missing_join_leave_messages(self, messages: message_thread, npcs_in_conversation: Characters | None = None) -> bool:
        """Adds missing join and leave messages to the beginning / end of the message thread.

        Args:
            messages: The message thread to check and update
            npcs_in_conversation: Optional Characters object containing NPCs that should be in the conversation.
                                  If provided, join messages will be added for NPCs that are missing them.
        """
        had_missing_messages = False
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

        # If npcs_in_conversation is provided, ensure all NPCs in it have join messages
        if npcs_in_conversation:
            for npc in npcs_in_conversation.get_all_characters():
                if not npc.is_player_character:
                    name = npc.name
                    if name not in characters_found:
                        characters_found[name] = npc

        # Insert the missing messages at the appropriate places
        if len(characters_joined) < len(characters_found):
            for name, character in characters_found.items():
                if name not in characters_joined:
                    messages.insert_after_system_messages(join_message(character, self.__config))
                    had_missing_messages = True
        if len(characters_left) < len(characters_found):
            for name, character in characters_found.items():
                if name not in characters_left:
                    messages.add_message(leave_message(character, self.__config))
                    had_missing_messages = True
        return had_missing_messages

    @utils.time_it
    def save_conversation_state(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, is_reload=False, pending_shares: list[tuple[str, str, str]] | None = None, end_timestamp: float | None = None):
        """Save conversation summaries for all NPCs, with per-NPC thread tracking.

        NPCs only get summaries of the messages they actually heard (based on join/leave).
        NPCs with identical message histories share a single LLM summarization call.

        Args:
            messages: The full conversation message thread
            npcs_in_conversation: All NPCs that were part of the conversation
            world_id: The world identifier
            is_reload: Whether this is a reload (save even if summary is empty)
            pending_shares: List of (sharer_name, recipient_name, recipient_ref_id) for memory sharing
            end_timestamp: Optional timestamp to prepend to summaries
        """
        self.may_add_missing_join_leave_messages(messages, npcs_in_conversation)

        characters = self.get_character_lookup_dict(messages)
        npc_message_threads: Dict[str, CharacterSummaryParameters] = self.get_threads_for_summarization(messages, characters)
        npcs_with_shared_threads = self.group_shared_threads(npc_message_threads)

        # Track the summary for pending_shares (use first generated summary)
        shared_summary = ''

        for npc_names in npcs_with_shared_threads:
            # Generate one summary per unique conversation experience
            summary = self.__create_new_conversation_summary(npc_message_threads[npc_names[0]], world_id, end_timestamp)

            # Store first summary for pending_shares
            if not shared_summary and summary:
                shared_summary = summary

            # Write the same summary to all NPCs who heard the same messages
            for npc_name in npc_names:
                if summary or is_reload:
                    self.__append_new_conversation_summary(summary, characters[npc_name], world_id)

        # Handle pending shares: write summary with prefix to recipient folders
        if pending_shares and len(shared_summary) > 0:
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
                prefixed_summary = f"{sharer_name} shared with {recipient_name} a conversation with {participants_text}:\n{shared_summary}"

                # Write to recipient using name and ref_id directly
                self.__append_new_conversation_summary_by_ids(prefixed_summary, recipient_name, recipient_ref_id, world_id)
                logger.info(f"Shared conversation summary with {recipient_name}")

    def get_character_lookup_dict(self, all_messages: message_thread) -> Dict[str, Character]:
        """Returns a dictionary of character names to Character objects."""
        characters = {}
        for message in all_messages.get_messages_of_type((join_message)):
            if not isinstance(message, (join_message, leave_message)) or message.character is None or message.character.is_player_character:
                continue
            characters[message.character.name] = message.character
        return characters

    @utils.time_it
    def get_threads_for_summarization(self, all_messages: message_thread, characters: Dict[str, Character]) -> Dict[str, CharacterSummaryParameters]:
        """Returns a dictionary mapping an NPC's name to a CharacterSummaryParameters object,
        which encapsulates the NPC's message_thread and the list of Characters they've seen.
        """
        npcs_in_conversation: Dict[str, bool] = {}
        def set_in_conversation(npc: Character, in_conversation: bool):
            npcs_in_conversation[npc.name] = in_conversation

        npc_message_threads: Dict[str, message_thread] = {}
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
                        npc_has_seen_npcs[npc_name][npc_name2] = characters[npc_name2]

                # We also store the message for the npc if they are in the conversation for it
                if in_conversation:
                    if npc_name not in npc_message_threads:
                        npc_message_threads[npc_name] = message_thread(self.__config, None)
                    thread: message_thread = npc_message_threads[npc_name]

                    # Mark passage of time, in case a character left and rejoined the conversation
                    if len(thread) > 0:
                        npcs_previous_message = thread.get_last_message()
                        if isinstance(npcs_previous_message, leave_message) and npcs_previous_message.character.name == npc_name:
                            narration_start, narration_end = self.__config.get_narration_indicators()
                            thread.add_message(UserMessage(self.__config, narration_start + "some time later*" + narration_end))

                    thread.add_message(message)

            # Mark npc as absent when they leave
            if isinstance(message, leave_message) and not message.character.is_player_character:
                set_in_conversation(message.character, False)

        # Prepare the result
        result: Dict[str, CharacterSummaryParameters] = {}
        for npc_name, seen_npcs_dict in npc_has_seen_npcs.items():
            if npc_name not in npc_message_threads:
                continue
            seen_npcs = [seen_npcs_dict[key] for key in seen_npcs_dict]
            thread = npc_message_threads[npc_name]
            result[npc_name] = CharacterSummaryParameters(thread, seen_npcs)

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

        result: list[list[str]] = []
        for messages, npc_list in thread_groups.items():
            result.append(npc_list)

        return result

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
            logger.info(f"Loaded latest summary file from: {target_folder}")
        elif os.path.exists(name_path):
            target_folder = name_path
            logger.info(f"Loaded latest summary file from: {target_folder}")
        else:
            target_folder = name_ref_path  # Use name_ref format for new folders
            logger.info(f"{name_ref_path} does not exist. A new summary file will be created.")

        latest_file_number = get_latest_file_number(target_folder)
        return f"{target_folder}/{base_name}_summary_{latest_file_number}.txt"

    @utils.time_it
    def __create_new_conversation_summary(self, npc_info: CharacterSummaryParameters, world_id: str, end_timestamp: float | None = None) -> str:
        if self.__config.game == "Fallout4" or self.__config.game == "Fallout4VR":
            location: str = 'the Commonwealth'
        else:
            location: str = "Skyrim"

        bios = '\n\n'.join([f"{c.name}: {c.bio}" for c in npc_info.characters])
        names = ', '.join([c.name for c in npc_info.characters])

        # Try to extract player name from the latest user message; default to 'the player'
        player_name = "the player"
        try:
            talk_messages = npc_info.messages.get_talk_only()
            for m in reversed(talk_messages):
                if isinstance(m, UserMessage):
                    pn = m.player_character_name if hasattr(m, 'player_character_name') else ""
                    if pn:
                        player_name = pn
                        break
        except Exception:
            pass

        # Convert list of characters to Characters object for get_prompt_text
        characters_obj = Characters()
        for char in npc_info.characters:
            characters_obj.add_or_update_character(char)

        prompt = self.__memory_prompt.format(
                    name=names,
                    names=names,
                    language=self.__language_name,
                    game=location,
                    bios=bios,
                    conversation_summaries=self.get_prompt_text(characters_obj, world_id),
                    player_name=player_name
                )
        while True:
            try:
                if len(npc_info.messages) >= 5:
                    summary = self.summarize_conversation(npc_info.messages.transform_to_dict_representation(npc_info.messages.get_talk_only()), prompt)
                    # Prepend timestamp to summary if available
                    if summary and end_timestamp is not None and self.__config.memory_prompt_datetime_prefix:
                        timestamp_prefix = self.__format_timestamp(end_timestamp)
                        summary = f"{timestamp_prefix}\n{summary}"
                    return summary
                else:
                    logger.info(f"Conversation summary not saved. Not enough dialogue spoken.")
                break
            except:
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
        if os.path.exists(conversation_summary_file):
            with open(conversation_summary_file, 'r', encoding='utf-8') as f:
                previous_conversation_summaries = f.read()
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

        summary_limit = round(self.__summary_client.token_limit * self.__summary_limit_pct, 0)

        count_tokens_summaries = self.__summary_client.get_count_tokens(conversation_summaries)
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
                except:
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
            messages = message_thread(self.__config, prompt)
            messages.add_message(UserMessage(self.__config, text_to_summarize))
            summary = self.__summary_client.request_call(messages)
            # Log the summary prompt being sent
            logger.log(23, f'Summary prompt sent to LLM: {prompt.strip()}')
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
