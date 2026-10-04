from collections import defaultdict
import logging
import os
import re
import time
from typing import Dict, List, Tuple
from src.config.config_loader import ConfigLoader
from src.games.gameable import Gameable
from src.llm.summary_client import SummaryLLMCLient
from src.llm.client_base import ClientBase
from src.llm.llm_client import LLMClient
from src.llm.message_thread import message_thread
from src.llm.messages import AssistantMessage, join_message, leave_message, UserMessage
from src.characters_manager import Characters
from src.character_manager import Character
from src.remember.remembering import Remembering
from src.lorebook_manager import LorebookManager
from src.prompt_profile_manager import PromptSectionError
from src.bio_section_filter import apply_bio_section_filter, should_filter_memory_bios
from src import utils

# ---------------------------------------------------------------------------
# Summary-block parsing helpers
# ---------------------------------------------------------------------------

# Regex for the timestamp marker that may appear as the first line of a block
_TS_MARKER_RE = re.compile(r'^ts=(\d+)$')


def _strip_timestamp_markers(text: str) -> str:
    """Remove all ``ts=<epoch>`` marker lines from *text*.

    This is used to sanitise summary text before sending it to the LLM
    (both for new-summary generation and for resummarization).
    """
    return '\n'.join(
        line for line in text.split('\n')
        if not _TS_MARKER_RE.match(line.strip())
    )


def parse_summary_blocks(raw_text: str) -> Tuple[List[str], List[Tuple[int, str]]]:
    """Parse a summary file into legacy blocks and timestamped blocks.

    A *block* is a contiguous group of non-empty lines separated from other
    blocks by one or more blank lines.

    If a block's first line matches ``ts=<epoch>``, it is a **timestamped**
    block and the remaining lines form the block text.  Otherwise it is a
    **legacy** block.

    Returns:
        A tuple of (*legacy_blocks*, *timestamped_blocks*) where
        *legacy_blocks* is a list of text strings (in file order) and
        *timestamped_blocks* is a list of ``(timestamp, text)`` pairs.
    """
    legacy_blocks: List[str] = []
    timestamped_blocks: List[Tuple[int, str]] = []

    # Split into blocks by blank lines.
    # Also split when a new `ts=...` marker appears mid-block (for backward
    # tolerance with older files that may be missing blank-line delimiters).
    current_lines: List[str] = []
    for line in raw_text.split('\n'):
        stripped = line.strip()
        if stripped == '':
            if current_lines:
                _classify_block(current_lines, legacy_blocks, timestamped_blocks)
                current_lines = []
        else:
            # If a timestamp marker appears after we've already collected
            # non-empty lines, treat it as the start of a new block.
            if _TS_MARKER_RE.match(stripped) and current_lines:
                _classify_block(current_lines, legacy_blocks, timestamped_blocks)
                current_lines = []
            current_lines.append(stripped)
    # Handle last block (no trailing blank line)
    if current_lines:
        _classify_block(current_lines, legacy_blocks, timestamped_blocks)

    return legacy_blocks, timestamped_blocks


def _classify_block(
    lines: List[str],
    legacy_blocks: List[str],
    timestamped_blocks: List[Tuple[int, str]],
) -> None:
    """Classify a single block as legacy or timestamped and append to the
    appropriate list."""
    marker_match = _TS_MARKER_RE.match(lines[0])
    if marker_match:
        ts = int(marker_match.group(1))
        text = '\n'.join(lines[1:]).strip()
        if text:
            timestamped_blocks.append((ts, text))
    else:
        text = '\n'.join(lines).strip()
        if text:
            legacy_blocks.append(text)


def drop_blocks_since(
    timestamped_blocks: List[Tuple[int, str]],
    conversation_start_ts: int | None,
    keep_latest_since: bool = False,
) -> List[Tuple[int, str]]:
    """Drop blocks written during the current conversation (``ts >= conversation_start_ts``).

    Regenerating a summary/thought/reflection mid-conversation must not feed earlier
    attempts back into the next request. With *keep_latest_since*, the newest block
    from this conversation is kept. ``None`` keeps every block.
    """
    if conversation_start_ts is None:
        return list(timestamped_blocks)
    kept = [block for block in timestamped_blocks if block[0] < conversation_start_ts]
    if keep_latest_since:
        since = [block for block in timestamped_blocks if block[0] >= conversation_start_ts]
        if since:
            kept.append(max(since, key=lambda item: item[0]))
    return kept


def build_merged_timeline(
    legacy_blocks: List[str],
    timestamped_summary_blocks: List[Tuple[int, str]],
    dynamic_tag_events: List[Tuple[int, str]],
    dedupe_legacy: bool = False,
    exclude_events: List[Tuple[int, str]] | None = None,
) -> str:
    """Build the final memory text for one NPC.

    Order:
      1. Legacy summary blocks — in their original file order (optionally
         de-duplicated for single-NPC prompts).
      2. Timestamped items (summary blocks + dynamic tag events) —
         merge-sorted by timestamp ascending.

    Timestamps are **stripped** from the output so the LLM never sees them.

    Args:
        exclude_events: Optional list of ``(ts, text)`` tuples to omit from
            the timeline (e.g. events that will appear in a separate
            "New developments" section).
    """
    # --- legacy section --------------------------------------------------
    if dedupe_legacy:
        seen = set()
        deduped: List[str] = []
        for block in legacy_blocks:
            if block not in seen:
                seen.add(block)
                deduped.append(block)
        legacy_blocks = deduped

    # --- build exclusion set ---------------------------------------------
    excluded: set[Tuple[int, str]] = set(exclude_events) if exclude_events else set()

    # --- timestamped section ---------------------------------------------
    all_timestamped: List[Tuple[int, str]] = list(timestamped_summary_blocks)
    all_timestamped.extend(dynamic_tag_events)
    all_timestamped.sort(key=lambda item: item[0])

    # --- combine ---------------------------------------------------------
    parts: List[str] = list(legacy_blocks)
    for item in all_timestamped:
        if item not in excluded:
            parts.append(item[1])

    return '\n'.join(parts)


def get_new_events(
    timestamped_summary_blocks: List[Tuple[int, str]],
    dynamic_tag_events: List[Tuple[int, str]],
) -> List[Tuple[int, str]]:
    """Return dynamic tag events newer than the latest summary block.

    An event is considered *new* if its timestamp is strictly greater than
    the latest timestamped summary block.  If there are no timestamped
    summary blocks the baseline is ``0``, so all dynamic events qualify.

    Returns a list of ``(timestamp, text)`` pairs sorted by timestamp.
    """
    if not dynamic_tag_events:
        return []

    latest_summary_ts = max((ts for ts, _ in timestamped_summary_blocks), default=0)
    return sorted(
        [(ts, text) for ts, text in dynamic_tag_events if ts > latest_summary_ts],
        key=lambda item: item[0],
    )


def _build_new_events_section(new_events: List[Tuple[int, str]]) -> str:
    """Format a list of new events into a "New developments" text block.

    Returns an empty string when *new_events* is empty.
    """
    if not new_events:
        return ""

    lines = ["New developments since last meeting:"]
    for _, text in new_events:
        # Ensure each event is rendered as a bullet
        if text.startswith("- "):
            lines.append(text)
        else:
            lines.append(f"- {text}")
    return "\n".join(lines)


def build_memory_text(
    legacy_blocks: List[str],
    timestamped_summary_blocks: List[Tuple[int, str]],
    dynamic_events: List[Tuple[int, str]],
    dedupe_legacy: bool = False,
) -> str:
    """Merge summary blocks and dynamic tag events into the memory text the LLM sees."""
    # Determine which dynamic events are "new since last meeting"
    new_events = get_new_events(timestamped_summary_blocks, dynamic_events)

    # Build timeline, excluding new events so they aren't duplicated
    timeline = build_merged_timeline(
        legacy_blocks,
        timestamped_summary_blocks,
        dynamic_events,
        dedupe_legacy=dedupe_legacy,
        exclude_events=new_events,
    )

    # --- "New developments since last meeting" section ---
    new_section = _build_new_events_section(new_events)
    if new_section and timeline:
        return f"{timeline}\n\n{new_section}"
    elif new_section:
        return new_section
    return timeline


def player_name_from_thread(messages: message_thread) -> str:
    """Best-effort player name from talk messages, else ``the player``."""
    try:
        talk_messages = messages.get_talk_only()
        for m in reversed(talk_messages):
            if isinstance(m, UserMessage):
                pn = m.player_character_name if hasattr(m, "player_character_name") else ""
                if pn:
                    return pn
    except Exception:
        pass
    return "the player"


def thread_contains_player(messages: message_thread | None) -> bool:
    """True when the thread looks like a player-involved (non-radiant) conversation."""
    if messages is None:
        return False
    try:
        for message in messages.get_persistent_messages():
            if isinstance(message, UserMessage):
                if (message.player_character_name or "").strip():
                    return True
                if not message.is_system_generated_message:
                    return True
            character = getattr(message, "character", None)
            if character is not None and getattr(character, "is_player_character", False):
                return True
    except Exception:
        return False
    return False


def format_character_bios_for_memory(characters, player_name: str, config, *, contains_player: bool) -> str:
    """Join character bios for memory prompts, optionally stripping excluded sections."""
    enabled = should_filter_memory_bios(config, contains_player=contains_player)
    parts: List[str] = []
    for character in characters:
        resolved = utils.resolve_player_name_placeholder(character.bio or "", player_name)
        filtered = apply_bio_section_filter(resolved, character.name, config, enabled=enabled)
        parts.append(f"{character.name}: {filtered}")
    return "\n\n==========\n\n".join(parts)


class CharacterSummaryParameters:
    def __init__(self, messages: message_thread, involved_characters: List[Character]) -> None:
        self.messages = messages
        self.characters = involved_characters


class Summaries(Remembering): 
    """ Stores a conversation as a summary in a text file.
        Loads the latest summary from disk for a prompt text.
    """
    def __init__(self, game: Gameable, config: ConfigLoader, client: LLMClient, language_name: str, summary_client: ClientBase | None = None, summary_limit_pct: float = 0.3, inner_monologue=None, personal_reflection=None) -> None:
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
        self.__inner_monologue = inner_monologue
        self.__personal_reflection = personal_reflection
        game_folder_name = "Fallout4" if game.game_name_in_filepath.lower() == "fallout4" else "Skyrim"
        lorebook_base_path = os.path.join(utils.resolve_path(), "data", game_folder_name, "lorebook")
        self.__lorebook_manager = LorebookManager(lorebook_base_path, config, game_folder_name)

    def update_summary_client(self, summary_client: ClientBase | None, fallback_client: LLMClient, thoughts_client: ClientBase | None, reflection_client: ClientBase | None) -> None:
        """Replace the LLM clients used for summarization, private thoughts and personal reflections without recreating the rememberer."""
        self.__client = fallback_client
        self.__summary_client = summary_client if summary_client else fallback_client
        if self.__inner_monologue:
            self.__inner_monologue.update_summary_client(thoughts_client, fallback_client)
        if self.__personal_reflection:
            self.__personal_reflection.update_summary_client(reflection_client, fallback_client)

    def __build_lorebook_text_for_prompt(
        self,
        prompt_template: str,
        format_values: Dict[str, str],
        excluded_variables: set[str],
        extra_scan_texts: List[str] | None = None,
    ) -> str:
        mentioned_variables = {
            match.group(1).strip()
            for match in re.finditer(r"\{([^{}]+)\}", prompt_template)
        }
        excluded = set(excluded_variables)
        excluded.add("lorebook")

        search_texts: List[str] = []
        for variable in mentioned_variables:
            if variable in excluded:
                continue
            value = format_values.get(variable, "")
            if value:
                search_texts.append(value)

        if extra_scan_texts:
            search_texts.extend([text for text in extra_scan_texts if text])

        return self.__lorebook_manager.render_lorebook_entries(search_texts)

    def __get_character_dynamic_events(self, character: Character) -> List[Tuple[int, str]]:
        """Retrieve dynamic tag events stored on a character, if any."""
        events = character.get_custom_character_value('mantella_dynamic_tag_events')
        if events and isinstance(events, list):
            return events
        return []

    def __build_character_memory(
        self,
        character: Character,
        world_id: str,
        dedupe_legacy: bool = False,
        conversation_start_ts: int | None = None,
        keep_latest_since: bool = False,
    ) -> str:
        """Build the merged memory text for a single character.

        Reads the summary file, parses it into legacy + timestamped blocks,
        retrieves dynamic tag events from the character, and returns the
        merged timeline string with all timestamps stripped.

        If any dynamic tag events have a timestamp **later** than the most
        recent summary block, they are highlighted in a
        "New developments since last meeting" section appended after the
        chronological timeline.

        *conversation_start_ts* / *keep_latest_since* filter summary blocks, see ``drop_blocks_since``.
        """
        legacy_blocks: List[str] = []
        timestamped_summary_blocks: List[Tuple[int, str]] = []

        conversation_summary_file = self.__get_latest_conversation_summary_file_path(character, world_id, False)
        if os.path.exists(conversation_summary_file):
            with open(conversation_summary_file, 'r', encoding='utf-8') as f:
                raw_text = f.read()
            legacy_blocks, timestamped_summary_blocks = parse_summary_blocks(raw_text)
            timestamped_summary_blocks = drop_blocks_since(
                timestamped_summary_blocks, conversation_start_ts, keep_latest_since
            )

        dynamic_events = self.__get_character_dynamic_events(character)
        return build_memory_text(legacy_blocks, timestamped_summary_blocks, dynamic_events, dedupe_legacy=dedupe_legacy)

    @utils.time_it
    def get_prompt_text(self, npcs_in_conversation: Characters, world_id: str, include_private_thoughts: bool = True, conversation_start_ts: int | None = None) -> str:
        """Load the conversation summaries for all NPCs in the conversation and returns them as one string

        Args:
            npcs_in_conversation (Characters): the npcs to load the summaries for
            world_id (str): the world identifier
            include_private_thoughts: When False, omit saved private thoughts. Live multi-NPC prompts keep them.
            conversation_start_ts: When set, ignore summaries written since this time.

        Returns:
            str: a concatenation of the summaries as a single string
        """
        # Get all non-player characters
        non_player_characters = [char for char in npcs_in_conversation.get_all_characters() if not char.is_player_character]
        
        if len(non_player_characters) == 1:
            # Single NPC conversation - thoughts use {private_thoughts}, not this string
            character = non_player_characters[0]
            memory_text = self.__build_character_memory(character, world_id, dedupe_legacy=True, conversation_start_ts=conversation_start_ts)
            if memory_text:
                return f"Below is a summary of past events:\n{memory_text}"
            else:
                return ""
        else:
            # Multi-NPC / radiant — live prompts append each NPC's newest thoughts. Summary generation does not.
            character_memories = []
            for character in non_player_characters:
                memory_text = self.__build_character_memory(character, world_id, dedupe_legacy=False, conversation_start_ts=conversation_start_ts)
                if include_private_thoughts:
                    memory_text = self.__append_thought_to_memory(memory_text, character, world_id)
                if memory_text:
                    memory_with_delimiters = f"[This is the beginning of {character.name}'s memory]\n" + \
                                           memory_text + \
                                           f"\n[This is the end of {character.name}'s memory]"
                    character_memories.append(memory_with_delimiters)
            
            if character_memories:
                result = "\n\n".join(character_memories)
                return f"Below is a summary of past events:\n{result}"
            else:
                return ""

    @utils.time_it
    def get_character_summary(self, character: Character, world_id: str, conversation_start_ts: int | None = None, keep_latest_since: bool = False) -> str:
        """ Gets the summary for a specific character
        
        Args:
            character (Character): the character to get the summary for
            world_id (str): the world ID
            conversation_start_ts: When set, ignore summaries written since this time.
            keep_latest_since: With conversation_start_ts, still keep the newest summary written since then.
            
        Returns:
            str: the summary text for this character, or empty string if no summary exists
        """
        return self.__build_character_memory(
            character,
            world_id,
            dedupe_legacy=True,
            conversation_start_ts=conversation_start_ts,
            keep_latest_since=keep_latest_since,
        )

    def get_character_private_thought(self, character: Character, world_id: str) -> str:
        """Return this character's newest private thoughts (raw, no divider, oldest first), or empty string.

        How many are returned is set by inner_monologue_load_count.
        """
        from src.remember.inner_monologue import get_thoughts_load_count
        count = get_thoughts_load_count(self.__config)
        if not self.__inner_monologue or count <= 0:
            return ""
        blocks = self.__inner_monologue.get_latest_thought_blocks(character, world_id, count)
        return "\n\n".join(text for _, text in blocks)

    def get_character_personal_reflection(self, character: Character, world_id: str) -> str:
        """Return this character's latest personal reflection (raw, no heading), or empty string."""
        from src.remember.personal_reflection import should_load_reflections_into_prompt
        if not self.__personal_reflection or not should_load_reflections_into_prompt(self.__config):
            return ""
        latest = self.__personal_reflection.get_latest_reflection_block(character, world_id)
        if not latest:
            return ""
        return latest[1]

    def get_private_thoughts_text(self, npcs_in_conversation: Characters, world_id: str) -> str:
        """Single-NPC {private_thoughts} fill. Multi-NPC / radiant return empty (thoughts go in memory)."""
        non_player_characters = [char for char in npcs_in_conversation.get_all_characters() if not char.is_player_character]
        if len(non_player_characters) != 1:
            return ""
        return self.get_character_private_thought(non_player_characters[0], world_id)

    def __append_thought_to_memory(self, memory_text: str, character: Character, world_id: str) -> str:
        """Append the newest thoughts, in one wrapper, after this NPC's memory (multi-NPC / radiant)."""
        from src.remember.inner_monologue import wrap_private_thought
        thought = wrap_private_thought(self.get_character_private_thought(character, world_id))
        if not thought:
            return memory_text
        if memory_text:
            return f"{memory_text}\n\n{thought}"
        return thought

    @utils.time_it
    def may_add_missing_join_leave_messages(self, messages: message_thread, npcs_in_conversation: Characters | None = None) -> bool:
        """ Adds missing join and leave messages to the beginning / end of the message thread.
        
        Args:
            messages: The message thread to check and update
            npcs_in_conversation: Optional Characters object containing NPCs that should be in the conversation.
                                  If provided, join messages will be added for NPCs that are missing them.
        """
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
                    hadMissingMessages = True
        if len(characters_left) < len(characters_found):
            for name, character in characters_found.items():
                if name not in characters_left:
                    messages.add_message(leave_message(character, self.__config))
                    hadMissingMessages = True
        return hadMissingMessages

    @utils.time_it
    def save_conversation_state(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, is_reload=False, save_timestamp: int | None = None, save_thoughts: bool | None = None, save_reflections: bool | None = None, conversation_start_ts: int | None = None):
        self.may_add_missing_join_leave_messages(messages, npcs_in_conversation)

        characters = self.get_character_lookup_dict(messages, npcs_in_conversation)
        npc_message_threads: Dict[str, CharacterSummaryParameters] = self.get_threads_for_summarization(messages, characters)
        npcs_with_shared_threads = self.group_shared_threads(npc_message_threads)
        ts = save_timestamp if save_timestamp is not None else int(time.time())
        saved_summaries: Dict[str, str] = {}

        for npc_names in npcs_with_shared_threads:
           summary = self.__create_new_conversation_summary(npc_message_threads[npc_names[0]], world_id, conversation_start_ts)
           for npc_name in npc_names:
               self.__append_new_conversation_summary(summary, characters[npc_name], world_id, ts)
               saved_summaries[npc_name] = summary

        should_save_thoughts = self.__config.inner_monologue_enabled if save_thoughts is None else save_thoughts
        should_save_reflections = self.__config.personal_reflection_enabled if save_reflections is None else save_reflections

        if self.__inner_monologue and should_save_thoughts:
            try:
                # Only NPCs that just got a new summary. Thoughts read the transcript, so the
                # summaries passed are those from before this conversation (all when no start time).
                summarized_threads = {
                    npc_name: params for npc_name, params in npc_message_threads.items()
                    if (saved_summaries.get(npc_name) or "").strip()
                }
                thought_summaries = {
                    npc_name: self.get_character_summary(characters[npc_name], world_id, conversation_start_ts)
                    for npc_name in summarized_threads
                }
                self.__inner_monologue.save_thoughts(
                    summarized_threads,
                    characters,
                    thought_summaries,
                    world_id,
                    ts,
                    require_summary=False,
                    conversation_start_ts=conversation_start_ts,
                )
            except Exception as e:
                logging.error(f"Failed to save private thoughts: {e}", exc_info=True)

        if self.__personal_reflection and should_save_reflections:
            try:
                # Reflections do not read the transcript, so keep the newest summary from this conversation.
                full_summaries: Dict[str, str] = {
                    npc_name: self.get_character_summary(npc, world_id, conversation_start_ts, keep_latest_since=True)
                    for npc_name, npc in characters.items()
                }
                reflection_characters = characters
                reflection_summaries = full_summaries
                # Conversation end uses the same 5-message cutoff as summaries.
                # Save Summary Now passes save_reflections explicitly and still reflects from summaries already on file.
                if save_reflections is None:
                    reflection_characters = {}
                    reflection_summaries = {}
                    for npc_name, npc in characters.items():
                        params = npc_message_threads.get(npc_name)
                        if params is None or len(params.messages) < 5:
                            logging.info(f"Personal reflection not saved for {npc_name}. Not enough dialogue spoken.")
                            continue
                        reflection_characters[npc_name] = npc
                        reflection_summaries[npc_name] = full_summaries.get(npc_name, "")
                self.__personal_reflection.save_reflections(
                    npc_message_threads,
                    reflection_characters,
                    reflection_summaries,
                    world_id,
                    ts,
                    conversation_start_ts=conversation_start_ts,
                )
            except Exception as e:
                logging.error(f"Failed to save personal reflections: {e}", exc_info=True)

        return saved_summaries

    @utils.time_it
    def save_thoughts_only(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, save_timestamp: int | None = None, conversation_start_ts: int | None = None):
        """Generate private thoughts from the current conversation without writing a new summary."""
        if not self.__inner_monologue:
            logging.info("Private thoughts not saved. Inner monologue is not available.")
            return

        self.may_add_missing_join_leave_messages(messages, npcs_in_conversation)
        characters = self.get_character_lookup_dict(messages, npcs_in_conversation)
        npc_message_threads: Dict[str, CharacterSummaryParameters] = self.get_threads_for_summarization(messages, characters)
        ts = save_timestamp if save_timestamp is not None else int(time.time())
        existing_summaries: Dict[str, str] = {}
        for npc_name, npc in characters.items():
            existing_summaries[npc_name] = self.get_character_summary(npc, world_id, conversation_start_ts)

        try:
            self.__inner_monologue.save_thoughts(
                npc_message_threads,
                characters,
                existing_summaries,
                world_id,
                ts,
                require_summary=False,
                conversation_start_ts=conversation_start_ts,
            )
        except Exception as e:
            logging.error(f"Failed to save private thoughts: {e}", exc_info=True)

    @utils.time_it
    def save_reflections_only(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, save_timestamp: int | None = None, conversation_start_ts: int | None = None):
        """Generate personal reflections from existing summaries without writing a new summary."""
        if not self.__personal_reflection:
            logging.info("Personal reflections not saved. Personal reflection is not available.")
            return

        self.may_add_missing_join_leave_messages(messages, npcs_in_conversation)
        characters = self.get_character_lookup_dict(messages, npcs_in_conversation)
        npc_message_threads: Dict[str, CharacterSummaryParameters] = self.get_threads_for_summarization(messages, characters)
        ts = save_timestamp if save_timestamp is not None else int(time.time())
        existing_summaries: Dict[str, str] = {}
        for npc_name, npc in characters.items():
            existing_summaries[npc_name] = self.get_character_summary(npc, world_id, conversation_start_ts, keep_latest_since=True)

        try:
            self.__personal_reflection.save_reflections(
                npc_message_threads,
                characters,
                existing_summaries,
                world_id,
                ts,
                conversation_start_ts=conversation_start_ts,
            )
        except Exception as e:
            logging.error(f"Failed to save personal reflections: {e}", exc_info=True)


        
    def get_character_lookup_dict(self, all_messages: message_thread, npcs_in_conversation: Characters | None = None) -> Dict[str, Character]:
        """Returns a dictionary of character names to Character objects.

        Join messages can hold frozen copies (after undo / reload), so NPCs still in
        npcs_in_conversation use the live Character to pick up runtime bio edits.
        """
        live_by_ref_id: Dict[str, Character] = {}
        if npcs_in_conversation:
            live_by_ref_id = {npc.ref_id: npc for npc in npcs_in_conversation.get_all_characters()}
        characters = {}
        for message in all_messages.get_messages_of_type((join_message)):
            if not isinstance(message, (join_message, leave_message)) or message.character == None or message.character.is_player_character:
                continue
            characters[message.character.name] = live_by_ref_id.get(message.character.ref_id, message.character)
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
                            thread.add_message(UserMessage(self.__config, narration_start + "some time later*" + narration_end))

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
    def __create_new_conversation_summary(self, npcInfo:CharacterSummaryParameters, world_id: str, conversation_start_ts: int | None = None) -> str:
        if self.__config.game == "Fallout4" or self.__config.game == "Fallout4VR":
            location: str = 'the Commonwealth'
        else:
            location: str = "Skyrim"
        
        names = ', '.join([c.name for c in npcInfo.characters])
        player_name = player_name_from_thread(npcInfo.messages)
        bios = format_character_bios_for_memory(
            npcInfo.characters,
            player_name,
            self.__config,
            contains_player=thread_contains_player(npcInfo.messages),
        )

        # Convert list of characters to Characters object for get_prompt_text
        characters_obj = Characters()
        for char in npcInfo.characters:
            characters_obj.add_or_update_character(char)

        memory_conversation_summaries = self.get_prompt_text(
            characters_obj, world_id, include_private_thoughts=False, conversation_start_ts=conversation_start_ts
        )
        prompt_values: Dict[str, str] = {
            "name": names,
            "names": names,
            "language": self.__language_name,
            "game": location,
            "bios": bios,
            "conversation_summaries": memory_conversation_summaries,
            "player_name": player_name,
        }
        talk_history_text = npcInfo.messages.transform_to_text(
            npcInfo.messages.get_talk_only(include_system_generated_messages=True)
        )
        memory_template = self.__config.memory_prompt
        lorebook_text = self.__build_lorebook_text_for_prompt(
            memory_template,
            prompt_values,
            excluded_variables={"bios", "conversation_summaries"},
            extra_scan_texts=[talk_history_text],
        )
        try:
            memory_template = self.__config.prompt_profile_manager.resolve_prompt("memory_prompt", memory_template)
        except PromptSectionError as e:
            logging.error(str(e))
            return ""
        prompt = memory_template.format(
                    name=names,
                    names=names,
                    language=self.__language_name,
                    game=location, 
                    bios=bios,
                    conversation_summaries=memory_conversation_summaries,
                    player_name=player_name,
                    lorebook=lorebook_text,
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
    def __append_new_conversation_summary(self, new_summary: str, npc: Character, world_id: str, save_timestamp: int | None = None):
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
                new_summary = '- ' + new_summary.strip()
            else:
                new_summary = new_summary.strip()

            # Prepend a real-world timestamp marker so this block can be
            # chronologically ordered with dynamic tag events later.
            ts_marker = f'ts={int(save_timestamp if save_timestamp is not None else time.time())}'
            new_summary = ts_marker + '\n' + new_summary + '\n\n'

            # Ensure block-level separation even if legacy files do not end
            # with a blank line.
            separator = ""
            if previous_conversation_summaries:
                if previous_conversation_summaries.endswith('\n\n'):
                    separator = ""
                elif previous_conversation_summaries.endswith('\n'):
                    separator = "\n"
                else:
                    separator = "\n\n"

            conversation_summaries = previous_conversation_summaries + separator + new_summary
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

                    # Strip timestamp markers before sending to the LLM
                    sanitized_summaries = _strip_timestamp_markers(conversation_summaries)
                    resummarize_values: Dict[str, str] = {
                        "name": npc.name,
                        "language": self.__language_name,
                        "game": str(self.__game),
                        "player_name": player_name,
                    }
                    resummarize_template = self.__config.resummarize_prompt
                    lorebook_text = self.__build_lorebook_text_for_prompt(
                        resummarize_template,
                        resummarize_values,
                        excluded_variables={"bios", "conversation_summaries"},
                        extra_scan_texts=None,
                    )
                    try:
                        resummarize_template = self.__config.prompt_profile_manager.resolve_prompt(
                            "resummarize_prompt", resummarize_template
                        )
                    except PromptSectionError as e:
                        logging.error(str(e))
                        return ""
                    prompt = resummarize_template.format(
                        name=npc.name,
                        language=self.__language_name,
                        game=self.__game,
                        player_name=player_name,
                        lorebook=lorebook_text,
                    )
                    long_conversation_summary = self.summarize_conversation(sanitized_summaries, prompt)
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

            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    summary = self.__summary_client.request_call(messages)
                    if summary:
                        break
                    logging.info(f"Summarizing conversation failed (attempt {attempt}/{max_retries}).")
                except Exception as e:
                    logging.error(f"Summarizing conversation error (attempt {attempt}/{max_retries}): {e}")
                    summary = ''
                if attempt < max_retries:
                    time.sleep(5)

            if not summary:
                logging.info(f"Summarizing conversation failed after {max_retries} attempts.")
                return ""

            npc_name = "Someone"
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