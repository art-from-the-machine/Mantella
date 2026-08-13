import pytest
from unittest.mock import MagicMock, patch
from src.config.config_loader import ConfigLoader
from src.llm.summary_client import SummaryLLMClient
from src.llm.client_base import ClientBase
from src.llm.llm_client import LLMClient
from src.remember.summaries import Summaries
from src.games.skyrim import Skyrim
from src.config.mantella_config_value_definitions_new import MantellaConfigValueDefinitionsNew
from src.http.communication_constants import communication_constants


class TestSummaryLLMClientInit:
    def test_init_uses_summary_config_values(self, default_config: ConfigLoader):
        """SummaryLLMClient should initialize with summary-specific config fields."""
        default_config.summary_llm_api = "OpenRouter"
        default_config.summary_llm = "google/gemma-4-26b-a4b-it:free"
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
    def test_summaries_uses_main_client_when_no_summary_client(self, skyrim: Skyrim, default_config: ConfigLoader, llm_client: LLMClient, english_language_info):
        """When summary_client is None, Summaries should use the main client for summarization."""
        summaries = Summaries(skyrim, default_config, llm_client, english_language_info['language'], summary_client=None)
        assert summaries._Summaries__client is llm_client

    def test_summaries_uses_separate_client_when_provided(self, skyrim: Skyrim, default_config: ConfigLoader, llm_client: LLMClient, english_language_info):
        """When a summary_client is provided, Summaries should use it instead of the main client."""
        default_config.summary_llm_api = "OpenRouter"
        default_config.summary_llm = "google/gemma-4-26b-a4b-it:free"
        default_config.summary_custom_token_count = 8192
        summary_client = SummaryLLMClient(default_config)

        summaries = Summaries(skyrim, default_config, llm_client, english_language_info['language'], summary_client=summary_client)
        assert summaries._Summaries__client is summary_client

    def test_direct_lan_summary_endpoint_is_local_and_needs_no_cloud_key(self, default_config: ConfigLoader):
        default_config.summary_llm_api = "http://172.16.0.247:8081/v1/"
        default_config.summary_llm = "local"
        client = SummaryLLMClient(default_config)
        assert client.base_url == "http://172.16.0.247:8081/v1/"
        assert client.is_local is True
        assert client.api_key == "abc123"

    def test_summary_retries_are_bounded_and_do_not_use_dialogue_client(
        self, skyrim: Skyrim, default_config: ConfigLoader, llm_client: LLMClient, english_language_info
    ):
        summary_client = MagicMock()
        summary_client.base_url = "http://172.16.0.247:8081/v1/"
        summary_client.request_call.return_value = None
        summaries = Summaries(skyrim, default_config, llm_client, english_language_info['language'], summary_client=summary_client)

        with patch.object(summaries, 'SUMMARY_MAX_ATTEMPTS', 3), patch('src.remember.summaries.time.sleep'), patch.object(llm_client, 'request_call') as dialogue_call:
            result = summaries.summarize_conversation("Player: hello\nNPC: goodbye", "Summarize this")

        assert result == ""
        assert summary_client.request_call.call_count == 3
        dialogue_call.assert_not_called()

    def test_summary_retry_can_succeed_on_later_attempt(
        self, skyrim: Skyrim, default_config: ConfigLoader, llm_client: LLMClient, english_language_info
    ):
        summary_client = MagicMock()
        summary_client.base_url = "http://172.16.0.247:8081/v1/"
        summary_client.request_call.side_effect = [None, "Recovered summary"]
        summaries = Summaries(skyrim, default_config, llm_client, english_language_info['language'], summary_client=summary_client)

        with patch('src.remember.summaries.time.sleep'):
            result = summaries.summarize_conversation("Player: hello\nNPC: goodbye", "Summarize this")

        assert result == "Recovered summary\n\n"
        assert summary_client.request_call.call_count == 2


class TestConfigLoadingSummaryValues:
    def test_summary_settings_have_dedicated_gui_labels(self):
        definitions = MantellaConfigValueDefinitionsNew.get_config_values(False)
        expected = {
            "summary_llm_enabled": "Enable Dedicated Summary LLM",
            "summary_llm_api": "Summary LLM API / Endpoint",
            "summary_llm": "Summary LLM Model",
            "summary_custom_token_count": "Summary Custom Token Count",
            "summary_llm_params": "Summary LLM Parameters",
        }
        for identifier, label in expected.items():
            assert definitions.get_config_value_definition(identifier).name == label

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


def test_interrupted_reply_constant_is_defined():
    assert communication_constants.KEY_REPLYTYPE_INTERRUPTED == "mantella_interrupted"
