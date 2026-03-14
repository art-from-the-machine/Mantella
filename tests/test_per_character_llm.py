import pytest
from unittest.mock import MagicMock
from src.character_manager import Character
from src.output_manager import ChatManager
from src.config.config_loader import ConfigLoader
from src.tts.piper import Piper
from tests.conftest import MockAIClient


@pytest.fixture
def output_manager(default_config: ConfigLoader, piper: Piper, mock_ai_client: MockAIClient, monkeypatch) -> ChatManager:
    piper.synthesize = MagicMock(return_value="mock_audio_file.wav")
    monkeypatch.setattr('src.utils.get_audio_duration', lambda *args, **kwargs: 1.0)
    return ChatManager(default_config, piper, mock_ai_client)


def test_config_default_disables_per_character_overrides(default_config: ConfigLoader):
    assert default_config.allow_per_character_llm_overrides is False


class TestGetPerCharacterClient:
    """Tests for ChatManager._get_per_character_client."""

    def test_returns_default_when_overrides_disabled(self, output_manager: ChatManager, mock_ai_client, example_skyrim_npc_character: Character):
        output_manager._ChatManager__config.allow_per_character_llm_overrides = False
        example_skyrim_npc_character.llm_service = "https://api.openai.com/v1"
        example_skyrim_npc_character.llm_model = "gpt-4"
        assert output_manager._get_per_character_client(example_skyrim_npc_character) is mock_ai_client

    @pytest.mark.parametrize("service, model", [
        ("", "gpt-4"),
        ("https://api.openai.com/v1", ""),
        ("", ""),
    ])
    def test_returns_default_when_service_or_model_missing(self, output_manager: ChatManager, mock_ai_client, example_skyrim_npc_character: Character, service, model):
        output_manager._ChatManager__config.allow_per_character_llm_overrides = True
        example_skyrim_npc_character.llm_service = service
        example_skyrim_npc_character.llm_model = model
        assert output_manager._get_per_character_client(example_skyrim_npc_character) is mock_ai_client

    def test_creates_new_client_when_both_set(self, output_manager: ChatManager, mock_ai_client, example_skyrim_npc_character: Character, monkeypatch):
        output_manager._ChatManager__config.allow_per_character_llm_overrides = True
        mock_new_client = MagicMock()
        monkeypatch.setattr("src.output_manager.ClientBase", lambda **kw: mock_new_client)
        example_skyrim_npc_character.llm_service = "https://api.openai.com/v1"
        example_skyrim_npc_character.llm_model = "gpt-4"

        result = output_manager._get_per_character_client(example_skyrim_npc_character)
        assert result is mock_new_client
        assert result is not mock_ai_client

    def test_client_cached_across_calls(self, output_manager: ChatManager, example_skyrim_npc_character: Character, monkeypatch):
        output_manager._ChatManager__config.allow_per_character_llm_overrides = True
        monkeypatch.setattr("src.output_manager.ClientBase", lambda **kw: MagicMock())
        example_skyrim_npc_character.llm_service = "https://api.openai.com/v1"
        example_skyrim_npc_character.llm_model = "gpt-4"

        first = output_manager._get_per_character_client(example_skyrim_npc_character)
        second = output_manager._get_per_character_client(example_skyrim_npc_character)
        assert first is second

    def test_different_characters_get_different_clients(self, output_manager: ChatManager, example_skyrim_npc_character: Character, another_example_skyrim_npc_character: Character, monkeypatch):
        output_manager._ChatManager__config.allow_per_character_llm_overrides = True
        monkeypatch.setattr("src.output_manager.ClientBase", lambda **kw: MagicMock())

        example_skyrim_npc_character.llm_service = "or"
        example_skyrim_npc_character.llm_model = "model-a"
        another_example_skyrim_npc_character.llm_service = "or"
        another_example_skyrim_npc_character.llm_model = "model-b"

        a = output_manager._get_per_character_client(example_skyrim_npc_character)
        b = output_manager._get_per_character_client(another_example_skyrim_npc_character)
        assert a is not b

    def test_fallback_on_client_creation_failure(self, output_manager: ChatManager, mock_ai_client, example_skyrim_npc_character: Character, monkeypatch):
        output_manager._ChatManager__config.allow_per_character_llm_overrides = True

        def raise_error(**kw):
            raise Exception("Connection refused")
        monkeypatch.setattr("src.output_manager.ClientBase", raise_error)

        example_skyrim_npc_character.llm_service = "https://bad-endpoint/v1"
        example_skyrim_npc_character.llm_model = "nonexistent-model"
        assert output_manager._get_per_character_client(example_skyrim_npc_character) is mock_ai_client

    def test_cache_cleared(self, output_manager: ChatManager, example_skyrim_npc_character: Character, monkeypatch):
        output_manager._ChatManager__config.allow_per_character_llm_overrides = True
        monkeypatch.setattr("src.output_manager.ClientBase", lambda **kw: MagicMock())
        example_skyrim_npc_character.llm_service = "or"
        example_skyrim_npc_character.llm_model = "mdl"

        first = output_manager._get_per_character_client(example_skyrim_npc_character)
        output_manager.clear_per_character_client_cache()
        second = output_manager._get_per_character_client(example_skyrim_npc_character)
        assert first is not second
