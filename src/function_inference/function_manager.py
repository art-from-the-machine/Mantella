import logging
import json
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
        self.__tools_manager.clear_all_functions()
        self.__tools_manager.clear_all_tooltips()
        self.clear_llm_output_data()  # Initialize to None for safety
        self.build_move_function()
        self.build_wait_function()
        self.build_attack_NPC_function()
        self.build_loot_items_function()
        toolsToSend = self.__tools_manager.list_all_functions()
        print(f"toolstosend is {toolsToSend}")
        tooltipsToAppend = self.__tools_manager.list_all_tooltips()
        print(f"tooltipsToAppend is {tooltipsToAppend}")
        #the message below will need to be customized dynamically according to what is sent to the LLM.
        if self.__context.config.function_llm_api == 'OpenAI':
            initial_system_message = "You are a helpful assistant. Please analyze the input and respond by calling only one function. Prioritize `make_npc_wait` if requested to wait or stop; or `move_character_near_npc` if requested to move or follow; or 'npc_attack_other_npc' if requested to attack or shoot at another NPC; or 'npc_loot_items' if requested to loot, scavenge or collect items. Do not call more than one function. If no function seems applicable or the command isn't clear then do not return any function."
        else:
            initial_system_message = f"You are a function calling AI model. You are provided with function signatures within <tools> </tools> XML tags. You may call one or more functions to assist with the user query. If available tools are not relevant in assisting with user query, just respond in natural conversational language. Don't make assumptions about what values to plug into functions.<tools>{toolsToSend} </tools>"
            #initial_system_message += '''For each function call return a JSON object, with the following pydantic model json schema:
    #{'title': 'FunctionCall', 'type': 'object', 'properties': {'name': {'title': 'Name', 'type': 'string'}, 'arguments': {'title': 'Arguments', 'type': 'object'}}, 'required': ['arguments', 'name']}
    #Each function call should be enclosed within <tool_call> </tool_call> XML tags'''
            initial_system_message += '''For each function call return a JSON object, with the following pydantic model json schema:
    <tool_call>{'title': 'FunctionCall', 'type': 'object', 'properties': {'name': {'title': 'Name', 'type': 'string'}, 'arguments': {'title': 'Arguments', 'type': 'object'}}, 'required': ['arguments', 'name']}</tool_call>'''
        self.__messages = message_thread(initial_system_message)
        self.__messages.add_message(user_message(lastUserMessage)) 
        self.__messages.add_message(user_message(tooltipsToAppend)) 
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
                #if all(len(arg_list) == 1 for arg_list in self.llm_output_arguments.values()):  
                # Check all lists have one item only
                #if all(len(arg_list) == 1 and not (isinstance(arg_list[0], bool) and arg_list[0] == False) for arg_list in self.llm_output_arguments.values()):
                #if self.llm_output_function_name in {"move_character_near_npc", "npc_attack_other_npc"}:
                if self.llm_output_function_name == "move_character_near_npc" or self.llm_output_function_name == "npc_attack_other_npc":
                    if all(len(arg_list) == 1 for arg_list in self.llm_output_arguments.values()):
                        try:
                            self.llm_output_target_id = self.llm_output_arguments['npc_id'][0]  # Directly pull the NPC ID
                            #print("NPC ID retrieved:", self.llm_output_target_id)
                            self.llm_output_target_name = self.llm_output_arguments['npc_name'][0]  # Directly pull the NPC name
                        except:
                            logging.error("Error retrieving function call arguments, ignoring function call: {e}")
                            self.clear_llm_output_data()
                            return
                        #print("NPC name retrieved:", self.llm_output_target_name)
                        characters = self.context.npcs_in_conversation.get_all_characters()
                        # Iterate through the characters to find the first non-player character
                        for character in characters:
                            if character.is_player_character:
                                playerName = character.name
                            if not character.is_player_character:
                                speakerName = character.name
                        ############################ TO DO : move this below to its own function object
                        if self.llm_output_function_name == "move_character_near_npc" :
                            return str(f"{speakerName} is about to move towards {self.llm_output_target_name} at {playerName}'s request. Begin your response with <veto> if {speakerName} would refuse to do that then explain in first person in character why.")
                        else:
                             return str(f"{speakerName} is about to attack {self.llm_output_target_name} at {playerName}'s request. Begin your response with <veto> if {speakerName} would refuse to do that then explain in first person in character why.")
                elif self.llm_output_function_name in {"npc_loot_items"}:
                    if all(len(arg_list) == 1 for arg_list in self.llm_output_arguments.values()):
                        self.llm_output_target_id = self.llm_output_arguments['item_type'][0]  # Directly pull the item type
                        print("Found valid item type.")
                        characters = self.context.npcs_in_conversation.get_all_characters()
                        for character in characters:
                            if character.is_player_character:
                                playerName = character.name
                            if not character.is_player_character:
                                speakerName = character.name
                        return str(f"{speakerName} is about to scavenge {self.llm_output_arguments} items at {playerName}'s request. Begin your response with <veto> if {speakerName} would refuse to do that then explain in first person in character why.")
                    else:
                         print("Issue with the return item output")
                         self.clear_llm_output_data()
                         

                elif self.llm_output_function_name == "make_npc_wait":
                    activate_wait = self.llm_output_arguments['is_waiting']
                    if isinstance(activate_wait, list):
                        # If it's a list, check the first item
                        if not activate_wait[0] == True:
                            print("Unusable output detected; resetting llm_output_arguments.")
                            self.clear_llm_output_data()
                    else:
                        # If it's not a list (direct boolean), use it directly
                        if not activate_wait == True:
                            print("Unusable output detected; resetting llm_output_arguments.")
                            self.clear_llm_output_data()
                    characters = self.context.npcs_in_conversation.get_all_characters()
                    for character in characters:
                        if character.is_player_character:
                            playerName = character.name
                        if not character.is_player_character:
                            speakerName = character.name
                    return str(f"{speakerName} is about to wait at their position at {playerName}'s request. Begin your response with <veto> if {speakerName} would refuse to do that then explain in first person in character why.")
                else:
                    print("Unusable output detected; resetting llm_output_arguments.")
                    self.clear_llm_output_data() 
            else:
                print("llm_output_arguments is not a valid dictionary.")
        else:
            print("No function results were generated.")


    def build_move_function(self):
        try:
            npc_names_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISPLAYNAMES)
            npc_distances_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISTANCES)
            npc_ids_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCIDS)
        except AttributeError as e:
            print(f"build_move_function: AttributeError encountered: {e}")
            return 
        if npc_ids_str is None:
            return

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

        if not self.__tools_manager.get_tooltip("npc_targeting_tooltip"):
            tooltips_intro = "Here are the values for NPC functions that require targets: "


            npc_tooltips = ""
        for i in range(len(npc_names)):
            npc_tooltips += f"{i+1}. name: {npc_names[i]}, distance: {npc_distances[i]}, npc ID: {npc_ids[i]}\n"
            tooltips_outro = "All the parameters are listed in the same order."
            tooltips = tooltips_intro + npc_tooltips + tooltips_outro
            self.__tools_manager.add_tooltip("npc_targeting_tooltip", tooltips)
            '''
            tooltips_arrays = [
                ('Here\'s a list of possible NPC names to be used as targets "npc_name":', npc_names),
                ('Here\'s a list of distances for the previous NPC names "npc_distance":', npc_distances),
                ('Here\'s a list of NPC IDs for the previous NPC names "npc_id":', npc_ids)
            ]
            tooltips_outro = "All the parameters are listed in the same order."
            tooltips = self.__tools_manager.format_with_multiple_arrays(tooltips_intro, tooltips_arrays, tooltips_outro)
            self.__tools_manager.add_tooltip("npc_targeting_tooltip",tooltips)

            '''
        # Build the function using build_GPT_function
        function_parameters = self.__tools_manager.build_dictionary([
            ("npc_name", {
                "type": "array",
                "description": "The name of the target NPC.",
                "items": {"type": "string"}
            }),
            ("npc_distance", {
                "type": "array",
                "description": "The distance from the target NPC.",
                "items": {"type": "number"}
            }),
            ("npc_id", {
                "type": "array",
                "description": "The ID of the target NPC.",
                "items": {"type": "string"}
            })
        ])
        move_character_function=None
        common_params = {
        "GPT_func_name": "move_character_near_npc",
        "GPT_func_description": "Determine where to move a character closest to a specific NPC.",
        "function_parameters": function_parameters,
        "GPT_required": ["npc_names", "distances", "npc_ids"],
        "is_generic_npc_function": False,
        "is_follower_function": False,
        "is_settler_function": False,
        }
        if self.context.config.function_llm_api.lower() == "openai":
            additional_params = {
                "additionalProperties": False,
                "strict": False,
                "parallel_tool_calls": False,
            }
            common_params.update(additional_params)
            move_character_function = LLMOpenAIfunction(**common_params)
        else:
            move_character_function = LLMFunction(**common_params)

        # Add the function to the ToolsManager
        self.__tools_manager.add_function(move_character_function)

    def build_wait_function(self):

        # Build the function using build_GPT_function
        function_parameters = self.__tools_manager.build_dictionary([
            ("is_waiting", {
                "type": "boolean",
                "description": "The name of the target NPC.",
            })
        ])
        common_params = {
        "GPT_func_name": "make_npc_wait",
        "GPT_func_description": "Use this function to make the NPC wait or stop by returning true for is_waiting.",
        "function_parameters": function_parameters,
        "GPT_required": ["is_waiting"],
        "is_generic_npc_function": False,
        "is_follower_function": False,
        "is_settler_function": False,
        }
        if self.context.config.function_llm_api.lower() == "openai":
            additional_params = {
                "additionalProperties": False,
                "strict": False,
                "parallel_tool_calls": False,
            }
            common_params.update(additional_params)
            make_character_wait_function = LLMOpenAIfunction(**common_params)
        else:
            make_character_wait_function = LLMFunction(**common_params)
        # Add the function to the ToolsManager
        self.__tools_manager.add_function(make_character_wait_function)

    def build_attack_NPC_function(self):
        try:
            npc_names = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISPLAYNAMES)
            npc_distances = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISTANCES)
            npc_ids = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCIDS)
        except AttributeError:
            print(f"build_attack_NPC_function :AttributeError encountered: {e}")
            return 
        if npc_ids == None:
            return

        if not self.__tools_manager.get_tooltip("npc_targeting_tooltip"):
            tooltips_intro = "Here are the values for functions that require NPC targets: "
            tooltips_arrays = [
                ('Here\'s a list of possible NPC names to be used as targets "npc_name":', npc_names),
                ('Here\'s a list of distances for the previous NPC names "npc_distance":', npc_distances),
                ('Here\'s a list of NPC IDs for the previous NPC names "npc_id":', npc_ids)
            ]
            tooltips_outro = "All the parameters are listed in the same order."
            tooltips = self.__tools_manager.format_with_multiple_arrays(tooltips_intro, tooltips_arrays, tooltips_outro)
            self.__tools_manager.add_tooltip("npc_targeting_tooltip",tooltips)
        # Build the function using build_GPT_function
        function_parameters = self.__tools_manager.build_dictionary([
            ("npc_name", {
                "type": "array",
                "description": "The name of the target NPC.",
                "items": {"type": "string"}
            }),
            ("npc_distance", {
                "type": "array",
                "description": "The distance from the target NPC.",
                "items": {"type": "number"}
            }),
            ("npc_id", {
                "type": "array",
                "description": "The ID of the target NPC.",
                "items": {"type": "string"}
            })
        ])

        common_params = {
        "GPT_func_name": "npc_attack_other_npc",
        "GPT_func_description": "Use this function to select a target NPC to attack.",
        "function_parameters": function_parameters,
        "GPT_required": ["npc_names", "distances", "npc_ids"],
        "is_generic_npc_function": False,
        "is_follower_function": False,
        "is_settler_function": False,
        }
        if self.context.config.function_llm_api.lower() == "openai":
            additional_params = {
                "additionalProperties": False,
                "strict": False,
                "parallel_tool_calls": False,
            }
            common_params.update(additional_params)
            attack_character_function = LLMOpenAIfunction(**common_params)
        else:
            attack_character_function = LLMFunction(**common_params)
        # Add the function to the ToolsManager
        self.__tools_manager.add_function(attack_character_function)

    def build_loot_items_function(self):

        if not self.__tools_manager.get_tooltip("loot_items_tooltip"):
            tooltips_intro = "Here are the values for loot_items"
            tooltips_arrays = [
                ('Here\'s a list of possible item types to loot :', ["any", "weapon", "armor"])
            ]
            tooltips_outro = " "
            tooltips = self.__tools_manager.format_with_multiple_arrays(tooltips_intro, tooltips_arrays, tooltips_outro)
            self.__tools_manager.add_tooltip("loot_items_tooltip",tooltips)
        # Build the function using build_GPT_function
        function_parameters = self.__tools_manager.build_dictionary([
            ("item_type", {
                "type": "array",
                "description": "The type of item to loot.",
                "items": {"type": "string"}
            })            
        ])
        common_params = {
        "GPT_func_name": "npc_loot_items",
        "GPT_func_description": "Use this function to loot items. If the type of item to loot is unspecified then use 'any'.",
        "function_parameters": function_parameters,
        "GPT_required": ["item_type"],
        "is_generic_npc_function": False,
        "is_follower_function": False,
        "is_settler_function": False,
        }
        if self.context.config.function_llm_api.lower() == "openai":
            additional_params = {
                "additionalProperties": False,
                "strict": False,
                "parallel_tool_calls": False,
            }
            common_params.update(additional_params)
            loot_items_function = LLMOpenAIfunction(**common_params)
        else:
            loot_items_function = LLMFunction(**common_params)
        # Add the function to the ToolsManager
        self.__tools_manager.add_function(loot_items_function)

def get_function_manager_instance():
    return FunctionManager()

    

