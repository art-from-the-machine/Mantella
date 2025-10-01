from __future__ import annotations

from src.config.config_loader import ConfigLoader
from src.llm.client_base import ClientBase
from src.llm.key_file_resolver import key_file_resolver
from src.llm.messages import UserMessage
from src.llm.sonnet_cache_connector import SonnetCacheConnector
import logging


class BioLLMRequester:
    """Encapsulates LLM interactions for the Bio Editor tab.

    Responsible for building a client using a selected service/model and
    executing a simple prompt request, returning plain text content.
    """

    def __init__(self, config: ConfigLoader) -> None:
        self._config = config

    def send(self, service: str, model: str, prompt_text: str, params_override: dict | None = None) -> str:
        """Send a one-shot prompt to the chosen LLM and return the reply text.

        Args:
            service: LLM service identifier (e.g., 'OpenRouter', 'OpenAI', 'NanoGPT', 'KoboldCpp', 'textgenwebui' or URL)
            model: Model name/id for the request
            prompt_text: Fully-resolved prompt text

        Returns:
            The model's reply text (empty string on failure)
        """
        try:
            key_files = key_file_resolver.get_key_files_for_service(service, 'GPT_SECRET_KEY.txt')
            params = params_override if params_override is not None else self._config.llm_params
            custom_token_count = self._config.custom_token_count

            client = ClientBase(service, model, params, custom_token_count, key_files)
            try:
                # Enable Sonnet caching for Bio Editor prompts too (OpenRouter-only)
                client._sonnet_cache_connector = SonnetCacheConnector(getattr(self._config, 'sonnet_prompt_caching_enabled', False))
            except Exception as e:
                logging.debug(f"Failed to attach Sonnet cache connector to Bio client: {e}")
            # Log prompt similar to dialogue flow
            try:
                token_count = client.get_count_tokens(prompt_text)
            except Exception:
                token_count = len(prompt_text) if prompt_text else 0
            logging.log(23, f"Prompt sent to LLM ({token_count} tokens): {prompt_text.strip() if prompt_text else ''}")
            message = UserMessage(self._config, prompt_text, is_system_generated_message=True)
            reply = client.request_call(message)
            return reply or ""
        except Exception as e:
            logging.error(f"BioLLMRequester error: {e}")
            return ""


