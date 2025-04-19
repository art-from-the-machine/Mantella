import logging
import json
import os
import re
from typing import List
from threading import Lock
from threading import Thread
from src.output_manager import ChatManager
from src.llm.message_thread import message_thread
from src.llm.messages import user_message, system_message
from src.conversation.context import context
from src.function_inference.tools_manager import ToolsManager
from src.function_inference.llm_function_class import LLMFunction,LLMOpenAIfunction, Source, ContextPayload, Target, LLMFunctionCondition
from src.function_inference.llm_tooltip_class import TargetInfo, Tooltip, ModeInfo
from src.function_inference.llm_function_class import Target
from src.llm.sentence import sentence
from itertools import zip_longest



class FunctionManager:
    
    #CUSTOM CONTEXT VALUES
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_ENABLED: str = "mantella_function_enabled"

    #CUSTOM ACTOR VALUES
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISPLAYNAMES: str = "mantella_function_npc_display_names"
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISTANCES: str = "mantella_function_npc_distances"
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCIDS: str = "mantella_function_npc_ids"
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_STIMPAK_ACTOR_LIST: str  = "mantella_function_npc_stimpak_list"
    KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_RADAWAY_ACTOR_LIST: str  = "mantella_function_npc_radaway_list"
    KEY_CONTEXT_CUSTOMVALUES_ACTORS_ALL_FOLLOWERS : bool = "mantella_actors_all_followers"
    KEY_CONTEXT_CUSTOMVALUES_ACTORS_ALL_SETTLERS : bool = "mantella_actors_all_settlers"
    KEY_CONTEXT_CUSTOMVALUES_ACTORS_ALL_GENERICNPCS : bool = "mantella_actors_all_generic_npcs"
    KEY_CONTEXT_CUSTOMVALUES_ACTORS_AT_LEAST_ONE_FOLLOWER: bool = "mantella_actors_one_follower"
    KEY_CONTEXT_CUSTOMVALUES_ACTORS_AT_LEAST_ONE_SETTLER: bool = "mantella_actors_one_settler"
    KEY_CONTEXT_CUSTOMVALUES_ACTORS_AT_LEAST_ONE_GENERIC: bool = "mantella_actors_one_generic"
    

    #The tooltips below are part of the dictionary create_tooltip_dict()
    KEY_TOOLTIPS_NPC_TARGETING : str = "npc_targeting_tooltip"
    KEY_TOOLTIPS_LOOT_ITEMS : str = "loot_items_tooltip"
    KEY_TOOLTIPS_PARTICIPANTS_NPCS_PLAYERLESS:str = "npc_participants_playerless_tooltip"
    KEY_TOOLTIPS_PARTICIPANTS_NPCS:str = "npc_participants_tooltip"
    KEY_TOOLTIPS_FO4_NPC_CARRY_ITEM_LIST_TOOLTIP:str = "fo4_npc_carry_item_list_tooltip"
    

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
            self.__standard_tooltips = self.create_tooltip_dict()
            self.initialized = True  # Mark the instance as initialized
            functions_folder = 'data/actions/functions'
            loaded_functions = self.load_functions_from_json(functions_folder)
            for function in loaded_functions:
                self.__tools_manager.add_function(function)
                logging.debug(f"LLM Functions : loaded from {functions_folder}")
                logging.debug(function.get_formatted_LLMFunction())
            conditions_folder = 'data/actions/conditions'
            loaded_conditions = self.load_conditions_from_json(conditions_folder)
            for condition in loaded_conditions:
                self.__tools_manager.add_condition(condition)
                logging.debug(f"LLM Conditions : loaded from {conditions_folder}")
                logging.debug(condition.__repr__())
            custom_tooltips_folder = 'data/actions/tooltips'
            loaded_custom_tooltips = self.load_custom_tooltips_from_json(custom_tooltips_folder)
            for custom_tooltip in loaded_custom_tooltips:
                self.__tools_manager.add_custom_tooltip(custom_tooltip)
                logging.debug(f"LLM Custom tooltips : loaded from {custom_tooltips_folder}")
                logging.debug(custom_tooltip.tooltip_name)
        else:
            self.context = context_for_conversation
            self.__output_manager: ChatManager = output_manager
            self.__output_manager.generated_function_results = None #Ensure to empty the output from LLM before proceeding further
            self.__generation_thread = generation_thread  # Ensure this is always initialized
            self.__tools_manager.clear_all_active_tooltips()
            self.__tools_manager.clear_all_context_payloads()
    
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







    #################################
    # Main functions
    #################################
    

    def process_function_call(self, mainConversationThreadMessages, lastUserMessage):
        '''Main workhorse for the function call handling this function will parse the context and json files to build a tools set and a prompt to send to the LLM.
        Then it will parse the results and send those back to the conversation script'''
        logging.debug(f"Intiating function call preparation")
        self.__tools_manager.clear_all_active_tooltips()
        self.clear_llm_output_data()  # Initialize to None for safety
        processed_game_name = self.__context.config.game.lower().replace(" ", "")
        
        characters = self.context.npcs_in_conversation.get_all_characters()
        conversation_is_multi_npc = self.__context.npcs_in_conversation.contains_multiple_npcs()
        # Iterate through the characters to find the first non-player character
        playerName = ""
        speakerName = ""
        for character in characters:
            if character.is_player_character:
                playerName = character.name
            if not character.is_player_character:
                speakerName = character.name

        toolsToSend, system_prompt_array = self.gather_functions_and_tooltips_to_send(
            processed_game_name=processed_game_name,
            conversation_is_multi_npc=conversation_is_multi_npc,
            playerName=playerName
            )                  

        if toolsToSend:
            
            system_prompt_LLMFunction_instructions = self.format_system_prompt_instructions(system_prompt_array)
            logging.debug(f"Functions sent to Function LLM : {toolsToSend}")
            tooltipsToAppend = self.__tools_manager.list_all_tooltips()
            logging.debug(f"Tooltips sent to Function LLM is {tooltipsToAppend}")
            #the message below will need to be customized dynamically according to what is sent to the LLM.

            if conversation_is_multi_npc:
                if self.__context.config.function_llm_api == 'OpenAI':
                    initial_system_message = self.__context.config.function_LLM_OpenAI_multi_NPC_prompt
                else:
                    initial_system_message = self.__context.config.function_LLM_multi_NPC_prompt
            else:
                if self.__context.config.function_llm_api == 'OpenAI':
                    initial_system_message = self.__context.config.function_LLM_OpenAI_single_NPC_prompt
                else:
                    initial_system_message = self.__context.config.function_LLM_single_NPC_prompt
            
            kwargs={
                "speakerName": speakerName,
                "playerName": playerName,
                "system_prompt_LLMFunction_instructions": system_prompt_LLMFunction_instructions,
                "toolsToSend": toolsToSend
            }
            initial_system_message = self.format_with_stop_marker(initial_system_message, "NO_REGEX_FORMATTING_PAST_THIS_POINT", **kwargs)
            self.__messages = message_thread(initial_system_message)
            self.__messages.add_message(user_message(tooltipsToAppend)) 
            self.__messages.add_message(user_message(lastUserMessage)) 
            result_was_generated:bool = True
            self.__generation_thread = Thread(
                target=self.__output_manager.generate_simple_response_from_message_thread, 
                args=[self.__messages, "function", toolsToSend]
            )
            self.__generation_thread.start()

            # Wait at most 5 seconds for the LLM response
            self.__generation_thread.join(timeout=self.__context.config.function_LLM_timeout)

            if self.__generation_thread.is_alive():
                logging.warning("LLM generation took too long. Proceeding without the LLM result.")
                result_was_generated=False

            self.__generation_thread = None
            if not result_was_generated:
                return None
            else:
                result_message = self._handle_generated_function_results(
                speakerName=speakerName,
                playerName=playerName
                )
                if result_message:
                    return result_message #Returning the result to Conversation script
        else:
            logging.debug("Function Manager : No eligible functions found.")

    def gather_functions_and_tooltips_to_send(
        self,
        processed_game_name: str,
        conversation_is_multi_npc: bool,
        playerName: str
        ):
        """
        Collects and returns all eligible functions (`toolsToSend` and `system_prompt_array`)
        based on the current conversation context and various checks.
        """
        toolsToSend = []
        system_prompt_array = []

        for current_function in self.__tools_manager.get_all_functions():
            current_function:LLMFunction
            # 1) Check if the function is allowed for the current game
            if any(processed_game_name.startswith(game_name.lower().replace(" ", ""))
                for game_name in current_function.allowed_games if game_name.strip()):
                    load_function = True

                    # 2) Check for presence of followers/settlers/generic NPCs
                    if self.check_context_value(self.KEY_CONTEXT_CUSTOMVALUES_ACTORS_AT_LEAST_ONE_FOLLOWER):
                        if not current_function.is_follower_function:
                            #logging.debug(f"Rejecting function {current_function.GPT_func_name} because it contains at least one follower but is is_follower is :  {current_function.is_follower_function}  ")
                            load_function = False

                    if self.check_context_value(self.KEY_CONTEXT_CUSTOMVALUES_ACTORS_AT_LEAST_ONE_SETTLER):
                        if not current_function.is_settler_function:
                            #logging.debug(f"Rejecting function {current_function.GPT_func_name} because it contains at least one settler but is is_settler is :  {current_function.is_settler_function}  ")
                            load_function = False

                    if self.check_context_value(self.KEY_CONTEXT_CUSTOMVALUES_ACTORS_AT_LEAST_ONE_GENERIC):
                        if not current_function.is_generic_npc_function:
                            #logging.debug(f"Rejecting function {current_function.GPT_func_name} because it contains at least one generic but is is_generic_npc is :  {current_function.is_generic_npc_function}  ")
                            load_function = False

                    # 3) Check conversation type (multi/radiant/one-on-one)
                    if load_function:
                        # Radiant conversation = multi-npc with no player in the conversation
                        if conversation_is_multi_npc and not self.__context.npcs_in_conversation.contains_player_character():
                            if not current_function.is_radiant:
                                #logging.debug(f"Rejecting function {current_function.GPT_func_name} because attribute radiant is {current_function.is_radiant}  ")
                                load_function = False
                        elif conversation_is_multi_npc:
                            if not current_function.is_multi_npc:
                                #logging.debug(f"Rejecting function {current_function.GPT_func_name} because attribute multi NPC is {current_function.is_multi_npc}  ")
                                load_function = False
                        else:
                            # Not multi-npc => must be one-on-one
                            if not current_function.is_one_on_one:
                                #logging.debug(f"Rejecting function {current_function.GPT_func_name} because attribute one_on_one is {current_function.is_one_on_one}  ")
                                load_function = False

                    # 4) Build tooltips based on the function’s parameter packages
                    if load_function:
                        if self.KEY_TOOLTIPS_NPC_TARGETING in current_function.parameter_package_key:
                            if not self.build_npc_targeting_tooltip(current_function, exclude_player=False):
                                #logging.debug(f"Rejecting function {current_function.GPT_func_name} due to  an issue with build_npc_targeting_tooltip() ")
                                load_function = False

                        if self.KEY_TOOLTIPS_LOOT_ITEMS in current_function.parameter_package_key:
                            if not self.build_loot_items_tooltips(current_function):
                                #logging.debug(f"Rejecting function {current_function.GPT_func_name} due to  an issue with build_loot_items_tooltips() ")
                                load_function = False

                        if self.KEY_TOOLTIPS_PARTICIPANTS_NPCS_PLAYERLESS in current_function.parameter_package_key:
                            if not self.build_npc_participants_tooltip(current_function, True):
                                #logging.debug(f"Rejecting function {current_function.GPT_func_name} due to  an issue with build_npc_participants_tooltip() ")
                                load_function = False

                        if self.KEY_TOOLTIPS_FO4_NPC_CARRY_ITEM_LIST_TOOLTIP in current_function.parameter_package_key:
                            if not self.build_fo4_npc_carry_item_list_tooltip(current_function):
                                #logging.debug(f"Rejecting function {current_function.GPT_func_name} due to an issue with build_fo4_npc_carry_item_list_tooltip() ")
                                load_function = False

                        # 4b) Build any custom tooltips
                        for parameter_package in current_function.parameter_package_key:
                            if parameter_package not in self.__standard_tooltips.values():
                                current_parameter_package = self.__tools_manager.get_custom_tooltip(parameter_package)
                                if current_parameter_package:
                                    if not self.build_custom_tooltip(current_parameter_package, current_function, playerName):
                                        load_function = False
                                        logging.debug(
                                            f"Rejecting function {current_function.GPT_func_name} "
                                            f"due to an issue with custom parameter package {current_parameter_package}"
                                        )

                    # 5) Check conditions
                    if load_function:
                        if current_function.conditions:
                            for function_condition in current_function.conditions:
                                if self.__tools_manager.evaluate_condition(function_condition, self.__context) is not True:
                                    logging.debug(
                                        f"Rejecting function {current_function.GPT_func_name} "
                                        f"due to failing condition {function_condition}"
                                    )
                                    load_function = False
                                    break

                    # 6) If still valid, add to the list
                    if load_function:
                        toolsToSend.append(current_function.get_formatted_LLMFunction())
                        system_prompt_array.append(current_function.system_prompt_info)

        return toolsToSend, system_prompt_array
    
    def take_post_response_actions(self, sentence_receiving_output:sentence):
        '''
        Handles the presence of a <veto> tag in the returned output
        Handles the modification of the sentence object in case of a successful function call.
        Clears output data if a function has been used to make sure the context_payload doesn't stick around across multiple replies
        Clears the message thread of warnings message so that they don't get sent to the LLM over and over.
        '''
        if sentence_receiving_output.has_veto:
            logging.log(22, f"Cancelling function call {self.llm_output_function_name } due to <veto> tag")
            self.clear_llm_output_data() 
        if self.llm_output_call_type == "function" :
            mantella_function_name = "mantella_" + self.llm_output_function_name
            output_function:LLMFunction = self.__tools_manager.get_function_object(self.llm_output_function_name)
            sentence_receiving_output.actions.append(mantella_function_name)
            if output_function.context_payload.targets:
                target_dec_ids_output = output_function.context_payload.get_targets_dec_ids()
                sentence_receiving_output.target_ids.extend(target_dec_ids_output)   
                #target_names_output = output_function.context_payload.get_targets_names()  #Cancel this as it's not actually used by the game
                #sentence_receiving_output.target_names.extend(target_names_output)  
            if output_function.context_payload.sources:
                source_dec_ids_output = output_function.context_payload.get_sources_dec_ids()
                sentence_receiving_output.source_ids.extend(source_dec_ids_output)
            if output_function.context_payload.modes:
                sentence_receiving_output.function_call_modes.extend(output_function.context_payload.get_modes_lowercase())
            self.clear_llm_output_data() 
        return sentence_receiving_output
    
    #################################
    # Tooltip building
    #################################

    def build_npc_targeting_tooltip(self, current_LLM_function:LLMFunction, exclude_player:bool=True):
        try:
            npc_names_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISPLAYNAMES)
            npc_distances_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISTANCES)
            npc_ids_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCIDS)
        except AttributeError as e:
            logging.debug(f"Function Manager : build_npc_targeting_tooltip: AttributeError encountered: {e}")
            return 
        if npc_ids_str is None:
            return False

        npc_names = self.parse_items(npc_names_str)
        npc_distances = self.parse_items(npc_distances_str)
        npc_ids = self.parse_items(npc_ids_str)

        # Convert distances to floats and IDs to integers
        npc_distances = [float(distance) for distance in npc_distances]
        npc_ids = [int(npc_id) for npc_id in npc_ids]

        player_name=""
        characters = self.context.npcs_in_conversation.get_all_characters()
        for character in characters:
            if character.is_player_character:
                player_name=character.name

        for npc_name, npc_id, npc_distance in zip(npc_names, npc_ids, npc_distances):
            if exclude_player and (npc_name==player_name):             #continue to the next NPC if this is the player and exclude_player is turned on
                continue
            # Ensure distance is at least 1 to prevent the LLM AI from refusing to move towards the player who distance is always 0.
            npc_distance = max(npc_distance, 1.0)
            npc_id=(str(npc_id))
            LLMFunction_target = Target(dec_id=npc_id, name=npc_name, distance=npc_distance)
            current_LLM_function.context_payload.targets.append(LLMFunction_target)

        if not self.__tools_manager.get_tooltip(self.KEY_TOOLTIPS_NPC_TARGETING):
            tooltips_intro = "Here are the values for NPC functions that require targets: "

            npc_tooltips = ""
            for i, target in enumerate(current_LLM_function.context_payload.targets):
                npc_tooltips += f"{i+1}. target name: {target.name}, distance: {target.distance}, target npc ID: {target.dec_id}\n"

            
            tooltips_outro = f"The distances are calculated from {player_name}'s position"
            tooltips = tooltips_intro + npc_tooltips + tooltips_outro
            self.__tools_manager.add_tooltip(self.KEY_TOOLTIPS_NPC_TARGETING, tooltips)
        return True

    def build_npc_participants_tooltip(self, current_LLM_function:LLMFunction, exclude_player:bool=True):
        try:
            npc_names_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCDISPLAYNAMES)
            npc_ids_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_NPCIDS)
        except AttributeError as e:
            logging.debug(f"Function Manager : build_npc_source_tooltip: AttributeError encountered: {e}")
            return 
        if npc_ids_str is None:
            return False

        npc_names = self.parse_items(npc_names_str)
        npc_ids = self.parse_items(npc_ids_str)

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
            logging.debug(f"Function Manager : Error creating loot items tooltip: {e}")
            return False  
        

    def build_fo4_npc_carry_item_list_tooltip(self, current_LLM_function: LLMFunction):
        #This tooltip needs to run with playerless to function properly.
        try:
            npc_with_stimpaks_names_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_STIMPAK_ACTOR_LIST)
            npc_with_radaway_names_str = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_RADAWAY_ACTOR_LIST)
        except AttributeError as e:
            logging.debug(f"Function Manager : Error during build_npc_source_tooltip: AttributeError encountered: {e}")
            return 
        if (npc_with_stimpaks_names_str is None or npc_with_stimpaks_names_str == "") and (npc_with_radaway_names_str is None or npc_with_radaway_names_str == ""):
            return False

        
        if not self.__tools_manager.get_tooltip(self.KEY_TOOLTIPS_FO4_NPC_CARRY_ITEM_LIST_TOOLTIP):
            tooltips_intro = "This is the tooltip for item use: \n"
            available_items_tooltip = "List of available items: "
            npc_radaway_tooltip = ""
            npc_stimpak_tooltip = ""
            item_modes:list = []
            if npc_with_radaway_names_str and npc_with_radaway_names_str != "":
                available_items_tooltip+="radaway"
                item_modes.append("radaway")
            if (npc_with_stimpaks_names_str and npc_with_stimpaks_names_str != "") and (npc_with_radaway_names_str and npc_with_radaway_names_str != ""):  
                available_items_tooltip+=", "
            if npc_with_stimpaks_names_str and npc_with_stimpaks_names_str != "":
                available_items_tooltip+="stimpak"
                item_modes.append("stimpak")
            if npc_with_radaway_names_str and npc_with_radaway_names_str != "":
                npc_radaway_tooltip = f"\nList NPC(s) carrying RadAway : {npc_with_stimpaks_names_str}\n"
            if npc_with_stimpaks_names_str and npc_with_stimpaks_names_str != "":
                npc_stimpak_tooltip = f"\nList NPC(s) carrying Stimpaks : {npc_with_stimpaks_names_str}\n"

            if item_modes :
                current_LLM_function.context_payload.modes.extend(item_modes)
            tooltips = tooltips_intro + available_items_tooltip + npc_radaway_tooltip + npc_stimpak_tooltip 
            self.__tools_manager.add_tooltip(self.KEY_TOOLTIPS_FO4_NPC_CARRY_ITEM_LIST_TOOLTIP, tooltips)
        return True  


    def build_custom_tooltip(self, custom_tooltip: Tooltip, current_LLM_function: LLMFunction, playername: str) -> bool:
        """
        Builds a custom tooltip string from the given Tooltip object (custom_tooltip)
        and updates current_LLM_function.context_payload.targets and .modes.

        Additional requirement:
        - Skip 'target_block' entirely if all name/distance/ID fields were empty
            (i.e., if target_lines is empty).
        - Similarly, skip 'mode_block' if mode_lines is empty.
        
        :param custom_tooltip: The Tooltip object containing target_info and mode_info.
        :param current_LLM_function: The LLMFunction object to be updated with new targets/modes.
        :param playername: Name of the player to substitute into tooltip text.
        :return: True if tooltip was successfully built (and not canceled), False otherwise.
        """

        

        t_info = custom_tooltip.target_info
        m_info = custom_tooltip.mode_info

        def resolve_values(field_dict: dict) -> list:
            """Parses bracketed data & checks cancel_tooltip_if_empty."""
            if not field_dict:
                return []

            context_key = field_dict.get("context_key", "")
            static_values = field_dict.get("static_values", [])
            cancel_if_empty = field_dict.get("cancel_tooltip_if_empty", False)

            if context_key:
                try:
                    context_data = self.__context.get_custom_context_value(context_key)
                except AttributeError:
                    context_data = []
            else:
                context_data = []

            if not context_data:
                context_data = static_values

            if not context_data and cancel_if_empty:
                logging.debug(
                    f"Function manager: build_custom_tooltip() : Tooltip canceled: {field_dict.get('description', 'Field')} is empty & cancel_tooltip_if_empty=True"
                )
                return None

            final_list = []

            def parse_string_to_list(input_str):
                return self.parse_items(input_str.strip())

            if isinstance(context_data, str):
                parsed = parse_string_to_list(context_data)
                final_list.extend(parsed)
            elif isinstance(context_data, list):
                for item in context_data:
                    if isinstance(item, str):
                        parsed = parse_string_to_list(item)
                        final_list.extend(parsed)
                    else:
                        final_list.append(str(item).strip())
            else:
                final_list.append(str(context_data).strip())

            if not final_list and cancel_if_empty:
                logging.debug(
                    f"Function manager: build_custom_tooltip() : Tooltip canceled: no data for {field_dict.get('description', 'Field')} & cancel_tooltip_if_empty=True"
                )
                return None

            return final_list

        # -------------------------------------
        # TARGETS SECTION
        # -------------------------------------
        from src.function_inference.llm_function_class import Target

        target_names_list = resolve_values(t_info.target_names) or []
        target_distances_list = resolve_values(t_info.target_distances) or []
        target_ids_list = resolve_values(t_info.target_ids) or []

        desc_name = t_info.target_names.get("description", "target name: ")
        desc_distance = t_info.target_distances.get("description", "distance: ")
        desc_id = t_info.target_ids.get("description", "target id: ")

        cancel_name = t_info.target_names.get("cancel_tooltip_if_empty", False)
        cancel_id = t_info.target_ids.get("cancel_tooltip_if_empty", False)

        valid_target_tuples = []
        target_lines = []

        for name_val, dist_val, id_val in zip_longest(
            target_names_list, target_distances_list, target_ids_list, fillvalue=""
        ):
            # 1) Handle name
            if not name_val and cancel_name:
                logging.debug("Function manager: build_custom_tooltip() : Skipping entire line: name empty & cancel_tooltip_if_empty=True.")
                continue

            # 2) Handle distance
            #    - If '0', change to '1'
            #    - If empty/unparseable, default to 0.0 (but keep the target)
            if dist_val == "0":
                dist_val = "1"

            distance_float = 0.0
            if dist_val:
                try:
                    candidate = float(dist_val)
                    distance_float = max(candidate, 1.0)
                except ValueError:
                    logging.debug(f"Function manager: build_custom_tooltip() : Distance '{dist_val}' unparseable. Defaulting to 0.0 but keeping the target.")

            # 3) Handle ID
            if not id_val and cancel_id:
                logging.debug("Function manager: build_custom_tooltip() : Skipping entire line: id empty & cancel_tooltip_if_empty=True.")
                continue

            # Create target object & store
            new_target = Target(dec_id=str(id_val), name=name_val, distance=distance_float)
            current_LLM_function.context_payload.targets.append(new_target)
            valid_target_tuples.append((name_val, distance_float, id_val))

        if not valid_target_tuples and cancel_name:
            logging.debug("Function manager: build_custom_tooltip() : No valid targets => returning False because name had cancel_tooltip_if_empty=True.")
            return False

        # Build lines for the valid targets
        for i, (name_val, dist_val, id_val) in enumerate(valid_target_tuples, start=1):
            line_parts = []
            # Only append if non-empty
            if name_val:
                line_parts.append(f"{desc_name}{name_val}")

            dist_str = str(dist_val) if dist_val != 0.0 else ""
            if dist_str:
                line_parts.append(f"{desc_distance}{dist_str}")

            if id_val:
                line_parts.append(f"{desc_id}{id_val}")

            line_str = f"{i}. " + ", ".join(line_parts)
            # If line_parts is empty, line_str would just be "i. "— you can decide if you want to skip it entirely
            # For now, let's only append if line_parts isn't empty
            if line_parts:
                target_lines.append(line_str)

        # If all fields are empty => target_lines will be empty
        if not target_lines:
            # Means we skip target_block entirely
            target_block = ""
        else:
            target_block = "\n".join([
                t_info.targeting_intro or "",
                *target_lines,
                t_info.targeting_outro or ""
            ]).strip()

        # -------------------------------------
        # MODES SECTION
        # -------------------------------------
        function_modes_dict = m_info.function_modes
        modes_list = resolve_values(function_modes_dict) or []

        desc_mode = function_modes_dict.get("description", "mode: ")
        cancel_mode = function_modes_dict.get("cancel_tooltip_if_empty", False)
        valid_modes = []

        for mode_val in modes_list:
            cleaned = mode_val.strip()
            if not cleaned and cancel_mode:
                logging.debug("Function manager: build_custom_tooltip() : Skipping empty mode line because cancel_tooltip_if_empty=True.")
                continue
            current_LLM_function.context_payload.modes.append(cleaned)
            valid_modes.append(cleaned)

        if not valid_modes and cancel_mode:
            logging.debug("Function manager: build_custom_tooltip() : No valid modes => returning False due to cancel_tooltip_if_empty=True.")
            return False

        mode_lines = []
        for i, mode_val in enumerate(valid_modes, start=1):
            line_str = f"{i}. {desc_mode}{mode_val}"
            mode_lines.append(line_str)

        # If all modes were empty => mode_lines is empty => skip mode_block
        if not mode_lines:
            mode_block = ""
        else:
            mode_block = "\n".join([
                m_info.modes_intro or "",
                *mode_lines,
                m_info.modes_outro or ""
            ]).strip()

        # -------------------------------------
        # FINAL COMBINED TOOLTIP TEXT
        # -------------------------------------
        blocks = []
        if target_block:
            blocks.append(target_block)
        if mode_block:
            blocks.append(mode_block)

        final_tooltip_str = "\n\n".join(blocks).strip()
        final_tooltip_str = final_tooltip_str.replace("{playerName}", playername)

        # 1. Check if a tooltip with the same name already exists
        existing_tooltip = self.__tools_manager.get_tooltip(custom_tooltip.tooltip_name)
        if existing_tooltip is not None:
            return True

        if t_info.send_info_to_llm or m_info.send_info_to_llm:
            logging.debug(f"Function manager: build_custom_tooltip() : Adding custom tooltip {custom_tooltip.tooltip_name}:\n{final_tooltip_str}")
            self.__tools_manager.add_tooltip(custom_tooltip.tooltip_name, final_tooltip_str)
        else:
            logging.debug(f"Function manager: build_custom_tooltip() : Tooltip '{custom_tooltip.tooltip_name}' not added (send_info_to_llm=False).")

        return True



    def create_tooltip_dict(self) -> dict:
        """
        Creates a dictionary that maps tooltip keys to their respective values dynamically.
        This ensures that any change in values is accounted for automatically.
        """
        return {
            "KEY_TOOLTIPS_NPC_TARGETING": self.KEY_TOOLTIPS_NPC_TARGETING,
            "KEY_TOOLTIPS_LOOT_ITEMS": self.KEY_TOOLTIPS_LOOT_ITEMS,
            "KEY_TOOLTIPS_PARTICIPANTS_NPCS_PLAYERLESS": self.KEY_TOOLTIPS_PARTICIPANTS_NPCS_PLAYERLESS,
            "KEY_TOOLTIPS_PARTICIPANTS_NPCS": self.KEY_TOOLTIPS_PARTICIPANTS_NPCS,
            "KEY_TOOLTIPS_FO4_NPC_CARRY_ITEM_LIST_TOOLTIP": self.KEY_TOOLTIPS_FO4_NPC_CARRY_ITEM_LIST_TOOLTIP,
        }
    
    def compare_tooltip_values(self, key: str, value: str) -> bool:
        """
        Compare a given key-value pair with the stored dictionary values.
        """
        return self.tooltip_dict.get(key) == value

    ###############################  
    #JSON manipulation and formatting
    ##############################

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
                            conditions = content.get("conditions", [])


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
                                    conditions=conditions,
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
                                    veto_warning=veto_warning,
                                    conditions=conditions,

                                )
                            result.append(function)
            except Exception as e:
                logging.warning(
                    f"Could not load function definition file '{file}' in '{functions_folder}'. "
                    f"Most likely there is an error in the formatting of the file. Error: {e}"
                )
        return result
    
    def load_conditions_from_json(self,directory: str) -> list:
        conditions = []
        if not os.path.exists(directory):
            os.makedirs(directory)
        json_files = [f for f in os.listdir(directory) if f.endswith(".json")]
        
        for file in json_files:
            try:
                with open(os.path.join(directory, file), 'r') as fp:
                    json_object = json.load(fp)
                    if isinstance(json_object, dict):
                        json_object = [json_object]
                    for content in json_object:
                        condition = LLMFunctionCondition(
                            condition_name=content.get("condition_name", ""),
                            condition_type=content.get("condition_type", "boolean_check"),
                            operator_type=content.get("operator_type", "and"),
                            keys_to_check=content.get("keys_to_check", [])
                        )
                        conditions.append(condition)
                        condition_name_str = content.get("condition_name", "")
            except Exception as e:
                logging.warning(
                    f"Could not load condition definition file '{file}' in '{directory}'. "
                    f"Most likely there is an error in the formatting of the file. Error: {e}"
                )
        return conditions

    def load_custom_tooltips_from_json(self, directory: str) -> List[Tooltip]:
        """
        Load and parse tooltip JSON files from the given directory into Tooltip objects.
        
        :param directory: The path to the directory containing JSON files.
        :return: A list of Tooltip objects parsed from the JSON files.
        """
        tooltips = []
        
        # Ensure the directory exists
        if not os.path.exists(directory):
            os.makedirs(directory)
        
        # Gather only .json files
        json_files = [f for f in os.listdir(directory) if f.endswith(".json")]
        
        for file in json_files:
            file_path = os.path.join(directory, file)
            try:
                with open(file_path, 'r') as fp:
                    data = json.load(fp)
                    
                    # If the top-level JSON is a single object, wrap it in a list for consistency
                    if isinstance(data, dict):
                        data = [data]
                    
                    # Iterate over each object in the JSON file (handle arrays of tooltips)
                    for content in data:
                        # Extract top-level fields
                        tooltip_name = content.get("tooltip_name", "")
                        
                        # Safely get the keys_to_check dictionary
                        keys_to_check = content.get("keys_to_check", {})
                        
                        # Extract data for TargetInfo
                        targeting_keys = keys_to_check.get("targeting_keys", {})
                        target_names_dict = targeting_keys.get("target_names", {})
                        target_distances_dict = targeting_keys.get("target_distances", {})
                        target_ids_dict = targeting_keys.get("target_ids", {})
                        targeting_intro = targeting_keys.get("targeting_intro", "")
                        targeting_outro = targeting_keys.get("targeting_outro", "")
                        targeting_send_info = targeting_keys.get("send_info_to_llm", True)
                        
                        # Create a TargetInfo object
                        target_info_obj = TargetInfo(
                            target_names=target_names_dict,
                            target_distances=target_distances_dict,
                            target_ids=target_ids_dict,
                            targeting_intro=targeting_intro,
                            targeting_outro=targeting_outro,
                            send_info_to_llm=targeting_send_info
                        )
                        
                        # Extract data for ModeInfo
                        mode_keys = keys_to_check.get("mode_keys", {})
                        function_modes_dict = mode_keys.get("function_modes", {})
                        modes_intro = mode_keys.get("modes_intro", "")
                        modes_outro = mode_keys.get("modes_outro", "")
                        modes_send_info = mode_keys.get("send_info_to_llm", True)
                        
                        mode_info_obj = ModeInfo(
                            function_modes=function_modes_dict,
                            modes_intro=modes_intro,
                            modes_outro=modes_outro,
                            send_info_to_llm=modes_send_info
                        )
                        
                        # Create the Tooltip object
                        tooltip_obj = Tooltip(
                            tooltip_name=tooltip_name,
                            target_info=target_info_obj,
                            mode_info=mode_info_obj
                        )
                        
                        # Add to our list of results
                        tooltips.append(tooltip_obj)
                        
            except Exception as e:
                logging.warning(
                    f"Could not load custom tooltip file '{file}' in '{directory}'. "
                    f"Check JSON formatting. Error: {e}"
                )
        
        return tooltips



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
            "llm_output_source_name"#,
            #"llm_output_mode"
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

    ###############################  
    #FUNCTION RESULT HANDLING 
    # #############################

    def _handle_generated_function_results(self, speakerName: str, playerName: str) -> str | None:
        """
        Processes self.__output_manager.generated_function_results and either:
        - Returns a string (e.g. formatted LLM warning) if one should be sent to the user
        - Returns None if no message should be returned or if the data is invalid

        :param speakerName: Name of the current NPC speaker (if any).
        :param playerName:  Name of the player character.
        :return: Optional string with an LLM response, or None
        """
        # 1) Check if we have any results at all
        if not self.__output_manager.generated_function_results:
            logging.debug("Function Manager : No function results were generated.")
            return None

        # 2) Unpack and clear
        self.llm_output_call_type, self.llm_output_function_name, self.llm_output_arguments = (
            self.__output_manager.generated_function_results
        )
        self.__output_manager.generated_function_results = None

        # 3) If arguments came back as a JSON string, attempt to decode
        if isinstance(self.llm_output_arguments, str):
            try:
                self.llm_output_arguments = json.loads(self.llm_output_arguments)
            except json.JSONDecodeError as e:
                logging.debug(
                    "Function manager : Error decoding Function LLM JSON output "
                    f"at the decode arguments step: {e}"
                )
                self.clear_llm_output_data()
                return None

        # 4) Now check if the arguments are in dictionary form
        if not isinstance(self.llm_output_arguments, dict):
            logging.debug("Function Manager : llm_output_arguments is not a valid dictionary.")
            return None

        # 5) Get the function by name
        if not isinstance(self.llm_output_function_name, str):
            logging.debug("Function Manager : llm_output_function_name is not a string.")
            return None

        returned_LLMFunction = self.__tools_manager.get_function_object(self.llm_output_function_name)
        if not returned_LLMFunction:
            logging.debug(f"Function Manager : No matching function object named '{self.llm_output_function_name}'.")
            return None

        # 6) Evaluate function's parameter presence
        has_no_params = not returned_LLMFunction.parameter_package_key
        has_source = bool(returned_LLMFunction.context_payload.sources)
        has_target = bool(returned_LLMFunction.context_payload.targets)
        has_modes = bool(returned_LLMFunction.context_payload.modes)

        # 7) If it requires source/target/modes => handle multi-value arguments
        if has_source or has_target or has_modes:
            return self.handle_function_call_with_multiple_value_arguments(
                returned_LLMFunction,
                speakerName=speakerName,
                playerName=playerName,
            )

        # 8) If no parameter_package_key => show a "warning" or "feedback" message
        elif has_no_params:
            formatted_LLM_warning = self.format_LLM_warning(
                returned_LLMFunction,
                speakerName=speakerName,
                playerName=playerName,
            )
            if formatted_LLM_warning:
                return formatted_LLM_warning
            else:
                logging.debug("Function Manager : Issue encountered with formatting LLM Warning")
                self.clear_llm_output_data()

        else:
            # 9) If we reached here, we found an unexpected case
            logging.debug(
                "Function Manager : Unrecognized Parameter key for LLM function. "
                "Try using an empty string: \"\""
            )
            self.clear_llm_output_data()

        # No string to return
        return None

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
                        logging.debug("Function Manager : All targets have been filtered away while parsing results")
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
                llm_output_mode=returned_LLMFunction.context_payload.get_modes_lowercase(),
            )
            if formatted_LLM_warning:
                #logging.debug(f"LLM warning formatted to : {formatted_LLM_warning}")
                return formatted_LLM_warning
            else:
                logging.debug(f"Function Manager : handle_function_call_with_multiple_value_arguments : Function {returned_LLMFunction.GPT_func_name} couldn't be formatted")
                self.clear_llm_output_data()
                

        except Exception as e:
            logging.error(f"Function Manager : handle_function_call_with_multiple_value_arguments :  Error retrieving function call arguments from {returned_LLMFunction.GPT_func_name}, ignoring function call: {e}")
            self.clear_llm_output_data()
            return None
        
    
    
    ##################################
    #Misc functions
    #################################
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

    @staticmethod
    def parse_items(input_string):
        # Parse the strings into lists
        # Remove leading/trailing whitespace and split the string
        items = input_string.strip().split('],[')
        # Clean up each item
        cleaned_items = []
        for item in items:
            item = item.strip('[]')  # Remove any leading/trailing brackets
            item = item.strip()      # Remove leading/trailing whitespace
            cleaned_items.append(item)
        return cleaned_items

    @staticmethod
    def format_with_stop_marker(prompt: str, stop_marker: str, **kwargs) -> str:
        # Split the string at the stop marker
        parts = prompt.split(stop_marker, 1)
        # Format the part before the stop marker
        formatted_part = parts[0].format(**kwargs)
        # Combine the formatted part with the unmodified part after the marker
        if len(parts) > 1:
            return formatted_part + parts[1].lstrip()  # Optional: .lstrip() to remove leading spaces from the second part
        else:
            return formatted_part

    def check_LLM_functions_enabled(self):
            '''Checks if function calling is enabled inside the game'''
            try:
                functions_enabled = self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_FUNCTIONS_ENABLED)
            except AttributeError as e:
                logging.debug(f"Functions not enabled in base game {self.context.config.game} or key value missing. Error type : {e}")
                return False
            return functions_enabled
    
    def check_context_value(self, context_key):
        '''Utility function that adds an extra try block to the context value check before returning it'''
        try:
            return self.__context.get_custom_context_value(context_key)
        except AttributeError as e:
            logging.warning(f"Missing context value for key {context_key} . Error type : {e}")
            return False

    def clear_llm_output_data (self): 
        self.llm_output_call_type = None
        self.llm_output_function_name = None
        self.llm_output_arguments = None
        self.__tools_manager.clear_all_context_payloads()

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







    

