import src.utils as utils
import logging
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_message import ChatCompletionMessageToolCall
from src.config.config_loader import ConfigLoader
from src.llm.client_base import ClientBase
from src.llm.message_thread import message_thread
from src.llm.messages import Message
from src.actions.function_manager import FunctionManager
from src.llm.messages import UserMessage

class FunctionClient(ClientBase):
    '''LLM class to handle function calling / actions
    '''
    @utils.time_it
    def __init__(self, config: ConfigLoader, secret_key_file: str, function_llm_secret_key_file: str) -> None:
        self.__custom_function_model: bool = True # TODO: Allow chat LLM to be used for function calling
        self.__config = config
        self.__prompt = config.actions_prompt
        
        if self.__custom_function_model:
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

        FunctionManager.load_all_actions()

        # TODO: Read tools from data/actions/ folder
        self.__tools = [
            {
                "type": "function",
                "function": {
                    "name": "follow",
                    "description": "Makes an NPC follow the player.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "npc_list": {
                                "type": "array",
                                "description": "The list of NPCs (by name) to follow the player. Defaults to all NPCs in the conversation.",
                                "items": {
                                    "type": "string"
                                }
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "attack",
                    "description": "Make any number of NPCs attack a target NPC.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_npc_list": {
                                "type": "array",
                                "description": "The list of NPCs (by name) to attack the target NPC. Defaults to all NPCs in the conversation.",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "target_npc": {
                                "type": "string",
                                "description": "The NPC (by name) to attack."
                            }
                        },
                        "required": [
                            "target_npc"
                        ]
                    }
                }
            }
        ]


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
    def check_for_actions(self, messages: message_thread, response_so_far: str, context) -> list[dict] | None:
        """Check if any actions should be called based on the conversation
        
        Args:
            messages: The conversation thread to analyze
            response_so_far: The first sentence returned by the LLM for additional context
            context: The conversation Context object for generating context-aware tools
            
        Returns:
            Parsed function call results or None if no actions needed
        """
        
        logging.log(23, f"Function LLM analyzing conversation for potential actions...")

        # Generate context-aware tools dynamically
        tools = FunctionManager.generate_context_aware_tools(context)
        
        if not tools:
            logging.debug("No available actions for current context")
            return None

        thread = message_thread(self.__config, self.__prompt)
        context_message = UserMessage(self.__config, f'User: {messages.get_last_message().text}\n\nAssistant: {response_so_far}')
        thread.add_message(context_message)
        
        # Call the function LLM with tools
        tools_called = self.request_call_with_tools(thread, tools)
        
        if not tools_called:
            logging.debug("No response from Function LLM")
            return None
        
        # Parse the function calls
        parsed_tools = FunctionManager.parse_function_calls(tools_called)
        
        if parsed_tools:
            logging.log(23, f"Function calling detected: {len(parsed_tools)} function(s) called")
        else:
            logging.debug("No function calls detected in LLM response")
        
        return parsed_tools
