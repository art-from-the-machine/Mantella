import logging
import os
import re
from typing import Dict, List, Tuple

import pandas as pd
import src.utils as utils


class LorebookManager:
    """Loads lorebook entries and resolves key matches in prompt text."""

    _BOUNDARY_CLASS = r"A-Za-z0-9_"

    def __init__(self, base_lorebook_folder: str, config_loader=None, game_name: str = "Skyrim"):
        self.base_lorebook_folder = base_lorebook_folder
        self.config_loader = config_loader
        self.game_name = game_name
        self._entries_by_normalized_key: Dict[str, Tuple[str, str]] = {}
        self._compiled_patterns: Dict[str, re.Pattern[str]] = {}
        self._load_entries()

    @staticmethod
    def _normalize_key(key: str) -> str:
        return key.strip().lower()

    def _load_entries(self):
        """Load lorebook entries in override order: base -> mod -> personal."""
        self._load_entries_from_folder(self.base_lorebook_folder, "base")

        if self.config_loader:
            extender_name = "SKSE" if self.game_name == "Skyrim" else "F4SE"
            mod_overrides_folder = os.path.join(
                self.config_loader.mod_path_base,
                extender_name,
                "Plugins",
                "MantellaSoftware",
                "data",
                self.game_name,
                "lorebook",
            )
            self._load_entries_from_folder(mod_overrides_folder, "mod override")

            personal_overrides_folder = os.path.join(
                self.config_loader.save_folder,
                "data",
                self.game_name,
                "lorebook",
            )
            self._load_entries_from_folder(personal_overrides_folder, "personal override")

    def _load_entries_from_folder(self, lorebook_folder: str, folder_type: str):
        if not os.path.exists(lorebook_folder):
            return

        try:
            for filename in os.listdir(lorebook_folder):
                if not filename.endswith(".csv"):
                    continue

                filepath = os.path.join(lorebook_folder, filename)
                try:
                    encoding = utils.get_file_encoding(filepath)
                    df = pd.read_csv(filepath, engine="python", encoding=encoding)
                    if "key" not in df.columns or "description" not in df.columns:
                        logging.warning(
                            f"CSV file {filename} in {folder_type} folder missing required "
                            "columns 'key' and 'description'"
                        )
                        continue

                    loaded_count = 0
                    for _, row in df.iterrows():
                        key = str(row["key"]).strip()
                        description = str(row["description"]).strip()
                        if key and description and key != "nan" and description != "nan":
                            normalized = self._normalize_key(key)
                            self._entries_by_normalized_key[normalized] = (key, description)
                            loaded_count += 1

                    logging.info(
                        f"Loaded {loaded_count} lorebook entries from {folder_type} file: {filename}"
                    )
                except Exception as e:
                    logging.warning(
                        f"Could not load lorebook file '{filename}' in '{lorebook_folder}'. Error: {e}"
                    )
        except Exception as e:
            logging.warning(
                f"Could not access {folder_type} lorebook folder '{lorebook_folder}'. Error: {e}"
            )

    def _get_compiled_pattern(self, key: str) -> re.Pattern[str]:
        normalized = self._normalize_key(key)
        cached = self._compiled_patterns.get(normalized)
        if cached:
            return cached

        escaped = re.escape(key)
        pattern = re.compile(
            rf"(?<![{self._BOUNDARY_CLASS}]){escaped}(?![{self._BOUNDARY_CLASS}])",
            flags=re.IGNORECASE,
        )
        self._compiled_patterns[normalized] = pattern
        return pattern

    def get_matching_entries(self, search_texts: List[str]) -> List[Tuple[str, str]]:
        """Return matched lorebook entries sorted by key (case-insensitive)."""
        merged_text = "\n".join(t for t in search_texts if t)
        if not merged_text:
            return []

        matches: List[Tuple[str, str]] = []
        for key, description in sorted(
            self._entries_by_normalized_key.values(),
            key=lambda item: item[0].lower(),
        ):
            pattern = self._get_compiled_pattern(key)
            if pattern.search(merged_text):
                matches.append((key, description))
        return matches

    def render_lorebook_entries(self, search_texts: List[str]) -> str:
        matches = self.get_matching_entries(search_texts)
        if not matches:
            return ""
        return "\n".join(f"- [{key}]: [{description}]" for key, description in matches)

    def reload_entries(self):
        self._entries_by_normalized_key.clear()
        self._compiled_patterns.clear()
        self._load_entries()

