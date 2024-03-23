import json
import os
from typing import Hashable, Callable
from src.conversation.conversation_log import conversation_log
from src.characters_manager import Characters
from src.remember.remembering import remembering
from src.utils import get_time_group
from src.character_manager import Character
from src.config_loader import ConfigLoader

class context:
    TOKEN_LIMIT_PERCENT: float = 0.45
    """Holds the context of a conversation
    """
    def __init__(self, config: ConfigLoader, rememberer: remembering, language: dict[Hashable, str], is_prompt_too_long: Callable[[str, float], bool]) -> None:
        self.__prev_game_time: tuple[str, str] = '', ''
        self.__npcs_in_conversation: Characters = Characters()
        self.__config: ConfigLoader = config
        self.__rememberer: remembering = rememberer
        self.__language: dict[Hashable, str] = language
        self.__is_prompt_too_long: Callable[[str, float], bool] = is_prompt_too_long
        self.__location: str = "Skyrim"
        self.__ingame_time: int = 12
        self.__ingame_events: list[str] = []
        self.__have_actors_changed: bool = False

        if config.game == "Fallout4" or config.game == "Fallout4VR":
            self.__location: str = 'the Commonwealth'
        else:
            self.__location: str = "Skyrim"

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
    def Location(self) -> str:
        return self.__location
    
    @property
    def Language(self) -> dict[Hashable, str]:
        return self.__language
    
    @Location.setter
    def Location(self, value: str):
        self.__location = value

    @property
    def Ingame_time(self) -> int:
        return self.__ingame_time
    
    @Ingame_time.setter
    def Ingame_time(self, value: int):
        self.__ingame_time = value       

    @property
    def Have_actors_changed(self) -> bool:
        return self.__have_actors_changed
    
    @Have_actors_changed.setter
    def Have_actors_changed(self, value: bool):
        self.__have_actors_changed = value

    def get_context_ingame_events(self) -> list[str]:
        return self.__ingame_events
    
    def clear_context_ingame_events(self):
        self.__ingame_events.clear()

    def add_or_update_character(self, npc: Character):
        if not self.__npcs_in_conversation.contains_character(npc):
            self.__npcs_in_conversation.add_character(npc)
            self.__have_actors_changed = True
        else:
            #check for updates in the transient stats and generate update events
            self.__update_ingame_events_on_npc_change(npc)

    def get_time_group(self) -> str:
        return get_time_group(self.__ingame_time)
    
    def update_context(self, location: str, in_game_time: int, custom_ingame_events: list[str]):
        self.__ingame_events.extend(custom_ingame_events)
        if location != self.__location:
            self.__location = location
            custom_ingame_events.append(f"The location is now {location}.")
        
        self.__ingame_time = in_game_time
        currentTime: tuple[str, str] = str(in_game_time), get_time_group(in_game_time)
        if currentTime != self.__prev_game_time:
            self.__prev_game_time = currentTime
            custom_ingame_events.append(f"*The time is {currentTime[0]} {currentTime[1]}.*\n")
        self.__ingame_events.extend(custom_ingame_events)
    
    def __update_ingame_events_on_npc_change(self, npc: Character):
        current_stats: Character = self.__npcs_in_conversation.get_character_by_name(npc.Name)
        #Is in Combat
        if current_stats.Is_in_combat != npc.Is_in_combat:
            if npc.Is_in_combat:
                self.__ingame_events.append(f"{npc.Name} is now in combat!")
            else:
                self.__ingame_events.append(f"{npc.Name} is no longer in combat!")
        if not npc.Is_player_character:
            player_name = "the player"
            player = self.__npcs_in_conversation.get_player_character()
            if player:
                player_name = player.Name
            #Is attacking player
            if current_stats.Is_enemy != npc.Is_enemy:
                if npc.Is_enemy: 
                    self.__ingame_events.append(f"*{npc.Name} is attacking {player_name}. This is either because {npc.Personal_pronoun_subject} is an enemy or {player_name} has attacked {npc.Personal_pronoun_object} first.*")
                else:
                    self.__ingame_events.append(f"*{npc.Name} is no longer attacking {player_name}.*")
            #Relationship rank
            if current_stats.Relationship_rank != npc.Relationship_rank:
                trust = self.__get_trust(npc)
                self.__ingame_events.append(f"*{player_name} is now {trust} to {npc.Name}.*")
    
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
        trust_level = len(conversation_log.load_conversation_log(npc))
        trust = 'a stranger'
        if npc.Relationship_rank == 0:
            if trust_level < 1:
                trust = 'a stranger'
            elif trust_level < 10:
                trust = 'an acquaintance'
            elif trust_level < 50:
                trust = 'a friend'
            elif trust_level >= 50:
                trust = 'a close friend'
        elif npc.Relationship_rank == 4:
            trust = 'a lover'
        elif npc.Relationship_rank > 0:
            trust = 'a friend'
        elif npc.Relationship_rank < 0:
            trust = 'an enemy'
        return trust
    
    def __get_trusts(self) -> str:
        """Calculates the trust towards the player for all NPCs in the conversation

        Args:
            player_name (str, optional): _description_. Defaults to "". The name of the player, if empty string treated as if the player is not in the conversation

        Returns:
            str: A combined natural text describing their relationship towards the player, empty if there is no player 
        """
        # if player_name == "" or len(self.__npcs_in_conversation) < 1:
        #     return ""
        
        relationships = []
        for npc in self.get_characters_excluding_player().get_all_characters():
            trust = self.__get_trust(npc)
            relationships.append(f"{trust} to {npc.Name}")
        
        return context.format_listing(relationships)
       
    def __get_character_names_as_text(self, should_include_player: bool) -> str:
        """Gets the names of the NPCs in the conversation as a natural language list

        Args:
            player_name (str, optional): _description_. Defaults to "". The name of the player, if empty string, does not include the player into the list

        Returns:
            str: text containing the names of the NPC concatenated by ',' and 'and'
        """
        keys: list[str] = []
        if should_include_player:
            keys = self.npcs_in_conversation.get_all_names()
        else:
            keys = self.get_characters_excluding_player().get_all_names()
        return context.format_listing(keys)
    
    def __get_bios_text(self) -> str:
        """Gets the bios of all characters in the conversation

        Returns:
            str: the bios concatenated together into a single string
        """
        bio_descriptions = []
        for character in self.get_characters_excluding_player().get_all_characters():
            if len(self.__npcs_in_conversation) == 1:
                bio_descriptions.append(character.Bio)
            else:
                bio_descriptions.append(f"{character.Name}: {character.Bio}")
        return "\n".join(bio_descriptions)
    
    def generate_system_message(self, prompt: str) -> str:
        """Fills the variables in the prompt with the values calculated from the context

        Args:
            prompt (str): The conversation specific system prompt to fill
            include_player (bool, optional): _description_. Defaults to False.

        Returns:
            str: the filled prompt
        """
        player: Character | None = self.__npcs_in_conversation.get_player_character()
        player_name = ""
        if player:
            player_name = player.Name
        if self.npcs_in_conversation.last_added_character:
            name: str = self.npcs_in_conversation.last_added_character.Name
        names = self.__get_character_names_as_text(False)
        names_w_player = self.__get_character_names_as_text(True)
        bios = self.__get_bios_text()
        trusts = self.__get_trusts()
        location = self.__location
        time = self.__ingame_time
        time_group = get_time_group(time)
        conversation_summaries = self.__rememberer.get_prompt_text(self.get_characters_excluding_player())

        removal_content: list[tuple[str, str]] = [(bios, conversation_summaries),(bios,""),("","")]
        
        for content in removal_content:
            result = prompt.format(
                player_name = player_name,
                name=name,
                names=names,
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
            if not self.__is_prompt_too_long(result, self.TOKEN_LIMIT_PERCENT): #self.__client.calculate_tokens_from_text(result) < self.__client.token_limit * self.__token_limit_percent:
                return result
        
        return prompt #This should only trigger, if the default prompt even without bios and conversation_summaries is too long
    
    def get_characters_excluding_player(self) -> Characters:
        new_characters = Characters()
        for actor in self.__npcs_in_conversation.get_all_characters():
            if not actor.Is_player_character:
                new_characters.add_character(actor)
        return new_characters