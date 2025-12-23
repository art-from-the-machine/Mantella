from src.character_manager import Character
from src import utils
from typing import Any

class Characters:
    """Manages a list of NPCs - both full Characters in conversation and (lightweight) nearby NPCs
    """
    def __init__(self):
        self.__active_characters: dict[str, Character] = {}
        # Lightweight nearby NPC data
        self.__nearby_npcs: list[dict[str, Any]] = []
        # List of non-participant NPCs that will receive a summary of the conversation once the conversation ends
        self.__pending_shares: list[tuple[str, str, str]] = []
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
    def get_player_name(self) -> str | None:
        return self.__player_character.name if self.__player_character else None
    
    @utils.time_it
    def contains_multiple_npcs(self) -> bool:
        return self.active_character_count() > 2 or (self.active_character_count() == 2 and not self.contains_player_character())
    
    def set_nearby_npcs(self, nearby_npcs: list[dict[str, Any]] | None):
        self.__nearby_npcs = nearby_npcs if nearby_npcs else []
    
    def get_nearby_npc_names(self) -> list[str]:
        return [npc['name'] for npc in self.__nearby_npcs]
    
    @utils.time_it
    def get_all_names_w_nearby(self, include_player: bool = True, include_nearby: bool = False, nearby_only: bool = False) -> list[str]:
        """Get names based on scope requirements
        
        Args:
            include_player: Include player character in results
            include_nearby: Include nearby NPCs in addition to conversation participants
            nearby_only: Only return nearby NPCs (excludes conversation participants)
            
        Returns:
            List of NPC names matching the scope
        """
        if nearby_only:
            # Only nearby NPCs (already filtered by client to exclude conversation participants)
            return self.get_nearby_npc_names()
        else:
            # Start with conversation participants
            if include_player:
                names = self.get_all_names()
            else:
                names = [name for name, char in self.__active_characters.items() if not char.is_player_character]
            
            # Optionally add nearby NPCs
            if include_nearby:
                names.extend(self.get_nearby_npc_names())
            
            return names

    def add_pending_share(self, sharer_name: str, recipient_name: str, recipient_ref_id: str) -> bool:
        """Add an NPC to the list of non-conversation participants to receive a summary of the conversation once it ends
        
        Args:
            sharer_name: The name of the NPC who is sharing the conversation
            recipient_name: The name of the NPC who will receive the summary
            recipient_ref_id: The ref_id of the recipient NPC
        
        Returns:
            bool: True if recipient was added, False if recipient was already in the pending shares list
        """
        # Check if this recipient is already in pending shares
        for _, _, existing_ref_id in self.__pending_shares:
            if existing_ref_id == recipient_ref_id:
                return False
        
        self.__pending_shares.append((sharer_name, recipient_name, recipient_ref_id))
        return True
    
    def get_pending_shares(self) -> list[tuple[str, str, str]]:
        return self.__pending_shares.copy()
    
    def clear_pending_shares(self):
        self.__pending_shares.clear()