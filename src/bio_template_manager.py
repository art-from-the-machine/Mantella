import os
import json
import logging
import re
import pandas as pd
from typing import Dict, List, Optional, Tuple
import src.utils as utils
from src.config.definitions.llm_definitions import AutoQuestTagOutcomesEnum

# Number of quest outcome columns (`potential_paste_N` / `code_N`) a bio template CSV can have
OUTCOME_SLOTS = 5

# The three layers bio template files are loaded from, in load order (a later layer wins)
LAYER_BASE = "base"
LAYER_MOD = "mod override"
LAYER_PERSONAL = "personal override"

# Every column a tag row can fill in. `notes` and `source` (which mod the tag is for) are for people editing the files;
# nothing at runtime reads them
TAG_COLUMNS = (
    ['description']
    + [f'{prefix}_{slot}' for slot in range(1, OUTCOME_SLOTS + 1) for prefix in ('potential_paste', 'code')]
    + ['announce', 'outcome_mode', 'notes', 'source']
)

# What a tag's `outcome_mode` cell can hold, besides nothing: where that tag's quest outcome goes, whatever the
# Auto Quest Tag Outcomes setting says (see docs/quest_tags_1_user_edits.md, Part 2)
OUTCOME_MODES = {
    'static': AutoQuestTagOutcomesEnum.STATIC,
    'dynamic': AutoQuestTagOutcomesEnum.DYNAMIC,
    'off': AutoQuestTagOutcomesEnum.OFF,
}
# Follows the setting, like an empty cell. It's how a later file undoes an earlier file's choice
OUTCOME_MODE_DEFAULT = 'default'

# Pattern to match dynamic event lines in tag descriptions: "- <timestamp>: <text>"
_DYNAMIC_EVENT_RE = re.compile(r'^-\s+(\d+):\s+(.+)$')


def _split_static_and_dynamic(description: str) -> Tuple[str, List[Tuple[int, str]]]:
    """Split a tag description into static text and dynamic event lines.

    Dynamic event lines match the format ``- <timestamp>: <text>``
    where ``<timestamp>`` is one or more digits (epoch seconds).

    Returns:
        A tuple of (*static_text*, *dynamic_events*) where *dynamic_events*
        is a list of ``(timestamp, event_text)`` pairs.
    """
    static_lines: List[str] = []
    dynamic_events: List[Tuple[int, str]] = []
    for line in description.split('\n'):
        match = _DYNAMIC_EVENT_RE.match(line.strip())
        if match:
            ts = int(match.group(1))
            text = match.group(2).strip()
            dynamic_events.append((ts, text))
        else:
            static_lines.append(line)
    static_text = '\n'.join(static_lines).strip()
    return static_text, dynamic_events


def file_encoding(path: str) -> str:
    """The encoding to read a tag file with. A file that is valid UTF-8 is UTF-8 (`utf-8-sig` with a BOM):
    encoding guesses can mistake a short UTF-8 file for another encoding and show its accented text garbled.
    Only other files use the guess"""
    with open(path, "rb") as file:
        data = file.read()
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return utils.get_file_encoding(path) or "utf-8"


def _clean_tags_cell(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def effective_tags(tags, tags_overwrite) -> str:
    """An NPC's tags at runtime: `tags_overwrite` when it's set (it replaces the accumulated `tags`), otherwise `tags`"""
    overwrite = _clean_tags_cell(tags_overwrite)
    return overwrite if overwrite else _clean_tags_cell(tags)


def split_tags(tags_string: str) -> List[str]:
    """The tag names in a comma-separated list: trimmed, each once, in order.

    Curly apostrophes become straight ones, as in the templates, so `risaad’s_caravan` finds `risaad's_caravan`.
    """
    tags: List[str] = []
    for tag in (utils.normalize_apostrophes(part.strip()) for part in str(tags_string or "").split(',')):
        if tag and tag not in tags:
            tags.append(tag)
    return tags


class BioTemplateManager:
    """Manages bio templates for tag-based dynamic bio injection"""
    
    def __init__(self, base_templates_folder: str, config_loader=None, game_name: str = "Skyrim"):
        self.base_templates_folder = base_templates_folder
        self.config_loader = config_loader
        self.game_name = game_name
        self.templates: Dict[str, str] = {}
        # Quest outcomes per tag, by outcome number (see docs/quest_tags_1_user_edits.md)
        self.outcome_texts: Dict[str, Dict[int, str]] = {}
        self.outcome_codes: Dict[str, Dict[int, str]] = {}
        self.no_announce: set[str] = set()
        # Tags with their own `outcome_mode` (a key of OUTCOME_MODES). Tags that follow the setting aren't in here
        self.outcome_modes: Dict[str, str] = {}
        # Where each value came from, for the Tag Editor (see docs/tag_editor.md)
        # tag -> column -> every (layer, file, value) that filled the cell, in load order; the last one wins
        self.sources: Dict[str, Dict[str, List[Tuple[str, str, str]]]] = {}
        # tag -> every (layer, file) with a row for the tag, in load order
        self.files_with_tag: Dict[str, List[Tuple[str, str]]] = {}
        self._load_templates()

    def _load_templates(self):
        """Load bio templates from CSV files with override support"""
        # 1. Load base templates first
        self._load_templates_from_folder(self.base_templates_folder, LAYER_BASE)
        
        # 2. Load mod override templates (if config is available)
        if self.config_loader:
            # Determine the correct extender name based on game
            extender_name = "SKSE" if self.game_name == "Skyrim" else "F4SE"
            
            mod_overrides_folder = os.path.join(
                self.config_loader.mod_path_base, 
                extender_name,
                "Plugins", 
                "MantellaSoftware", 
                "data", 
                self.game_name, 
                "bio_templates"
            )
            self._load_templates_from_folder(mod_overrides_folder, LAYER_MOD)
            
            # 3. Load personal override templates
            personal_overrides_folder = os.path.join(
                self.config_loader.save_folder, 
                "data", 
                self.game_name, 
                "bio_templates"
            )
            self._load_templates_from_folder(personal_overrides_folder, LAYER_PERSONAL)

    def _load_templates_from_folder(self, templates_folder: str, folder_type: str):
        """Load bio templates from a specific folder"""
        if not os.path.exists(templates_folder):
            if folder_type == LAYER_BASE:
                # Only create base folder and default templates
                os.makedirs(templates_folder, exist_ok=True)
                default_templates_file = os.path.join(templates_folder, "bio_templates.csv")
                if not os.path.exists(default_templates_file):
                    self._create_default_templates(default_templates_file)
            else:
                # For override folders, just return if they don't exist
                return
        
        # Load all CSV files in the templates folder
        try:
            for filename in os.listdir(templates_folder):
                if filename.endswith('.csv'):
                    filepath = os.path.join(templates_folder, filename)
                    try:
                        # The same encoding the Tag Editor writes with, so what it shows is what it saves
                        encoding = file_encoding(filepath)
                        df = pd.read_csv(filepath, engine='python', encoding=encoding)

                        # Expected columns: 'tag' and 'description'
                        if 'tag' in df.columns and 'description' in df.columns:
                            templates_loaded = 0
                            for _, row in df.iterrows():
                                tag = utils.normalize_apostrophes(self._get_cell(row, 'tag'))
                                if not tag:
                                    continue
                                self._record_sources(row, tag, folder_type, filepath)
                                # Cell by cell: a later file only replaces the cells it fills in
                                description = self._get_cell(row, 'description')
                                if description:
                                    self.templates[tag] = description
                                    templates_loaded += 1
                                for slot in range(1, OUTCOME_SLOTS + 1):
                                    text = self._get_cell(row, f'potential_paste_{slot}')
                                    if text:
                                        self.outcome_texts.setdefault(tag, {})[slot] = text
                                    code = self._get_cell(row, f'code_{slot}')
                                    if code:
                                        self.outcome_codes.setdefault(tag, {})[slot] = code
                                announce = self._get_cell(row, 'announce').lower()
                                if announce == 'no':
                                    self.no_announce.add(tag)
                                elif announce:
                                    self.no_announce.discard(tag)
                                outcome_mode = self._get_cell(row, 'outcome_mode').lower()
                                if outcome_mode in OUTCOME_MODES:
                                    self.outcome_modes[tag] = outcome_mode
                                elif outcome_mode == OUTCOME_MODE_DEFAULT:
                                    self.outcome_modes.pop(tag, None)
                                elif outcome_mode:
                                    logging.warning(f"Tag '{tag}' in {filename}: outcome_mode '{outcome_mode}' is not static, dynamic, off or default - ignoring it")
                            logging.info(f"Loaded {templates_loaded} bio templates from {folder_type} file: {filename}")
                        else:
                            logging.warning(f"CSV file {filename} in {folder_type} folder missing required columns 'tag' and 'description'")
                    except Exception as e:
                        logging.warning(f"Could not load bio template file '{filename}' in '{templates_folder}'. Error: {e}")
        except Exception as e:
            logging.warning(f"Could not access {folder_type} bio templates folder '{templates_folder}'. Error: {e}")
    
    def _record_sources(self, row: pd.Series, tag: str, folder_type: str, filepath: str):
        """Remember which file has a row for the tag, and which file filled each of its cells"""
        files = self.files_with_tag.setdefault(tag, [])
        if (folder_type, filepath) not in files:
            files.append((folder_type, filepath))
        for column in TAG_COLUMNS:
            value = self._get_cell(row, column)
            if value:
                self.sources.setdefault(tag, {}).setdefault(column, []).append((folder_type, filepath, value))

    @staticmethod
    def _get_cell(row: pd.Series, column: str) -> str:
        if column not in row.index or pd.isna(row[column]):
            return ""
        value = str(row[column]).strip()
        return "" if value == 'nan' else value

    def _create_default_templates(self, filepath: str):
        """Create default bio templates CSV file"""
        default_templates = [
            ("warrior", "Known for exceptional combat prowess and martial skills."),
            ("noble", "Born into nobility with refined manners and political connections."),
            ("merchant", "A shrewd trader with extensive knowledge of commerce and markets."),
            ("scholar", "Devoted to learning and possessing vast knowledge of ancient texts."),
            ("thief", "Skilled in stealth, lockpicking, and moving unseen through shadows."),
            ("mage", "Practitioner of arcane arts with deep understanding of magical forces."),
            ("hunter", "Expert tracker and survivalist, at home in the wilderness."),
            ("skilled_fighter", "Exceptionally talented in various forms of combat and weaponry."),
            ("local_leader", "Respected figure who holds influence in their community."),
            ("religious", "Devoted follower of divine teachings and spiritual practices."),
            ("loyal", "Demonstrates unwavering loyalty to companions and cause."),
            ("blacksmith", "Master craftsperson skilled in forging weapons and armor."),
            ("guard", "Dedicated protector who maintains order and safety."),
            ("bard", "Talented performer who tells stories through song and verse."),
            ("assassin", "Deadly and precise killer who strikes from the shadows."),
            ("dragonborn", "Blessed with the soul and power of a dragon."),
            ("vampire", "Undead creature with supernatural abilities and bloodthirst."),
            ("werewolf", "Shape-shifter who can transform into a fearsome wolf."),
            ("nord", "Hardy northerner accustomed to cold climates and battle."),
            ("imperial", "Citizen of the Empire with diplomatic and administrative skills."),
            ("redguard", "Skilled warrior from the desert provinces of Hammerfell."),
            ("breton", "Magically gifted people with resistance to spells."),
            ("dunmer", "Dark elf with natural magical abilities and long lifespan."),
            ("altmer", "High elf with superior magical prowess and intellectual pursuits."),
            ("bosmer", "Wood elf with natural archery skills and forest knowledge."),
            ("khajiit", "Cat-like humanoid with stealth abilities and merchant instincts."),
            ("argonian", "Reptilian humanoid with natural swimming abilities and disease resistance."),
            ("orc", "Strong and fierce warrior culture with excellent smithing skills."),
            ("companion", "Member of the prestigious warrior guild in Whiterun."),
            ("housecarl", "Personal bodyguard and servant sworn to a thane."),
            ("jarl", "Ruler of a hold with authority over their territory."),
            ("thane", "Honored title granted for service to a jarl."),
            ("steward", "Administrative assistant who manages a jarl's affairs."),
            ("follower", "Loyal companion willing to accompany on adventures."),
            ("innkeeper", "Hospitable keeper of a tavern or inn."),
            ("court_wizard", "Magical advisor to a jarl or important noble."),
            ("sellsword", "Mercenary fighter available for hire."),
            ("bandit", "Outlaw who preys on travelers and settlements."),
            ("pilgrim", "Religious traveler on a spiritual journey."),
            ("farmer", "Hard-working cultivator of crops and livestock."),
            ("milk_drinker", "Derogatory term for someone considered weak or cowardly."),
            ("veteran", "Experienced fighter with many battles behind them."),
            ("survivor", "One who has endured great hardships and lived to tell about it."),
            ("wise", "Possesses great knowledge and understanding of the world."),
            ("cursed", "Afflicted by dark magic or supernatural misfortune."),
            ("blessed", "Favored by the gods with divine protection or abilities."),
            ("stormcloak", "Supporter of Ulfric Stormcloak and Nordic independence."),
            ("imperial_legion", "Loyal soldier of the Imperial Legion."),
            ("neutral", "Tries to stay out of the civil war conflict."),
            ("greybeard", "Master of the Thu'um and keeper of ancient wisdom."),
            ("blade", "Former member of the legendary dragonslayer order."),
            ("forsworn", "Member of the native Reachmen rebellion."),
            ("vigilant", "Member of the Vigilants of Stendarr, hunting daedra and undead.")
        ]
        
        # Create DataFrame and save as CSV
        df = pd.DataFrame(default_templates, columns=['tag', 'description'])
        df.to_csv(filepath, index=False, encoding='utf-8')
        
        logging.info(f"Created default bio templates CSV at {filepath}")
    
    def get_template(self, tag: str) -> Optional[str]:
        """Get bio template for a specific tag"""
        return self.templates.get(utils.normalize_apostrophes(tag))

    def get_outcome_text(self, tag: str, slot: int) -> Optional[str]:
        """The text of one quest outcome. Placeholders like `custom` are never used"""
        text = self.outcome_texts.get(utils.normalize_apostrophes(tag), {}).get(slot)
        if not text or text.lower() == 'custom':
            return None
        return text

    def get_outcome_codes(self) -> Dict[str, Dict[int, str]]:
        """Conditions of every tag the game should check: all but the tags whose `outcome_mode` is `off`"""
        return {tag: codes for tag, codes in self.outcome_codes.items() if self.outcome_modes.get(tag) != 'off'}

    def _get_auto_outcomes_mode(self) -> AutoQuestTagOutcomesEnum:
        return getattr(self.config_loader, 'auto_quest_tag_outcomes', AutoQuestTagOutcomesEnum.STATIC)

    def get_outcome_mode(self, tag: str) -> AutoQuestTagOutcomesEnum:
        """Where this tag's quest outcome goes: its own `outcome_mode`, otherwise the Auto Quest Tag Outcomes setting.
        With the setting Off, nothing is checked in the game, so every tag is Off"""
        setting = self._get_auto_outcomes_mode()
        if setting == AutoQuestTagOutcomesEnum.OFF:
            return AutoQuestTagOutcomesEnum.OFF
        return OUTCOME_MODES.get(self.outcome_modes.get(utils.normalize_apostrophes(tag), ''), setting)

    def _get_auto_outcome_text(self, tag: str, tag_outcomes: Optional[Dict[str, Tuple[int, int]]]) -> Optional[str]:
        if not tag_outcomes or tag not in tag_outcomes:
            return None
        slot = tag_outcomes[tag][0]
        text = self.get_outcome_text(tag, slot)
        if text is None:
            logging.debug(f"Quest tag {tag}: slot {slot} has no text in the bio templates - ignoring")
        return text

    def _outcome_goes_to_bio(self, tag: str, tag_outcomes: Optional[Dict[str, Tuple[int, int]]]) -> bool:
        """Static: always. Dynamic: only outcomes with time 0 (already true when tracking started), which have no place in the timeline.
        Off: never. Which of the three applies is the tag's own choice, or the setting (`get_outcome_mode`)"""
        mode = self.get_outcome_mode(tag)
        if mode == AutoQuestTagOutcomesEnum.STATIC:
            return True
        if mode == AutoQuestTagOutcomesEnum.DYNAMIC:
            return bool(tag_outcomes) and tag in tag_outcomes and tag_outcomes[tag][1] == 0
        return False

    def _get_effective_tags_list(self, tags_string: str) -> List[str]:
        """Parse and validate tags_string, returning a list of tag names.

        Returns an empty list when tag reading is disabled or the input is
        empty / NaN.
        """
        # Check if tag reading is disabled in config
        if self.config_loader and hasattr(self.config_loader, 'enable_character_tag_reading'):
            if not self.config_loader.enable_character_tag_reading:
                return []

        # Handle case where tags_string might be NaN (float) from CSV
        if tags_string is None or (isinstance(tags_string, float) and str(tags_string) == 'nan'):
            return []

        # Convert to string and check if empty
        tags_string = str(tags_string)
        if not tags_string or not tags_string.strip():
            return []

        # Deduplicated, so repeated tags do not duplicate bio sections or dynamic events
        return split_tags(tags_string)

    def expand_bio_with_tags(self, base_bio: str, tags_string: str, tag_outcomes: Optional[Dict[str, Tuple[int, int]]] = None) -> str:
        """Expand base bio with tag templates.

        Dynamic event lines (``- <timestamp>: text``) inside a tag
        description are **excluded** from the bio expansion so they can be
        injected into the chronological memory timeline instead.

        *tag_outcomes* maps a quest tag to its current ``(outcome, time first seen)``
        in the playthrough. When the tag's outcome mode (``get_outcome_mode``) is Static,
        the outcome's text is added right after the tag's own text, in the same paragraph
        (on its own line when that text has several lines).
        With Dynamic, only outcomes with time 0 are added here; the rest go to the memory timeline.
        """
        tags = self._get_effective_tags_list(tags_string)
        if not tags:
            return base_bio

        # Get templates for each tag (ignore missing or empty templates)
        tag_expansions: List[str] = []
        for tag in tags:
            template = self.get_template(tag)
            is_quest_tag = tag in self.outcome_codes or tag in self.outcome_texts
            # The tag's own text first, then its current quest outcome: the latest state on top of the background
            parts: List[str] = []
            if template and template.strip():
                # Separate static text from dynamic events
                static_text, _ = _split_static_and_dynamic(template)
                if static_text:
                    parts.append(static_text)
            if is_quest_tag and self._outcome_goes_to_bio(tag, tag_outcomes):
                outcome_text = self._get_auto_outcome_text(tag, tag_outcomes)
                if outcome_text:
                    parts.append(outcome_text)
            if parts:
                # Same paragraph as the tag's text. After a text of several lines (e.g. a list) it gets its own line,
                # so it doesn't read as part of the last one
                tag_expansions.append(("\n" if "\n" in parts[0] else " ").join(parts))
            elif template is None and not is_quest_tag:
                logging.warning(f"Tag '{tag}' not found in bio_templates.csv - ignoring")

        # Combine base bio with tag expansions, adding newlines between descriptions
        if tag_expansions:
            expanded_bio = base_bio + "\n\n## Additional info\n" + "\n\n".join(tag_expansions)
            return expanded_bio.strip()

        return base_bio

    def extract_dynamic_events(self, tags_string: str, tag_outcomes: Optional[Dict[str, Tuple[int, int]]] = None) -> List[Tuple[int, str]]:
        """Return all dynamic events from the tags assigned to a character.

        Each dynamic event is a ``(timestamp, event_text)`` tuple extracted
        from tag descriptions that contain lines matching
        ``- <timestamp>: text``.

        The current outcome of each quest tag in *tag_outcomes* whose outcome mode
        (``get_outcome_mode``) is Dynamic is added too, dated when it was first seen,
        next to the tag's hand-written events. Outcomes with time 0 (already true when
        tracking started) go to the bio instead.

        The returned list is sorted by timestamp (ascending).
        """
        tags = self._get_effective_tags_list(tags_string)
        if not tags:
            return []

        all_events: List[Tuple[int, str]] = []
        for tag in tags:
            template = self.get_template(tag)
            if template and template.strip():
                _, dynamic_events = _split_static_and_dynamic(template)
                all_events.extend(dynamic_events)
            if (tag in self.outcome_codes and self.get_outcome_mode(tag) == AutoQuestTagOutcomesEnum.DYNAMIC
                    and not self._outcome_goes_to_bio(tag, tag_outcomes)):
                outcome_text = self._get_auto_outcome_text(tag, tag_outcomes)
                if outcome_text:
                    all_events.append((tag_outcomes[tag][1], outcome_text))

        # Sort by timestamp ascending
        all_events.sort(key=lambda ev: ev[0])
        return all_events
    
    def reload_templates(self):
        """Reload templates from disk (useful for live updating)"""
        self.templates.clear()
        self.outcome_texts.clear()
        self.outcome_codes.clear()
        self.no_announce.clear()
        self.outcome_modes.clear()
        self.sources.clear()
        self.files_with_tag.clear()
        self._load_templates()
        logging.info(f"Reloaded {len(self.templates)} bio templates")
    
    def get_template_count(self) -> int:
        """Get the total number of loaded templates"""
        return len(self.templates)
    
    def list_all_tags(self) -> List[str]:
        """Get a list of all available tags"""
        return sorted(list(self.templates.keys())) 