import logging
from openai.types.chat.chat_completion_message import ChatCompletionMessageToolCall
import json

class FunctionManager:

    @staticmethod
    def parse_function_calls(tools_called: list[ChatCompletionMessageToolCall]) -> list[dict]:
        """Parse function calls from the LLM response
        
        Args:
            tools_called: The result from the LLM
            tools_available: The tools that were provided to the LLM
            
        Returns:
            Dictionary with parsed function call information
        """
        parsed_tools = []
        
        if tools_called:
            for tool_call in tools_called:
                try:
                    try:
                        # While the LLM should return arguments in JSON format, 
                        # the OpenAI package returns them in a string format in case of malformed JSON
                        parsed_arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        logging.warning(f"Could not parse function arguments as JSON: {tool_call['arguments']}")

                    parsed_tool = {
                        'id': tool_call.id,
                        'name': tool_call.function.name,
                        'arguments': parsed_arguments
                    }
                    
                    parsed_tools.append(parsed_tool)
                    logging.log(23, f"Parsed function call: {parsed_tool['name']} with args: {parsed_tool['arguments']}")
                except Exception as e:
                    logging.error(f"Error parsing function call: {e}")
        
        return parsed_tools
