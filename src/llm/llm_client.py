import src.utils as utils
from openai import AsyncOpenAI
from src.config.config_loader import ConfigLoader
from src.llm.image_client import ImageClient
from src.llm.function_client import FunctionClient
from src.llm.client_base import ClientBase

logger = utils.get_logger()


class LLMClient(ClientBase):
    '''LLM class to handle NPC responses
    '''
    @utils.time_it
    def __init__(self, config: ConfigLoader, secret_key_file: str, image_secret_key_file: str, function_secret_key_file: str = None) -> None:
        super().__init__(config.llm_api, config.llm, config.llm_params, config.custom_token_count, [secret_key_file])

        if self._is_local:
            logger.info(f"Running Mantella with local language model")
        else:
            logger.log(23, f"Running Mantella with '{config.llm}'. The language model can be changed in the Mantella UI: http://localhost:4999/ui")

        self._startup_async_client: AsyncOpenAI | None = self.generate_async_client() # initialize first client in advance of sending first LLM request to save time

        if config.vision_enabled:
            logger.info(f"Setting up vision language model...")
            self._image_client: ImageClient | None = ImageClient(config, secret_key_file, image_secret_key_file)

        if config.advanced_actions_enabled and config.custom_function_model:
            try:
                logger.info(f"Setting up tool calling language model...")
                self._function_client: FunctionClient | None = FunctionClient(config, secret_key_file, function_secret_key_file)
            except Exception as e:
                logger.error(f"Failed to initialize function calling LLM: {e}. Tool calling will be disabled.")
                self._function_client = None
