import logging
import json
from pathlib import Path
from openai.types.chat.chat_completion_message import ChatCompletionMessageToolCall
from src.characters_manager import Characters
from src.conversation.action import Action

class FunctionManager:
    _actions: dict[str, dict] = {}  # Map identifier -> action data

    @staticmethod
    def parse_function_calls(tools_called: list[ChatCompletionMessageToolCall], characters: Characters = None) -> list[dict]:
        """Parse function calls from the LLM response and validate arguments
        
        Args:
            tools_called: The result from the LLM
            characters: Characters manager for NPC name validation (optional)
            
        Returns:
            List of parsed function call information with validated parameters
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

                    # Get the action definition to validate against
                    action_def = FunctionManager._actions[identifier]
                    defined_params = action_def.get('parameters', {})
                    
                    # Validate that arguments match the schema
                    validated_args = FunctionManager._validate_arguments_against_schema(parsed_arguments, defined_params, identifier)
                    
                    # Validate NPCs named are actually in the conversation / exist
                    if characters:
                        # Handle source parameter (NPCs performing action)
                        if 'source' in validated_args:
                            source_names = validated_args['source']
                            if not isinstance(source_names, list):
                                source_names = [source_names]
                            validated_args['source'] = FunctionManager._validate_npc_names(
                                source_names, characters, exclude_player=True  # Player can't be controlled
                            )

                            # Skip this action if no valid NPCs (e.g., all names were invalid)
                            if len(validated_args['source']) == 0:
                                logging.warning(f"Skipping action '{identifier}' - no valid source NPCs")
                                continue
                        
                        # Handle target parameter (NPCs being acted upon)
                        if 'target' in validated_args:
                            target_names = validated_args['target']
                            if not isinstance(target_names, list):
                                target_names = [target_names]
                            validated_args['target'] = FunctionManager._validate_npc_names(
                                target_names, characters, exclude_player=False  # Player can be target
                            )

                    parsed_tool = {
                        'identifier': identifier
                    }
                    
                    # Only include arguments if there are any,
                    # tools without actions will be treated as basic actions
                    if validated_args:
                        parsed_tool['arguments'] = validated_args
                    
                    parsed_tools.append(parsed_tool)
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

        # TODO: Load new functions folder
        # Load functions folder
        # functions_dir = actions_dir / "functions"
        # if functions_dir.exists():
        #     for file_path in functions_dir.glob("*.json"):
        #         try:
        #             FunctionManager._load_action_file(file_path)
        #         except Exception as e:
        #             logging.warning(f"Failed to load function file {file_path}: {e}")

        logging.log(23, f"Loaded {len(FunctionManager._actions)} actions from data/actions/")


    @staticmethod
    def get_legacy_actions() -> list:
        """Convert loaded actions to legacy Action objects for prompt-based system
        
        Returns:
            List of Action objects for use with the legacy prompt-based action system
        """
        
        result = []
        for action_data in FunctionManager._actions.values():
            identifier = action_data['identifier']
            name = action_data.get('name', '')
            key = action_data.get('key', '')
            description = action_data.get('description', '')
            prompt = action_data.get('prompt', '')
            is_interrupting = bool(action_data.get('is-interrupting', action_data.get('is_interrupting', False)))
            one_on_one = bool(action_data.get('one-on-one', action_data.get('one_on_one', False)))
            multi_npc = bool(action_data.get('multi-npc', action_data.get('multi_npc', False)))
            radiant = bool(action_data.get('radiant', False))
            
            result.append(Action(identifier, name, key, description, prompt, is_interrupting, one_on_one, multi_npc, radiant))
        
        return result


    @staticmethod
    def _load_action_file(file_path: Path) -> None:
        """Load a single action file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle both single action and array of actions
        actions_data = data if isinstance(data, list) else [data]

        for action_data in actions_data:
            # Skip disabled actions (default to enabled if not specified)
            if not action_data.get('enabled', True):
                logging.debug(f"Skipping disabled action: {action_data.get('identifier', 'unknown')}")
                continue
            
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
            if 'allowed_games' in action and action['allowed_games']:
                game_name = context.config.game.display_name.lower().replace(" ", "")
                cleaned_allowed_games = [g.lower().replace(" ", "") for g in action['allowed_games']]
                if game_name not in cleaned_allowed_games:
                    continue

            # Filter by conversation type
            is_multi_npc = context.npcs_in_conversation.contains_multiple_npcs()
            is_radiant = is_multi_npc and not context.npcs_in_conversation.contains_player_character()
            if is_radiant:
                if not action.get('radiant', False):
                    continue
            elif is_multi_npc:
                if not action.get('multi_npc', action.get('multi-npc', False)):
                    continue
            else:
                if not action.get('one_on_one', action.get('one-on-one', False)):
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
    def _validate_arguments_against_schema(llm_arguments: dict, defined_params: dict, action_identifier: str) -> dict:
        """Validate that LLM-provided arguments match the action's parameter schema
        
        Args:
            llm_arguments: Arguments provided by the LLM
            defined_params: Parameter schema from the action JSON config
            action_identifier: Identifier of the action (for logging)
            
        Returns:
            Dictionary containing only valid arguments that match the schema
        """
        validated_args = {}
        
        # Check each LLM-provided argument against the schema
        for arg_name, arg_value in llm_arguments.items():
            if arg_name in defined_params:
                # Argument is valid according to schema
                validated_args[arg_name] = arg_value
            else:
                # LLM hallucinated a parameter that doesn't exist in the schema
                logging.warning(
                    f"LLM provided unknown argument '{arg_name}' for action '{action_identifier}'. "
                    f"Valid parameters are: {list(defined_params.keys())}. Ignoring this argument."
                )
        
        return validated_args


    @staticmethod
    def _validate_npc_names(npc_names: list[str], characters: Characters, exclude_player: bool = True) -> list[str]:
        """Validate that NPC names exist in the conversation
        
        Args:
            npc_names: List of NPC names to validate (from LLM)
            characters: Characters manager containing character information
            exclude_player: If True, filter out player character (default: True)
            
        Returns:
            List of valid, unique NPC names
        """
        if not npc_names:
            return []
        
        # Build case-insensitive lookup: lowercase name -> actual name
        char_names_lower = {name.lower(): name for name in characters.get_all_names()}
        
        valid_names = []
        seen_lower = set()
        
        for llm_name in npc_names:
            llm_lower = llm_name.lower()
            
            if llm_lower in seen_lower:
                continue
            
            if llm_lower in char_names_lower:
                actual_name = char_names_lower[llm_lower]
                
                # Skip player if excluded
                if exclude_player and characters.get_character_by_name(actual_name).is_player_character:
                    continue
                
                valid_names.append(llm_name)  # Preserve LLM casing
                seen_lower.add(llm_lower)
            else:
                logging.warning(f"NPC name '{llm_name}' not found in conversation. Available NPCs: {list(char_names_lower.values())}")
        
        return valid_names


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
