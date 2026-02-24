import pytest
from src.llm.claude_cache_connector import ClaudeCacheConnector

OPENROUTER_URL = "https://openrouter.ai/api/v1"
CLAUDE_MODEL = "anthropic/claude-haiku-4.5"


@pytest.fixture
def connector() -> ClaudeCacheConnector:
    return ClaudeCacheConnector()


class TestIsApplicable:
    def test_openrouter_claude(self, connector: ClaudeCacheConnector):
        assert connector.is_applicable(OPENROUTER_URL, CLAUDE_MODEL) is True

    def test_openrouter_claude_case_insensitive(self, connector: ClaudeCacheConnector):
        assert connector.is_applicable("https://OPENROUTER.AI/api/v1", "Anthropic/Claude-3-Haiku") is True

    def test_openrouter_non_claude(self, connector: ClaudeCacheConnector):
        assert connector.is_applicable(OPENROUTER_URL, "mistralai/mistral-small") is False

    def test_openai_claude(self, connector: ClaudeCacheConnector):
        """Claude model on non-OpenRouter service -> not applicable"""
        assert connector.is_applicable("https://api.openai.com/v1", CLAUDE_MODEL) is False

    def test_local_url(self, connector: ClaudeCacheConnector):
        assert connector.is_applicable("http://127.0.0.1:5001/v1", CLAUDE_MODEL) is False

    def test_empty_model_name(self, connector: ClaudeCacheConnector):
        assert connector.is_applicable(OPENROUTER_URL, "") is False

    def test_none_model_name(self, connector: ClaudeCacheConnector):
        assert connector.is_applicable(OPENROUTER_URL, None) is False

    def test_openrouter_with_trailing_space(self, connector: ClaudeCacheConnector):
        assert connector.is_applicable("  https://openrouter.ai/api/v1  ", CLAUDE_MODEL) is True


class TestGetCacheTargetIndex:
    """Test the breakpoint placement strategy."""

    def test_empty_messages(self, connector: ClaudeCacheConnector):
        assert connector._get_cache_target_index([]) is None

    def test_single_user_message(self, connector: ClaudeCacheConnector):
        """Only one user message -> nothing to cache"""
        msgs = [{"role": "user", "content": "Hello."}]
        assert connector._get_cache_target_index(msgs) is None

    def test_system_plus_one_user(self, connector: ClaudeCacheConnector):
        """Turn 1: system + user_new -> cache on system (index 0)"""
        msgs = [
            {"role": "system", "content": "You are an AI."},
            {"role": "user", "content": "Hello."},
        ]
        assert connector._get_cache_target_index(msgs) == 0

    def test_two_user_turns(self, connector: ClaudeCacheConnector):
        """Turn 2: system + user_prev + assistant + user_new -> cache on user_prev (index 1)"""
        msgs = [
            {"role": "system", "content": "You are an AI."},
            {"role": "user", "content": "Hello."},
            {"role": "assistant", "content": "Hi there."},
            {"role": "user", "content": "How are you?"},
        ]
        assert connector._get_cache_target_index(msgs) == 1

    def test_three_user_turns(self, connector: ClaudeCacheConnector):
        """Turn 3: cache on second-to-last user (index 3)"""
        msgs = [
            {"role": "system", "content": "You are an AI."},
            {"role": "user", "content": "Hello."},
            {"role": "assistant", "content": "Hi there."},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "Good thanks."},
            {"role": "user", "content": "Me too thanks."},
        ]
        assert connector._get_cache_target_index(msgs) == 3

    def test_last_message_not_user(self, connector: ClaudeCacheConnector):
        """If last message isn't a user message, no caching"""
        msgs = [
            {"role": "system", "content": "You are an AI."},
            {"role": "user", "content": "Hello."},
            {"role": "assistant", "content": "Hi there."},
        ]
        assert connector._get_cache_target_index(msgs) is None

    def test_no_system_no_previous_user(self, connector: ClaudeCacheConnector):
        """assistant + user -> no previous user and no system at index 0"""
        msgs = [
            {"role": "assistant", "content": "Something something."},
            {"role": "user", "content": "Hello."},
        ]
        assert connector._get_cache_target_index(msgs) is None


class TestTransformMessages:
    def test_empty_list(self, connector: ClaudeCacheConnector):
        assert connector.transform_messages([]) == []

    def test_does_not_mutate_original(self, connector: ClaudeCacheConnector):
        msgs = [
            {"role": "system", "content": "You are an AI."},
            {"role": "user", "content": "Hello."},
        ]
        original_content = msgs[0]["content"]
        connector.transform_messages(msgs)
        # Original should be untouched
        assert msgs[0]["content"] == original_content
        assert isinstance(msgs[0]["content"], str)

    def test_turn1_caches_system(self, connector: ClaudeCacheConnector):
        """Turn 1: system [cached] + user_new"""
        msgs = [
            {"role": "system", "content": "You are a helpful NPC."},
            {"role": "user", "content": "Hello there."},
        ]
        result = connector.transform_messages(msgs)

        # System message should be normalized to content blocks with cache_control
        system_content = result[0]["content"]
        assert isinstance(system_content, list)
        assert len(system_content) == 1
        assert system_content[0]["type"] == "text"
        assert system_content[0]["text"] == "You are a helpful NPC."
        assert system_content[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}

        # User message should be unchanged (string)
        assert result[1]["content"] == "Hello there."

    def test_turn2_caches_previous_user(self, connector: ClaudeCacheConnector):
        """Turn 2+: cache breakpoint on previous user message"""
        msgs = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
        ]
        result = connector.transform_messages(msgs)

        # Previous user (index 1) should have cache_control
        prev_user = result[1]["content"]
        assert isinstance(prev_user, list)
        assert any(b.get("cache_control") for b in prev_user)

        # System should remain a plain string (not the cache target)
        assert result[0]["content"] == "System prompt"

        # Latest user should remain a plain string
        assert result[3]["content"] == "Second question"

    def test_no_applicable_target(self, connector: ClaudeCacheConnector):
        """Single user message -> no transformation"""
        msgs = [{"role": "user", "content": "Just me"}]
        result = connector.transform_messages(msgs)
        assert result[0]["content"] == "Just me"


class TestNormalizeContent:
    def test_string_content(self, connector: ClaudeCacheConnector):
        result = connector._normalize_content("Hello world")
        assert result == [{"type": "text", "text": "Hello world"}]

    def test_none_content(self, connector: ClaudeCacheConnector):
        result = connector._normalize_content(None)
        assert result == [{"type": "text", "text": ""}]

    def test_list_of_dicts(self, connector: ClaudeCacheConnector):
        content = [{"type": "text", "text": "Hello"}, {"type": "text", "text": "World"}]
        result = connector._normalize_content(content)
        assert len(result) == 2
        assert result[0] == {"type": "text", "text": "Hello"}
        assert result[1] == {"type": "text", "text": "World"}

    def test_clears_stale_cache_control(self, connector: ClaudeCacheConnector):
        content = [{"type": "text", "text": "Hello", "cache_control": {"type": "ephemeral", "ttl": "1h"}}]
        result = connector._normalize_content(content)
        assert "cache_control" not in result[0]

    def test_list_with_non_dict(self, connector: ClaudeCacheConnector):
        content = ["plain string", 42]
        result = connector._normalize_content(content)
        assert result[0] == {"type": "text", "text": "plain string"}
        assert result[1] == {"type": "text", "text": "42"}

    def test_unexpected_type_serialized(self, connector: ClaudeCacheConnector):
        result = connector._normalize_content({"key": "value"})
        assert result[0]["type"] == "text"
        assert "key" in result[0]["text"]


class TestApplyCacheControl:
    def test_applies_to_last_text_block(self, connector: ClaudeCacheConnector):
        message = {"content": [
            {"type": "text", "text": "First"},
            {"type": "text", "text": "Second"},
        ]}
        connector._apply_cache_control(message)
        assert "cache_control" not in message["content"][0]
        assert message["content"][1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}

    def test_skips_non_text_blocks(self, connector: ClaudeCacheConnector):
        message = {"content": [
            {"type": "text", "text": "Text block"},
            {"type": "image_url", "image_url": {"url": "data:..."}},
        ]}
        connector._apply_cache_control(message)
        # Should apply to the text block (index 0), not the image (index 1)
        assert message["content"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        assert "cache_control" not in message["content"][1]

    def test_fallback_empty_content(self, connector: ClaudeCacheConnector):
        message = {"content": []}
        connector._apply_cache_control(message)
        assert len(message["content"]) == 1
        assert message["content"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}

    def test_does_not_mutate_original_block(self, connector: ClaudeCacheConnector):
        original_block = {"type": "text", "text": "Hello"}
        message = {"content": [original_block]}
        connector._apply_cache_control(message)
        # The block in the list should be a new dict, not the original
        assert "cache_control" not in original_block


class TestFullRoundTrip:
    """Simulate realistic Mantella conversation flows."""

    def _has_cache_control(self, message: dict) -> bool:
        content = message.get("content", [])
        if not isinstance(content, list):
            return False
        return any(isinstance(b, dict) and "cache_control" in b for b in content)

    def test_growing_conversation(self, connector: ClaudeCacheConnector):
        """Verify cache breakpoint moves as conversation grows."""
        system = {"role": "system", "content": "You are Lydia, a housecarl in Skyrim."}

        # Turn 1: system + user
        turn1 = [dict(system), {"role": "user", "content": "Hello Lydia."}]
        result1 = connector.transform_messages(turn1)
        assert self._has_cache_control(result1[0]) # system cached

        # Turn 2: system + user1 + assistant + user2
        turn2 = [
            dict(system),
            {"role": "user", "content": "Hello Lydia."},
            {"role": "assistant", "content": "I am sworn to carry your burdens."},
            {"role": "user", "content": "Follow me."},
        ]
        result2 = connector.transform_messages(turn2)
        assert not self._has_cache_control(result2[0]) # system no longer the target
        assert self._has_cache_control(result2[1]) # previous user cached
        assert not self._has_cache_control(result2[3]) # new user not cached

        # Turn 3
        turn3 = [
            dict(system),
            {"role": "user", "content": "Hello Lydia."},
            {"role": "assistant", "content": "I am sworn to carry your burdens."},
            {"role": "user", "content": "Follow me."},
            {"role": "assistant", "content": "Lead the way."},
            {"role": "user", "content": "Wait here."},
        ]
        result3 = connector.transform_messages(turn3)
        assert self._has_cache_control(result3[3]) # "Follow me" is now the previous user
        assert not self._has_cache_control(result3[5]) # "Wait here" is new

    def test_only_one_cache_breakpoint(self, connector: ClaudeCacheConnector):
        """Exactly one message should have cache_control, never more."""
        msgs = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
            {"role": "user", "content": "Q3"},
        ]
        result = connector.transform_messages(msgs)
        cached_count = sum(1 for m in result if self._has_cache_control(m))
        assert cached_count == 1
