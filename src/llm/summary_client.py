import src.utils as utils
from openai import AsyncOpenAI
from src.config.config_loader import ConfigLoader
from src.llm.client_base import ClientBase

class SummaryLLMClient(ClientBase):
    '''LLM client dedicated to generating conversation summaries.
    Allows using a cheaper/faster model for summaries while keeping a more capable model for conversations.
    '''
    @utils.time_it
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__(config.summary_llm_api, config.summary_llm, config.summary_llm_params, config.summary_custom_token_count)
        self._startup_async_client: AsyncOpenAI | None = self.generate_async_client() # initialize first client in advance of sending first LLM request to save time
