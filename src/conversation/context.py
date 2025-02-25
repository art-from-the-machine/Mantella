import logging
from typing import Any, Hashable, List
from src.conversation.action import action
from src.http.communication_constants import communication_constants
from src.conversation.conversation_log import conversation_log
from src.characters_manager import Characters
from src.remember.remembering import remembering
from src import utils
from src.utils import get_time_group
from src.character_manager import Character
from src.config.config_loader import ConfigLoader
from src.llm.llm_client import LLMClient

class add_or_update_result:
    def __init__(self, added_npcs: List[Character], removed_npcs: List[Character]):
        self.added_npcs: List[Character]  = added_npcs
        self.removed_npcs: List[Character]  = removed_npcs

class context:
    """Holds the context of a conversation
    """
    TOKEN_LIMIT_PERCENT: float = 0.45

    @utils.time_it
    def __init__(self, world_id: str, config: ConfigLoader, client: LLMClient, rememberer: remembering, language: dict[Hashable, str]) -> None:
        self.__world_id = world_id
        self.__hourly_time = config.hourly_time
        self.__prev_game_time: tuple[str | None, str] | None = None
        self.__npcs_in_conversation: Characters = Characters()
        self.__config: ConfigLoader = config
        self.__client: LLMClient = client
        self.__rememberer: remembering = rememberer
        self.__language: dict[Hashable, str] = language
        self.__weather: str = ""
        self.__custom_context_values: dict[str, Any] = {}
        self.__ingame_time: int = 12
        self.__ingame_events: list[str] = []
        self.__vision_hints: str = ''
        self.__have_actors_changed: bool = False
        self.__game = config.game

        self.__prev_location: str | None = None
        if self.__game == "Fallout4" or self.__game == "Fallout4VR":
            self.__location: str = 'the Commonwealth'
        else:
            self.__location: str = "Skyrim"

    @property
    def world_id(self) -> str:
        return self.__world_id

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
    def have_actors_changed(self) -> bool:
        return self.__have_actors_changed
    
    @have_actors_changed.setter
    def have_actors_changed(self, value: bool):
        self.__have_actors_changed = value

    @property
    def vision_hints(self) -> dict[Hashable, str]:
        return self.__vision_hints
    
    @utils.time_it
    def set_vision_hints(self, names: str, distances: str):
        def get_category(distance):
            if distance < 150:
                return "very close"
            elif distance < 500:
                return "close"
            elif distance < 1000:
                return "medium distance"
            elif distance < 2500:
                return "far"
            else:
                return "very far"
        
        names = [x.strip('[]') for x in names.split(',')]
        distances = [float(x.strip('[]')) for x in distances.split(',')]

        pairs = sorted(zip(distances, names))
        descriptions = [f"{name} ({get_category(dist)})" for dist, name in pairs]
        self.__vision_hints = "Characters currently in view: " + ", ".join(descriptions)

    @utils.time_it
    def get_custom_context_value(self, key: str) -> Any | None:
        if self.__custom_context_values.__contains__(key):
            return self.__custom_context_values[key]
        return None

    @utils.time_it
    def get_context_ingame_events(self) -> list[str]:
        return self.__ingame_events
    
    @utils.time_it
    def clear_context_ingame_events(self):
        self.__ingame_events.clear()

    @utils.time_it
    def add_or_update_characters(self, new_list_of_npcs: list[Character]) -> add_or_update_result:
        added_npcs: List[Character] = []
        removed_npcs: List[Character] = []
        for npc in new_list_of_npcs:
            if not self.__npcs_in_conversation.contains_character(npc):
                self.__npcs_in_conversation.add_or_update_character(npc)
                #self.__ingame_events.append(f"{npc.name} has joined the conversation")
                self.__have_actors_changed = True
                added_npcs.append(npc)
            else:
                self.__update_ingame_events_on_npc_change(npc)
                self.__npcs_in_conversation.add_or_update_character(npc)
        for npc in self.__npcs_in_conversation.get_all_characters():
            if not npc in new_list_of_npcs:
                removed_npcs.append(npc)
                self.__remove_character(npc)
        return add_or_update_result(added_npcs, removed_npcs)
    
    @utils.time_it
    def remove_character(self, npc: Character):
        if self.__npcs_in_conversation.contains_character(npc):
            self.__remove_character(npc)
    
    @utils.time_it
    def __remove_character(self, npc: Character):
        self.__npcs_in_conversation.remove_character(npc)
        self.__ingame_events.append(f"{npc.name} has left the conversation.")
        self.__have_actors_changed = True

    @utils.time_it
    def get_time_group(self) -> str:
        return get_time_group(self.__ingame_time)
    
    @utils.time_it
    def update_context(self, location: str | None, in_game_time: int | None, custom_ingame_events: list[str] | None, weather: str, custom_context_values: dict[str, Any]):
        self.__custom_context_values = custom_context_values

        if location:
            if location != '':
                self.__location = location
            else:
                if self.__game == "Fallout4" or self.__game == "Fallout4VR":
                    self.__location: str = 'the Commonwealth'
                else:
                    self.__location: str = "Skyrim"
            if (self.__location != self.__prev_location) and (self.__prev_location != None):
                self.__prev_location = self.__location
                self.__ingame_events.append(f"The location is now {location}.")
        
        if in_game_time:
            self.__ingame_time = in_game_time
            in_game_time_twelve_hour = in_game_time - 12 if in_game_time > 12 else in_game_time
            if self.__hourly_time:
                current_time: tuple[str | None, str] = str(in_game_time_twelve_hour), get_time_group(in_game_time)
            else:
                current_time: tuple[str | None, str] = None, get_time_group(in_game_time)

            if (current_time != self.__prev_game_time) and (self.__prev_game_time != None):
                self.__prev_game_time = current_time
                if self.__hourly_time:
                    self.__ingame_events.append(f"The time is {current_time[0]} {current_time[1]}.")
                else:
                    self.__ingame_events.append(f"The conversation now takes place {current_time[1]}.")

        if weather != self.__weather:
            if self.__weather != "":
                self.__ingame_events.append(weather)
            self.__weather = weather

        self.__vision_hints = ''
        if self.get_custom_context_value(communication_constants.KEY_CONTEXT_CUSTOMVALUES_VISION_HINTSNAMEARRAY) and self.get_custom_context_value(communication_constants.KEY_CONTEXT_CUSTOMVALUES_VISION_HINTSDISTANCEARRAY):
            self.set_vision_hints(
                str(self.get_custom_context_value(communication_constants.KEY_CONTEXT_CUSTOMVALUES_VISION_HINTSNAMEARRAY)), 
                str(self.get_custom_context_value(communication_constants.KEY_CONTEXT_CUSTOMVALUES_VISION_HINTSDISTANCEARRAY)))
            self.__ingame_events.append(self.__vision_hints)

        if custom_ingame_events:
            self.__ingame_events.extend(custom_ingame_events)
    
    @utils.time_it
    def __update_ingame_events_on_npc_change(self, npc: Character):
        current_stats: Character = self.__npcs_in_conversation.get_character_by_name(npc.name)
        #Is in Combat
        if current_stats.is_in_combat != npc.is_in_combat:
            name = 'The player' if npc.is_player_character else npc.name
            if npc.is_in_combat:
                self.__ingame_events.append(f"{name} is now in combat!")
            else:
                self.__ingame_events.append(f"{name} is no longer in combat.")
        #update custom  values
        try:
            if (current_stats.get_custom_character_value("mantella_actor_pos_x") is not None and
                npc.get_custom_character_value("mantella_actor_pos_x") is not None and
                current_stats.get_custom_character_value("mantella_actor_pos_x") != npc.get_custom_character_value("mantella_actor_pos_x")):
                current_stats.set_custom_character_value("mantella_actor_pos_x", npc.get_custom_character_value("mantella_actor_pos_x"))

            if (current_stats.get_custom_character_value("mantella_actor_pos_y") is not None and
                npc.get_custom_character_value("mantella_actor_pos_y") is not None and
                current_stats.get_custom_character_value("mantella_actor_pos_y") != npc.get_custom_character_value("mantella_actor_pos_y")):
                current_stats.set_custom_character_value("mantella_actor_pos_y", npc.get_custom_character_value("mantella_actor_pos_y"))
        except Exception as e:
            logging.info(f"Updating custom values failed: {e}")
        if not npc.is_player_character:
            player_name = "the player"
            player = self.__npcs_in_conversation.get_player_character()
            if player:
                player_name = player.name
            #Is attacking player
            if current_stats.is_enemy != npc.is_enemy:
                if npc.is_enemy: 
                    # TODO: review if pronouns can be replaced with "they"
                    self.__ingame_events.append(f"{npc.name} is attacking {player_name}. This is either because {npc.personal_pronoun_subject} is an enemy or {player_name} has attacked {npc.personal_pronoun_object} first.")
                else:
                    self.__ingame_events.append(f"{npc.name} is no longer attacking {player_name}.")
            #Relationship rank
            if current_stats.relationship_rank != npc.relationship_rank:
                trust = self.__get_trust(npc)
                self.__ingame_events.append(f"{player_name} is now {trust} to {npc.name}.")
    
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
       
    @utils.time_it
    def __get_trust(self, npc: Character) -> str:
        """Calculates the trust of a NPC towards the player

        Args:
            npc (Character): the NPC to calculate the trust for

        Returns:
            str: a natural text representing the trust
        """
        # BUG: this measure includes radiant conversations, 
        # so "trust" is accidentally increased even when an NPC hasn't spoken with the player
        trust_level = conversation_log.get_conversation_log_length(npc, self.__world_id)
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
    
    @utils.time_it
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
            relationships.append(f"{trust} to {npc.name}")
        
        return context.format_listing(relationships)
       
    @utils.time_it
    def get_character_names_as_text(self, should_include_player: bool) -> str:
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
    
    @utils.time_it
    def __get_bios_text(self) -> str:
        """Gets the bios of all characters in the conversation

        Returns:
            str: the bios concatenated together into a single string
        """
        bio_descriptions = []
        for character in self.get_characters_excluding_player().get_all_characters():
            if len(self.__npcs_in_conversation) == 1:
                bio_descriptions.append(character.bio)
            else:
                bio_descriptions.append(f"{character.name}: {character.bio}")
        return "\n".join(bio_descriptions)
    
    @utils.time_it
    def __get_npc_equipment_text(self) -> str:
        """Gets the equipment description of all npcs in the conversation

        Returns:
            str: the equipment descriptions concatenated together into a single string
        """
        equipment_descriptions = []
        for character in self.get_characters_excluding_player().get_all_characters():
                equipment_descriptions.append(character.equipment.get_equipment_description(character.name))
        return " ".join(equipment_descriptions)
    
    @utils.time_it
    def __get_action_texts(self, actions: list[action]) -> str:
        """Generates the prompt text for the available actions

        Args:
            actions (list[action]): the list of possible actions. Already filtered for conversation type and config choices

        Returns:
            str: the text for the {actions} variable
        """
        result = ""
        for a in actions:
            result += a.prompt_text.format(key=a.keyword) + " "
        return result
    
    @utils.time_it
    def generate_system_message(self, prompt: str, actions_for_prompt: list[action]) -> str:
        """Fills the variables in the prompt with the values calculated from the context

        Args:
            prompt (str): The conversation specific system prompt to fill
            include_player (bool, optional): _description_. Defaults to False.

        Returns:
            str: the filled prompt
        """
        player: Character | None = self.__npcs_in_conversation.get_player_character()
        player_name = ""
        player_description = self.__config.player_character_description
        player_equipment = ""
        if player:
            player_name = player.name
            player_equipment = player.equipment.get_equipment_description('')
            game_sent_description = player.get_custom_character_value(communication_constants.KEY_ACTOR_PC_DESCRIPTION)
            if game_sent_description and game_sent_description != "":
                player_description = game_sent_description
        if self.npcs_in_conversation.last_added_character:
            name: str = self.npcs_in_conversation.last_added_character.name
        names = self.get_character_names_as_text(False)
        names_w_player = self.get_character_names_as_text(True)
        bios = self.__get_bios_text()
        trusts = self.__get_trusts()
        equipment = self.__get_npc_equipment_text()
        location = self.__location
        self.__prev_location = location
        weather = self.__weather
        time = self.__ingame_time - 12 if self.__ingame_time > 12 else self.__ingame_time
        time_group = get_time_group(self.__ingame_time)
        if self.__hourly_time:
            self.__prev_game_time = str(time), time_group
        else:
            self.__prev_game_time = None, time_group
        conversation_summaries = self.__rememberer.get_prompt_text(self.get_characters_excluding_player(), self.__world_id)
        actions = self.__get_action_texts(actions_for_prompt)

        removal_content: list[tuple[str, str]] = [(bios, conversation_summaries),(bios,""),("","")]
        have_bios_been_dropped = False
        have_summaries_been_dropped = False
        logging.log(23, f'Maximum size of prompt is {self.__client.token_limit} x {self.TOKEN_LIMIT_PERCENT} = {int(round(self.__client.token_limit * self.TOKEN_LIMIT_PERCENT, 0))} tokens.')
        for content in removal_content:
            result = prompt.format(
                player_name = player_name,
                player_description = player_description,
                player_equipment = player_equipment,
                name=name,
                names=names,
                names_w_player = names_w_player,
                bio=content[0],
                bios=content[0], 
                trust=trusts,
                equipment = equipment,
                location=location,
                weather = weather,
                time=time, 
                time_group=time_group, 
                language=self.__language['language'], 
                conversation_summary=content[1],
                conversation_summaries=content[1],
                actions = actions
                )
            if self.__client.is_too_long(result, self.TOKEN_LIMIT_PERCENT):
                if content[0] != "":
                    have_summaries_been_dropped = True
                else:
                    have_bios_been_dropped = True
            else:
                break
        
        logging.log(23, f'Prompt sent to LLM ({self.__client.get_count_tokens(result)} tokens): {result.strip()}')
        if have_summaries_been_dropped and have_bios_been_dropped:
            logging.log(logging.WARNING, f'Both the bios and summaries of the NPCs selected could not fit into the maximum prompt size of {int(round(self.__client.token_limit * self.TOKEN_LIMIT_PERCENT, 0))} tokens. NPCs will not remember previous conversations and will have limited knowledge of who they are.')
        elif have_summaries_been_dropped:
            logging.log(logging.WARNING, f'The summaries of the NPCs selected could not fit into the maximum prompt size of {int(round(self.__client.token_limit * self.TOKEN_LIMIT_PERCENT, 0))} tokens. NPCs will not remember previous conversations.')
        return result
    
    @utils.time_it
    def get_characters_excluding_player(self) -> Characters:
        new_characters = Characters()
        for actor in self.__npcs_in_conversation.get_all_characters():
            if not actor.is_player_character:
                new_characters.add_or_update_character(actor)
        return new_characters
    
