import json
import os
from src.utils import get_time_group
from src.character_manager import Character
from src.config_loader import ConfigLoader


class context:
    def __init__(self, config: ConfigLoader, initial_character: Character, language: str, location: str = "Skyrim", ingame_time: int = 12) -> None:
        self.__npcs_in_conversation: set[Character] = {initial_character}
        self.__config: ConfigLoader = config
        self.__language: str = language
        self.__location: str = location
        self.__ingame_time: int = ingame_time        

    @property
    def npcs_in_conversation(self) -> set[Character]:
        return self.__npcs_in_conversation
    
    @property
    def prompt_multinpc(self) -> str:
        return self.__config.multi_npc_prompt
    
    @property
    def location(self) -> str:
        return self.__location
    
    @location.setter
    def location(self, value: str):
        self.__location = value

    @property
    def ingame_time(self) -> int:
        return self.__ingame_time
    
    @ingame_time.setter
    def ingame_time(self, value: int):
        self.__ingame_time = value

    def get_time_group(self) -> str:
        return get_time_group(self.__ingame_time)
    
    @staticmethod
    def formated_listing(listing: list[str]) -> str:
        return ', '.join(listing[:-1]) + ' and ' + listing[-1]
    
    @staticmethod
    def __get_trust(character: Character, trust_level: int) -> str:
        trust = 'a stranger'
        if character.relationship_rank == 0:
            if trust_level < 1:
                trust = 'a stranger'
            elif trust_level < 10:
                trust = 'an acquaintance'
            elif trust_level < 50:
                trust = 'a friend'
            elif trust_level >= 50:
                trust = 'a close friend'
        elif character.relationship_rank == 4:
            trust = 'a lover'
        elif character.relationship_rank > 0:
            trust = 'a friend'
        elif character.relationship_rank < 0:
            trust = 'an enemy'
        return trust
    
    def __get_trusts(self, player_name: str = "") -> str:
        if player_name == "" or len(self.__npcs_in_conversation) < 1:
            return ""
        
        relationships = []
        for character in self.__npcs_in_conversation:
            trust_level: int = 0
            if os.path.exists(character.conversation_history_file):
                with open(character.conversation_history_file, 'r', encoding='utf-8') as f:
                    conversation_history = json.load(f)
                previous_conversations = []
                for conversation in conversation_history:
                    previous_conversations.extend(conversation)
                trust_level = len(previous_conversations)
            trust = context.__get_trust(character, trust_level)
            relationships.append(f"{trust} to {character.name}")
        
        return context.formated_listing(relationships)
    
    def __get_conversation_summaries(self) -> str:
        result = ""
        for character in self.__npcs_in_conversation:
            if os.path.exists(character.conversation_history_file):
                with open(character.conversation_summary_file, 'r', encoding='utf-8') as f:
                    previous_conversation_summaries = f.read()
                    character.conversation_summary = previous_conversation_summaries
                    if len(self.__npcs_in_conversation) == 1 and len(previous_conversation_summaries) > 0:
                        result = f"Below is a summary for each of your previous conversations:\n\n{previous_conversation_summaries}"
                    elif len(self.__npcs_in_conversation) > 1 and len(previous_conversation_summaries) > 0:
                        result += f"{character.name}: {previous_conversation_summaries}"
        return result
    
    def __get_characters_text(self, player_name: str = "") -> str:
        keys = [c.name for c in self.__npcs_in_conversation]
        if len(player_name) > 0:
            keys.append(player_name)
        return context.formated_listing(keys)
    
    def __get_bios_text(self) -> str:
        bio_descriptions = []
        for character in self.__npcs_in_conversation:
            if len(self.__npcs_in_conversation) == 1:
                bio_descriptions.append(character.bio)
            else:
                bio_descriptions.append(f"{character.name}: {character.bio}")
        return "\n".join(bio_descriptions)
    
    def generate_system_message(self, prompt: str, include_player: bool = False) -> str:
        
        player_name = ""
        if include_player:
            player_name = self.__config.player_name
        names = self.__get_characters_text(player_name)
        bios = self.__get_bios_text()
        trusts = self.__get_trusts(player_name)
        location = self.__location
        time = self.__ingame_time
        time_group = get_time_group(time)
        conversation_summaries = self.__get_conversation_summaries()

        return prompt.format(
            player_name = player_name,
            name=names, 
            bio=bios, 
            trust=trusts, 
            location=location, 
            time=time, 
            time_group=time_group, 
            language=self.__language, 
            conversation_summary=conversation_summaries
            )