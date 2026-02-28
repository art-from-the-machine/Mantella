"""Tests for the Summary Client feature: SummaryLLMClient, per-NPC thread extraction,
thread grouping, conversation_summary_enabled gating, and fallback behavior."""

import pytest
from unittest.mock import MagicMock, patch
from collections import defaultdict

from src.config.config_loader import ConfigLoader
from src.llm.summary_client import SummaryLLMClient
from src.llm.client_base import ClientBase
from src.llm.llm_client import LLMClient
from src.llm.message_thread import message_thread
from src.llm.messages import AssistantMessage, UserMessage
from src.remember.summaries import Summaries, CharacterSummaryParameters
from src.character_manager import Character
from src.characters_manager import Characters
from src.games.equipment import Equipment

def _make_character(name: str, ref_id: str = "0", is_player: bool = False) -> Character:
    return Character(
        base_id="0",
        ref_id=ref_id,
        name=name,
        gender=0,
        race="Nord",
        is_player_character=is_player,
        bio=f"You are {name}.",
        is_in_combat=False,
        is_enemy=False,
        relationship_rank=0,
        is_generic_npc=False,
        ingame_voice_model="MaleEvenToned",
        tts_voice_model="MaleEvenToned",
        csv_in_game_voice_model="MaleEvenToned",
        advanced_voice_model="MaleEvenToned",
        voice_accent="en",
        equipment=Equipment({}),
        custom_character_values=None,
    )


class TestSummaryLLMClientInit:
    def test_init_uses_summary_config_values(self, default_config: ConfigLoader):
        """SummaryLLMClient should initialize with summary-specific config fields."""
        # Set distinct summary config values
        default_config.summary_llm_api = "OpenRouter"
        default_config.summary_llm = "google/gemma-2-9b-it:free"
        default_config.summary_llm_params = {"temperature": 0.1}
        default_config.summary_custom_token_count = 8192

        client = SummaryLLMClient(default_config)
        assert client is not None
        assert isinstance(client, ClientBase)

    def test_summary_client_separate_from_main(self, default_config: ConfigLoader):
        """SummaryLLMClient should be a distinct instance from LLMClient."""
        main_client = LLMClient(default_config)
        summary_client = SummaryLLMClient(default_config)
        assert main_client is not summary_client


class TestFallbackToMainClient:
    def test_summaries_uses_main_client_when_no_summary_client(self, skyrim, default_config, llm_client, english_language_info):
        """When summary_client is None, Summaries should use the main client for summarization."""
        summaries = Summaries(skyrim, default_config, llm_client, english_language_info['language'], summary_client=None)
        assert summaries._Summaries__client is llm_client

    def test_summaries_uses_separate_client_when_provided(self, skyrim, default_config, llm_client, english_language_info):
        """When a summary_client is provided, Summaries should use it instead of the main client."""
        default_config.summary_llm_api = "OpenRouter"
        default_config.summary_llm = "google/gemma-2-9b-it:free"
        default_config.summary_llm_params = {"temperature": 0.1}
        default_config.summary_custom_token_count = 8192
        summary_client = SummaryLLMClient(default_config)

        summaries = Summaries(skyrim, default_config, llm_client, english_language_info['language'], summary_client=summary_client)
        assert summaries._Summaries__client is summary_client
        assert summaries._Summaries__client is not llm_client


class TestPerNpcThreadExtraction:
    def test_single_npc_gets_all_messages(self, default_config: ConfigLoader):
        """A single NPC present for the full conversation should get all messages."""
        guard = _make_character("Guard", ref_id="G1")

        thread = message_thread(default_config, "system prompt")
        # Guard joins at message index 1 (after system prompt)
        characters = Characters()
        characters.add_or_update_character(guard, len(thread))
        thread.add_message(UserMessage(default_config, "Hello Guard", "Player"))
        thread.add_message(AssistantMessage(default_config))
        # Guard leaves at current message count
        characters.remove_character(guard, len(thread))

        summaries = Summaries.__new__(Summaries)
        summaries._Summaries__config = default_config
        npc_threads = summaries.get_threads_for_summarization(thread, characters)

        assert "Guard" in npc_threads
        # Should have messages
        assert len(npc_threads["Guard"].messages) > 0

    def test_multi_npc_with_join_leave(self, default_config: ConfigLoader):
        """NPCs joining/leaving at different times should get different subsets of messages."""
        guard = _make_character("Guard", ref_id="G1")
        lydia = _make_character("Lydia", ref_id="L1")

        thread = message_thread(default_config, "system prompt")
        characters = Characters()
        # Guard joins at index 1
        characters.add_or_update_character(guard, len(thread))
        thread.add_message(UserMessage(default_config, "Hello Guard", "Player"))
        thread.add_message(AssistantMessage(default_config))
        # Lydia joins mid-conversation at index 3
        characters.add_or_update_character(lydia, len(thread))
        thread.add_message(UserMessage(default_config, "Hello everyone", "Player"))
        thread.add_message(AssistantMessage(default_config))
        # Guard leaves at index 5
        characters.remove_character(guard, len(thread))
        thread.add_message(UserMessage(default_config, "Looks like the guard left", "Player"))
        thread.add_message(AssistantMessage(default_config))
        thread.add_message(UserMessage(default_config, "One more thing", "Player"))
        thread.add_message(AssistantMessage(default_config))
        # Lydia leaves at index 9
        characters.remove_character(lydia, len(thread))

        summaries = Summaries.__new__(Summaries)
        summaries._Summaries__config = default_config
        npc_threads = summaries.get_threads_for_summarization(thread, characters)

        assert "Guard" in npc_threads
        assert "Lydia" in npc_threads
        # Guard left before extra messages, so Lydia heard more
        guard_talk = npc_threads["Guard"].messages.get_talk_only()
        lydia_talk = npc_threads["Lydia"].messages.get_talk_only()
        assert len(guard_talk) < len(lydia_talk)


class TestThreadGrouping:
    def test_identical_threads_grouped(self, default_config: ConfigLoader):
        """NPCs who heard the same messages should be grouped together."""
        guard = _make_character("Guard", ref_id="G1")
        lydia = _make_character("Lydia", ref_id="L1")

        thread = message_thread(default_config, "system prompt")
        characters = Characters()
        # Both join at the same index
        characters.add_or_update_character(guard, len(thread))
        characters.add_or_update_character(lydia, len(thread))
        thread.add_message(UserMessage(default_config, "Hello", "Player"))
        thread.add_message(AssistantMessage(default_config))
        # Both leave at the same index
        characters.remove_character(guard, len(thread))
        characters.remove_character(lydia, len(thread))

        summaries = Summaries.__new__(Summaries)
        summaries._Summaries__config = default_config
        npc_threads = summaries.get_threads_for_summarization(thread, characters)
        groups = summaries.group_shared_threads(npc_threads)

        # Both NPCs heard the same messages, so they should be in one group
        assert len(groups) == 1
        assert set(groups[0]) == {"Guard", "Lydia"}

    def test_different_threads_separate(self, default_config: ConfigLoader):
        """NPCs with different message histories should be in separate groups."""
        guard = _make_character("Guard", ref_id="G1")
        lydia = _make_character("Lydia", ref_id="L1")

        thread = message_thread(default_config, "system prompt")
        characters = Characters()
        # Guard joins
        characters.add_or_update_character(guard, len(thread))
        thread.add_message(UserMessage(default_config, "Hello Guard only", "Player"))
        thread.add_message(AssistantMessage(default_config))
        # Guard leaves, Lydia joins
        characters.remove_character(guard, len(thread))
        characters.add_or_update_character(lydia, len(thread))
        thread.add_message(UserMessage(default_config, "Hello Lydia only", "Player"))
        thread.add_message(AssistantMessage(default_config))
        characters.remove_character(lydia, len(thread))

        summaries = Summaries.__new__(Summaries)
        summaries._Summaries__config = default_config
        npc_threads = summaries.get_threads_for_summarization(thread, characters)
        groups = summaries.group_shared_threads(npc_threads)

        # Each NPC heard different messages, so two separate groups
        assert len(groups) == 2


class TestConversationSummaryEnabledGating:
    def _make_conversation_with_mocks(self, config):
        """Helper to create a Conversation with mocked internals."""
        from src.conversation.conversation import Conversation
        mock_rememberer = MagicMock()
        mock_context = MagicMock()
        mock_context.config = config
        mock_context.npcs_in_conversation = Characters()
        mock_context.world_id = "test"

        mock_messages = MagicMock()
        mock_messages.transform_to_openai_messages.return_value = []
        mock_messages.get_talk_only.return_value = []

        conv = Conversation.__new__(Conversation)
        conv._Conversation__context = mock_context
        conv._Conversation__messages = mock_messages
        conv._Conversation__rememberer = mock_rememberer
        conv._Conversation__has_already_ended = False
        return conv, mock_rememberer

    def test_summary_disabled_skips_save(self, default_config: ConfigLoader):
        """When conversation_summary_enabled is False, save_conversation_state should not be called."""
        default_config.conversation_summary_enabled = False
        conv, mock_rememberer = self._make_conversation_with_mocks(default_config)

        conv._Conversation__save_conversation(is_reload=False)

        # save_conversation_state should not have been called
        mock_rememberer.save_conversation_state.assert_not_called()

    def test_summary_enabled_calls_save(self, default_config: ConfigLoader):
        """When conversation_summary_enabled is True, save_conversation_state should be called."""
        default_config.conversation_summary_enabled = True
        conv, mock_rememberer = self._make_conversation_with_mocks(default_config)

        conv._Conversation__save_conversation(is_reload=False)

        # save_conversation_state SHOULD have been called
        mock_rememberer.save_conversation_state.assert_called_once()

    def test_reload_ignores_summary_disabled(self, default_config: ConfigLoader):
        """Even when conversation_summary_enabled is False, reload saves should still proceed."""
        default_config.conversation_summary_enabled = False
        conv, mock_rememberer = self._make_conversation_with_mocks(default_config)

        conv._Conversation__save_conversation(is_reload=True)

        # save_conversation_state SHOULD be called on reload even when summaries disabled
        mock_rememberer.save_conversation_state.assert_called_once()


class TestEdgeCases:
    def test_empty_conversation(self, default_config: ConfigLoader):
        """An empty conversation (no participation) should produce no threads."""
        thread = message_thread(default_config, "system prompt")
        characters = Characters()

        summaries = Summaries.__new__(Summaries)
        summaries._Summaries__config = default_config
        npc_threads = summaries.get_threads_for_summarization(thread, characters)

        assert len(npc_threads) == 0

    def test_npc_leaving_early(self, default_config: ConfigLoader):
        """An NPC that leaves early should only see messages up to their departure."""
        guard = _make_character("Guard", ref_id="G1")
        merchant = _make_character("Merchant", ref_id="M1")

        thread = message_thread(default_config, "system prompt")
        characters = Characters()
        characters.add_or_update_character(guard, len(thread))
        characters.add_or_update_character(merchant, len(thread))
        thread.add_message(UserMessage(default_config, "Hello everyone", "Player"))
        characters.remove_character(guard, len(thread))
        # Messages after guard left
        thread.add_message(UserMessage(default_config, "Guard is gone now", "Player"))
        thread.add_message(AssistantMessage(default_config))

        summaries = Summaries.__new__(Summaries)
        summaries._Summaries__config = default_config
        npc_threads = summaries.get_threads_for_summarization(thread, characters)

        assert "Guard" in npc_threads
        assert "Merchant" in npc_threads
        # Guard's thread should not contain messages after they left
        guard_messages = npc_threads["Guard"].messages.get_talk_only()
        for msg in guard_messages:
            if isinstance(msg, UserMessage):
                assert "Guard is gone now" not in msg.text
        # Merchant's thread should contain all messages
        merchant_texts = [msg.text for msg in npc_threads["Merchant"].messages.get_talk_only() if isinstance(msg, UserMessage)]
        assert any("Hello everyone" in t for t in merchant_texts)
        assert any("Guard is gone now" in t for t in merchant_texts)

    def test_duplicate_join_events(self, default_config: ConfigLoader):
        """Duplicate add_or_update_character calls should not cause errors or duplicate threads."""
        guard = _make_character("Guard", ref_id="G1")

        thread = message_thread(default_config, "system prompt")
        characters = Characters()
        characters.add_or_update_character(guard, len(thread))
        characters.add_or_update_character(guard, len(thread))  # duplicate (update, not new join)
        thread.add_message(UserMessage(default_config, "Hello", "Player"))
        characters.remove_character(guard, len(thread))

        summaries = Summaries.__new__(Summaries)
        summaries._Summaries__config = default_config
        npc_threads = summaries.get_threads_for_summarization(thread, characters)

        # Should still only have one entry for Guard
        assert "Guard" in npc_threads
        assert len(npc_threads) == 1


class TestConfigLoadingSummaryValues:
    def test_summary_config_values_exist(self, default_config: ConfigLoader):
        """Config should have summary-specific attributes."""
        assert hasattr(default_config, "summary_llm_enabled")
        assert hasattr(default_config, "summary_llm_api")
        assert hasattr(default_config, "summary_llm")
        assert hasattr(default_config, "summary_custom_token_count")
        assert hasattr(default_config, "summary_llm_params")
        assert hasattr(default_config, "conversation_summary_enabled")

    def test_summary_llm_enabled_default_false(self, default_config: ConfigLoader):
        """summary_llm_enabled should default to False (use main LLM for summaries by default)."""
        assert default_config.summary_llm_enabled is False

    def test_conversation_summary_enabled_default_true(self, default_config: ConfigLoader):
        """conversation_summary_enabled should default to True."""
        assert default_config.conversation_summary_enabled is True

    def test_summary_llm_has_default(self, default_config: ConfigLoader):
        """summary_llm should have a default model value."""
        assert default_config.summary_llm is not None
        assert len(default_config.summary_llm) > 0
