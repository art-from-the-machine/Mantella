from typing import Any
from src.games.equipment import Equipment

class Character:
    """Representation of a character in the game
    """
    def __init__(self, base_id: str, ref_id: str,  name: str, gender: int, race: str, is_player_character: bool, bio: str, is_in_combat: bool, is_outside_talking_range:bool, is_enemy: bool, relationship_rank: int, is_generic_npc: bool, ingame_voice_model:str, tts_voice_model: str, csv_in_game_voice_model: str, advanced_voice_model: str, voice_accent: str, equipment:Equipment, custom_character_values: dict[str, Any]):
        self.__base_id: str = base_id
        self.__ref_id: str = ref_id
        self.__name: str = name
        self.__gender: int = gender
        self.__race: str = race
        self.__is_player_character: bool = is_player_character
        self.__bio: str = bio
        self.__is_in_combat: bool = is_in_combat
        self.__is_outside_talking_range: bool = is_outside_talking_range
        self.__is_enemy: bool = is_enemy
        self.__relationship_rank: int = relationship_rank
        self.__is_generic_npc: bool = is_generic_npc
        self.__ingame_voice_model: str = ingame_voice_model
        self.__tts_voice_model: str = tts_voice_model
        self.__csv_in_game_voice_model = csv_in_game_voice_model # info['skyrim_voice_folder'] if 'skyrim' in game.lower() else info['fallout4_voice_folder']
        self.__advanced_voice_model = advanced_voice_model
        self.__voice_accent = voice_accent #info.get('voice_accent', None)
        self.__equipment = equipment
        self.__custom_character_values: dict[str, Any] = custom_character_values

    @property
    def base_id(self) -> str:
        return self.__base_id
    
    @base_id.setter
    def base_id(self, value: str):
        self.__base_id = value

    @property
    def ref_id(self) -> str:
        return self.__ref_id
    
    @ref_id.setter
    def ref_id(self, value: str):
        self.__ref_id = value

    @property
    def name(self) -> str:
        return self.__name
    
    @name.setter
    def name(self, value: str):
        self.__name = value

    @property
    def gender(self) -> int:
        return self.__gender
    
    @gender.setter
    def gender(self, value: int):
        self.__gender = value
    
    @property
    def personal_pronoun_subject(self) -> str:
        return ["he", "she"][self.__gender]
    
    @property
    def personal_pronoun_object(self) -> str:
        return ["him", "her"][self.__gender]
    
    @property
    def possesive_pronoun(self) -> str:
        return ["his", "hers"][self.__gender]

    @property
    def race(self) -> str:
        return self.__race
    
    @race.setter
    def race(self, value: str):
        self.__race = value

    @property
    def is_player_character(self) -> bool:
        return self.__is_player_character
    
    @is_player_character.setter
    def is_player_character(self, value: bool):
        self.__is_player_character = value

    @property
    def bio(self) -> str:
        return self.__bio
    
    @bio.setter
    def bio(self, value: str):
        self.__bio = value

    @property
    def is_in_combat(self) -> bool:
        return self.__is_in_combat
    
    @is_in_combat.setter
    def is_in_combat(self, value: bool):
        self.__is_in_combat = value
        
    @property
    def is_outside_talking_range(self) -> bool:
        return self.__is_outside_talking_range
    
    @is_outside_talking_range.setter
    def is_outside_talking_range(self, value: bool):
        self.__is_outside_talking_range = value
    
    @property
    def is_enemy(self) -> bool:
        return self.__is_enemy
    
    @is_enemy.setter
    def is_enemy(self, value: bool):
        self.__is_enemy = value

    @property
    def relationship_rank(self) -> int:
        return self.__relationship_rank
    
    @relationship_rank.setter
    def relationship_rank(self, value: int):
        self.__relationship_rank = value

    @property
    def is_generic_npc(self) -> bool:
        return self.__is_generic_npc
    
    @is_generic_npc.setter
    def is_generic_npc(self, value: bool):
        self.__is_generic_npc = value

    @property
    def in_game_voice_model(self) -> str:
        return self.__ingame_voice_model
    
    @in_game_voice_model.setter
    def in_game_voice_model(self, value: str):
        self.__ingame_voice_model = value

    @property
    def tts_voice_model(self) -> str:
        return self.__tts_voice_model
    
    @tts_voice_model.setter
    def tts_voice_model(self, value: str):
        self.__tts_voice_model = value

    @property
    def csv_in_game_voice_model(self) -> str:
        return self.__csv_in_game_voice_model
    
    @csv_in_game_voice_model.setter
    def csv_in_game_voice_model(self, value: str):
        self.__csv_in_game_voice_model = value

    @property
    def advanced_voice_model(self) -> str:
        return self.__advanced_voice_model
    
    @advanced_voice_model.setter
    def advanced_voice_model(self, value: str):
        self.__advanced_voice_model = value

    @property
    def voice_accent(self) -> str:
        return self.__voice_accent
    
    @voice_accent.setter
    def voice_accent(self, value: str):
        self.__voice_accent = value

    @property
    def custom_character_values(self) -> dict[str, Any]:
        return self.__custom_character_values
    
    @custom_character_values.setter
    def custom_character_values(self, value: dict[str, Any]):
        self.__custom_character_values = value
    
    @property
    def equipment(self) -> Equipment:
        return self.__equipment

    def get_custom_character_value(self, key: str) -> Any:
        if self.__custom_character_values.__contains__(key):
            return self.__custom_character_values[key]
        return None
    
    def set_custom_character_value(self, key: str, value: Any):
        self.__custom_character_values[key] = value

    def __eq__(self, other):
        if isinstance(self, type(other)):
            return self.name == other.name and self.base_id == other.base_id and self.ref_id == other.ref_id and self.race == other.race
        return NotImplemented
    
    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))
    
    