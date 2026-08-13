from src.conversation.context import Context
from src.config.config_loader import ConfigLoader
from src.character_manager import Character
from src.game_manager import GameStateManager
from src.llm.messages import UserMessage

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


class TestContextGenderAndRacePromptVariables:
    """Tests that Context.generate_system_message fills the gender and race prompt variables"""

    def test_player_gender_and_race(self, default_context: Context):
        """The player's gender and race should be filled with readable values (not the raw game race string)"""
        result = default_context.generate_system_message("{player_gender} {player_race}", [])
        assert result == "male Nord"

    def test_single_npc_gender_and_race(self, default_context: Context):
        """The singular variables should return bare descriptions for inline use, the plural variables full sentences"""
        result = default_context.generate_system_message("{gender}|{race}|{genders}|{races}|{genders_and_races}", [])
        assert result == "male|Imperial|Guard is a male.|Guard is an Imperial.|Guard is a male Imperial."

    def test_multi_npc_genders_and_races(self, default_context: Context, another_example_skyrim_npc_character: Character):
        """With multiple NPCs, the plural variables should return one sentence per NPC"""
        all_characters = default_context.npcs_in_conversation.get_all_characters() + [another_example_skyrim_npc_character]
        default_context.add_or_update_characters(all_characters, message_count=0)

        result = default_context.generate_system_message("{genders_and_races}", [])

        assert result == "Guard is a male Imperial. Lydia is a female Nord."

    def test_raw_race_string_does_not_leak_into_prompt(self, default_context: Context):
        result = default_context.generate_system_message("{player_race} {race} {races} {genders_and_races}", [])
        assert "[Race <" not in result

    def test_default_prompt_includes_gender_and_race(self, default_config: ConfigLoader, default_context: Context):
        """The default one-on-one prompt should introduce the NPC and the player with their gender and race"""
        result = default_context.generate_system_message(default_config.prompt, [])
        assert "You are Guard, a male Imperial, in Skyrim." in result
        assert "You are talking with Dragonborn (the player), a male Nord." in result

    def test_default_multi_npc_prompt_includes_genders_and_races(self, default_config: ConfigLoader, default_context: Context, another_example_skyrim_npc_character: Character):
        """The default multi-NPC prompt should describe the gender and race of each NPC and the player"""
        all_characters = default_context.npcs_in_conversation.get_all_characters() + [another_example_skyrim_npc_character]
        default_context.add_or_update_characters(all_characters, message_count=0)

        result = default_context.generate_system_message(default_config.multi_npc_prompt, [])

        assert "Guard is a male Imperial. Lydia is a female Nord." in result
        assert "Dragonborn (the player) is a male Nord." in result


def test_meaningful_location_transition_creates_in_world_travel_event(default_config, default_rememberer, llm_client, english_language_info):
    context = Context("1", default_config, llm_client, default_rememberer, english_language_info, previous_location="Whiterun", previous_game_days=10.0)
    context.update_context("Riften", 12, None, None, None, {}, None, game_days=10.5)
    events = context.get_context_ingame_events()
    assert any("traveled from Whiterun to Riften" in event for event in events)
    assert all("fast travel" not in event.casefold() for event in events)


def test_active_conversation_uses_authoritative_location_in_next_outgoing_messages(default_conversation):
    default_conversation.update_context("Hillgrund's Tomb", 12, None, None, None, {}, None, game_days=10.0)
    stable_system_prompt = default_conversation._Conversation__messages[0].text
    default_conversation.update_context("Whiterun", 12, None, None, None, {}, None, game_days=10.5)
    message = UserMessage(default_conversation.context.config, "Where are we now?", "Player")
    default_conversation.update_game_events(message)
    default_conversation._Conversation__messages.add_message(message)
    outgoing = default_conversation._Conversation__messages.get_openai_messages()
    assert outgoing[0]["content"] == stable_system_prompt
    assert "AUTHORITATIVE CURRENT SKYRIM STATE: The group is currently in Whiterun." in outgoing[-1]["content"]


def test_location_event_updates_messages_with_noise(default_conversation):
    default_conversation.update_context("Whiterun", 12, None, None, None, {}, None, game_days=10.0)
    stable_system_prompt = default_conversation._Conversation__messages[0].text
    events = [f"equipment event {index}" for index in range(8)] + ["The location is now Hillgrund's Tomb"]
    location = GameStateManager._GameStateManager__extract_authoritative_location(events)
    default_conversation.update_context(location, 12, events, None, None, {}, None, game_days=10.5)
    message = UserMessage(default_conversation.context.config, "Where are we now?", "Player")
    default_conversation.update_game_events(message)
    default_conversation._Conversation__messages.add_message(message)
    outgoing = default_conversation._Conversation__messages.get_openai_messages()
    assert outgoing[0]["content"] == stable_system_prompt
    assert "Hillgrund's Tomb" in outgoing[-1]["content"]
    events = [f"equipment event {index}" for index in range(8)] + ["The location is now Solitude"]
    location = GameStateManager._GameStateManager__extract_authoritative_location(events)
    default_conversation.update_context(location, 12, events, None, None, {}, None, game_days=11.0)
    message = UserMessage(default_conversation.context.config, "Where are we now?", "Player")
    default_conversation.update_game_events(message)
    default_conversation._Conversation__messages.add_message(message)
    outgoing = default_conversation._Conversation__messages.get_openai_messages()
    assert outgoing[0]["content"] == stable_system_prompt
    assert "AUTHORITATIVE CURRENT SKYRIM STATE: The group is currently in Solitude." in outgoing[-1]["content"]


def test_same_area_location_change_does_not_create_travel_event(default_config, default_rememberer, llm_client, english_language_info):
    context = Context("1", default_config, llm_client, default_rememberer, english_language_info, previous_location="Whiterun")
    context.update_context("Whiterun Interior", 12, None, None, None, {}, None)
    assert not any("traveled from" in event for event in context.get_context_ingame_events())


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
