import src.utils as utils
from src.config.config_loader import ConfigLoader
from src.llm.client_base import ClientBase

class SummaryLLMClient(ClientBase):
    '''LLM client dedicated to generating conversation summaries.'''
    @utils.time_it
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__(config.summary_llm_api, config.summary_llm, config.summary_llm_params, config.summary_custom_token_count)
