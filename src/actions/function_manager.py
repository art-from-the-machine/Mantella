import logging
import json
from pathlib import Path
from openai.types.chat.chat_completion_message import ChatCompletionMessageToolCall

class FunctionManager:
    _actions: dict[str, dict] = {}  # Map identifier -> action data

    @staticmethod
    def parse_function_calls(tools_called: list[ChatCompletionMessageToolCall]) -> list[dict]:
        """Parse function calls from the LLM response
        
        Args:
            tools_called: The result from the LLM
            
        Returns:
            List of parsed function call information
        """
        parsed_tools = []
        
        if tools_called:
            for tool_call in tools_called:
                try:
                    # Find the action identifier from the function name
                    identifier = None
                    for action_id, action_data in FunctionManager._actions.items():
                        if action_data['name'] == tool_call['function']['name']:
                            identifier = action_id
                            break
                    
                    if not identifier:
                        break  # Unknown function, skip

                    try:
                        # While the LLM should return arguments in JSON format, 
                        # the OpenAI package returns them in a string format in case of malformed JSON
                        parsed_arguments = json.loads(tool_call['function']['arguments'])
                    except json.JSONDecodeError:
                        logging.warning(f"Could not parse function arguments as JSON: {tool_call['function']['arguments']}")
                        parsed_arguments = {}

                    parsed_tool = {
                        'identifier': identifier,
                        'arguments': parsed_arguments
                    }
                    
                    parsed_tools.append(parsed_tool)
                    logging.log(23, f"Parsed function call: {tool_call['function']['name']} -> {identifier} with args: {parsed_arguments}")
                except Exception as e:
                    logging.error(f"Error parsing function call: {e}")
        
        return parsed_tools


    @staticmethod
    def load_all_actions() -> None:
        """Load all actions from the data/actions/ folder at server startup"""
        # Get the project root directory (two levels up from this file)
        project_root = Path(__file__).parent.parent.parent
        actions_dir = project_root / "data" / "actions"
        
        if not actions_dir.exists():
            logging.warning(f"Actions directory '{actions_dir}' not found")
            return

        FunctionManager._actions.clear()

        # Load top-level action files
        for file_path in actions_dir.glob("*.json"):
            try:
                FunctionManager._load_action_file(file_path)
            except Exception as e:
                logging.warning(f"Failed to load action file {file_path}: {e}")

        # Load functions folder
        functions_dir = actions_dir / "functions"
        if functions_dir.exists():
            for file_path in functions_dir.glob("*.json"):
                try:
                    FunctionManager._load_action_file(file_path)
                except Exception as e:
                    logging.warning(f"Failed to load function file {file_path}: {e}")

        logging.log(23, f"Loaded {len(FunctionManager._actions)} actions from data/actions/")


    @staticmethod
    def _load_action_file(file_path: Path) -> None:
        """Load a single action file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle both single action and array of actions
        actions_data = data if isinstance(data, list) else [data]

        for action_data in actions_data:
            # Ensure identifier starts with 'mantella_'
            action_data['identifier'] = f"mantella_{action_data['identifier']}" if not action_data['identifier'].startswith('mantella_') else action_data['identifier']

            FunctionManager._actions[action_data['identifier']] = action_data
            logging.debug(f"Loaded action: {action_data['identifier']}")


    @staticmethod
    def generate_context_aware_tools(context) -> list[dict]:
        """Generate OpenAI tools based on current conversation context"""
        tools = []
        
        for action in FunctionManager._actions.values():
            # Filter by game compatibility
            # TODO: Fix this logic and uncomment
            # if 'allowed_games' in action and action['allowed_games']:
            #     game_name = context.config.game.display_name
            #     if game_name not in action['allowed_games']:
            #         continue

            # Filter by conversation type
            is_multi_npc = context.npcs_in_conversation.contains_multiple_npcs()
            if is_multi_npc:
                if not action.get('multi_npc', True):
                    continue
            else:
                if not action.get('one_on_one', True):
                    continue

            # Create OpenAI tool definition
            tool = {
                'type': 'function',
                'function': {
                    'name': action['name'],
                    'description': action['description']
                }
            }

            # Only add parameters if they exist
            if 'parameters' in action:
                tool['function']['parameters'] = {}
                tool['function']['parameters']['type'] = 'object'
                tool['function']['parameters']['properties'] = action['parameters']
                if 'required' in action:
                    tool['function']['parameters']['required'] = action['required']
                
                # Add NPC context to source/target parameters
                FunctionManager._add_npc_context_to_parameters(tool['function']['parameters'], context)

            tools.append(tool)

        return tools


    @staticmethod
    def _add_npc_context_to_parameters(parameters: dict, context) -> None:
        """Add available NPC context to source/target parameters"""
        if 'properties' not in parameters:
            return

        # Get available NPCs
        source_list = context.get_character_names_as_text(should_include_player=False) # Player can't be commanded
        target_list = context.get_character_names_as_text(should_include_player=True)

        # Add context to parameters that reference NPCs
        for param_name, param_def in parameters['properties'].items():
            current_desc = param_def.get('description', '')
            
            # Handle different NPC parameter types
            if 'source' in param_name.lower():
                param_def['description'] = f"{current_desc} Available source NPCs: {source_list}".strip()
            elif 'target' in param_name.lower():
                param_def['description'] = f"{current_desc} Available target NPCs: {target_list}".strip()
            elif 'npc_name' in param_name.lower():
                param_def['description'] = f"{current_desc} Available NPCs: {target_list}".strip()
