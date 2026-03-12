import os
from typing import Dict, List, Optional
import pandas as pd
import src.utils as utils

logger = utils.get_logger()


class BioTemplateManager:
    """Manages bio templates for tag-based dynamic bio injection.

    Templates are loaded with 3-tier cascading priority:
    1. Base templates (data/Skyrim/bio_templates/bio_templates.csv)
    2. Mod overrides ({mod_path}/SKSE/Plugins/MantellaSoftware/data/Skyrim/bio_templates/)
    3. Personal overrides ({save_folder}/data/Skyrim/bio_templates/) - highest priority
    """

    def __init__(self, base_templates_folder: str, mod_path_base: Optional[str] = None, save_folder: Optional[str] = None, enable_tag_reading: bool = True, game_name: str = "Skyrim"):
        self.base_templates_folder = base_templates_folder
        self.mod_path_base = mod_path_base
        self.save_folder = save_folder
        self.enable_tag_reading = enable_tag_reading
        self.game_name = game_name
        self.templates: Dict[str, str] = {}
        if self.enable_tag_reading:
            self._load_templates()

    def _load_templates(self):
        """Load bio templates from CSV files with override support."""
        # 1. Load base templates first
        self._load_templates_from_folder(self.base_templates_folder, "base")

        # 2. Load mod override templates
        if self.mod_path_base:
            extender_name = "SKSE" if self.game_name == "Skyrim" else "F4SE"

            mod_overrides_folder = os.path.join(
                self.mod_path_base,
                extender_name,
                "Plugins",
                "MantellaSoftware",
                "data",
                self.game_name,
                "bio_templates",
            )
            self._load_templates_from_folder(mod_overrides_folder, "mod override")

        # 3. Load personal override templates (highest priority)
        if self.save_folder:
            personal_overrides_folder = os.path.join(
                self.save_folder,
                "data",
                self.game_name,
                "bio_templates",
            )
            self._load_templates_from_folder(personal_overrides_folder, "personal override")

    def _load_templates_from_folder(self, templates_folder: str, folder_type: str):
        """Load bio templates from a specific folder."""
        if not os.path.exists(templates_folder):
            if folder_type != "base":
                return
            logger.warning(f"Base bio templates folder '{templates_folder}' not found. No bio templates will be loaded.")
            return

        try:
            for filename in os.listdir(templates_folder):
                if filename.endswith('.csv'):
                    filepath = os.path.join(templates_folder, filename)
                    try:
                        encoding = utils.get_file_encoding(filepath)
                        df = pd.read_csv(filepath, engine='python', encoding=encoding)

                        if 'tag' in df.columns and 'description' in df.columns:
                            templates_loaded = 0
                            for tag_raw, desc_raw in df[['tag', 'description']].values.tolist():
                                tag = utils.safe_str(tag_raw).lower()
                                description = utils.safe_str(desc_raw)
                                if tag and description:
                                    self.templates[tag] = description
                                    templates_loaded += 1
                            logger.info(f"Loaded {templates_loaded} bio templates from {folder_type} file: {filename}")
                        else:
                            logger.warning(f"CSV file {filename} in {folder_type} folder missing required columns 'tag' and 'description'")
                    except Exception as e:
                        logger.warning(f"Could not load bio template file '{filename}' in '{templates_folder}'. Error: {e}")
        except Exception as e:
            logger.warning(f"Could not access {folder_type} bio templates folder '{templates_folder}'. Error: {e}")

    def get_template(self, tag: str) -> Optional[str]:
        """Get bio template for a specific tag (case-insensitive lookup)."""
        return self.templates.get(tag.lower())

    def expand_bio_with_tags(self, base_bio: str, tags_string, tags_overwrite=None) -> str:
        """Expand base bio with tag-based template descriptions.

        Args:
            base_bio: The NPC's base biography text.
            tags_string: Comma-separated tag string (may be None, NaN, or empty).
            tags_overwrite: If non-empty, replaces tags_string.

        Returns:
            The bio with tag descriptions appended, or the original bio if no valid tags.
        """
        if not self.enable_tag_reading:
            return base_bio

        # tags_overwrite replaces tags when non-empty
        safe_overwrite = utils.safe_str(tags_overwrite)
        if safe_overwrite:
            tags_string = tags_overwrite

        safe_tags = utils.safe_str(tags_string)
        if not safe_tags:
            return base_bio

        # Parse tags (comma-separated), normalize to lowercase
        tags = [tag.strip().lower() for tag in safe_tags.split(',') if tag.strip()]

        if not tags:
            return base_bio

        # Collect descriptions for each tag
        tag_expansions = []
        for tag in tags:
            template = self.get_template(tag)
            if template and template.strip():
                tag_expansions.append(template)
            else:
                logger.warning(f"Tag '{tag}' not found in bio templates - ignoring")

        if tag_expansions:
            expanded_bio = base_bio + "\n\n" + "\n\n".join(tag_expansions)
            return expanded_bio.strip()

        return base_bio

    def get_template_count(self) -> int:
        """Get the total number of loaded templates."""
        return len(self.templates)

    def list_all_tags(self) -> List[str]:
        """Get a sorted list of all available tag names."""
        return sorted(list(self.templates.keys()))
