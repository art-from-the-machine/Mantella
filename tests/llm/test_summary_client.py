import pytest
from src.config.config_loader import ConfigLoader
from src.llm.summary_client import SummaryLLMClient
from src.llm.client_base import ClientBase
from src.llm.llm_client import LLMClient
from src.remember.summaries import Summaries
from src.games.skyrim import Skyrim


class TestSummaryLLMClientInit:
    def test_init_uses_summary_config_values(self, default_config: ConfigLoader):
        """SummaryLLMClient should initialize with summary-specific config fields."""
        default_config.summary_llm_api = "OpenRouter"
        default_config.summary_llm = "mistralai/mistral-small-3.1-24b-instruct:free"
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
        default_config.summary_llm = "mistralai/mistral-small-3.1-24b-instruct:free"
        default_config.summary_custom_token_count = 8192
        summary_client = SummaryLLMClient(default_config)

        summaries = Summaries(skyrim, default_config, llm_client, english_language_info['language'], summary_client=summary_client)
        assert summaries._Summaries__client is summary_client


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
