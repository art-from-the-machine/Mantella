from src.config.config_loader import ConfigLoader
from src.llm.client_base import ClientBase
from src.model_profile_manager import get_profile_manager

class SummaryLLMClient(ClientBase):
    '''LLM client dedicated to generating conversation summaries.'''
    def __init__(self, config: ConfigLoader) -> None:
        profile_manager = get_profile_manager()
        summary_llm_params = profile_manager.resolve_params(
            service=config.summary_llm_api,
            model=config.summary_llm,
            fallback_params=config.summary_llm_params,
            apply_profile=config.apply_model_profiles,
            log_context="SummaryLLMClient",
        )
        super().__init__(config.summary_llm_api, config.summary_llm, summary_llm_params, config.summary_custom_token_count)
