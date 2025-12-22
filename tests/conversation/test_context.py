from src.conversation.context import Context
from src.config.config_loader import ConfigLoader

def test_context_generates_prompt_without_actions_when_advanced_enabled(default_config: ConfigLoader, default_context: Context):
    """
    Tests that Context.generate_system_message returns empty actions placeholder when advanced actions are enabled
    """
    default_config.advanced_actions_enabled = True
    default_context._Context__config = default_config
    
    # Generate prompt with actions list
    prompt = default_context.generate_system_message(
        default_config.prompt,
        [a for a in default_config.actions if a.use_in_on_on_one]
    )
    
    # The prompt should not contain legacy action text when advanced actions are enabled
    # Check that none of the action prompts appear in the full prompt
    for action in default_config.actions:
        if action.use_in_on_on_one:
            # The keyword might still appear in character names/bios, but the full prompt text shouldn't
            assert action.prompt_text.format(key=action.keyword) not in prompt


def test_context_generates_prompt_with_actions_when_advanced_disabled(default_config: ConfigLoader, default_context: Context):
    """
    Tests that Context.generate_system_message includes actions placeholder when advanced actions are disabled
    """
    default_config.advanced_actions_enabled = False
    default_context._Context__config = default_config
    
    # Generate prompt with actions list
    prompt = default_context.generate_system_message(
        default_config.prompt,
        [a for a in default_config.actions if a.use_in_on_on_one]
    )
    
    # At least one action's prompt text should appear
    action_text_found = False
    for action in default_config.actions:
        if action.prompt_text.format(key=action.keyword) in prompt:
            action_text_found = True
            break
    
    assert action_text_found


class TestContextNearbyNPCs:
    """Tests for Context integration with nearby NPCs"""

    def test_update_context_stores_nearby_npcs(self, default_context: Context):
        """Should store nearby NPCs when provided in update_context"""
        nearby_data = [
            {"name": "Bandit", "distance": 10.5},
            {"name": "Merchant", "distance": 15.0}
        ]
        
        default_context.update_context(
            location="Whiterun",
            in_game_time=12,
            custom_ingame_events=None,
            weather=None,
            npcs_nearby=nearby_data,
            custom_context_values={},
            config_settings=None
        )
        
        # Verify nearby NPCs were stored
        names = default_context.npcs_in_conversation.get_nearby_npc_names()
        assert len(names) == 2
        assert "Bandit" in names
        assert "Merchant" in names

    def test_update_context_with_none_nearby_npcs(self, default_context: Context):
        """Should handle None gracefully"""
        default_context.update_context(
            location="Whiterun",
            in_game_time=12,
            custom_ingame_events=None,
            weather=None,
            npcs_nearby=None,
            custom_context_values={},
            config_settings=None
        )
        
        # Should result in empty list
        names = default_context.npcs_in_conversation.get_nearby_npc_names()
        assert len(names) == 0

    def test_get_character_names_as_text_conversation_only(self, example_context_with_nearby: Context):
        """Should return only conversation NPCs when include_nearby=False"""
        result = example_context_with_nearby.get_character_names_as_text(
            include_player=False,
            include_nearby=False
        )
        
        assert "Guard" in result
        assert "Bandit" not in result
        assert "Dragonborn" not in result

    def test_get_character_names_as_text_with_nearby(self, example_context_with_nearby: Context):
        """Should include nearby NPCs when include_nearby=True"""
        result = example_context_with_nearby.get_character_names_as_text(
            include_player=False,
            include_nearby=True
        )
        
        assert "Guard" in result
        assert "Bandit" in result
        assert "Merchant" in result
        assert "Dragonborn" not in result

    def test_get_character_names_as_text_nearby_only(self, example_context_with_nearby: Context):
        """Should return only nearby NPCs when nearby_only=True"""
        result = example_context_with_nearby.get_character_names_as_text(
            include_player=False,
            include_nearby=False,
            nearby_only=True
        )
        
        assert "Bandit" in result
        assert "Merchant" in result
        assert "Guard" not in result  # Conversation NPC excluded
        assert "Dragonborn" not in result

    def test_get_character_names_as_text_with_player_and_nearby(self, example_context_with_nearby: Context):
        """Should include player and nearby NPCs when both flags set"""
        result = example_context_with_nearby.get_character_names_as_text(
            include_player=True,
            include_nearby=True
        )
        
        assert "Guard" in result
        assert "Dragonborn" in result
        assert "Bandit" in result

    def test_get_character_names_as_text_empty_nearby(self, default_context: Context):
        """Should work normally when no nearby NPCs set"""
        result = default_context.get_character_names_as_text(
            include_player=True,
            include_nearby=True
        )
        
        # Should only have conversation participants
        assert "Guard" in result
        assert "Dragonborn" in result

    def test_get_character_names_as_text_formatting(self, example_context_with_nearby: Context):
        """Should format names correctly as natural language list"""
        result = example_context_with_nearby.get_character_names_as_text(
            include_player=False,
            include_nearby=True
        )
        
        # Should be comma-separated with 'and' before last item
        # Format should be something like "Guard, Bandit, and Merchant" or "Guard, Bandit and Merchant"
        assert "Guard" in result
        assert "Bandit" in result
        assert "Merchant" in result
        # Should contain commas for multiple items
        assert "," in result or " and " in result