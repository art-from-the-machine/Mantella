from src.character_manager import Character
from src import utils

class Characters:
    """Manages a list of NPCs
    """
    def __init__(self):
        self.__active_characters: dict[str, Character] = {}
        self.__all_characters: dict[str, Character] = {} # Actives characters + those that were removed
        self.__last_added_character: Character | None = None
        self.__player_character: Character | None = None
    
    def __len__(self) -> int:
        return len(self.__active_characters)
    
    @utils.time_it
    def contains_character(self, character_to_check: str | Character) -> bool:
        if isinstance(character_to_check, Character):
            return self.__active_characters.__contains__(character_to_check.name)
        else:
            return self.__active_characters.__contains__(character_to_check)
    
    @property
    def last_added_character(self) -> Character | None:
        return self.__last_added_character
    
    def active_character_count(self):
        return len(self.__active_characters)
    
    @utils.time_it
    def add_or_update_character(self, new_character: Character):
        if not self.__active_characters.__contains__(new_character.name): #Is add
            self.__active_characters[new_character.name] = new_character   
            self.__all_characters[new_character.name] = new_character
            if new_character.is_player_character:
                self.__player_character = new_character
            else:
                self.__last_added_character = new_character
        else: #Is update: update transient stats + custom values
            self.__active_characters[new_character.name].is_enemy = new_character.is_enemy
            self.__active_characters[new_character.name].is_in_combat = new_character.is_in_combat
            self.__active_characters[new_character.name].relationship_rank = new_character.relationship_rank
            self.__active_characters[new_character.name].custom_character_values = new_character.custom_character_values
    
    @utils.time_it
    def remove_character(self, character_to_remove: Character):
        if self.__active_characters.__contains__(character_to_remove.name):
            del self.__active_characters[character_to_remove.name]
            if character_to_remove.is_player_character:
                self.__player_character = None
            if character_to_remove == self.__last_added_character:
                for (name, character) in self.__active_characters.items():
                    if not character.is_player_character:
                        self.__last_added_character = character
    
    @utils.time_it
    def get_character_by_name(self, name: str) -> Character:
        return self.__active_characters[name]
        
    @utils.time_it
    def get_all_characters(self) -> list[Character]:
        return list(self.__active_characters.values())
    
    @utils.time_it
    def get_all_names(self) -> list[str]:
        return list(self.__active_characters.keys())
    
    @utils.time_it
    def contains_player_character(self) -> bool:
        return self.__player_character != None
    
    @utils.time_it
    def get_player_character(self) -> Character | None:
        return self.__player_character
    
    @utils.time_it
    def contains_multiple_npcs(self) -> bool:
        return self.active_character_count() > 2 or (self.active_character_count() == 2 and not self.contains_player_character())