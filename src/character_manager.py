from typing import Any
import json
import os
import logging

from openai.types.chat import ChatCompletionMessageParam

class Character:
    def __init__(self, character_id:str, name: str, gender: int, race: str, is_player_character: bool, bio: str, is_in_combat: bool, is_enemy: bool, relationship_rank: int, is_generic_npc: bool, ingame_voice_model:str, tts_voice_model: str, custom_character_values: dict[str, Any]):
        self.__id: str = character_id
        self.__name: str = name
        self.__gender: int = gender
        self.__race: str = race
        self.__is_player_character: bool = is_player_character
        self.__bio: str = bio
        self.__is_in_combat: bool = is_in_combat
        self.__is_enemy: bool = is_enemy
        self.__relationship_rank: int = relationship_rank
        self.__is_generic_npc: bool = is_generic_npc
        self.__ingame_voice_model: str = ingame_voice_model
        self.__tts_voice_model: str = tts_voice_model
        self.__custom_character_values: dict[str, Any] = custom_character_values
        self.__conversation_history_file = f"data/conversations/{name}/{name}.json"

    @property
    def Id(self) -> str:
        return self.__id
    
    @Id.setter
    def Id(self, value: str):
        self.__id = value

    @property
    def Name(self) -> str:
        return self.__name
    
    @Name.setter
    def Name(self, value: str):
        self.__name = value

    @property
    def Gender(self) -> int:
        return self.__gender
    
    @Gender.setter
    def Gender(self, value: int):
        self.__gender = value
    
    @property
    def Personal_pronoun_subject(self) -> str:
        return ["he", "she"][self.__gender]
    
    @property
    def Personal_pronoun_object(self) -> str:
        return ["him", "her"][self.__gender]
    
    @property
    def Possesive_pronoun(self) -> str:
        return ["his", "hers"][self.__gender]

    @property
    def Race(self) -> str:
        return self.__race
    
    @Race.setter
    def Race(self, value: str):
        self.__race = value

    @property
    def Is_player_character(self) -> bool:
        return self.__is_player_character
    
    @Is_player_character.setter
    def Is_player_character(self, value: bool):
        self.__is_player_character = value

    @property
    def Bio(self) -> str:
        return self.__bio
    
    @Bio.setter
    def Bio(self, value: str):
        self.__bio = value

    @property
    def Is_in_combat(self) -> bool:
        return self.__is_in_combat
    
    @Is_in_combat.setter
    def Is_in_combat(self, value: bool):
        self.__is_in_combat = value
    
    @property
    def Is_enemy(self) -> bool:
        return self.__is_enemy
    
    @Is_enemy.setter
    def Is_enemy(self, value: bool):
        self.__is_enemy = value

    @property
    def Relationship_rank(self) -> int:
        return self.__relationship_rank
    
    @Relationship_rank.setter
    def Relationship_rank(self, value: int):
        self.__relationship_rank = value

    @property
    def Is_generic_npc(self) -> bool:
        return self.__is_generic_npc
    
    @Is_generic_npc.setter
    def Is_generic_npc(self, value: bool):
        self.__is_generic_npc = value

    @property
    def In_game_voice_model(self) -> str:
        return self.__ingame_voice_model
    
    @In_game_voice_model.setter
    def In_game_voice_model(self, value: str):
        self.__ingame_voice_model = value

    @property
    def TTS_voice_model(self) -> str:
        return self.__tts_voice_model
    
    @TTS_voice_model.setter
    def TTS_voice_model(self, value: str):
        self.__tts_voice_model = value

    @property
    def Conversation_history_file(self) -> str:
        return self.__conversation_history_file

    def get_custom_character_value(self, key: str) -> Any:
        if self.__custom_character_values.__contains__(key):
            return self.__custom_character_values[key]
        return None
    
    def set_custom_character_value(self, key: str, value: Any):
        self.__custom_character_values[key] = value

    def __eq__(self, other):
        if isinstance(self, type(other)):
            return self.Name == other.Name
        return NotImplemented
    
    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))
    
    def save_conversation_log(self, messages: list[ChatCompletionMessageParam]):
        # save conversation history
        # if this is not the first conversation
        transformed_messages = messages
        if os.path.exists(self.__conversation_history_file):
            with open(self.__conversation_history_file, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)

            # add new conversation to conversation history
            conversation_history.append(transformed_messages) # append everything except the initial system prompt
        # if this is the first conversation
        else:
            directory = os.path.dirname(self.__conversation_history_file)
            os.makedirs(directory, exist_ok=True)
            conversation_history = transformed_messages
        
        with open(self.__conversation_history_file, 'w', encoding='utf-8') as f:
            json.dump(conversation_history, f, indent=4) # save everything except the initial system prompt
    
    def load_conversation_log(self) -> list[str]:
        if os.path.exists(self.__conversation_history_file):
            with open(self.__conversation_history_file, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)
            previous_conversations = []
            for conversation in conversation_history:
                previous_conversations.extend(conversation)
            return previous_conversations
        else:
            return []