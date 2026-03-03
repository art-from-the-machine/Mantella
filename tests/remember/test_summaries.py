import pytest
import os
import logging
from unittest.mock import patch
from src.config.config_loader import ConfigLoader
from src.config.definitions.game_definitions import GameEnum
from src.conversation.context import Context
from src.conversation.conversation import Conversation
from src.games.skyrim import Skyrim
from src.llm.llm_client import LLMClient
from src.llm.message_thread import message_thread
from src.llm.messages import AssistantMessage, UserMessage
from src.remember.summaries import Summaries
from src.character_manager import Character
from src.characters_manager import Characters


def _build_enough_messages(thread: message_thread, config: ConfigLoader, count: int = 3):
    """Add enough user+assistant message pairs to exceed the 5-message summarization threshold."""
    for i in range(count):
        thread.add_message(UserMessage(config, f"Message {i}", "Player"))
        thread.add_message(AssistantMessage(config))


class TestPerNpcThreadExtraction:
    def test_single_npc_gets_all_messages(self, default_config: ConfigLoader, default_rememberer: Summaries, example_skyrim_npc_character: Character):
        """A single NPC present for the full conversation should get all messages."""
        thread = message_thread(default_config, "system prompt")
        characters = Characters()
        characters.add_or_update_character(example_skyrim_npc_character, len(thread))
        thread.add_message(UserMessage(default_config, "Hello Guard", "Player"))
        thread.add_message(AssistantMessage(default_config))
        characters.remove_character(example_skyrim_npc_character, len(thread))

        npc_threads = default_rememberer.get_threads_for_summarization(thread, characters)

        assert "Guard" in npc_threads
        assert len(npc_threads["Guard"].messages) > 0

    def test_multi_npc_with_join_leave(self, default_config: ConfigLoader, default_rememberer: Summaries, example_skyrim_npc_character: Character, another_example_skyrim_npc_character: Character):
        """NPCs joining/leaving at different times should get different subsets of messages."""
        guard = example_skyrim_npc_character
        lydia = another_example_skyrim_npc_character

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

        npc_threads = default_rememberer.get_threads_for_summarization(thread, characters)

        assert "Guard" in npc_threads
        assert "Lydia" in npc_threads
        # Guard left before extra messages, so Lydia heard more
        guard_talk = npc_threads["Guard"].messages.get_talk_only()
        lydia_talk = npc_threads["Lydia"].messages.get_talk_only()
        assert len(guard_talk) < len(lydia_talk)


    def test_npc_rejoin_only_gets_latest_interval(self, default_config: ConfigLoader, default_rememberer: Summaries, example_skyrim_npc_character: Character, another_example_skyrim_npc_character: Character):
        """An NPC who leaves and later rejoins should only get messages from the latest interval."""
        guard = example_skyrim_npc_character
        lydia = another_example_skyrim_npc_character

        thread = message_thread(default_config, "system prompt")
        characters = Characters()
        # Guard and Lydia both join
        characters.add_or_update_character(guard, len(thread))
        characters.add_or_update_character(lydia, len(thread))
        thread.add_message(UserMessage(default_config, "Hello everyone", "Player"))
        thread.add_message(AssistantMessage(default_config))
        # Guard leaves
        characters.remove_character(guard, len(thread))
        thread.add_message(UserMessage(default_config, "Guard is away", "Player"))
        thread.add_message(AssistantMessage(default_config))
        # Guard rejoins
        characters.add_or_update_character(guard, len(thread))
        thread.add_message(UserMessage(default_config, "Welcome back Guard", "Player"))
        thread.add_message(AssistantMessage(default_config))
        # Both leave
        characters.remove_character(guard, len(thread))
        characters.remove_character(lydia, len(thread))

        npc_threads = default_rememberer.get_threads_for_summarization(thread, characters)

        assert "Guard" in npc_threads
        guard_texts = [msg.text for msg in npc_threads["Guard"].messages.get_talk_only() if isinstance(msg, UserMessage)]
        # Guard should only have messages from the latest interval (after rejoin)
        assert any("Welcome back Guard" in t for t in guard_texts)
        # Messages from the first interval should not be included (already summarized on first departure)
        assert not any("Hello everyone" in t for t in guard_texts)
        # Messages from the gap should not be included either
        assert not any("Guard is away" in t for t in guard_texts)


class TestThreadGrouping:
    def test_identical_threads_grouped(self, default_config: ConfigLoader, default_rememberer: Summaries, example_skyrim_npc_character: Character, another_example_skyrim_npc_character: Character):
        """NPCs who heard the same messages should be grouped together."""
        guard = example_skyrim_npc_character
        lydia = another_example_skyrim_npc_character

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

        npc_threads = default_rememberer.get_threads_for_summarization(thread, characters)
        groups = default_rememberer.group_shared_threads(npc_threads)

        # Both NPCs heard the same messages, so they should be in one group
        assert len(groups) == 1
        assert set(groups[0]) == {"Guard", "Lydia"}

    def test_different_threads_separate(self, default_config: ConfigLoader, default_rememberer: Summaries, example_skyrim_npc_character: Character, another_example_skyrim_npc_character: Character):
        """NPCs with different message histories should be in separate groups."""
        guard = example_skyrim_npc_character
        lydia = another_example_skyrim_npc_character

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

        npc_threads = default_rememberer.get_threads_for_summarization(thread, characters)
        groups = default_rememberer.group_shared_threads(npc_threads)

        # Each NPC heard different messages, so two separate groups
        assert len(groups) == 2


class TestConversationSummaryEnabledGating:
    """Tests that __save_conversation respects the conversation_summary_enabled config flag.

    Uses the real default_conversation fixture and asserts on log output to verify
    whether the summary path was taken or skipped.
    """
    SUMMARY_DISABLED_LOG = "Conversation summaries disabled"
    SUMMARY_ATTEMPTED_LOG = "Not enough dialogue spoken"

    def test_summary_disabled_skips_save(self, default_conversation: Conversation, default_config: ConfigLoader, caplog):
        """When conversation_summary_enabled is False, save_conversation_state should not be called."""
        default_config.conversation_summary_enabled = False

        with caplog.at_level(logging.INFO, logger="Mantella"):
            default_conversation._Conversation__save_conversation(is_reload=False)

        assert any(self.SUMMARY_DISABLED_LOG in m for m in caplog.messages)
        assert not any(self.SUMMARY_ATTEMPTED_LOG in m for m in caplog.messages)

    def test_summary_enabled_calls_save(self, default_conversation: Conversation, default_config: ConfigLoader, caplog):
        """When conversation_summary_enabled is True, save_conversation_state should be called."""
        default_config.conversation_summary_enabled = True

        with caplog.at_level(logging.INFO, logger="Mantella"):
            default_conversation._Conversation__save_conversation(is_reload=False)

        assert not any(self.SUMMARY_DISABLED_LOG in m for m in caplog.messages)
        assert any(self.SUMMARY_ATTEMPTED_LOG in m for m in caplog.messages)

    def test_reload_ignores_summary_disabled(self, default_conversation: Conversation, default_config: ConfigLoader, caplog):
        """Even when conversation_summary_enabled is False, reload saves should still proceed."""
        default_config.conversation_summary_enabled = False

        with caplog.at_level(logging.INFO, logger="Mantella"):
            default_conversation._Conversation__save_conversation(is_reload=True)

        assert not any(self.SUMMARY_DISABLED_LOG in m for m in caplog.messages)
        assert any(self.SUMMARY_ATTEMPTED_LOG in m for m in caplog.messages)


class TestEdgeCases:
    def test_empty_conversation(self, default_config: ConfigLoader, default_rememberer: Summaries):
        """An empty conversation (no participation) should produce no threads."""
        thread = message_thread(default_config, "system prompt")
        characters = Characters()

        npc_threads = default_rememberer.get_threads_for_summarization(thread, characters)

        assert len(npc_threads) == 0

    def test_npc_leaving_early(self, default_config: ConfigLoader, default_rememberer: Summaries, example_skyrim_npc_character: Character, another_example_skyrim_npc_character: Character):
        """An NPC that leaves early should only see messages up to their departure."""
        guard = example_skyrim_npc_character
        lydia = another_example_skyrim_npc_character

        thread = message_thread(default_config, "system prompt")
        characters = Characters()
        characters.add_or_update_character(guard, len(thread))
        characters.add_or_update_character(lydia, len(thread))
        thread.add_message(UserMessage(default_config, "Hello everyone", "Player"))
        characters.remove_character(guard, len(thread))
        # Messages after guard left
        thread.add_message(UserMessage(default_config, "Guard is gone now", "Player"))
        thread.add_message(AssistantMessage(default_config))

        npc_threads = default_rememberer.get_threads_for_summarization(thread, characters)

        assert "Guard" in npc_threads
        assert "Lydia" in npc_threads
        # Guard's thread should not contain messages after they left
        guard_messages = npc_threads["Guard"].messages.get_talk_only()
        for msg in guard_messages:
            if isinstance(msg, UserMessage):
                assert "Guard is gone now" not in msg.text
        # Lydia's thread should contain all messages
        lydia_texts = [msg.text for msg in npc_threads["Lydia"].messages.get_talk_only() if isinstance(msg, UserMessage)]
        assert any("Hello everyone" in t for t in lydia_texts)
        assert any("Guard is gone now" in t for t in lydia_texts)

    def test_duplicate_join_events(self, default_config: ConfigLoader, default_rememberer: Summaries, example_skyrim_npc_character: Character):
        """Duplicate add_or_update_character calls should not cause errors or duplicate threads."""
        guard = example_skyrim_npc_character

        thread = message_thread(default_config, "system prompt")
        characters = Characters()
        characters.add_or_update_character(guard, len(thread))
        characters.add_or_update_character(guard, len(thread)) # duplicate update (not new join)
        thread.add_message(UserMessage(default_config, "Hello", "Player"))
        characters.remove_character(guard, len(thread))

        npc_threads = default_rememberer.get_threads_for_summarization(thread, characters)

        assert "Guard" in npc_threads
        assert len(npc_threads) == 1


class TestSummarizationHappensOncePerNPC:
    """Tests that an NPC who leaves mid-conversation is only summarized once."""

    def test_departed_npc_not_re_summarized_at_conversation_end(
        self, default_config: ConfigLoader, llm_client: LLMClient,
        default_rememberer: Summaries, english_language_info: dict,
        example_skyrim_player_character: Character,
        example_skyrim_npc_character: Character, another_example_skyrim_npc_character: Character
    ):
        """An NPC summarized on departure (reload save) should not be summarized again at conversation end."""
        player = example_skyrim_player_character
        guard = example_skyrim_npc_character
        lydia = another_example_skyrim_npc_character
        world_id = "TestWorld"

        # Set up context with all three characters (player + guard + lydia)
        context = Context(world_id, default_config, llm_client, default_rememberer, english_language_info)
        context.add_or_update_characters([player, guard, lydia], message_count=0)

        thread = message_thread(default_config, "system prompt")
        _build_enough_messages(thread, default_config)

        # Game sends updated actor list without the guard (guard departs)
        context.add_or_update_characters([player, lydia], message_count=len(thread))
        npcs = context.npcs_in_conversation

        # Reload save (triggered by character departure)
        with patch.object(default_rememberer, 'summarize_conversation', return_value="Guard departure summary.\n\n"):
            default_rememberer.save_conversation_state(thread, [guard], npcs, world_id, is_reload=True)

        # Conversation continues with just Lydia
        _build_enough_messages(thread, default_config)

        # Final save (triggered at conversation end)
        with patch.object(default_rememberer, 'summarize_conversation', return_value="Final summary.\n\n") as mock_summarize:
            default_rememberer.save_conversation_state(thread, [lydia], npcs, world_id, is_reload=False)

            # The guard was already summarized in the reload save.
            # The final save should only produce one summarization call (for Lydia).
            # Before the fix, two calls were made (Guard + Lydia in separate groups).
            assert mock_summarize.call_count == 1, (
                f"Expected 1 summarize call (Lydia only), but got {mock_summarize.call_count}"
            )

    def test_departed_npc_summary_written_to_disk_once(
        self, skyrim: Skyrim, default_config: ConfigLoader, llm_client: LLMClient,
        default_rememberer: Summaries, english_language_info: dict,
        example_skyrim_player_character: Character,
        example_skyrim_npc_character: Character, another_example_skyrim_npc_character: Character
    ):
        """The departed NPC's summary file should contain exactly one entry after both saves."""
        player = example_skyrim_player_character
        guard = example_skyrim_npc_character
        lydia = another_example_skyrim_npc_character
        world_id = "TestWorld"

        context = Context(world_id, default_config, llm_client, default_rememberer, english_language_info)
        context.add_or_update_characters([player, guard, lydia], message_count=0)

        thread = message_thread(default_config, "system prompt")
        _build_enough_messages(thread, default_config)

        # Guard departs via updated actor list
        context.add_or_update_characters([player, lydia], message_count=len(thread))
        npcs = context.npcs_in_conversation

        # Reload save (guard gets summarized here)
        with patch.object(default_rememberer, 'summarize_conversation', return_value="Guard was at the sawmill.\n\n"):
            default_rememberer.save_conversation_state(thread, [guard], npcs, world_id, is_reload=True)

        # Conversation continues
        _build_enough_messages(thread, default_config)

        # Final save at conversation end
        with patch.object(default_rememberer, 'summarize_conversation', return_value="Lydia continued talking.\n\n"):
            default_rememberer.save_conversation_state(thread, [lydia], npcs, world_id, is_reload=False)

        # Guard's summary file should have exactly one entry (from the reload save)
        guard_folder = os.path.join(skyrim.conversation_folder_path, world_id, f"Guard - {guard.ref_id}")
        guard_summary_file = os.path.join(guard_folder, "Guard_summary_1.txt")
        assert os.path.exists(guard_summary_file)
        with open(guard_summary_file, 'r', encoding='utf-8') as f:
            content = f.read()

        entries = [e.strip() for e in content.strip().split('\n\n') if e.strip()]
        assert len(entries) == 1


class TestSummaryLocationByGame:
    """Tests that __create_new_conversation_summary uses the correct location string per game."""

    def test_fallout4_uses_commonwealth_location(
        self, default_config: ConfigLoader, llm_client: LLMClient,
        default_rememberer: Summaries, english_language_info: dict,
        example_skyrim_player_character: Character,
        example_skyrim_npc_character: Character
    ):
        """When the game is Fallout4, the summary prompt should reference 'the Commonwealth' instead of 'Skyrim'."""
        player = example_skyrim_player_character
        guard = example_skyrim_npc_character
        world_id = "TestWorld"

        default_config.game = GameEnum.FALLOUT4

        context = Context(world_id, default_config, llm_client, default_rememberer, english_language_info)
        context.add_or_update_characters([player, guard], message_count=0)

        thread = message_thread(default_config, "system prompt")
        _build_enough_messages(thread, default_config)

        # Guard departs via updated actor list
        context.add_or_update_characters([player], message_count=len(thread))
        npcs = context.npcs_in_conversation

        with patch.object(default_rememberer, 'summarize_conversation', return_value="Summary.\n\n") as mock_summarize:
            default_rememberer.save_conversation_state(thread, [guard], npcs, world_id, is_reload=False)

            assert mock_summarize.call_count == 1
            prompt_arg = mock_summarize.call_args[0][1]
            assert "the Commonwealth" in prompt_arg
            assert "Skyrim" not in prompt_arg

    def test_skyrim_uses_skyrim_location(
        self, default_config: ConfigLoader, llm_client: LLMClient,
        default_rememberer: Summaries, english_language_info: dict,
        example_skyrim_player_character: Character,
        example_skyrim_npc_character: Character
    ):
        """When the game is Skyrim, the summary prompt should reference 'Skyrim'."""
        player = example_skyrim_player_character
        guard = example_skyrim_npc_character
        world_id = "TestWorld"

        context = Context(world_id, default_config, llm_client, default_rememberer, english_language_info)
        context.add_or_update_characters([player, guard], message_count=0)

        thread = message_thread(default_config, "system prompt")
        _build_enough_messages(thread, default_config)

        # Guard departs via updated actor list
        context.add_or_update_characters([player], message_count=len(thread))
        npcs = context.npcs_in_conversation

        with patch.object(default_rememberer, 'summarize_conversation', return_value="Summary.\n\n") as mock_summarize:
            default_rememberer.save_conversation_state(thread, [guard], npcs, world_id, is_reload=False)

            assert mock_summarize.call_count == 1
            prompt_arg = mock_summarize.call_args[0][1]
            assert "Skyrim" in prompt_arg


class TestPendingShares:
    """Tests for the pending_shares code path in save_conversation_state."""

    def test_pending_share_writes_prefixed_summary_to_recipient(
        self, skyrim: Skyrim, default_config: ConfigLoader, llm_client: LLMClient,
        default_rememberer: Summaries, english_language_info: dict,
        example_skyrim_player_character: Character,
        example_skyrim_npc_character: Character
    ):
        """Shared summary is written to recipient folder with prefix including participants."""
        player = example_skyrim_player_character
        guard = example_skyrim_npc_character
        world_id = "TestWorld"
        recipient_name = "Farengar"
        recipient_ref_id = "ABC123"

        context = Context(world_id, default_config, llm_client, default_rememberer, english_language_info)
        context.add_or_update_characters([player, guard], message_count=0)

        thread = message_thread(default_config, "system prompt")
        _build_enough_messages(thread, default_config)
        npcs = context.npcs_in_conversation

        pending_shares = [("Guard", recipient_name, recipient_ref_id)]

        with patch.object(default_rememberer, 'summarize_conversation', return_value="Guard had a conversation.\n\n"):
            default_rememberer.save_conversation_state(
                thread, [guard], npcs, world_id, is_reload=False, pending_shares=pending_shares
            )

        recipient_folder = os.path.join(
            skyrim.conversation_folder_path, world_id, f"{recipient_name} - {recipient_ref_id}"
        )
        recipient_summary_file = os.path.join(recipient_folder, f"{recipient_name}_summary_1.txt")
        assert os.path.exists(recipient_summary_file)

        with open(recipient_summary_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "Guard shared with Farengar a conversation with" in content
        assert "Dragonborn (the player)" in content
        assert "Guard had a conversation." in content

    def test_pending_share_skipped_when_sharer_has_empty_summary(
        self, skyrim: Skyrim, default_config: ConfigLoader, llm_client: LLMClient,
        default_rememberer: Summaries, english_language_info: dict,
        example_skyrim_player_character: Character,
        example_skyrim_npc_character: Character
    ):
        """When the sharer produces no summary, no file should be created for the recipient."""
        player = example_skyrim_player_character
        guard = example_skyrim_npc_character
        world_id = "TestWorld"
        recipient_name = "Farengar"
        recipient_ref_id = "ABC123"

        context = Context(world_id, default_config, llm_client, default_rememberer, english_language_info)
        context.add_or_update_characters([player, guard], message_count=0)

        thread = message_thread(default_config, "system prompt")
        _build_enough_messages(thread, default_config)
        npcs = context.npcs_in_conversation

        pending_shares = [("Guard", recipient_name, recipient_ref_id)]

        with patch.object(default_rememberer, 'summarize_conversation', return_value=""):
            default_rememberer.save_conversation_state(
                thread, [guard], npcs, world_id, is_reload=False, pending_shares=pending_shares
            )

        recipient_folder = os.path.join(
            skyrim.conversation_folder_path, world_id, f"{recipient_name} - {recipient_ref_id}"
        )
        assert not os.path.exists(recipient_folder)


class TestTimestampPrefix:
    """Tests for timestamp prefix in __create_new_conversation_summary."""

    def test_timestamp_prepended_when_enabled_and_timestamp_provided(
        self, skyrim: Skyrim, default_config: ConfigLoader, llm_client: LLMClient,
        default_rememberer: Summaries, english_language_info: dict,
        example_skyrim_player_character: Character,
        example_skyrim_npc_character: Character
    ):
        """Summary on disk should have a [Day X, Y ...] prefix when config flag is on and timestamp is given."""
        player = example_skyrim_player_character
        guard = example_skyrim_npc_character
        world_id = "TestWorld"

        default_config.memory_prompt_datetime_prefix = True

        context = Context(world_id, default_config, llm_client, default_rememberer, english_language_info)
        context.add_or_update_characters([player, guard], message_count=0)

        thread = message_thread(default_config, "system prompt")
        _build_enough_messages(thread, default_config)

        context.add_or_update_characters([player], message_count=len(thread))
        npcs = context.npcs_in_conversation

        with patch.object(default_rememberer, 'summarize_conversation', return_value="Guard spoke about dragons.\n\n"):
            default_rememberer.save_conversation_state(
                thread, [guard], npcs, world_id, is_reload=False, end_timestamp=42.75
            )

        guard_folder = os.path.join(skyrim.conversation_folder_path, world_id, f"Guard - {guard.ref_id}")
        guard_summary_file = os.path.join(guard_folder, "Guard_summary_1.txt")
        assert os.path.exists(guard_summary_file)
        with open(guard_summary_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert content.startswith("[Day 42, 6 in the early evening]")
        assert "Guard spoke about dragons." in content

    def test_no_timestamp_when_config_flag_disabled(
        self, skyrim: Skyrim, default_config: ConfigLoader, llm_client: LLMClient,
        default_rememberer: Summaries, english_language_info: dict,
        example_skyrim_player_character: Character,
        example_skyrim_npc_character: Character
    ):
        """Summary on disk should not have a timestamp prefix when the config flag is disabled."""
        player = example_skyrim_player_character
        guard = example_skyrim_npc_character
        world_id = "TestWorld"

        default_config.memory_prompt_datetime_prefix = False

        context = Context(world_id, default_config, llm_client, default_rememberer, english_language_info)
        context.add_or_update_characters([player, guard], message_count=0)

        thread = message_thread(default_config, "system prompt")
        _build_enough_messages(thread, default_config)

        context.add_or_update_characters([player], message_count=len(thread))
        npcs = context.npcs_in_conversation

        with patch.object(default_rememberer, 'summarize_conversation', return_value="Guard spoke about dragons.\n\n"):
            default_rememberer.save_conversation_state(
                thread, [guard], npcs, world_id, is_reload=False, end_timestamp=42.75
            )

        guard_folder = os.path.join(skyrim.conversation_folder_path, world_id, f"Guard - {guard.ref_id}")
        guard_summary_file = os.path.join(guard_folder, "Guard_summary_1.txt")
        assert os.path.exists(guard_summary_file)
        with open(guard_summary_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert not content.startswith("[Day")
        assert "Guard spoke about dragons." in content

    def test_no_timestamp_when_end_timestamp_is_none(
        self, skyrim: Skyrim, default_config: ConfigLoader, llm_client: LLMClient,
        default_rememberer: Summaries, english_language_info: dict,
        example_skyrim_player_character: Character,
        example_skyrim_npc_character: Character
    ):
        """Summary on disk should not have a timestamp prefix when end_timestamp is None."""
        player = example_skyrim_player_character
        guard = example_skyrim_npc_character
        world_id = "TestWorld"

        default_config.memory_prompt_datetime_prefix = True

        context = Context(world_id, default_config, llm_client, default_rememberer, english_language_info)
        context.add_or_update_characters([player, guard], message_count=0)

        thread = message_thread(default_config, "system prompt")
        _build_enough_messages(thread, default_config)

        context.add_or_update_characters([player], message_count=len(thread))
        npcs = context.npcs_in_conversation

        with patch.object(default_rememberer, 'summarize_conversation', return_value="Guard spoke about dragons.\n\n"):
            default_rememberer.save_conversation_state(
                thread, [guard], npcs, world_id, is_reload=False, end_timestamp=None
            )

        guard_folder = os.path.join(skyrim.conversation_folder_path, world_id, f"Guard - {guard.ref_id}")
        guard_summary_file = os.path.join(guard_folder, "Guard_summary_1.txt")
        assert os.path.exists(guard_summary_file)
        with open(guard_summary_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert not content.startswith("[Day")
        assert "Guard spoke about dragons." in content


class TestResummarization:
    """Tests for resummarization when token limit is exceeded."""

    def test_new_summary_file_created_when_token_limit_exceeded(self, skyrim: Skyrim, default_rememberer: Summaries, example_skyrim_npc_character: Character):
        """When conversation summaries exceed the token limit, a new file with incremented number should be created."""
        guard = example_skyrim_npc_character
        world_id = "TestWorld"

        # Set up the initial summary file
        folder = os.path.join(skyrim.conversation_folder_path, world_id, f"Guard - {guard.ref_id}")
        os.makedirs(folder, exist_ok=True)
        initial_file = os.path.join(folder, "Guard_summary_1.txt")
        with open(initial_file, 'w', encoding='utf-8') as f:
            f.write("Existing summary content.\n\n")

        new_summary = "New conversation summary."
        client = default_rememberer._Summaries__client

        with patch.object(client, 'get_count_tokens', return_value=99999), \
             patch.object(default_rememberer, 'summarize_conversation', return_value="Resummarized content."):
            default_rememberer._Summaries__append_new_conversation_summary_by_ids(
                new_summary, guard.name, guard.ref_id, world_id
            )

        new_file = os.path.join(folder, "Guard_summary_2.txt")
        assert os.path.exists(new_file)
        with open(new_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "Resummarized content." in content

    def test_resummarize_prompt_formatted_correctly(self, skyrim: Skyrim, default_rememberer: Summaries, example_skyrim_npc_character: Character):
        """The resummarize prompt passed to summarize_conversation should contain the NPC name, language, and game."""
        guard = example_skyrim_npc_character
        world_id = "TestWorld"

        folder = os.path.join(skyrim.conversation_folder_path, world_id, f"Guard - {guard.ref_id}")
        os.makedirs(folder, exist_ok=True)
        initial_file = os.path.join(folder, "Guard_summary_1.txt")
        with open(initial_file, 'w', encoding='utf-8') as f:
            f.write("Existing summary content.\n\n")

        client = default_rememberer._Summaries__client

        with patch.object(client, 'get_count_tokens', return_value=99999), \
             patch.object(default_rememberer, 'summarize_conversation', return_value="Resummarized.") as mock_summarize:
            default_rememberer._Summaries__append_new_conversation_summary_by_ids(
                "New summary.", guard.name, guard.ref_id, world_id
            )

            assert mock_summarize.call_count == 1
            prompt_arg = mock_summarize.call_args[0][1]
            assert "Guard" in prompt_arg
            assert "English" in prompt_arg


class TestFormatTimestamp:
    """Tests for __format_timestamp."""

    @pytest.mark.parametrize("game_days,expected", [
        (10.0, "[Day 10, 0 at night]"),
        (1.25, "[Day 1, 6 in the early morning]"),
        (5.375, "[Day 5, 9 in the morning]"),
        (100.5625, "[Day 100, 1 in the afternoon]"),
        (42.75, "[Day 42, 6 in the early evening]"),
        (30.875, "[Day 30, 9 in the late evening]"),
    ])
    def test_format_timestamp(self, default_rememberer: Summaries, game_days: float, expected: str):
        """__format_timestamp should produce the correct [Day X, Y time_group] format."""
        result = default_rememberer._Summaries__format_timestamp(game_days)
        assert result == expected


class TestSummarizeConversation:
    """Tests for summarize_conversation."""

    def test_real_llm_call_produces_summary(self, default_rememberer: Summaries):
        """An actual LLM call should return a non-empty summary ending with double newlines."""
        text = (
            "Player: Hello Guard, how are you?\n"
            "Guard: I am well, thank you for asking.\n"
            "Player: What's happening in Whiterun today?\n"
            "Guard: The usual. Keeping the peace.\n"
            "Player: Stay safe out there.\n"
            "Guard: You too, citizen."
        )
        prompt = "Summarize the following conversation briefly."

        result = default_rememberer.summarize_conversation(text, prompt)

        assert len(result) > 0
        assert result.endswith("\n\n")

    def test_short_text_returns_empty_string(self, default_rememberer: Summaries):
        """Text with 5 or fewer characters should return empty without calling the LLM."""
        result = default_rememberer.summarize_conversation("Hi", "Summarize this.")
        assert result == ""

    def test_text_replacements_applied(self, default_rememberer: Summaries):
        """'The assistant', 'the user', etc. should be replaced in the returned summary."""
        llm_response = "The assistant discussed The user's quest. the assistant helped the user. an AI assistant was present."

        with patch.object(default_rememberer._Summaries__client, 'request_call', return_value=llm_response):
            result = default_rememberer.summarize_conversation(
                "A long enough text to trigger summarization beyond five characters.",
                "Summarize this."
            )

        assert "The assistant" not in result
        assert "the assistant" not in result
        assert "an AI assistant" not in result
        assert "The user" not in result
        assert "the user" not in result
        assert "Someone" in result
        assert "The player" in result
        assert "the player" in result
