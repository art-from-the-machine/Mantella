import csv
import logging
import os
import re
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
from src.bio_section_filter import apply_bio_section_filter, should_filter_memory_bios
from src.prompt_profile_manager import PromptSectionError
from src.remember.summaries import (
    CharacterSummaryParameters,
    build_memory_text,
    drop_blocks_since,
    format_character_bios_for_memory,
    parse_summary_blocks,
    player_name_from_thread,
    thread_contains_player,
)

PERSONAL_REFLECTION_HEADER = "## Personal Reflection (Don't speak out loud, these are private thoughts)"
PERSONAL_REFLECTION_LOAD_NONE = "none"
_TS_MARKER_RE = re.compile(r"^ts=(\d+)$")
_HEADING_RE = re.compile(r"^##\s*personal reflection(?:\s*\(.*\))?\s*$", re.IGNORECASE)
_USER_INSTRUCTION = "Write your personal reflection."


def resolve_language_display_name(language: str) -> str:
    """Map a config language code (``en``) to the display name used in prompts (``English``)."""
    code = (language or "").strip()
    if not code:
        return "English"
    try:
        csv_path = os.path.join(utils.resolve_path(), "data", "language_support.csv")
        with open(csv_path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if (row.get("alpha2") or "").strip() == code:
                    name = (row.get("language") or "").strip()
                    if name:
                        return name
                    break
    except Exception:
        pass
    return code


def _find_existing_npc_folder(base_dir: str, world_id: str, base_name: str) -> str | None:
    """Newest ``Name`` or ``Name - ref`` folder, matching Bio Editor Save/Refresh."""
    try:
        world_path = os.path.join(base_dir, world_id)
        if not os.path.isdir(world_path):
            return None
        prefix = f"{base_name} - "
        candidates: List[Tuple[float, str]] = []
        for entry in os.listdir(world_path):
            entry_path = os.path.join(world_path, entry)
            if not os.path.isdir(entry_path):
                continue
            if entry == base_name or entry.startswith(prefix):
                try:
                    candidates.append((os.path.getmtime(entry_path), entry_path))
                except Exception:
                    continue
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]
    except Exception:
        return None


def should_load_reflections_into_prompt(config) -> bool:
    """True when the conversation prompt should include the latest personal reflection."""
    mode = str(getattr(config, "personal_reflection_load_mode", "Latest") or "Latest").strip().lower()
    return mode != PERSONAL_REFLECTION_LOAD_NONE


def wrap_personal_reflection(text: str) -> str:
    """Wrap reflection text as a bio section heading. Stored files do not include this heading."""
    stripped = (text or "").strip()
    if not stripped:
        return ""
    first_line = stripped.split("\n", 1)[0].strip()
    if _HEADING_RE.match(first_line):
        return stripped
    return f"{PERSONAL_REFLECTION_HEADER}\n{stripped}"


def strip_reflection_heading(text: str) -> str:
    """Remove a leading Personal Reflection heading from LLM output before storing."""
    stripped = (text or "").strip()
    if not stripped:
        return ""
    lines = stripped.split("\n")
    if _HEADING_RE.match(lines[0].strip()):
        return "\n".join(lines[1:]).strip()
    return stripped


def parse_reflection_blocks(raw_text: str) -> Tuple[List[str], List[Tuple[int, str]]]:
    """Parse a reflection file into legacy blocks and timestamped blocks.

    Unlike summary/thought parsing, a block continues until the next ``ts=`` line.
    Blank lines inside a reflection are kept so multi-paragraph text stays one block.
    """
    legacy_blocks: List[str] = []
    timestamped_blocks: List[Tuple[int, str]] = []
    current_ts: int | None = None
    current_lines: List[str] = []

    def flush() -> None:
        nonlocal current_ts, current_lines
        text = "\n".join(current_lines).strip()
        if text:
            if current_ts is not None:
                timestamped_blocks.append((current_ts, text))
            else:
                legacy_blocks.append(text)
        current_ts = None
        current_lines = []

    for line in (raw_text or "").split("\n"):
        marker = _TS_MARKER_RE.match(line.strip())
        if marker:
            flush()
            current_ts = int(marker.group(1))
            continue
        current_lines.append(line)
    flush()
    return legacy_blocks, timestamped_blocks


def select_latest_reflection(
    legacy_blocks: List[str],
    timestamped_blocks: List[Tuple[int, str]],
) -> Tuple[int, str] | None:
    """Return the newest reflection as ``(timestamp, text)``, or None if none exist."""
    if timestamped_blocks:
        return max(timestamped_blocks, key=lambda item: item[0])
    if legacy_blocks:
        return (0, legacy_blocks[-1])
    return None


class PersonalReflection:
    """Stores per-NPC long-term personal reflections, separate from thoughts and summaries."""

    def __init__(
        self,
        game: Gameable | None,
        config: ConfigLoader,
        client: LLMClient | ClientBase,
        language_name: str,
        summary_client: ClientBase | None = None,
        reflections_folder_path: str | None = None,
    ) -> None:
        self.loglevel = 28
        self.__config = config
        self.__game = game
        self.__client = client
        self.__summary_client: ClientBase = summary_client if summary_client else client
        self.__language_name = resolve_language_display_name(language_name)
        if reflections_folder_path:
            self.__reflections_folder_path = reflections_folder_path
        elif game is not None:
            self.__reflections_folder_path = game.reflections_folder_path
        else:
            raise ValueError("PersonalReflection requires a game or reflections_folder_path.")

    def update_summary_client(self, summary_client: ClientBase | None, fallback_client: LLMClient) -> None:
        self.__client = fallback_client
        self.__summary_client = summary_client if summary_client else fallback_client

    def get_latest_reflection_block(self, character: Character, world_id: str, conversation_start_ts: int | None = None) -> Tuple[int, str] | None:
        legacy_blocks, timestamped_blocks = self._parse_reflection_file(character, world_id)
        latest = select_latest_reflection(legacy_blocks, drop_blocks_since(timestamped_blocks, conversation_start_ts))
        if not latest:
            return None
        ts, text = latest
        text = (text or "").strip()
        if not text:
            return None
        return (ts, text)

    def get_latest_reflection_text(self, character: Character, world_id: str, conversation_start_ts: int | None = None) -> str:
        latest = self.get_latest_reflection_block(character, world_id, conversation_start_ts)
        if not latest:
            return ""
        return latest[1]

    @utils.time_it
    def save_reflections(
        self,
        npc_threads: Dict[str, CharacterSummaryParameters],
        characters: Dict[str, Character],
        summaries_by_npc: Dict[str, str],
        world_id: str,
        save_timestamp: int,
        conversation_start_ts: int | None = None,
    ) -> None:
        """Generate and append a personal reflection for each NPC that has summaries.

        *conversation_start_ts* hides reflections written since then from the previous-reflection prompt.
        """
        for npc_name, npc in characters.items():
            if getattr(npc, "is_player_character", False):
                continue
            summary_text = (summaries_by_npc.get(npc_name) or "").strip()
            if not summary_text:
                logging.info(f"Personal reflection not saved for {npc_name}. No summaries.")
                continue
            params = npc_threads.get(npc_name)
            involved = params.characters if params else [npc]
            player_name = player_name_from_thread(params.messages) if params else "the player"
            contains_player = thread_contains_player(params.messages) if params else False
            try:
                reflection = self.__create_reflection(
                    npc, involved, summary_text, world_id, player_name,
                    contains_player=contains_player, conversation_start_ts=conversation_start_ts,
                )
                if reflection:
                    self.__append_reflection(reflection, npc, world_id, save_timestamp)
            except Exception as e:
                logging.error(f"Failed to save personal reflection for {npc_name}: {e}", exc_info=True)

    def save_for_named_npc(
        self,
        npc_name: str,
        bio: str,
        summaries: str,
        world_id: str,
        save_timestamp: int | None = None,
        player_name: str = "the player",
        tags: str = "",
        selected_ts: int | None = None,
    ) -> str:
        """Generate and append a reflection from Bio Editor texts. Returns the new body, or empty.

        *selected_ts* (when the NPC was selected) hides reflections generated since then from
        the previous-reflection prompt, so regenerating does not build on rejected attempts.
        """
        summary_text = (summaries or "").strip()
        if not summary_text:
            logging.info(f"Personal reflection not saved for {npc_name}. No summaries.")
            return ""
        # Bio Editor shows the raw summary file; merge in dynamic tag events like in-game memory does.
        summary_text = build_memory_text(
            *parse_summary_blocks(summary_text), self.__tag_dynamic_events(tags), dedupe_legacy=True
        )
        ts = save_timestamp if save_timestamp is not None else int(time.time())
        dummy = _NameOnlyCharacter(npc_name)
        source_bio = self.__append_tag_templates(bio or "", tags)
        resolved_bio = utils.resolve_player_name_placeholder(source_bio, player_name)
        filtered_bio = apply_bio_section_filter(
            resolved_bio,
            npc_name,
            self.__config,
            enabled=should_filter_memory_bios(self.__config, contains_player=True),
        )
        involved_bios = f"{npc_name}: {filtered_bio}"
        previous = self.get_latest_reflection_text(dummy, world_id, selected_ts) or "(none)"
        prompt = self.__format_prompt(
            name=npc_name,
            names=npc_name,
            bios=involved_bios,
            player_name=player_name,
            conversation_summary=summary_text,
            previous_reflection=previous,
        )
        reflection = self.__request_reflection(prompt)
        if not reflection:
            return ""
        self.__append_reflection(reflection, dummy, world_id, ts)
        return reflection

    def __append_tag_templates(self, bio: str, tags: str) -> str:
        """Append tag-template text the same way an in-game character bio is expanded.

        Bio Editor stores the raw bio and tags separately. Gameplay already expands
        tags onto ``Character.bio`` before a reflection is written.
        """
        cleaned_tags = (tags or "").strip()
        if not cleaned_tags:
            return bio
        game = self.__game
        expander = getattr(game, "expand_bio_with_tags", None) if game is not None else None
        if callable(expander):
            return expander(bio, cleaned_tags)
        if self.__config.game.base_game == GameEnum.FALLOUT4:
            return bio
        return self.__load_bio_template_manager().expand_bio_with_tags(bio, cleaned_tags)

    def __tag_dynamic_events(self, tags: str) -> List[Tuple[int, str]]:
        """Dynamic tag events, matching what in-game character load merges into the summary timeline."""
        cleaned_tags = (tags or "").strip()
        if not cleaned_tags:
            return []
        game = self.__game
        extractor = getattr(game, "extract_dynamic_events", None) if game is not None else None
        if callable(extractor):
            return extractor(cleaned_tags)
        if self.__config.game.base_game == GameEnum.FALLOUT4:
            return []
        return self.__load_bio_template_manager().extract_dynamic_events(cleaned_tags)

    def __load_bio_template_manager(self):
        from src.bio_template_manager import BioTemplateManager
        templates_path = os.path.join(utils.resolve_path(), "data", "Skyrim", "bio_templates")
        return BioTemplateManager(templates_path, self.__config, "Skyrim")

    def _parse_reflection_file(self, character: Character, world_id: str) -> Tuple[List[str], List[Tuple[int, str]]]:
        reflection_file = self.__get_latest_reflection_file_path(character, world_id)
        if not os.path.exists(reflection_file):
            return [], []
        try:
            with open(reflection_file, "r", encoding="utf-8") as f:
                raw_text = f.read()
        except Exception as e:
            logging.error(f"Failed to read personal reflections for {character.name}: {e}")
            return [], []
        return parse_reflection_blocks(raw_text)

    def __get_latest_reflection_file_path(self, character: Character, world_id: str) -> str:
        base_name: str = utils.remove_trailing_number(character.name)
        ref_id = str(getattr(character, "ref_id", None) or "").strip()

        def get_folder_path(folder_name: str) -> str:
            return os.path.join(self.__reflections_folder_path, world_id, folder_name)

        def get_latest_file_number(folder_path: str) -> int:
            if not os.path.exists(folder_path):
                return 1
            prefix = f"{base_name}_reflections_"
            numbers: List[int] = []
            for filename in os.listdir(folder_path):
                if filename.startswith(prefix) and filename.endswith(".txt"):
                    try:
                        numbers.append(int(os.path.splitext(filename)[0].split("_")[-1]))
                    except ValueError:
                        continue
            return max(numbers) if numbers else 1

        if ref_id:
            name_ref_path = get_folder_path(f"{base_name} - {ref_id}")
            name_path = get_folder_path(base_name)
            if os.path.exists(name_ref_path):
                target_folder = name_ref_path
            elif os.path.exists(name_path):
                target_folder = name_path
            else:
                target_folder = name_ref_path
        else:
            # Bio Editor has no ref_id; reuse the newest Name / Name - ref folder
            # so generate appends where in-game save/load already writes.
            existing = _find_existing_npc_folder(self.__reflections_folder_path, world_id, base_name)
            target_folder = existing or get_folder_path(base_name)

        latest_file_number = get_latest_file_number(target_folder)
        return os.path.join(target_folder, f"{base_name}_reflections_{latest_file_number}.txt")

    def __create_reflection(
        self,
        npc: Character,
        involved_characters: List[Character],
        conversation_summary: str,
        world_id: str,
        player_name: str,
        contains_player: bool = False,
        conversation_start_ts: int | None = None,
    ) -> str:
        names = ", ".join([c.name for c in involved_characters])
        bios = format_character_bios_for_memory(
            involved_characters,
            player_name,
            self.__config,
            contains_player=contains_player,
        )
        previous_reflection = self.get_latest_reflection_text(npc, world_id, conversation_start_ts) or "(none)"
        prompt = self.__format_prompt(
            name=npc.name,
            names=names,
            bios=bios,
            player_name=player_name,
            conversation_summary=conversation_summary.strip(),
            previous_reflection=previous_reflection,
        )
        if not prompt:
            return ""
        return self.__request_reflection(prompt)

    def __format_prompt(
        self,
        name: str,
        names: str,
        bios: str,
        player_name: str,
        conversation_summary: str,
        previous_reflection: str,
    ) -> str:
        if self.__config.game.base_game == GameEnum.FALLOUT4:
            location = "the Commonwealth"
        else:
            location = "Skyrim"
        try:
            reflection_template = self.__config.prompt_profile_manager.resolve_prompt(
                "personal_reflection_prompt", self.__config.personal_reflection_prompt
            )
        except PromptSectionError as e:
            logging.error(str(e))
            return ""
        return reflection_template.format(
            name=name,
            names=names,
            language=self.__language_name,
            game=location,
            bios=bios,
            player_name=player_name,
            previous_reflection=previous_reflection,
            conversation_summary=conversation_summary,
            lorebook="",
        )

    def __append_reflection(self, new_reflection: str, npc: Character, world_id: str, save_timestamp: int) -> None:
        reflection_file = self.__get_latest_reflection_file_path(npc, world_id)
        if os.path.exists(reflection_file):
            with open(reflection_file, "r", encoding="utf-8") as f:
                previous = f.read()
        else:
            directory = os.path.dirname(reflection_file)
            os.makedirs(directory, exist_ok=True)
            previous = ""

        body = strip_reflection_heading(new_reflection)
        if not body:
            return
        block = f"ts={int(save_timestamp)}\n{body}\n\n"
        if previous:
            if previous.endswith("\n\n"):
                separator = ""
            elif previous.endswith("\n"):
                separator = "\n"
            else:
                separator = "\n\n"
        else:
            separator = ""

        with open(reflection_file, "w", encoding="utf-8") as f:
            f.write(previous + separator + block)
        logging.info(f"Personal reflection saved for {npc.name}")

    def __request_reflection(self, prompt: str) -> str:
        reflection = ""
        messages = message_thread(self.__config, prompt)
        messages.add_message(UserMessage(self.__config, _USER_INSTRUCTION))
        logging.log(23, f"Personal reflection prompt sent to LLM: {prompt.strip()}")

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                reflection = self.__summary_client.request_call(messages)
                if reflection:
                    break
                logging.info(f"Generating personal reflection failed (attempt {attempt}/{max_retries}).")
            except Exception as e:
                logging.error(f"Generating personal reflection error (attempt {attempt}/{max_retries}): {e}")
                reflection = ""
            if attempt < max_retries:
                time.sleep(5)

        if not reflection:
            logging.info(f"Generating personal reflection failed after {max_retries} attempts.")
            return ""

        reflection = strip_reflection_heading(reflection)
        logging.log(self.loglevel, f"Personal reflection: {reflection}")
        return reflection


class _NameOnlyCharacter:
    """Minimal stand-in so Bio Editor generation can reuse character file-path logic."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.ref_id = ""
        self.bio = ""
        self.is_player_character = False
