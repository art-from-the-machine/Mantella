import pytest
from src.characters_manager import Characters
from src.character_manager import Character


class TestNearbyNPCs:
    """Test nearby NPC storage and retrieval in Characters manager"""

    def test_set_nearby_npcs_stores_data(self):
        """Should store nearby NPC data"""
        chars = Characters()
        nearby_data = [
            {"name": "Bandit", "distance": 10.5},
            {"name": "Guard", "distance": 15.2}
        ]
        
        chars.set_nearby_npcs(nearby_data)
        
        names = chars.get_nearby_npc_names()
        assert len(names) == 2
        assert "Bandit" in names
        assert "Guard" in names

    def test_set_nearby_npcs_with_none(self):
        """Should handle None gracefully (empty list)"""
        chars = Characters()
        
        chars.set_nearby_npcs(None)
        
        assert chars.get_nearby_npc_names() == []

    def test_set_nearby_npcs_replaces_previous(self):
        """Should replace previous nearby NPCs"""
        chars = Characters()
        chars.set_nearby_npcs([{"name": "OldNPC", "distance": 5.0}])
        
        chars.set_nearby_npcs([{"name": "NewNPC", "distance": 10.0}])
        
        names = chars.get_nearby_npc_names()
        assert len(names) == 1
        assert "NewNPC" in names
        assert "OldNPC" not in names

    def test_get_nearby_npc_names_empty(self):
        """Should return empty list when no nearby NPCs"""
        chars = Characters()
        
        assert chars.get_nearby_npc_names() == []


class TestGetAllNamesWithNearby:
    """Test the unified get_all_names_w_nearby method with various scopes"""

    def test_conversation_scope_excludes_player_and_nearby(self, example_skyrim_player_character: Character, example_skyrim_npc_character: Character):
        """Scope 'conversation' should return only NPCs in conversation (no player, no nearby)"""
        chars = Characters()
        chars.add_or_update_character(example_skyrim_player_character)
        chars.add_or_update_character(example_skyrim_npc_character)
        chars.set_nearby_npcs([{"name": "Bandit", "distance": 10.0}])
        
        names = chars.get_all_names_w_nearby(include_player=False, include_nearby=False)
        
        assert len(names) == 1
        assert "Guard" in names
        assert "Dragonborn" not in names
        assert "Bandit" not in names

    def test_conversation_w_player_scope(self, example_skyrim_player_character: Character, example_skyrim_npc_character: Character):
        """Scope 'conversation_w_player' should include player but not nearby"""
        chars = Characters()
        chars.add_or_update_character(example_skyrim_player_character)
        chars.add_or_update_character(example_skyrim_npc_character)
        chars.set_nearby_npcs([{"name": "Bandit", "distance": 10.0}])
        
        names = chars.get_all_names_w_nearby(include_player=True, include_nearby=False)
        
        assert len(names) == 2
        assert "Guard" in names
        assert "Dragonborn" in names
        assert "Bandit" not in names

    def test_nearby_scope(self, example_skyrim_player_character: Character, example_skyrim_npc_character: Character):
        """Scope 'nearby' should return only nearby NPCs (no conversation, no player)"""
        chars = Characters()
        chars.add_or_update_character(example_skyrim_player_character)
        chars.add_or_update_character(example_skyrim_npc_character)
        chars.set_nearby_npcs([
            {"name": "Bandit", "distance": 10.0},
            {"name": "Merchant", "distance": 8.5}
        ])
        
        names = chars.get_all_names_w_nearby(include_player=False, include_nearby=False, nearby_only=True)
        
        assert len(names) == 2
        assert "Bandit" in names
        assert "Merchant" in names
        assert "Guard" not in names
        assert "Dragonborn" not in names

    def test_all_npcs_scope(self, example_skyrim_player_character: Character, example_skyrim_npc_character: Character):
        """Scope 'all_npcs' should return conversation + nearby (no player)"""
        chars = Characters()
        chars.add_or_update_character(example_skyrim_player_character)
        chars.add_or_update_character(example_skyrim_npc_character)
        chars.set_nearby_npcs([{"name": "Bandit", "distance": 10.0}])
        
        names = chars.get_all_names_w_nearby(include_player=False, include_nearby=True)
        
        assert len(names) == 2
        assert "Guard" in names
        assert "Bandit" in names
        assert "Dragonborn" not in names

    def test_all_npcs_w_player_scope(self, example_skyrim_player_character: Character, example_skyrim_npc_character: Character):
        """Scope 'all_npcs_w_player' should return everyone"""
        chars = Characters()
        chars.add_or_update_character(example_skyrim_player_character)
        chars.add_or_update_character(example_skyrim_npc_character)
        chars.set_nearby_npcs([{"name": "Bandit", "distance": 10.0}])
        
        names = chars.get_all_names_w_nearby(include_player=True, include_nearby=True)
        
        assert len(names) == 3
        assert "Guard" in names
        assert "Dragonborn" in names
        assert "Bandit" in names

    def test_no_nearby_npcs_set(self, example_skyrim_player_character: Character, example_skyrim_npc_character: Character):
        """Should handle case where no nearby NPCs have been set"""
        chars = Characters()
        chars.add_or_update_character(example_skyrim_player_character)
        chars.add_or_update_character(example_skyrim_npc_character)
        
        names = chars.get_all_names_w_nearby(include_player=True, include_nearby=True)
        
        assert len(names) == 2
        assert "Guard" in names
        assert "Dragonborn" in names

    def test_multiple_conversation_npcs_with_nearby(self, example_skyrim_npc_character: Character, another_example_skyrim_npc_character: Character):
        """Should handle multiple conversation NPCs plus nearby NPCs"""
        chars = Characters()
        
        chars.add_or_update_character(example_skyrim_npc_character)
        chars.add_or_update_character(another_example_skyrim_npc_character)
        chars.set_nearby_npcs([
            {"name": "Bandit", "distance": 10.0},
            {"name": "Merchant", "distance": 12.0}
        ])
        
        names = chars.get_all_names_w_nearby(include_player=False, include_nearby=True)
        
        assert len(names) == 4
        assert "Guard" in names
        assert "Lydia" in names
        assert "Bandit" in names
        assert "Merchant" in names
