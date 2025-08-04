import src.utils as utils
import logging
from src.config.config_loader import ConfigLoader
from src.llm.client_base import ClientBase
from src.llm.message_thread import message_thread
from src.llm.messages import Message

class FunctionClient(ClientBase):
    '''LLM class to handle function calling / actions
    '''
    @utils.time_it
    def __init__(self, config: ConfigLoader, secret_key_file: str, function_llm_secret_key_file: str) -> None:
        self.__custom_function_model: bool = True # TODO: Allow chat LLM to be used for function calling
        
        if self.__custom_function_model: # if using a custom model for vision, load these custom config values
            # TODO: Create function LLM params in config
            setup_values = {'api_url': config.function_llm_api, 'llm': config.function_llm, 'llm_params': config.llm_params, 'custom_token_count': config.function_llm_custom_token_count}
        else: # default to base LLM config values
            setup_values = {'api_url': config.llm_api, 'llm': config.llm, 'llm_params': config.llm_params, 'custom_token_count': config.custom_token_count}
        
        super().__init__(**setup_values, secret_key_files=[function_llm_secret_key_file, secret_key_file])

        if self.__custom_function_model:
            if self._is_local:
                logging.info(f"Running local function model")
            else:
                logging.log(23, f"Running Mantella with custom function model '{config.function_llm}'")

    @utils.time_it
    def request_call(self, messages: Message | message_thread, tools: list | None) -> str | None:
        """Override request_call to allow passing tools for function calling
        
        Args:
            messages: The messages to send to the LLM
            tools: Tools list to use for this call
            
        Returns:
            The LLM response or None if the request failed
        """
        self._request_params['tools'] = tools
        result = super().request_call(messages)
        
        return result
