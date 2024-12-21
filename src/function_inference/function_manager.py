import logging
import json
import os
import re
from threading import Lock
from threading import Thread
from src.output_manager import ChatManager
from src.llm.message_thread import message_thread
from src.llm.messages import user_message, system_message
from src.conversation.context import context
from src.function_inference.tools_manager import ToolsManager
from src.function_inference.LLMFunction_class import LLMFunction,LLMOpenAIfunction



class FunctionManager:
    

    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISPLAYNAMES: str = "mantella_function_npc_display_names"
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISTANCES: str = "mantella_function_npc_distances"
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCIDS: str = "mantella_function_npc_ids"

    KEY_TOOLTIPS_NPC_TARGETING : str = "npc_targeting_tooltip"
    KEY_TOOLTIPS_LOOT_ITEMS : str = "loot_items_tooltip"

    _instance = None
    def __new__(cls):
        if not cls._instance:
            cls._instance = super(FunctionManager, cls).__new__(cls)
            cls._instance.initialized = False  # Flag to check initialization
        return cls._instance

    def initialize(self, context_for_conversation, output_manager, generation_thread) -> None:
        if not self.initialized:  # Check if already initialized
            self.__context: context = context_for_conversation 
            self.__context_lock = Lock() 
            self.__output_manager: ChatManager = output_manager
            self.__output_manager.generated_function_results = None #Ensure to empty the output from LLM before proceeding further
            self.__generation_thread = generation_thread  # Ensure this is always initialized
            self.__tools_manager = ToolsManager()
            self.__llm_output_call_type = None
            self.__llm_output_call_type_lock = Lock()
            self.__llm_output_function_name = None
            self.__llm_output_function_name_lock = Lock()
            self.__llm_output_arguments = None
            self.__llm_output_arguments_lock = Lock()
            self.__llm_output_target_id = None
            self.__llm_output_target_id_lock = Lock()
            self.__llm_output_target_name = None
            self.__llm_output_target_name_lock = Lock()
            self.initialized = True  # Mark the instance as initialized
            functions_folder = 'src/function_inference/functions'
            loaded_functions = self.load_functions_from_json(functions_folder)
            for function in loaded_functions:
                self.__tools_manager.add_function(function)
                print("function loaded from json test")
                print(function.get_formatted_LLMFunction())


    
    def is_initialized(self):
        return self.initialized

    @property
    def context(self):
        with self.__context_lock:
            return self.__context

    @context.setter
    def context(self, value):
        with self.__context_lock:
            self.__context = value

    @property
    def llm_output_call_type(self):
        with self.__llm_output_call_type_lock:
            return self.__llm_output_call_type

    @llm_output_call_type.setter
    def llm_output_call_type(self, value):
        with self.__llm_output_call_type_lock:
            self.__llm_output_call_type = value

    @property
    def llm_output_function_name(self):
        with self.__llm_output_function_name_lock:
            return self.__llm_output_function_name

    @llm_output_function_name.setter
    def llm_output_function_name(self, value):
        with self.__llm_output_function_name_lock:
            self.__llm_output_function_name = value

    @property
    def llm_output_arguments(self):
        with self.__llm_output_arguments_lock:
            return self.__llm_output_arguments

    @llm_output_arguments.setter
    def llm_output_arguments(self, value):
        with self.__llm_output_arguments_lock:
            self.__llm_output_arguments = value

    @property
    def llm_output_target_id(self):
        with self.__llm_output_target_id_lock:
            return self.__llm_output_target_id

    @llm_output_target_id.setter
    def llm_output_target_id(self, value):
        with self.__llm_output_target_id_lock:
            self.__llm_output_target_id = value

    @property
    def llm_output_target_name(self):
        with self.__llm_output_target_name_lock:
            return self.__llm_output_target_name

    @llm_output_target_name.setter
    def llm_output_target_name(self, value):
        with self.__llm_output_target_name_lock:
            self.__llm_output_target_name = value
    
    def clear_llm_output_data (self):
        self.llm_output_call_type = None
        self.llm_output_function_name = None
        self.llm_output_arguments = None
        self.llm_output_target_id = None

    def process_function_call(self, mainConversationThreadMessages, lastUserMessage):
        #self.__tools_manager.clear_all_functions()
        self.__tools_manager.clear_all_tooltips()
        self.clear_llm_output_data()  # Initialize to None for safety
        toolsToSend=[]
        system_prompt_array=[]
        print(f"IMPORTANT : All functions are {self.__tools_manager.get_all_functions()}")
        processed_game_name = self.__context.config.game.lower().replace(" ", "")
        current_function:LLMFunction
        for current_function in self.__tools_manager.get_all_functions(): 
            if any(processed_game_name.startswith(game_name.lower().replace(" ", "")) 
                for game_name in current_function.allowed_games if game_name.strip()):
                    if current_function.parameter_package_key == self.KEY_TOOLTIPS_NPC_TARGETING:
                        if self.build_npc_targeting_tooltip():
                            toolsToSend.append(current_function.get_formatted_LLMFunction())
                            system_prompt_array.append(current_function.system_prompt_info)
                    elif current_function.parameter_package_key == self.KEY_TOOLTIPS_LOOT_ITEMS:
                        if self.build_loot_items_tooltips():
                            toolsToSend.append(current_function.get_formatted_LLMFunction())
                            system_prompt_array.append(current_function.system_prompt_info)
                    elif current_function.parameter_package_key == "" :
                        toolsToSend.append(current_function.get_formatted_LLMFunction())
                        system_prompt_array.append(current_function.system_prompt_info)
        #self.build_move_function()
        #self.build_wait_function()
        #self.build_attack_NPC_function()
        #self.build_loot_items_function()
        #toolsToSend = self.__tools_manager.list_all_functions()
        if toolsToSend:
            characters = self.context.npcs_in_conversation.get_all_characters()
            # Iterate through the characters to find the first non-player character
            for character in characters:
                if character.is_player_character:
                    playerName = character.name
                if not character.is_player_character:
                    speakerName = character.name
            system_prompt_LLMFunction_instructions = self.format_system_prompt_instructions(system_prompt_array)
            print(f"toolstosend is {toolsToSend}")
            tooltipsToAppend = self.__tools_manager.list_all_tooltips()
            print(f"tooltipsToAppend is {tooltipsToAppend}")
            #the message below will need to be customized dynamically according to what is sent to the LLM.
            if self.__context.config.function_llm_api == 'OpenAI':
                initial_system_message = f"You are a helpful assistant named {speakerName}. Please analyze the input and respond by calling only one function. {system_prompt_LLMFunction_instructions}. The user might refer to {playerName} as 'me' or 'I'. Do not call more than one function. If no function seems applicable or the command isn't clear then do not return any function."
            else:
                initial_system_message = f"You are a function calling AI model named {speakerName}. You are provided with function signatures within <tools> </tools> XML tags. You may call one or more functions to assist with the user query. If available tools are not relevant in assisting with user query, just respond in natural conversational language. Don't make assumptions about what values to plug into functions. The user might refer to {playerName} as 'me' or 'I'. {system_prompt_LLMFunction_instructions}<tools>{toolsToSend} </tools>"
                #initial_system_message += '''For each function call return a JSON object, with the following pydantic model json schema:
        #{'title': 'FunctionCall', 'type': 'object', 'properties': {'name': {'title': 'Name', 'type': 'string'}, 'arguments': {'title': 'Arguments', 'type': 'object'}}, 'required': ['arguments', 'name']}
        #Each function call should be enclosed within <tool_call> </tool_call> XML tags'''
                initial_system_message += '''For each function call return a JSON object, with the following pydantic model json schema:
        <tool_call>{'title': 'FunctionCall', 'type': 'object', 'properties': {'name': {'title': 'Name', 'type': 'string'}, 'arguments': {'title': 'Arguments', 'type': 'object'}}, 'required': ['arguments', 'name']}</tool_call>'''
            self.__messages = message_thread(initial_system_message)
            self.__messages.add_message(user_message(tooltipsToAppend)) 
            self.__messages.add_message(user_message(lastUserMessage)) 
            self.__generation_thread = Thread(target=self.__output_manager.generate_simple_response_from_message_thread, args=[self.__messages, "function", toolsToSend])
            self.__generation_thread.start()
            self.__generation_thread.join()
            self.__generation_thread = None
            
            if self.__output_manager.generated_function_results:
                print(f"Function Manager received output from Output manager : {self.__output_manager.generated_function_results}")
                self.llm_output_call_type, self.llm_output_function_name, self.llm_output_arguments = self.__output_manager.generated_function_results
                self.__output_manager.generated_function_results = None
                
                if isinstance(self.llm_output_arguments, str):
                    try:
                        self.llm_output_arguments = json.loads(self.llm_output_arguments)
                    except json.JSONDecodeError as e:
                        print("Error decoding JSON:", e)
                        self.clear_llm_output_data()  

                if isinstance(self.llm_output_arguments, dict):
                    returned_LLMFunction=None
                    if isinstance(self.llm_output_function_name, str): #check if it's really a string in case that the LLM spout out gibberish
                        returned_LLMFunction = self.__tools_manager.get_function_object(self.llm_output_function_name)
                    if returned_LLMFunction :
                        if returned_LLMFunction.parameter_package_key == self.KEY_TOOLTIPS_NPC_TARGETING:
                            # NPC targeting: needs npc_id and npc_name
                            return self.handle_function_call_arguments(
                                returned_LLMFunction,
                                speakerName=speakerName,
                                playerName=playerName,
                                target_id_key='npc_id',
                                target_name_key='npc_name'
                            )

                        elif returned_LLMFunction.parameter_package_key == self.KEY_TOOLTIPS_LOOT_ITEMS:
                            # Loot items: needs item_type as target_id
                            return self.handle_function_call_arguments(
                                returned_LLMFunction,
                                speakerName=speakerName,
                                playerName=playerName,
                                target_id_key='item_type'
                            )
                        elif returned_LLMFunction.parameter_package_key == "":
                            formatted_LLM_warning = self.format_LLM_warning(
                                returned_LLMFunction,
                                speakerName=speakerName,
                                playerName=playerName,
                            )
                            return formatted_LLM_warning
                        else:
                            print("Unrecognized Parameter key for LLM function. Try using an empty string : \"\"")
                            self.clear_llm_output_data()
                    else:
                       print("llm_output_function_name is not a string.") 
            
                else:
                    print("llm_output_arguments is not a valid dictionary.")
            else:
                print("No function results were generated.")

    def build_npc_targeting_tooltip(self):
        try:
            npc_names_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISPLAYNAMES)
            npc_distances_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISTANCES)
            npc_ids_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCIDS)
        except AttributeError as e:
            print(f"build_npc_targeting_tooltip: AttributeError encountered: {e}")
            return 
        if npc_ids_str is None:
            return False

        # Parse the strings into lists
        def parse_items(s):
            # Remove leading/trailing whitespace and split the string
            items = s.strip().split('],[')
            # Clean up each item
            cleaned_items = []
            for item in items:
                item = item.strip('[]')  # Remove any leading/trailing brackets
                item = item.strip()      # Remove leading/trailing whitespace
                cleaned_items.append(item)
            return cleaned_items

        npc_names = parse_items(npc_names_str)
        npc_distances = parse_items(npc_distances_str)
        npc_ids = parse_items(npc_ids_str)

        # Convert distances to floats and IDs to integers
        npc_distances = [float(distance) for distance in npc_distances]
        npc_ids = [int(npc_id) for npc_id in npc_ids]

        if not self.__tools_manager.get_tooltip(self.KEY_TOOLTIPS_NPC_TARGETING):
            tooltips_intro = "Here are the values for NPC functions that require targets: "

            npc_tooltips = ""
            for i in range(len(npc_names)):
                npc_tooltips += f"{i+1}. name: {npc_names[i]}, distance: {npc_distances[i]}, npc ID: {npc_ids[i]}\n"
            tooltips_outro = ""
            tooltips = tooltips_intro + npc_tooltips + tooltips_outro
            self.__tools_manager.add_tooltip(self.KEY_TOOLTIPS_NPC_TARGETING, tooltips)
            print("Tooltip built!")
        return True

    def build_loot_items_tooltips(self):
        if not self.__tools_manager.get_tooltip(self.KEY_TOOLTIPS_LOOT_ITEMS):
            tooltips_intro = "Here are the values for loot items functions: "

            tooltips_arrays = [
                ('Possible item types to loot:', ["any", "weapons", "armor","junk","consumables"])
            ]
            tooltips_outro = ""
            tooltips = self.__tools_manager.format_with_multiple_arrays(tooltips_intro, tooltips_arrays, tooltips_outro)
            self.__tools_manager.add_tooltip(self.KEY_TOOLTIPS_LOOT_ITEMS, tooltips)
        return True

    

    def load_functions_from_json(self, functions_folder: str) -> list[LLMFunction]:
        result = []
        if not os.path.exists(functions_folder):
            os.makedirs(functions_folder)
        function_files: list[str] = os.listdir(functions_folder)
        for file in function_files:
            try:
                filename, extension = os.path.splitext(file)
                full_path_file = os.path.join(functions_folder, file)
                if extension == ".json":
                    with open(full_path_file, 'r') as fp:
                        json_object = json.load(fp)
                        if isinstance(json_object, dict):  # If it's a single function, wrap it in a list
                            json_object = [json_object]
                        for content in json_object:
                            # Extract common fields required for LLMFunction
                            GPT_func_name = content.get("GPT_func_name", "")
                            GPT_func_description = content.get("GPT_func_description", "")
                            function_parameters = content.get("function_parameters", {})
                            system_prompt_info = content.get("system_prompt_info", "")
                            GPT_required = content.get("GPT_required", [])
                            is_generic_npc_function = content.get("is_generic_npc_function", False)
                            is_follower_function = content.get("is_follower_function", False)
                            is_settler_function = content.get("is_settler_function", False)
                            is_pre_dialogue = content.get("is_pre_dialogue", True)
                            is_post_dialogue = content.get("is_post_dialogue", False)
                            key = content.get("key", "")
                            is_interrupting = content.get("is_interrupting", False)
                            is_one_on_one = content.get("is_one_on_one", True)
                            is_multi_npc = content.get("is_multi_npc", False)
                            is_radiant = content.get("is_radiant", False)
                            llm_feedback = content.get("llm_feedback", "")
                            parameter_package_key = content.get("parameter_package_key", "")
                            veto_warning = content.get("veto_warning", "")
                            allowed_games = content.get("allowed_games", [])


                            # Process dynamic parameters in system_prompt_info
                            system_prompt_info = system_prompt_info.format(GPT_func_name=GPT_func_name)
                            # Initialize parameters for OpenAI-specific fields
                            additionalProperties = False
                            strict = False
                            parallel_tool_calls = False

                            # Check if OpenAI-specific parameters should be included
                            if self.context.config.function_llm_api.lower() == "openai":
                                # Get OpenAI-specific parameters from JSON or default to False
                                additionalProperties = content.get("additionalProperties", False)
                                strict = content.get("strict", False)
                                parallel_tool_calls = content.get("parallel_tool_calls", False)

                                # Create an instance of LLMOpenAIfunction
                                function = LLMOpenAIfunction(
                                    GPT_func_name=GPT_func_name,
                                    GPT_func_description=GPT_func_description,
                                    function_parameters=function_parameters,
                                    system_prompt_info=system_prompt_info,
                                    GPT_required=GPT_required,
                                    allowed_games=allowed_games,
                                    additionalProperties=bool(additionalProperties),
                                    strict=bool(strict),
                                    parallel_tool_calls=bool(parallel_tool_calls),
                                    is_generic_npc_function=bool(is_generic_npc_function),
                                    is_follower_function=bool(is_follower_function),
                                    is_settler_function=bool(is_settler_function),
                                    is_pre_dialogue=bool(is_pre_dialogue),
                                    is_post_dialogue=bool(is_post_dialogue),
                                    key=key,
                                    is_interrupting=bool(is_interrupting),
                                    is_one_on_one=bool(is_one_on_one),
                                    is_multi_npc=bool(is_multi_npc),
                                    is_radiant=bool(is_radiant),
                                    llm_feedback=llm_feedback,
                                    parameter_package_key=parameter_package_key,
                                    veto_warning=veto_warning,
                                )
                            else:
                                # Create an instance of LLMFunction
                                function = LLMFunction(
                                    GPT_func_name=GPT_func_name,
                                    GPT_func_description=GPT_func_description,
                                    function_parameters=function_parameters,
                                    system_prompt_info=system_prompt_info,
                                    GPT_required=GPT_required,
                                    allowed_games=allowed_games,
                                    is_generic_npc_function=bool(is_generic_npc_function),
                                    is_follower_function=bool(is_follower_function),
                                    is_settler_function=bool(is_settler_function),
                                    is_pre_dialogue=bool(is_pre_dialogue),
                                    is_post_dialogue=bool(is_post_dialogue),
                                    key=key,
                                    is_interrupting=bool(is_interrupting),
                                    is_one_on_one=bool(is_one_on_one),
                                    is_multi_npc=bool(is_multi_npc),
                                    is_radiant=bool(is_radiant),
                                    llm_feedback=llm_feedback,
                                    parameter_package_key=parameter_package_key,
                                    veto_warning=veto_warning

                                )
                            result.append(function)
            except Exception as e:
                logging.warning(
                    f"Could not load function definition file '{file}' in '{functions_folder}'. "
                    f"Most likely there is an error in the formatting of the file. Error: {e}"
                )
        return result

    def format_system_prompt_instructions(self,elements):
        if not elements:
            return ""
        elif len(elements) == 1:
            return f"Prioritize {elements[0]}."
        else:
            # Join all elements with '; or ' as separator
            elements_str = '; or '.join(elements)
            return f"Prioritize {elements_str}."
        
    def extract_placeholders(self, format_string):
        return set(re.findall(r'\{(\w+)\}', format_string))

    def format_LLM_warning(self, returned_LLMFunction:LLMFunction, **kwargs):
        """
        Formats the LLM_warning string of the returned_LLMFunction using provided keyword arguments.

        Parameters:
            returned_LLMFunction: The function object containing the LLM_warning string.
            **kwargs: Arbitrary keyword arguments used for formatting the LLM_warning string.

        Returns:
            The formatted LLM_warning string if formatting is successful.
            Otherwise, returns the unformatted LLM_warning string.
        """
        if self.__context.config.function_enable_veto:
            formatted_output=returned_LLMFunction.veto_warning
        else:
            formatted_output=returned_LLMFunction.llm_feedback
        placeholders = self.extract_placeholders(formatted_output)
        missing_keys = placeholders - kwargs.keys()
        if missing_keys:
            for key in missing_keys:
                kwargs[key] = "Unknown"
            missing_keys_str = ', '.join(missing_keys)
            logging.warning(f"The following placeholders were missing and substituted with 'Unknown': {missing_keys_str}")
        try:
            formatted_LLM_warning = formatted_output.format(**kwargs)
            return formatted_LLM_warning
        except Exception as e:
            logging.error(f"Unexpected error while parsing LLM warning: {e}. Returning unformatted string.")
            return formatted_output

    def extract_single_value_argument(self, argument_name: str) -> str:
        """
        Attempts to extract a single value argument from self.llm_output_arguments.
        If the argument is a list with one element, return that element.
        If it's a scalar (string/int), return it directly.
        If it doesn't exist or is not single-valued, return None.
        """
        value = self.llm_output_arguments.get(argument_name)
        if isinstance(value, list):
            return value[0] if len(value) == 1 else None
        return value

    def handle_function_call_arguments(self, returned_LLMFunction, speakerName, playerName, target_id_key=None, target_name_key=None):
        """
        Generic handler for extracting target ID, target name, and then formatting the LLM warning.
        If target_id_key or target_name_key are provided, extract them.
        If extraction fails, clear llm_output_data and return None.
        Ensures all arguments (strings or ints) are wrapped with apostrophes ('').
        """
        try:
            # Check if all arguments are single-valued
            def is_single_valued(arg):
                if isinstance(arg, list):
                    return len(arg) == 1
                return True

            if not all(is_single_valued(arg) for arg in self.llm_output_arguments.values()):
                print("Arguments are not single-valued as expected.")
                self.clear_llm_output_data()
                return None

            # Ensure all arguments are properly formatted with apostrophes
            self.llm_output_arguments = {
                key: ensure_string(value[0] if isinstance(value, list) else value)
                for key, value in self.llm_output_arguments.items()
            }

            # Extract target ID if requested
            if target_id_key:
                self.llm_output_target_id = self.extract_single_value_argument(target_id_key)
                if self.llm_output_target_id is None:
                    raise ValueError(f"Missing or invalid argument for {target_id_key}")
                self.llm_output_target_id = ensure_string(self.llm_output_target_id)

            # Extract target name if requested
            if target_name_key:
                self.llm_output_target_name = self.extract_single_value_argument(target_name_key)
                if self.llm_output_target_name is None:
                    raise ValueError(f"Missing or invalid argument for {target_name_key}")
                self.llm_output_target_name = ensure_string(self.llm_output_target_name)

            # Format and return the LLM warning
            formatted_LLM_warning = self.format_LLM_warning(
                returned_LLMFunction,
                speakerName=speakerName,
                playerName=playerName,
                llm_output_target_id=self.llm_output_target_id,
                llm_output_target_name=getattr(self, 'llm_output_target_name', None)
            )
            return formatted_LLM_warning

        except Exception as e:
            logging.error(f"Error retrieving function call arguments, ignoring function call: {e}")
            self.clear_llm_output_data()
            return None

def get_function_manager_instance():
    return FunctionManager()

@staticmethod
def is_single_valued(arg):
    if isinstance(arg, list):
        return len(arg) == 1
    # If it's not a list, treat it as a single value by default
    return True

@staticmethod
def ensure_string(value):
    if isinstance(value, int):
        return f"{value}"  # Convert integer to a string wrapped in apostrophes
    return value 





    

