from src.character_manager import Character

class Characters:
    """Manages a list of NPCs
    """
    def __init__(self):
        self.__active_characters: dict[str, Character] = {}
        self.__last_added_character: Character | None = None
    
    def __len__(self) -> int:
        return len(self.__active_characters)
    
    def contains_character(self, character_to_check: str | Character) -> bool:
        if isinstance(character_to_check, Character):
            return self.__active_characters.values().__contains__(character_to_check)
        else:
            return self.__active_characters.__contains__(character_to_check)
    
    @property
    def last_added_character(self) -> Character | None:
        return self.__last_added_character
    
    def active_character_count(self):
        return len(self.__active_characters)
    
    def add_character(self, new_character: Character):
        if not self.__active_characters.__contains__(new_character.name):
            self.__active_characters[new_character.name] = new_character
            self.__last_added_character = new_character

    def get_character_by_name(self, name: str) -> Character:
        return self.__active_characters[name]
        
    def get_all_characters(self) -> list[Character]:
        return list(self.__active_characters.values())
    
    def get_all_names(self) -> list[str]:
        return list(self.__active_characters.keys())