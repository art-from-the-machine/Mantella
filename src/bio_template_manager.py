import os
import json
import logging
import pandas as pd
from typing import Dict, List
import src.utils as utils


class BioTemplateManager:
    """Manages bio templates for tag-based dynamic bio injection"""
    
    def __init__(self, base_templates_folder: str, config_loader=None, game_name: str = "Skyrim"):
        self.base_templates_folder = base_templates_folder
        self.config_loader = config_loader
        self.game_name = game_name
        self.templates: Dict[str, str] = {}
        self._load_templates()
    
    def _load_templates(self):
        """Load bio templates from CSV files with override support"""
        # 1. Load base templates first
        self._load_templates_from_folder(self.base_templates_folder, "base")
        
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
            self._load_templates_from_folder(mod_overrides_folder, "mod override")
            
            # 3. Load personal override templates
            personal_overrides_folder = os.path.join(
                self.config_loader.save_folder, 
                "data", 
                self.game_name, 
                "bio_templates"
            )
            self._load_templates_from_folder(personal_overrides_folder, "personal override")
    
    def _load_templates_from_folder(self, templates_folder: str, folder_type: str):
        """Load bio templates from a specific folder"""
        if not os.path.exists(templates_folder):
            if folder_type == "base":
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
                        encoding = utils.get_file_encoding(filepath)
                        df = pd.read_csv(filepath, engine='python', encoding=encoding)
                        
                        # Expected columns: 'tag' and 'description'
                        if 'tag' in df.columns and 'description' in df.columns:
                            templates_loaded = 0
                            for _, row in df.iterrows():
                                tag = str(row['tag']).strip()
                                description = str(row['description']).strip()
                                if tag and description and tag != 'nan' and description != 'nan':
                                    self.templates[tag] = description
                                    templates_loaded += 1
                            logging.info(f"Loaded {templates_loaded} bio templates from {folder_type} file: {filename}")
                        else:
                            logging.warning(f"CSV file {filename} in {folder_type} folder missing required columns 'tag' and 'description'")
                    except Exception as e:
                        logging.warning(f"Could not load bio template file '{filename}' in '{templates_folder}'. Error: {e}")
        except Exception as e:
            logging.warning(f"Could not access {folder_type} bio templates folder '{templates_folder}'. Error: {e}")
    
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
    
    def get_template(self, tag: str) -> str:
        """Get bio template for a specific tag"""
        return self.templates.get(tag, f"Has the trait: {tag}.")
    
    def expand_bio_with_tags(self, base_bio: str, tags_string: str) -> str:
        """Expand base bio with tag templates"""
        if not tags_string or not tags_string.strip():
            return base_bio
        
        # Parse tags (comma-separated)
        tags = [tag.strip() for tag in tags_string.split(',') if tag.strip()]
        
        if not tags:
            return base_bio
        
        # Get templates for each tag
        tag_expansions = []
        for tag in tags:
            template = self.get_template(tag)
            tag_expansions.append(template)
        
        # Combine base bio with tag expansions, adding newlines between descriptions
        if tag_expansions:
            expanded_bio = base_bio + "\n\n" + "\n\n".join(tag_expansions)
            return expanded_bio.strip()
        
        return base_bio
    
    def reload_templates(self):
        """Reload templates from disk (useful for live updating)"""
        self.templates.clear()
        self._load_templates()
        logging.info(f"Reloaded {len(self.templates)} bio templates")
    
    def get_template_count(self) -> int:
        """Get the total number of loaded templates"""
        return len(self.templates)
    
    def list_all_tags(self) -> List[str]:
        """Get a list of all available tags"""
        return sorted(list(self.templates.keys())) 