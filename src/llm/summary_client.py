import src.utils as utils
import logging
from openai import AsyncOpenAI
from src.config.config_loader import ConfigLoader
from src.llm.image_client import ImageClient
from src.llm.client_base import ClientBase

class SummaryLLMCLient(ClientBase):
    '''LLM class to handle NPC responses
    '''
    @utils.time_it
    def __init__(self, config: ConfigLoader, secret_key_file: str, image_secret_key_file: str) -> None:
        used_llm = config.summary_llm if config.use_summary_llm else config.llm
        super().__init__(config.llm_api, used_llm, config.llm_params, config.llm_priority, config.custom_token_count, [secret_key_file])

        self._startup_async_client: AsyncOpenAI | None = self.generate_async_client() # initialize first client in advance of sending first LLM request to save time

        if config.vision_enabled:
            self._image_client: ImageClient | None = ImageClient(config, secret_key_file, image_secret_key_file)