from typing import Any, Hashable
import re
from src.conversation.action import Action
from src.http.communication_constants import communication_constants
from src.conversation.conversation_log import conversation_log
from src.characters_manager import Characters
from src.remember.remembering import Remembering
from src import utils
from src.utils import get_time_group
from src.character_manager import Character, get_genders_text, get_races_text, get_genders_and_races_text
from src.config.config_loader import ConfigLoader
from src.llm.llm_client import LLMClient
from src.config.definitions.game_definitions import GameEnum

logger = utils.get_logger()


class Context:
    """Holds the context of a conversation
    """
    TOKEN_LIMIT_PERCENT: float = 0.45

    @utils.time_it
    def __init__(self, world_id: str, config: ConfigLoader, client: LLMClient, rememberer: Remembering, language: dict[Hashable, str], previous_location: str | None = None, previous_game_days: float | None = None) -> None:
        self.__world_id = world_id
        self.__hourly_time = config.hourly_time
        self.__prev_game_time: tuple[str | None, str] | None = None
        self.__npcs_in_conversation: Characters = Characters()
        self.__config: ConfigLoader = config
        self.__client: LLMClient = client
        self.__rememberer: Remembering = rememberer
        self.__language: dict[Hashable, str] = language
        self.__weather: str = ""
        self.__config_settings: dict[str, Any] = {}
        self.__custom_context_values: dict[str, Any] = {}
        self.__ingame_time: int = 12
        self.__game_days: float = 1.0  # Full game timestamp (days.fraction)
        self.__ingame_events: list[str] = []
        self.__recent_equip_items_by_actor: dict[str, list[str]] = {}
        self.__authoritative_inventory_items_by_actor: dict[str, list[str]] = {}
        self.__authoritative_inventory_actor_refs: set[str] = set()
        self.__vision_hints: str = ''
        self.__have_actors_changed: bool = False
        self.__game: GameEnum = config.game
        self.__prev_nearby_npc_names: list[str] = []  # Cache for nearby NPC names

        self.__prev_location: str | None = None
        self.__location_changed: bool = False
        self.__previous_location_for_transition = previous_location
        self.__previous_game_days_for_transition = previous_game_days
        if self.__game.base_game == GameEnum.FALLOUT4:
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
    def game_days(self) -> float:
        return self.__game_days

    @property
    def have_actors_changed(self) -> bool:
        return self.__have_actors_changed

    @property
    def location_changed(self) -> bool:
        return self.__location_changed

    def clear_location_changed(self):
        self.__location_changed = False

    def get_authoritative_current_state_event(self) -> str:
        """Return present-state location and equipment for the next LLM turn."""
        state = (
            "AUTHORITATIVE CURRENT SKYRIM STATE: The group is currently in "
            f"{self.__location}. This current location overrides older location "
            "claims in dialogue, memories, and prior scene context."
        )
        equipment = self.__get_npc_equipment_text()
        if equipment:
            state += (
                " AUTHORITATIVE CURRENT SKYRIM EQUIPMENT: "
                f"{equipment} This overrides older equipment descriptions, "
                "conversation claims, memories, and cached/static context."
            )
        return state
    
    @have_actors_changed.setter
    def have_actors_changed(self, value: bool):
        self.__have_actors_changed = value

    def get_config_setting(self, key: str) -> Any | None:
        if self.__config_settings.__contains__(key):
            return self.__config_settings[key]
        return None
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
        if self.__custom_context_values and self.__custom_context_values.__contains__(key):
            return self.__custom_context_values[key]
        return None

    @utils.time_it
    def get_context_ingame_events(self) -> list[str]:
        return self.__ingame_events
    
    @utils.time_it
    def clear_context_ingame_events(self):
        self.__ingame_events.clear()

    def get_recent_equip_items(self, actor_ref_id: str) -> tuple[str, ...]:
        """Return immediate authoritative transfer referents for one stable actor."""
        return tuple(self.__recent_equip_items_by_actor.get(str(actor_ref_id), []))

    def get_known_owned_equip_items(self, actor_ref_id: str) -> tuple[str, ...]:
        """Snapshot currently owned/equipped items known for one stable actor."""
        ref_id = str(actor_ref_id)
        items = list(self.__authoritative_inventory_items_by_actor.get(ref_id, ()))
        actor = self.__npcs_in_conversation.get_character_by_ref_id(ref_id)
        if actor:
            items.extend(actor.equipment.item_names())
        items.extend(self.__recent_equip_items_by_actor.get(ref_id, ()))
        return tuple(dict.fromkeys(item for item in items if item))

    def has_authoritative_inventory(self, actor_ref_id: str) -> bool:
        return str(actor_ref_id) in self.__authoritative_inventory_actor_refs

    def clear_recent_equip_items(self, actor_ref_id: str | None = None) -> None:
        if actor_ref_id is None:
            self.__recent_equip_items_by_actor.clear()
        else:
            self.__recent_equip_items_by_actor.pop(str(actor_ref_id), None)

    @staticmethod
    def __parse_inventory_items(raw_items: str) -> list[str]:
        value = raw_items.strip().rstrip(".")
        value = re.sub(r",?\s+and\s+", ", ", value, flags=re.IGNORECASE)
        result: list[str] = []
        for raw_item in value.split(","):
            item = re.sub(r"\s+x\d+\s*$", "", raw_item.strip(), flags=re.IGNORECASE)
            if item and item.casefold() not in {"nothing", "empty"}:
                result.append(item)
        return list(dict.fromkeys(result))

    def __unique_npc(self, display_name: str) -> Character | None:
        matches = [
            actor for actor in self.__npcs_in_conversation.get_non_player_characters()
            if actor.name.casefold() == display_name.strip().casefold()
        ]
        return matches[0] if len(matches) == 1 else None

    def remember_authoritative_item_state(self, events: list[str] | tuple[str, ...] | None) -> None:
        """Persist inventory evidence and invalidate equipment removed by newer events."""
        if not events:
            return
        for event in events:
            inventory = re.match(
                r"\s*Authoritative Skyrim inventory for (.+?) at action time:\s*(.*?)\s*$",
                event,
                re.IGNORECASE,
            )
            if inventory:
                actor = self.__unique_npc(inventory.group(1))
                if actor:
                    actor_ref_id = str(actor.ref_id)
                    self.__authoritative_inventory_items_by_actor[actor_ref_id] = self.__parse_inventory_items(inventory.group(2))
                    self.__authoritative_inventory_actor_refs.add(actor_ref_id)
                continue

            transfer = re.match(
                r"\s*(.+?)\s+(?:picked up\s*/\s*took|picked up|took)\s+(.+?)\s+from\s+(.+?)\.?\s*$",
                event,
                re.IGNORECASE,
            )
            if not transfer:
                continue
            recipient_name, item_name, source_name = (part.strip() for part in transfer.groups())
            recipient = self.__unique_npc(recipient_name)
            source = self.__unique_npc(source_name)
            if recipient:
                actor_ref_id = str(recipient.ref_id)
                recent = self.__recent_equip_items_by_actor.setdefault(actor_ref_id, [])
                if item_name not in recent:
                    recent.append(item_name)
                    logger.info("Equip transfer remembered: actor=%s item=%s", actor_ref_id, item_name)
                inventory_items = self.__authoritative_inventory_items_by_actor.setdefault(actor_ref_id, [])
                if item_name not in inventory_items:
                    inventory_items.append(item_name)
            if source:
                actor_ref_id = str(source.ref_id)
                target = item_name.casefold()
                self.__authoritative_inventory_items_by_actor[actor_ref_id] = [
                    item for item in self.__authoritative_inventory_items_by_actor.get(actor_ref_id, [])
                    if item.casefold() != target
                ]
                self.__recent_equip_items_by_actor[actor_ref_id] = [
                    item for item in self.__recent_equip_items_by_actor.get(actor_ref_id, [])
                    if item.casefold() != target
                ]
                if source.equipment.remove_item(item_name):
                    logger.info("Authoritative equipment invalidated: actor=%s item=%s", actor_ref_id, item_name)

    def remember_recent_equip_transfers(self, events: list[str] | tuple[str, ...] | None) -> None:
        """Compatibility entry point for authoritative inventory/transfer persistence."""
        self.remember_authoritative_item_state(events)

    @utils.time_it
    def add_or_update_characters(self, new_list_of_npcs: list[Character], message_count: int) -> list[Character]:
        removed_npcs = []
        for npc in new_list_of_npcs:
            if not self.__npcs_in_conversation.contains_character(npc):
                self.__npcs_in_conversation.add_or_update_character(npc, message_count)
                #self.__ingame_events.append(f"{npc.name} has joined the conversation")
                self.__have_actors_changed = True
            else:
                #check for updates in the transient stats and generate update events
                self.__update_ingame_events_on_npc_change(npc)
                self.__npcs_in_conversation.add_or_update_character(npc, message_count)
        for npc in self.__npcs_in_conversation.get_all_characters():
            if not npc in new_list_of_npcs:
                removed_npcs.append(npc)
                self.__remove_character(npc, message_count)
        return removed_npcs
    
    @utils.time_it
    def remove_character(self, npc: Character, message_count: int):
        if self.__npcs_in_conversation.contains_character(npc):
            self.__remove_character(npc, message_count)
    
    @utils.time_it
    def __remove_character(self, npc: Character, message_count: int):
        self.__npcs_in_conversation.remove_character(npc, message_count)
        self.__ingame_events.append(f"{npc.name} has left the conversation.")
        self.__have_actors_changed = True

    @utils.time_it
    def get_time_group(self) -> str:
        return get_time_group(self.__ingame_time)
    
    @utils.time_it
    def update_context(self, location: str | None, in_game_time: int | None, custom_ingame_events: list[str] | None, weather: str | None, npcs_nearby: list[dict[str, Any]] | None, custom_context_values: dict[str, Any], config_settings: dict[str, Any] | None, game_days: float | None = None):
        self.__custom_context_values = custom_context_values

        previous_game_days = self.__game_days
        # Store game_days if provided
        if game_days is not None:
            self.__game_days = game_days

        if location:
            previous_location = self.__location
            if location != '':
                if location != self.__location:
                    self.__location_changed = True
                self.__location = location
            else:
                if self.__game.base_game == GameEnum.FALLOUT4:
                    self.__location: str = 'the Commonwealth'
                else:
                    self.__location: str = "Skyrim"
            if self.__prev_location is None:
                self.__prev_location = self.__location
                if self.__locations_are_meaningfully_different(self.__previous_location_for_transition, self.__location):
                    self.__append_travel_event(self.__previous_location_for_transition, self.__location, self.__previous_game_days_for_transition, game_days)
                else:
                    self.__ingame_events.append(f"The location is now {self.__location}.")
            elif self.__location != self.__prev_location:
                if self.__locations_are_meaningfully_different(previous_location, self.__location):
                    self.__append_travel_event(previous_location, self.__location, previous_game_days, game_days)
                else:
                    self.__ingame_events.append(f"The location is now {location}.")
                self.__prev_location = self.__location
        
        if in_game_time is not None:
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

        if weather != self.__weather and weather is not None:
            if self.__weather != "":
                self.__ingame_events.append(weather)
            self.__weather = weather

        # Update nearby NPCs in the Characters manager (only when game sends new data)
        if npcs_nearby is not None:
            self.__npcs_in_conversation.set_nearby_npcs(npcs_nearby)
        
        # Add vision hints to in-game events
        self.__vision_hints = ''
        if self.get_custom_context_value(communication_constants.KEY_CONTEXT_CUSTOMVALUES_VISION_HINTSNAMEARRAY) and self.get_custom_context_value(communication_constants.KEY_CONTEXT_CUSTOMVALUES_VISION_HINTSDISTANCEARRAY):
            self.set_vision_hints(
                str(self.get_custom_context_value(communication_constants.KEY_CONTEXT_CUSTOMVALUES_VISION_HINTSNAMEARRAY)), 
                str(self.get_custom_context_value(communication_constants.KEY_CONTEXT_CUSTOMVALUES_VISION_HINTSDISTANCEARRAY)))
            self.__ingame_events.append(self.__vision_hints)
        elif npcs_nearby:
            # Sort by distance and list names (nearest to furthest)
            sorted_npcs = sorted(npcs_nearby, key=lambda x: float(x.get('distance', 0)))
            nearby_names = [npc['name'] for npc in sorted_npcs if 'name' in npc]
            # Only add event if the set of nearby NPCs has changed (not just order)
            if nearby_names and set(nearby_names) != set(self.__prev_nearby_npc_names):
                self.__vision_hints = "Characters nearby (from nearest to furthest): " + ", ".join(nearby_names)
                self.__ingame_events.append(self.__vision_hints)
                self.__prev_nearby_npc_names = nearby_names

        if custom_ingame_events:
            self.__ingame_events.extend(custom_ingame_events)
            self.remember_recent_equip_transfers(custom_ingame_events)

        if config_settings:
            self.__config_settings = config_settings

    @staticmethod
    def __location_key(location: str | None) -> str | None:
        if not location:
            return None
        key = " ".join(location.casefold().split())
        for suffix in (" interior", " exterior", " interior cell", " exterior cell"):
            if key.endswith(suffix):
                key = key[:-len(suffix)].rstrip(" -:")
        return key

    @classmethod
    def __locations_are_meaningfully_different(cls, previous: str | None, current: str | None) -> bool:
        previous_key = cls.__location_key(previous)
        current_key = cls.__location_key(current)
        return bool(previous_key and current_key and previous_key != current_key)

    def __append_travel_event(self, previous: str | None, current: str, previous_game_days: float | None, game_days: float | None):
        travel_event = (
            f"Since the previous relevant interaction, the player and accompanying characters "
            f"traveled from {previous} to {current}."
        )
        if previous_game_days is not None and game_days is not None:
            elapsed_days = game_days - previous_game_days
            if elapsed_days > 0:
                travel_event += f" Approximately {elapsed_days:.1f} in-game days passed during the journey."
        self.__ingame_events.append(travel_event)
    
    @utils.time_it
    def __update_ingame_events_on_npc_change(self, npc: Character):
        current_stats: Character = self.__npcs_in_conversation.get_character_by_ref_id(npc.ref_id)
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
            logger.error(f"Updating custom values failed: {e}")
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
        for npc in self.__npcs_in_conversation.get_non_player_characters():
            trust = self.__get_trust(npc)
            relationships.append(f"{trust} to {npc.name}")
        
        return Context.format_listing(relationships)
       
    @utils.time_it
    def get_character_names_as_text(self, include_player: bool, include_nearby: bool = False, nearby_only: bool = False) -> str:
        """Gets the names of the NPCs in the conversation as a natural language list

        Args:
            include_player (bool): If True, includes the player in the list
            include_nearby (bool): If True, includes nearby NPCs in the list
            nearby_only (bool): If True, only includes nearby NPCs (not in conversation)

        Returns:
            str: text containing the names concatenated by ',' and 'and'
        """
        names = self.__npcs_in_conversation.get_all_names_w_nearby(
            include_player=include_player,
            include_nearby=include_nearby,
            nearby_only=nearby_only
        )
        return Context.format_listing(names)
    
    @utils.time_it
    def __get_bios_text(self) -> str:
        """Gets the bios of all characters in the conversation

        Returns:
            str: the bios concatenated together into a single string
        """
        bio_descriptions = []
        for character in self.__npcs_in_conversation.get_non_player_characters():
            if len(self.__npcs_in_conversation) == 1:
                bio_descriptions.append(character.bio)
            else:
                bio_descriptions.append(f"{character.name}: {character.bio}")
        return "\n\n".join(bio_descriptions)
    
    @utils.time_it
    def __get_npc_equipment_text(self) -> str:
        """Gets authoritative live equipment for all NPCs in the conversation.

        Returns:
            str: the equipment descriptions concatenated together into a single string
        """
        equipment_descriptions = []
        for character in self.__npcs_in_conversation.get_non_player_characters():
            description = character.equipment.get_equipment_description(character.name)
            if description:
                equipment_descriptions.append(description)
            else:
                equipment_descriptions.append(f"{character.name} has no equipped armor or weapons reported by Skyrim.")
        if not equipment_descriptions:
            return ""
        return ("Authoritative shared current Skyrim equipment for every active NPC "
                "(use this for questions about any participant; it overrides contradictory "
                "dialogue, events, and memories): " + " ".join(equipment_descriptions))
    
    @utils.time_it
    def __get_action_texts(self, actions: list[Action]) -> str:
        """Generates the prompt text for the available actions

        Args:
            actions (list[Action]): the list of possible actions. Already filtered for conversation type and config choices

        Returns:
            str: the text for the {actions} variable
        """
        result = ""
        for a in actions:
            if a.prompt_text:
                result += a.prompt_text.format(key=a.keyword) + "\n"
        if result and len(self.__npcs_in_conversation.get_non_player_characters()) > 1:
            result += "Both the action prefix and NPC name need colons to be valid, e.g. 'CharacterName: Action: Lead the way.'\n"
        return result
    
    @utils.time_it
    def generate_system_message(self, prompt: str, actions_for_prompt: list[Action]) -> str:
        """Fills the variables in the prompt with the values calculated from the context

        Args:
            prompt (str): The conversation specific system prompt to fill
            actions_for_prompt (list[Action]): the list of possible actions

        Returns:
            str: the filled prompt
        """
        player: Character | None = self.__npcs_in_conversation.get_player_character()
        player_name = ""
        player_description = self.__config.player_character_description
        player_equipment = ""
        player_gender = ""
        player_race = ""
        if player:
            player_name = player.name
            player_equipment = player.equipment.get_equipment_description('')
            player_gender = player.gender
            player_race = player.race
            game_sent_description = player.get_custom_character_value(communication_constants.KEY_ACTOR_PC_DESCRIPTION)
            if game_sent_description and game_sent_description != "":
                player_description = game_sent_description
        if self.npcs_in_conversation.last_added_character:
            name: str = self.npcs_in_conversation.last_added_character.name
            gender: str = self.npcs_in_conversation.last_added_character.gender
            race: str = self.npcs_in_conversation.last_added_character.race
        else:
            name = self.get_character_names_as_text(False)
            gender = ""
            race = ""
        names = self.get_character_names_as_text(False)
        names_w_player = self.get_character_names_as_text(True)
        bios = self.__get_bios_text()
        trusts = self.__get_trusts()
        equipment = self.__get_npc_equipment_text()
        non_player_chars = self.__npcs_in_conversation.get_non_player_characters()
        genders = get_genders_text(non_player_chars)
        races = get_races_text(non_player_chars)
        genders_and_races = get_genders_and_races_text(non_player_chars)
        location = self.__location
        self.__prev_location = location
        weather = self.__weather
        time = self.__ingame_time - 12 if self.__ingame_time > 12 else self.__ingame_time
        time_group = get_time_group(self.__ingame_time)
        
        # Calculate current day number from game_days
        current_day = int(self.__game_days) if self.__game_days > 1 else 1
        
        if self.__hourly_time:
            self.__prev_game_time = str(time), time_group
        else:
            self.__prev_game_time = None, time_group
        conversation_summaries = self.__rememberer.get_prompt_text(non_player_chars, self.__world_id)
        if conversation_summaries:
            # Summaries preserve narrative continuity, but they can contain
            # obsolete dialogue about transient equipment. Make that temporal
            # boundary explicit wherever a configured prompt inserts history.
            conversation_summaries = (
                "[Historical memory only: any inventory or equipment claims below are past "
                "narrative, not evidence of what anyone is currently wearing or using. "
                "Use the authoritative current Skyrim equipment above for every present-state "
                "question.]\n" + conversation_summaries
            )
        
        # Only include legacy action prompts if advanced actions are disabled
        actions = self.__get_action_texts(actions_for_prompt) if not self.__config.advanced_actions_enabled else ""

        removal_content: list[tuple[str, str]] = [(bios, conversation_summaries),(bios,""),("","")]
        have_bios_been_dropped = False
        have_summaries_been_dropped = False
        logger.log(23, f'Maximum size of prompt is {self.__client.token_limit} x {self.TOKEN_LIMIT_PERCENT} = {int(round(self.__client.token_limit * self.TOKEN_LIMIT_PERCENT, 0))} tokens.')
        for content in removal_content:
            result = prompt.format(
                player_name = player_name,
                player_description = player_description,
                player_equipment = player_equipment,
                player_gender = player_gender,
                player_race = player_race,
                name=name,
                names=names,
                names_w_player = names_w_player,
                bio=content[0],
                bios=content[0], 
                trust=trusts,
                gender=gender,
                race=race,
                genders=genders,
                races=races,
                genders_and_races=genders_and_races,
                equipment = equipment,
                location=location,
                weather = weather,
                time=time,
                current_day=current_day,
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
        
        logger.log(23, f'Prompt sent to LLM ({self.__client.get_count_tokens(result)} tokens): {result.strip()}')
        if have_summaries_been_dropped and have_bios_been_dropped:
            logger.warning(f'Both the bios and summaries of the NPCs selected could not fit into the maximum prompt size of {int(round(self.__client.token_limit * self.TOKEN_LIMIT_PERCENT, 0))} tokens. NPCs will not remember previous conversations and will have limited knowledge of who they are.')
        elif have_summaries_been_dropped:
            logger.warning(f'The summaries of the NPCs selected could not fit into the maximum prompt size of {int(round(self.__client.token_limit * self.TOKEN_LIMIT_PERCENT, 0))} tokens. NPCs will not remember previous conversations.')
        return result
    
