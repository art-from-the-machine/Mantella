import src.utils as utils
import logging
from openai.types.chat import ChatCompletion
from openai.types.chat import ChatCompletionMessageToolCall
from src.config.config_loader import ConfigLoader
from src.llm.client_base import ClientBase
from src.llm.message_thread import message_thread
from src.llm.messages import Message
from src.llm.messages import SystemMessage

class FunctionClient(ClientBase):
    '''LLM class to handle function calling / actions
    '''
    @utils.time_it
    def __init__(self, config: ConfigLoader, secret_key_file: str, function_llm_secret_key_file: str) -> None:
        self.__config = config
        self.__function_prompt: str = config.function_llm_prompt.format(game=config.game.display_name)
        
        # Use custom function model config values
        setup_values = {
            'api_url': config.function_llm_api, 
            'llm': config.function_llm, 
            'llm_params': config.function_llm_params, 
            'custom_token_count': config.function_llm_custom_token_count
        }
        
        super().__init__(**setup_values, secret_key_files=[function_llm_secret_key_file, secret_key_file])

        if self._is_local:
            logging.info(f"Running local tool calling model")
        else:
            logging.log(23, f"Running Mantella with custom tool calling model '{config.function_llm}'")


    @utils.time_it
    def request_call_with_tools(self, messages: Message | message_thread, tools: list[dict] | None = None) -> list[ChatCompletionMessageToolCall] | None:
        """Make a request with tools and return tool calls
        
        Args:
            messages: The messages to send to the LLM
            tools: Tools list to use for this call
            
        Returns:
            tool_calls
        """
        # Store original request params to restore later
        original_params = self._request_params.copy() if self._request_params else {}
        
        # Temporarily add tools to request params
        if self._request_params is None:
            self._request_params = {}
        if tools:
            self._request_params['tools'] = tools
        
        try:
            # Use the full request call to get both message and tool calls
            chat_completion: ChatCompletion = self._request_call_full(messages)
            
            if not chat_completion or not chat_completion.choices or len(chat_completion.choices) < 1:
                logging.info("Function LLM response failed")
                return None
            
            tool_calls = getattr(chat_completion.choices[0].message, 'tool_calls', None)
            
            return tool_calls
            
        finally:
            # Restore original request params
            self._request_params = original_params


    @utils.time_it
    def check_for_actions(self, messages: message_thread, tools: list[dict]) -> list[dict] | None:
        """Check if any actions should be called based on the conversation
        
        Args:
            messages: The conversation thread to analyze
            tools: The context-aware tools list to use
            
        Returns:
            List of tool calls or None if no actions needed / error
        """
        
        if not tools:
            logging.debug("No available actions for current context")
            return None
        
        try:
            logging.log(23, f"Function LLM analyzing conversation for potential actions...")
            
            # Replace the system prompt with the function LLM prompt
            shortened_thread = messages.clone_with_new_system_message(self.__function_prompt)
            
            # Call the function LLM with tools
            tools_called = self.request_call_with_tools(shortened_thread, tools)
            
            if not tools_called:
                logging.debug("No actions chosen by tool calling LLM")
                return None
            
            # Convert ChatCompletionMessageToolCall objects to dict format for further processing
            tool_calls_dicts = []
            for tool_call in tools_called:
                tool_calls_dicts.append({
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                })
            
            return tool_calls_dicts
            
        except Exception as e:
            logging.error(f"Tool calling LLM error: {e}. Skipping tool calling for this turn.")
            return None
