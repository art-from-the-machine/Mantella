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
from src.function_inference.LLMFunction_class import LLMFunction,LLMOpenAIfunction, Source, ContextPayload, Target
from src.llm.sentence import sentence



class FunctionManager:
    

    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISPLAYNAMES: str = "mantella_function_npc_display_names"
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISTANCES: str = "mantella_function_npc_distances"
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCIDS: str = "mantella_function_npc_ids"
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_ENABLED: bool = "mantella_function_enabled"
    KEY_ACTOR_CUSTOMVALUES_ACTORS_ALL_FOLLOWERS : bool = "mantella_actors_all_followers"
    KEY_ACTOR_CUSTOMVALUES_ACTORS_ALL_SETTLERS : bool = "mantella_actors_all_settlers"
    KEY_ACTOR_CUSTOMVALUES_ACTORS_ALL_GENERICNPCS : bool = "mantella_actors_all_generic_npcs"

    KEY_TOOLTIPS_NPC_TARGETING : str = "npc_targeting_tooltip"
    KEY_TOOLTIPS_LOOT_ITEMS : str = "loot_items_tooltip"
    KEY_TOOLTIPS_PARTICIPANTS_NPCS_PLAYERLESS:str = "npc_participants_playerless_tooltip"
    KEY_TOOLTIPS_PARTICIPANTS_NPCS:str = "npc_participants_tooltip"
    

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
            self.__llm_output_pending_character_switch = None
            self.__llm_output_pending_character_switch_lock = Lock()
            self.__llm_output_source_ids = None ###################TO REMOVE ###########################
            self.__llm_output_source_ids_lock = Lock()  ###################TO REMOVE ###########################
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


    ########################################## REMOVE THE BELOW, NON FUNCTIONAL###########################################
    @property
    def llm_output_source_ids(self):
        with self.__llm_output_source_ids_lock:
            return self.__llm_output_source_ids

    @llm_output_source_ids.setter
    def llm_output_source_ids(self, value):
        with self.__llm_output_source_ids_lock:
            self.__llm_output_source_ids = value
    


    @property
    def llm_output_pending_character_switch(self):
        with self.__llm_output_pending_character_switch_lock:
            return self.__llm_output_pending_character_switch

    @llm_output_pending_character_switch.setter
    def llm_output_pending_character_switch(self, value):
        with self.__llm_output_pending_character_switch_lock:
            self.__llm_output_pending_character_switch = value
    ##############################################################################################################################
    
    def check_LLM_functions_enabled(self):
            '''Checks if function calling is enabled inside the game'''
            try:
                functions_enabled = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_ENABLED)
            except AttributeError as e:
                print(f"Functions not enabled in base game {self.context.config.game} or key value missing. Error type : {e}")
                return False
            return functions_enabled
    
    def check_context_value(self, context_key):
        '''Utility function that adds an extra try block to the context value check before returning it'''
        try:
            return self.__context.get_custom_context_value(context_key)
        except AttributeError as e:
            print(f"Missing context value for key {context_key} . Error type : {e}")
            return False

    def clear_llm_output_data (self): 
        self.llm_output_call_type = None
        self.llm_output_function_name = None
        self.llm_output_arguments = None
        self.llm_output_target_id = None
        self.llm_output_source_ids  ###################TO REMOVE ###########################
        self.llm_output_pending_character_switch=False  ############TO REMOVE ###########
        self.__tools_manager.clear_all_context_payloads()

    def process_function_call(self, mainConversationThreadMessages, lastUserMessage):
        self.llm_output_pending_character_switch=False  ############TO REMOVE ###########
        #self.__tools_manager.clear_all_functions()
        self.__tools_manager.clear_all_tooltips()
        self.clear_llm_output_data()  # Initialize to None for safety
        toolsToSend=[]
        system_prompt_array=[]
        print(f"IMPORTANT : All functions are {self.__tools_manager.get_all_functions()}")
        processed_game_name = self.__context.config.game.lower().replace(" ", "")
        current_function:LLMFunction
        characters = self.context.npcs_in_conversation.get_all_characters()
        # Iterate through the characters to find the first non-player character
        for character in characters:
            if character.is_player_character:
                playerName = character.name
            if not character.is_player_character:
                speakerName = character.name

        conversation_is_multi_npc = self.__context.npcs_in_conversation.contains_multiple_npcs()
        

        for current_function in self.__tools_manager.get_all_functions(): 
            if any(processed_game_name.startswith(game_name.lower().replace(" ", "")) 
                for game_name in current_function.allowed_games if game_name.strip()):
                    load_function:bool = False


                    #sequential series of check that filters out functions according to NPC type, conversation type and parameter packages
                    #checking follower or generic variables first
                    if current_function.is_follower_function:
                        if self.check_context_value(self.KEY_ACTOR_CUSTOMVALUES_ACTORS_ALL_FOLLOWERS):
                            print(f"Accepting function {current_function.GPT_func_name} because attribute follower_function is {current_function.is_follower_function} and custom value all followers is {self.check_context_value(self.KEY_ACTOR_CUSTOMVALUES_ACTORS_ALL_FOLLOWERS):}  ")
                            load_function=True
                    if current_function.is_settler_function:
                        if self.check_context_value(self.KEY_ACTOR_CUSTOMVALUES_ACTORS_ALL_SETTLERS):
                            print(f"Accepting function {current_function.GPT_func_name} because attribute settler_function is {current_function.is_settler_function} and custom value all settlers is {self.check_context_value(self.KEY_ACTOR_CUSTOMVALUES_ACTORS_ALL_SETTLERS):}  ")
                            load_function=True
                    if current_function.is_generic_npc_function:
                        if self.check_context_value(self.KEY_ACTOR_CUSTOMVALUES_ACTORS_ALL_GENERICNPCS):
                            print(f"Accepting function {current_function.GPT_func_name} because attribute generic_function is {current_function.is_generic_npc_function} and custom value all generic is {self.check_context_value(self.KEY_ACTOR_CUSTOMVALUES_ACTORS_ALL_GENERICNPCS):}  ")
                            load_function=True
                    if load_function==True:
                        #checking if the conversation is multi, radiant or one_on_one and rejecting based on that
                        if conversation_is_multi_npc and not self.__context.npcs_in_conversation.contains_player_character(): #basically checking for radiant conversation here
                            if not current_function.is_radiant:
                                print(f"Rejecting function {current_function.GPT_func_name} because attribute radiant is {current_function.is_radiant}  ")
                                load_function=False
                        elif conversation_is_multi_npc:
                            if not current_function.is_multi_npc:
                                print(f"Rejecting function {current_function.GPT_func_name} because attribute multi NPC is {current_function.is_multi_npc}  ")
                                load_function=False   
                        elif not conversation_is_multi_npc:
                            if not current_function.is_one_on_one:
                                print(f"Rejecting function {current_function.GPT_func_name} because attribute one_on_one is {current_function.is_one_on_one}  ")
                                load_function=False
                        #checking if the necessary data packages are present for targeting functions   
                        if load_function==True:
                            if self.KEY_TOOLTIPS_NPC_TARGETING in current_function.parameter_package_key :
                                if not self.build_npc_targeting_tooltip(current_function,False):
                                    load_function=False
                                    print(f"Rejecting function {current_function.GPT_func_name} of an issue with build_npc_targeting_tooltip() ")
                            if self.KEY_TOOLTIPS_LOOT_ITEMS in current_function.parameter_package_key :
                                if not self.build_loot_items_tooltips(current_function):
                                    load_function=False
                                    print(f"Rejecting function {current_function.GPT_func_name} of an issue with build_loot_items_tooltips() ")
                            if  self.KEY_TOOLTIPS_PARTICIPANTS_NPCS_PLAYERLESS in current_function.parameter_package_key:
                                if not self.build_npc_participants_tooltip(current_function,True):
                                    load_function=False
                                    print(f"Rejecting function {current_function.GPT_func_name} of an issue with build_npc_participants_tooltip() ")
                            if  load_function==True:
                                toolsToSend.append(current_function.get_formatted_LLMFunction())
                                system_prompt_array.append(current_function.system_prompt_info)

                        
        #self.build_move_function()
        #self.build_wait_function()
        #self.build_attack_NPC_function()
        #self.build_loot_items_function()
        #toolsToSend = self.__tools_manager.list_all_functions()
        if toolsToSend:
            
            system_prompt_LLMFunction_instructions = self.format_system_prompt_instructions(system_prompt_array)
            print(f"toolstosend is {toolsToSend}")
            tooltipsToAppend = self.__tools_manager.list_all_tooltips()
            print(f"tooltipsToAppend is {tooltipsToAppend}")
            #the message below will need to be customized dynamically according to what is sent to the LLM.

            if conversation_is_multi_npc:
                if self.__context.config.function_llm_api == 'OpenAI':
                    initial_system_message = f"You are a helpful assistant tasked with executing actions on NPCs in a program. Please analyze the input and respond by calling only one function. {system_prompt_LLMFunction_instructions}. The user might refer to {playerName} as 'me' or 'I'. Do not call more than one function. If no function seems applicable or the command isn't clear then do not return any function."
                else:
                    initial_system_message = f"You are a function calling AI model named {speakerName}. You are provided with function signatures within <tools> </tools> XML tags. You may call one or more functions to assist with the user query. If available tools are not relevant in assisting with user query, just respond in natural conversational language. Don't make assumptions about what values to plug into functions. The user might refer to {playerName} as 'me' or 'I'. {system_prompt_LLMFunction_instructions}<tools>{toolsToSend} </tools>"
                    #initial_system_message += '''For each function call return a JSON object, with the following pydantic model json schema:
            #{'title': 'FunctionCall', 'type': 'object', 'properties': {'name': {'title': 'Name', 'type': 'string'}, 'arguments': {'title': 'Arguments', 'type': 'object'}}, 'required': ['arguments', 'name']}
            #Each function call should be enclosed within <tool_call> </tool_call> XML tags'''
                    initial_system_message += '''For each function call return a JSON object, with the following pydantic model json schema:
            <tool_call>{'title': 'FunctionCall', 'type': 'object', 'properties': {'name': {'title': 'Name', 'type': 'string'}, 'arguments': {'title': 'Arguments', 'type': 'object'}}, 'required': ['arguments', 'name']}</tool_call>'''
            else:
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
                        #Evaluates the function type according to known parameter inside the context_payload instance and the parameter package key
                        has_no_params = not returned_LLMFunction.parameter_package_key
                        has_source = bool(returned_LLMFunction.context_payload.sources)
                        has_target = bool(returned_LLMFunction.context_payload.targets)
                        has_modes = bool(returned_LLMFunction.context_payload.modes)
                        print(f" Returned sources are {returned_LLMFunction.context_payload.sources}")
                        print(f" Returned targets are {returned_LLMFunction.context_payload.targets}")
                        print(f" Returned modes are {returned_LLMFunction.context_payload.modes}")

                        if has_source or has_target or has_modes:
                            return self.handle_function_call_with_multiple_value_arguments(
                                returned_LLMFunction,
                                speakerName=speakerName,
                                playerName=playerName,
                            )
                        elif has_no_params:
                            # No parameter_package_key
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

    def build_npc_targeting_tooltip(self, current_LLM_function:LLMFunction, exclude_player:bool=True):
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


        if exclude_player:
            characters = self.context.npcs_in_conversation.get_all_characters()
            for character in characters:
                if character.is_player_character:
                    player_name=character.name

        for npc_name, npc_id, npc_distance in zip(npc_names, npc_ids, npc_distances):
            if exclude_player and (npc_name==player_name):             #continue to the next NPC if this is the player and exclude_player is turned on
                continue
            npc_id=(str(npc_id))
            LLMFunction_target = Target(dec_id=npc_id, name=npc_name, distance=npc_distance)
            current_LLM_function.context_payload.targets.append(LLMFunction_target)

        if not self.__tools_manager.get_tooltip(self.KEY_TOOLTIPS_NPC_TARGETING):
            tooltips_intro = "Here are the values for NPC functions that require targets: "

            npc_tooltips = ""
            for i, target in enumerate(current_LLM_function.context_payload.targets):
                npc_tooltips += f"{i+1}. target name: {target.name}, distance: {target.distance}, target npc ID: {target.dec_id}\n"

            
            tooltips_outro = ""
            tooltips = tooltips_intro + npc_tooltips + tooltips_outro
            self.__tools_manager.add_tooltip(self.KEY_TOOLTIPS_NPC_TARGETING, tooltips)
        return True

    def build_npc_participants_tooltip(self, current_LLM_function:LLMFunction, exclude_player:bool=True):
        try:
            npc_names_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISPLAYNAMES)
            npc_ids_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCIDS)
        except AttributeError as e:
            print(f"build_npc_source_tooltip: AttributeError encountered: {e}")
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
        npc_ids = parse_items(npc_ids_str)

        # Logic to match names and collect IDs
        characters = self.context.npcs_in_conversation.get_all_characters()
        for name, npc_id in zip(npc_names, npc_ids):
            for character in characters:
                if character.name == name:
                    if character.is_player_character and exclude_player:
                        continue
                    npc_id=(str(npc_id))
                    character_source = Source(dec_id=npc_id, name=character.name)
                    current_LLM_function.context_payload.sources.append(character_source)
                    break
        if exclude_player:
            tooltip_to_build = self.KEY_TOOLTIPS_PARTICIPANTS_NPCS_PLAYERLESS
        else:
            tooltip_to_build = self.KEY_TOOLTIPS_PARTICIPANTS_NPCS

        if not self.__tools_manager.get_tooltip(tooltip_to_build):
            tooltips_intro = "Here are the values for NPC functions that require sources: "

            npc_tooltips = ""
            for i, source in enumerate(current_LLM_function.context_payload.sources):
                npc_tooltips += f"{i+1}. source name: {source.name}, source npc ID: {source.dec_id}\n"

            tooltips_outro = ""
            tooltips = tooltips_intro + npc_tooltips + tooltips_outro
            self.__tools_manager.add_tooltip(tooltip_to_build, tooltips)
            print(f"Tooltip {tooltip_to_build} built!")
        return True

    def build_loot_items_tooltips(self, current_LLM_function: LLMFunction):
        try:
            loot_item_modes = ["any", "weapons", "armor", "junk", "consumables"]

            current_LLM_function.context_payload.modes.extend(loot_item_modes)
            if not self.__tools_manager.get_tooltip(self.KEY_TOOLTIPS_LOOT_ITEMS):
                tooltips_intro = "Here are the values for loot items functions: "
                tooltips_arrays = [
                    ('Possible item types to loot:', loot_item_modes)
                ]
                tooltips_outro = ""
                tooltips = self.__tools_manager.format_with_multiple_arrays(tooltips_intro, tooltips_arrays, tooltips_outro)
                self.__tools_manager.add_tooltip(self.KEY_TOOLTIPS_LOOT_ITEMS, tooltips)
            return True  
        except Exception as e:
            print(f"Error creating loot items tooltip: {e}")
            return False  
        

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

    def format_LLM_warning(self, returned_LLMFunction: LLMFunction, **kwargs):
        """
        Formats the LLM_warning or veto_warning string from the returned_LLMFunction using provided keyword arguments.

        If any of the single-value keys (llm_output_target_id, llm_output_target_name,
        llm_output_source_name, llm_output_mode) end up having more than one value,
        the function will immediately return False.
        """
        # 1. Decide which string to use (veto or feedback)
        if self.__context.config.function_enable_veto:
            formatted_output = returned_LLMFunction.veto_warning
        else:
            formatted_output = returned_LLMFunction.llm_feedback

        # 2. Identify placeholders
        placeholders = self.extract_placeholders(formatted_output)
        missing_keys = placeholders - kwargs.keys()

        # 3. Substitute missing placeholders with 'Unknown'
        if missing_keys:
            for key in missing_keys:
                kwargs[key] = "Unknown"
            missing_keys_str = ', '.join(missing_keys)
            logging.warning(f"The following placeholders were missing and substituted with 'Unknown': {missing_keys_str}")

        # Define the keys that must be single-valued
        single_value_keys = {
            "llm_output_target_id",
            "llm_output_target_name",
            "llm_output_source_name",
            "llm_output_mode"
        }

        # 4. Convert any list placeholders into the "item1, item2 & item3" style
        #    BUT first check whether they are single-valued where appropriate.
        for key, value in kwargs.items():
            # If the key is supposed to be a single value:
            if key in single_value_keys:
                # If it is a list and has more than one item, return False
                bracketed_key = f"{{{key}}}"
                if isinstance(value, list) and len(value) > 1 and bracketed_key in  formatted_output:
                    logging.warning(
                        f"Key '{key}' received multiple values: {value}. "
                        f"Expected single value for '{key}'. Returning False."
                    )
                    return False
            # Proceed to join (or convert) whatever the value is into a string
            kwargs[key] = self.convert_list_to_joined_string(value)

        # 5. Safely format
        try:
            return formatted_output.format(**kwargs)
        except Exception as e:
            logging.error(f"Unexpected error while parsing LLM warning: {e}. Returning unformatted string.")
            return formatted_output
            
    @staticmethod
    def convert_list_to_joined_string(value):
        """
        Converts a list into a string of the form:
        item1, item2, item3 & item4
        If 'value' is not a list, returns str(value) as-is.
        Handles edge cases:
        - Empty list -> ""
        - Single item -> "item1"
        - Two items -> "item1 & item2"
        - More -> "item1, item2, ..., itemN-1 & itemN"
        """
        if not isinstance(value, list):
            return str(value)

        if not value:
            return ""

        if len(value) == 1:
            return str(value[0])

        if len(value) == 2:
            return f"{value[0]} & {value[1]}"

        # If more than two items, join all but the last with commas, 
        # then append '& itemN' at the end.
        return f"{', '.join(str(x) for x in value[:-1])} & {value[-1]}"
   
    def handle_function_call_with_multiple_value_arguments(
        self,
        returned_LLMFunction: LLMFunction,
        speakerName: str,
        playerName: str
    ):
        """
        Handler for extracting multiple arguments from self.llm_output_arguments.
        It checks for keys containing 'mode', 'target', or 'source' and uses
        the appropriate filter_* call on the returned_LLMFunction.context_payload.
        """
        try:
            # 1. Convert every argument value to a *list* of strings
            processed_arguments = {}
            for key, value in self.llm_output_arguments.items():
                if isinstance(value, list):
                    processed_arguments[key] = [ensure_string(v) for v in value]
                else:
                    # Even a single scalar is wrapped in a list so that
                    # the function is more consistent with multi-value usage.
                    processed_arguments[key] = [ensure_string(value)]

            # Update self.llm_output_arguments
            self.llm_output_arguments = processed_arguments

            # 2. Go through each key in processed_arguments and check for
            # the substrings "mode", "target", or "source"
            for key, values_list in processed_arguments.items():
                key_lower = key.lower()

                if "mode" in key_lower:
                    # will recognize any argument that contains mode
                    returned_LLMFunction.context_payload.filter_modes(values_list)

                elif "source" in key_lower:
                    #  will recognize any argument that contains source
                    returned_LLMFunction.context_payload.filter_sources_by_dec_ids(values_list)

                elif "target" in key_lower:
                    # will recognize any argument that contains target
                    stringified = [str(v) for v in values_list]
                    returned_LLMFunction.context_payload.filter_targets_by_dec_ids(stringified)
                    if not returned_LLMFunction.context_payload.targets:
                        print("All targets have been filtered away")
                        return None

            # 3. Format and return the LLM warning/feedback as before
            formatted_LLM_warning = self.format_LLM_warning(
                returned_LLMFunction,
                speakerName=speakerName,
                playerName=playerName,
                # Fill out properties stores in context payload:
                llm_output_target_id=returned_LLMFunction.context_payload.get_targets_dec_ids(),
                llm_output_target_ids=returned_LLMFunction.context_payload.get_targets_dec_ids(),
                llm_output_target_name=returned_LLMFunction.context_payload.get_targets_names(),
                llm_output_target_names=returned_LLMFunction.context_payload.get_targets_names(),
                llm_output_source_name=returned_LLMFunction.context_payload.get_sources_names(),
                llm_output_source_names=returned_LLMFunction.context_payload.get_sources_names(),
                llm_output_mode=returned_LLMFunction.context_payload.get_modes(),
            )
            if formatted_LLM_warning:
                print(f"LLM warning formatted to : {formatted_LLM_warning}")
                return formatted_LLM_warning
            else:
                print(f"Function {returned_LLMFunction.GPT_func_name} couldn't be formatted")

        except Exception as e:
            logging.error(f"Error retrieving function call arguments, ignoring function call: {e}")
            self.clear_llm_output_data()
            return None
        
    def take_post_response_actions(self, sentence_receiving_output:sentence):
        '''
        Handles the presence of a <veto> tag in the returned output
        Handles the modification of the sentence object in case of a successful function call.
        Clears output data if a function has been used to make sure the context_payload doesn't stick around across multiple replies
        Clears the message thread of warnings message so that they don't get sent to the LLM over and over.
        '''
        if sentence_receiving_output.has_veto:
            print(f"Cancelling function call {self.llm_output_function_name } due to <veto> tag")
            if self.__context.npcs_in_conversation.contains_multiple_npcs() and self.__output_manager.is_generating :
                self.llm_output_pending_character_switch=True ############TO REMOVE ###########
            else:
                self.clear_llm_output_data() 
        if self.llm_output_call_type == "function" :
            mantella_function_name = "mantella_" + self.llm_output_function_name
            output_function:LLMFunction = self.__tools_manager.get_function_object(self.llm_output_function_name)
            sentence_receiving_output.actions.append(mantella_function_name)
            if output_function.context_payload.targets:
                target_dec_ids_output = output_function.context_payload.get_targets_dec_ids()
                sentence_receiving_output.target_ids.extend(target_dec_ids_output)   
                target_names_output = output_function.context_payload.get_targets_names()
                sentence_receiving_output.target_names.extend(target_names_output)  
            if output_function.context_payload.sources:
                source_dec_ids_output = output_function.context_payload.get_sources_dec_ids()
                sentence_receiving_output.source_ids.extend(source_dec_ids_output)
            #if self.__context.npcs_in_conversation.contains_multiple_npcs() and self.__output_manager.is_generating :
                #self.llm_output_pending_character_switch=True
            #else:
            self.clear_llm_output_data() 
        if self.__context.config.function_enable_veto:
            self.__messages.remove_LLM_warnings()
        return sentence_receiving_output


##################################
#Script functions
#################################
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





    

