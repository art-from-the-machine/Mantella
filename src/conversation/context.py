import json
import os
from typing import Hashable
from src.llm.openai_client import openai_client
from src.characters_manager import Characters
from src.remember.remembering import remembering
from src.utils import get_time_group
from src.character_manager import Character
from src.config_loader import ConfigLoader

class context:
    """Holds the context of a conversation
    """
    def __init__(self, config: ConfigLoader, rememberer: remembering, language: dict[Hashable, str], client: openai_client, token_limit_percent: float = 0.45) -> None:
        self.__npcs_in_conversation: Characters = Characters()
        self.__config: ConfigLoader = config
        self.__rememberer: remembering = rememberer
        self.__language: dict[Hashable, str] = language
        self.__client: openai_client = client #Just passed in for the moment to measure the length of the system message, maybe better solution in the future?
        self.__location: str = "Skyrim"
        self.__ingame_time: int = 12
        self.__token_limit_percent = token_limit_percent
        self.__should_switch_to_multi_npc_conversation: bool = False

    @property
    def npcs_in_conversation(self) -> Characters:
        return self.__npcs_in_conversation
    
    @property
    def config(self) -> ConfigLoader:
        return self.__config

    @property
    def prompt_multinpc(self) -> str:
        return self.__config.multi_npc_prompt
    
    @property
    def location(self) -> str:
        return self.__location
    
    @property
    def language(self) -> dict[Hashable, str]:
        return self.__language
    
    @location.setter
    def location(self, value: str):
        self.__location = value

    @property
    def ingame_time(self) -> int:
        return self.__ingame_time
    
    @ingame_time.setter
    def ingame_time(self, value: int):
        self.__ingame_time = value

    @property
    def should_switch_to_multi_npc_conversation(self) -> bool:
        return self.__should_switch_to_multi_npc_conversation
    
    @should_switch_to_multi_npc_conversation.setter
    def should_switch_to_multi_npc_conversation(self, value: bool):
        self.__should_switch_to_multi_npc_conversation = value

    def add_character(self, new_character: Character):
        self.__npcs_in_conversation.add_character(new_character)

    def get_time_group(self) -> str:
        return get_time_group(self.__ingame_time)
    
    @staticmethod
    def format_listing(listing: list[str]) -> str:
        """Returns a list of string concatenated by ',' and 'and' to be used in a text

        Args:
            listing (list[str]): the list of strings

        Returns:
            str: A natural language listing. Returns an empty string if listing is empty, returns the the string if length of listing is 1
        """
        if len(listing) == 0:
            return ""
        elif len(listing) == 1:
            return listing[0]
        else:
            return ', '.join(listing[:-1]) + ' and ' + listing[-1]
       
    def __get_trust(self, npc: Character) -> str:
        """Calculates the trust of a NPC towards the player

        Args:
            npc (Character): the NPC to calculate the trust for

        Returns:
            str: a natural text representing the trust
        """
        trust_level = len(npc.load_conversation_log())
        trust = 'a stranger'
        if npc.relationship_rank == 0:
            if trust_level < 1:
                trust = 'a stranger'
            elif trust_level < 10:
                trust = 'an acquaintance'
            elif trust_level < 50:
                trust = 'a friend'
            elif trust_level >= 50:
                trust = 'a close friend'
        elif npc.relationship_rank == 4:
            trust = 'a lover'
        elif npc.relationship_rank > 0:
            trust = 'a friend'
        elif npc.relationship_rank < 0:
            trust = 'an enemy'
        return trust
    
    def __get_trusts(self, player_name: str = "") -> str:
        """Calculates the trust towards the player for all NPCs in the conversation

        Args:
            player_name (str, optional): _description_. Defaults to "". The name of the player, if empty string treated as if the player is not in the conversation

        Returns:
            str: A combined natural text describing their relationship towards the player, empty if there is no player 
        """
        if player_name == "" or len(self.__npcs_in_conversation) < 1:
            return ""
        
        relationships = []
        for npc in self.__npcs_in_conversation.get_all_characters():
            trust = self.__get_trust(npc)
            relationships.append(f"{trust} to {npc.name}")
        
        return context.format_listing(relationships)
       
    def __get_characters_text(self, player_name: str = "") -> str:
        """Gets the names of the NPCs in the conversation as a natural language list

        Args:
            player_name (str, optional): _description_. Defaults to "". The name of the player, if empty string, does not include the player into the list

        Returns:
            str: text containing the names of the NPC concatenated by ',' and 'and'
        """
        keys = self.__npcs_in_conversation.get_all_names()
        if len(player_name) > 0:
            keys.append(player_name)
        return context.format_listing(keys)
    
    def __get_bios_text(self) -> str:
        """Gets the bios of all characters in the conversation

        Returns:
            str: the bios concatenated together into a single string
        """
        bio_descriptions = []
        for character in self.__npcs_in_conversation.get_all_characters():
            if len(self.__npcs_in_conversation) == 1:
                bio_descriptions.append(character.bio)
            else:
                bio_descriptions.append(f"{character.name}: {character.bio}")
        return "\n".join(bio_descriptions)
    
    def generate_system_message(self, prompt: str, include_player: bool = False, include_conversation_summaries: bool = True, include_bios: bool = True) -> str:
        """Fills the variables in the prompt with the values calculated from the context

        Args:
            prompt (str): The conversation specific system prompt to fill
            include_player (bool, optional): _description_. Defaults to False.

        Returns:
            str: the filled prompt
        """
        player_name = ""
        if include_player:
            player_name = self.__config.player_name
        name = self.__get_characters_text()
        names_w_player = self.__get_characters_text(player_name)
        if include_bios:            
            bios = self.__get_bios_text()
        else:
            bios = "" 
        trusts = self.__get_trusts(player_name)
        location = self.__location
        time = self.__ingame_time
        time_group = get_time_group(time)
        if include_conversation_summaries:
            conversation_summaries = self.__rememberer.get_prompt_text(self.__npcs_in_conversation)
        else:
            conversation_summaries = ""

        removal_content: list[tuple[str, str]] = [(bios, conversation_summaries),(bios,""),("","")]
        
        for content in removal_content:
            result = prompt.format(
                player_name = player_name,
                name=name,
                names=name,
                names_w_player = names_w_player,
                bio=content[0],
                bios=content[0], 
                trust=trusts, 
                location=location, 
                time=time, 
                time_group=time_group, 
                language=self.__language['language'], 
                conversation_summary=content[1],
                conversation_summaries=content[1]
                )
            if self.__client.calculate_tokens_from_text(result) < self.__client.token_limit * self.__token_limit_percent:
                return result
        
        return prompt #This should only trigger, if the default prompt even without bios and conversation_summaries is too long