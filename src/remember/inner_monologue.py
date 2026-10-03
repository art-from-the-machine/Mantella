import logging
import os
import time
from typing import Dict, List, Tuple

from src import utils
from src.character_manager import Character
from src.config.config_loader import ConfigLoader
from src.config.definitions.game_definitions import GameEnum
from src.games.gameable import Gameable
from src.llm.client_base import ClientBase
from src.llm.llm_client import LLMClient
from src.llm.message_thread import message_thread
from src.llm.messages import UserMessage
from src.prompt_profile_manager import PromptSectionError
from src.remember.summaries import (
    CharacterSummaryParameters,
    drop_blocks_since,
    format_character_bios_for_memory,
    parse_summary_blocks,
    player_name_from_thread,
    thread_contains_player,
)

PRIVATE_THOUGHT_HEADER = "--- PRIVATE THOUGHT (unspoken; other people must not know this) ---"
PRIVATE_THOUGHT_FOOTER = "--- END PRIVATE THOUGHT ---"
INNER_MONOLOGUE_LOAD_NONE = "none"


def should_load_thoughts_into_prompt(config) -> bool:
    """True when the conversation prompt should include the latest private thought."""
    mode = str(getattr(config, "inner_monologue_load_mode", "Latest") or "Latest").strip().lower()
    return mode != INNER_MONOLOGUE_LOAD_NONE


def wrap_private_thought(text: str) -> str:
    """Wrap thought text so the conversation LLM can tell it apart from a summary."""
    stripped = (text or "").strip()
    if not stripped:
        return ""
    if PRIVATE_THOUGHT_HEADER in stripped:
        return stripped
    return f"{PRIVATE_THOUGHT_HEADER}\n{stripped}\n{PRIVATE_THOUGHT_FOOTER}"


def select_latest_thought(
    legacy_blocks: List[str],
    timestamped_blocks: List[Tuple[int, str]],
) -> Tuple[int, str] | None:
    """Return the newest thought as ``(timestamp, text)``, or None if none exist.

    Timestamped blocks win. If the file only has legacy (un-timestamped) text,
    the last legacy block is returned with timestamp ``0``.
    """
    if timestamped_blocks:
        return max(timestamped_blocks, key=lambda item: item[0])
    if legacy_blocks:
        return (0, legacy_blocks[-1])
    return None


class InnerMonologue:
    """Stores per-NPC private thoughts in a folder separate from conversation summaries."""

    def __init__(
        self,
        game: Gameable,
        config: ConfigLoader,
        client: LLMClient,
        language_name: str,
        summary_client: ClientBase | None = None,
    ) -> None:
        self.loglevel = 28
        self.__config = config
        self.__game = game
        self.__client: LLMClient = client
        self.__summary_client: ClientBase = summary_client if summary_client else client
        self.__language_name = language_name

    def update_summary_client(self, summary_client: ClientBase | None, fallback_client: LLMClient) -> None:
        self.__client = fallback_client
        self.__summary_client = summary_client if summary_client else fallback_client

    def get_latest_thought_block(self, character: Character, world_id: str) -> Tuple[int, str] | None:
        """Load the latest thought and return ``(timestamp, raw_text)``."""
        latest = select_latest_thought(*self._parse_thought_file(character, world_id))
        if not latest:
            return None
        ts, text = latest
        text = (text or "").strip()
        if not text:
            return None
        return (ts, text)

    def get_previous_thoughts_text(self, character: Character, world_id: str, conversation_start_ts: int | None = None) -> str:
        """Unwrapped thought history for the generation prompt, ignoring thoughts written since *conversation_start_ts*."""
        legacy_blocks, timestamped_blocks = self._parse_thought_file(character, world_id)
        timestamped_blocks = drop_blocks_since(timestamped_blocks, conversation_start_ts)
        parts: List[str] = list(legacy_blocks)
        for _, text in sorted(timestamped_blocks, key=lambda item: item[0]):
            parts.append(text)
        return "\n\n".join(part.strip() for part in parts if part and part.strip())

    @utils.time_it
    def save_thoughts(
        self,
        npc_threads: Dict[str, CharacterSummaryParameters],
        characters: Dict[str, Character],
        saved_summaries: Dict[str, str],
        world_id: str,
        save_timestamp: int,
        require_summary: bool = True,
        conversation_start_ts: int | None = None,
    ) -> None:
        """Generate and append a private thought for each NPC.

        *saved_summaries* should be this NPC's full past-event summary text (the latest
        summary file), not only the paragraph just written.

        When *require_summary* is True (normal conversation-end path), NPCs without a
        newly written summary are skipped. Manual "save thoughts" can pass False so a
        thought is still written from the live conversation.
        """
        npc_names = saved_summaries.keys() if require_summary else npc_threads.keys()
        for npc_name in npc_names:
            summary_text = saved_summaries.get(npc_name, "")
            if require_summary and not (summary_text or "").strip():
                continue
            params = npc_threads.get(npc_name)
            npc = characters.get(npc_name)
            if not params or not npc:
                continue
            try:
                thought = self.__create_thought(npc, params, world_id, summary_text, conversation_start_ts)
                if thought:
                    self.__append_thought(thought, npc, world_id, save_timestamp)
            except Exception as e:
                logging.error(f"Failed to save private thought for {npc_name}: {e}", exc_info=True)

    def _parse_thought_file(self, character: Character, world_id: str) -> Tuple[List[str], List[Tuple[int, str]]]:
        thought_file = self.__get_latest_thought_file_path(character, world_id)
        if not os.path.exists(thought_file):
            return [], []
        try:
            with open(thought_file, "r", encoding="utf-8") as f:
                raw_text = f.read()
        except Exception as e:
            logging.error(f"Failed to read private thoughts for {character.name}: {e}")
            return [], []
        return parse_summary_blocks(raw_text)

    def __get_latest_thought_file_path(self, character: Character, world_id: str) -> str:
        base_name: str = utils.remove_trailing_number(character.name)
        name_ref: str = f"{base_name} - {character.ref_id}"

        def get_folder_path(folder_name: str) -> str:
            return os.path.join(self.__game.thoughts_folder_path, world_id, folder_name)

        def get_latest_file_number(folder_path: str) -> int:
            if not os.path.exists(folder_path):
                return 1
            prefix = f"{base_name}_thoughts_"
            numbers: List[int] = []
            for filename in os.listdir(folder_path):
                if filename.startswith(prefix) and filename.endswith(".txt"):
                    try:
                        numbers.append(int(os.path.splitext(filename)[0].split("_")[-1]))
                    except ValueError:
                        continue
            return max(numbers) if numbers else 1

        name_ref_path = get_folder_path(name_ref)
        name_path = get_folder_path(base_name)
        if os.path.exists(name_ref_path):
            target_folder = name_ref_path
        elif os.path.exists(name_path):
            target_folder = name_path
        else:
            target_folder = name_ref_path

        latest_file_number = get_latest_file_number(target_folder)
        return os.path.join(target_folder, f"{base_name}_thoughts_{latest_file_number}.txt")

    def __create_thought(
        self,
        npc: Character,
        npc_info: CharacterSummaryParameters,
        world_id: str,
        conversation_summary: str,
        conversation_start_ts: int | None = None,
    ) -> str:
        if self.__config.game.base_game == GameEnum.FALLOUT4:
            location = "the Commonwealth"
        else:
            location = "Skyrim"

        names = ", ".join([c.name for c in npc_info.characters])
        player_name = player_name_from_thread(npc_info.messages)
        bios = format_character_bios_for_memory(
            npc_info.characters,
            player_name,
            self.__config,
            contains_player=thread_contains_player(npc_info.messages),
        )

        previous_thoughts = self.get_previous_thoughts_text(npc, world_id, conversation_start_ts) or "(none)"
        try:
            monologue_template = self.__config.prompt_profile_manager.resolve_prompt(
                "inner_monologue_prompt", self.__config.inner_monologue_prompt
            )
        except PromptSectionError as e:
            logging.error(str(e))
            return ""
        prompt = monologue_template.format(
            name=npc.name,
            names=names,
            language=self.__language_name,
            game=location,
            bios=bios,
            player_name=player_name,
            previous_thoughts=previous_thoughts,
            conversation_summary=conversation_summary.strip(),
            lorebook="",
        )
        talk_text = npc_info.messages.transform_to_text(
            npc_info.messages.get_talk_only(include_system_generated_messages=True)
        )
        return self.__request_thought(talk_text, prompt)

    def __append_thought(self, new_thought: str, npc: Character, world_id: str, save_timestamp: int) -> None:
        thought_file = self.__get_latest_thought_file_path(npc, world_id)
        if os.path.exists(thought_file):
            with open(thought_file, "r", encoding="utf-8") as f:
                previous = f.read()
        else:
            directory = os.path.dirname(thought_file)
            os.makedirs(directory, exist_ok=True)
            previous = ""

        thought_body = new_thought.strip()
        if thought_body and not thought_body.startswith("-"):
            thought_body = "- " + thought_body
        block = f"ts={int(save_timestamp)}\n{thought_body}\n\n"
        if previous:
            if previous.endswith("\n\n"):
                separator = ""
            elif previous.endswith("\n"):
                separator = "\n"
            else:
                separator = "\n\n"
        else:
            separator = ""

        with open(thought_file, "w", encoding="utf-8") as f:
            f.write(previous + separator + block)
        logging.info(f"Private thought saved for {npc.name}")

    def __request_thought(self, text_to_reflect_on: str, prompt: str) -> str:
        thought = ""
        if len(text_to_reflect_on) <= 5:
            logging.info("Private thought not saved. Not enough dialogue spoken.")
            return ""

        messages = message_thread(self.__config, prompt)
        messages.add_message(UserMessage(self.__config, text_to_reflect_on))
        logging.log(23, f"Inner monologue prompt sent to LLM: {prompt.strip()}")

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                thought = self.__summary_client.request_call(messages)
                if thought:
                    break
                logging.info(f"Generating private thought failed (attempt {attempt}/{max_retries}).")
            except Exception as e:
                logging.error(f"Generating private thought error (attempt {attempt}/{max_retries}): {e}")
                thought = ""
            if attempt < max_retries:
                time.sleep(5)

        if not thought:
            logging.info(f"Generating private thought failed after {max_retries} attempts.")
            return ""

        thought = thought.strip()
        logging.log(self.loglevel, f"Private thought: {thought}")
        return thought
