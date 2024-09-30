import logging
import json
from threading import Lock
from threading import Thread
from src.output_manager import ChatManager
from src.llm.message_thread import message_thread
from src.llm.messages import user_message, system_message
from src.conversation.context import context
from src.function_inference.tools_manager import ToolsManager



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
        self.clear_llm_output_data()  # Initialize to None for safety
        self.build_move_function()
        toolsToSend = self.__tools_manager.list_all_functions()
        tooltipsToAppend = self.__tools_manager.list_all_tooltips()
        #the message below will need to be customized dynamically according to what is sent to the LLM.
        initial_system_message = "You are a helpful assistant. Please analyze the input and respond by calling only one function. Prioritize `pick_item_from_ground` if the input involves items, or `move_character_near_npc` if it involves NPCs. Do not call more than one function. If no function seems applicable or the command isn't clear then do not return any function."
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
                if all(len(arg_list) == 1 for arg_list in self.llm_output_arguments.values()):  # Check all lists have one item only
                    self.llm_output_target_id = self.llm_output_arguments['npc_id'][0]  # Directly pull the NPC ID
                    print("NPC ID retrieved:", self.llm_output_target_id)
                    self.llm_output_target_name = self.llm_output_arguments['npc_name'][0]  # Directly pull the NPC name
                    print("NPC name retrieved:", self.llm_output_target_name)
                else:
                    print("Multiple arguments detected; resetting llm_output_arguments.")
                    self.clear_llm_output_data()  
            else:
                print("llm_output_arguments is not a valid dictionary.")
        else:
            print("No function results were generated.")


    def build_move_function(self):
        try:
            npc_names = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISPLAYNAMES)
            npc_distances = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISTANCES)
            npc_ids = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCIDS)
        except AttributeError:
            return
        print("function_manager.py here is build_move_function() npc_names" )
        print(npc_ids)
        if npc_ids == None:
            return

        tooltips_intro = "Here are the values for move_to_npc_function"
        tooltips_arrays = [
            ('Here\'s a list of possible NPC names to be used as targets "npc_name":', npc_names),
            ('Here\'s a list of distances for the previous NPC names "npc_distance":', npc_distances),
            ('Here\'s a list of NPC IDs for the previous NPC names "npc_id":', npc_ids)
        ]
        tooltips_outro = "All the parameters are listed in the same order."
        tooltips = self.__tools_manager.format_with_multiple_arrays(tooltips_intro, tooltips_arrays, tooltips_outro)
        self.__tools_manager.add_tooltip("move_character_near_npc_tooltip",tooltips)
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
        move_character_function = self.__tools_manager.build_GPT_function(
            GPT_func_name="move_character_near_npc",
            GPT_func_description="Select a target to move the NPC towards.",
            GPT_func_parameters=function_parameters,
            GPT_required=["npc_name", "npc_distance", "npc_id"],  # Required fields
            additionalProperties=False,
            strict=False,
            parallel_tool_calls=False
        )
        # Add the function to the ToolsManager
        self.__tools_manager.add_function("move_character_near_npc", move_character_function)

def get_function_manager_instance():
    return FunctionManager()

    

