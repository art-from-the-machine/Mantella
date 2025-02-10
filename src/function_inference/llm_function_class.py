from src.conversation.context import context

class ContextPayload:
    """
    Holds information about context payload such as modes, targets, and sources.
    """
    def __init__(self, modes: list = None, targets: list = None, sources: list = None) -> None:
        if modes is None:
            modes = []
        if targets is None:
            targets = []
        if sources is None:
            sources = []
        self.__modes: list = modes
        self.__targets: list = targets
        self.__sources: list = sources

    @property
    def modes(self) -> list:
        return self.__modes

    @property
    def targets(self) -> list:
        return self.__targets

    @property
    def sources(self) -> list:
        return self.__sources
    
    def filter_sources_by_dec_ids(self, dec_ids: list) -> None:
        """
        Removes sources from the object if their dec_ids do not match any in the provided list.

        Args:
            dec_ids (list): A list of dec_ids to keep.
        """
        self.__sources = [source for source in self.__sources if source.dec_id in dec_ids]

    def get_sources_names(self) -> list:
        """
        Returns a list of all names present in the sources.

        Returns:
            list: A list of names from the sources.
        """
        return [source.name for source in self.__sources]
    
    def get_sources_dec_ids(self) -> list:
        """
        Returns a list of all names present in the sources.

        Returns:
            list: A list of names from the sources.
        """
        return [source.dec_id for source in self.__sources]
    
    def filter_targets_by_dec_ids(self, dec_ids: list) -> None:
        """
        Filters a list of Target objects, keeping only those with dec_ids in the provided list.

        Args:
            targets (list): A list of Target objects.
            dec_ids (list): A list of dec_ids to keep.

        Returns:
            list: A filtered list of Target objects.
        """
        self.__targets =  [target for target in self.__targets if target.dec_id in dec_ids]

    def get_targets_names(self) -> list:
        """
        Returns a list of names from a list of Target objects.

        Args:
            targets (list): A list of Target objects.

        Returns:
            list: A list of names from the targets.
        """
        return [target.name for target in self.__targets]

    def get_targets_dec_ids(self) -> list:
        """
        Returns a list of dec_ids from a list of Target objects.

        Args:
            targets (list): A list of Target objects.

        Returns:
            list: A list of dec_ids from the targets.
        """
        return [target.dec_id for target in self.__targets]
    
    def get_modes_lowercase(self) -> list:
        """
        Returns a list of names from a list of Target objects in lowercase.

        Args:
            targets (list): A list of Target objects.

        Returns:
            list: A list of names from the targets in lowercase. Non-string items are ignored.
        """
        return [mode.lower() for mode in self.__modes if isinstance(mode, str)]
    
    def filter_modes(self, modes_to_keep: list) -> None:
        """
        Filters the modes in the object, keeping only those present in the provided list.

        Args:
            modes_to_keep (list): A list of modes to keep.
        """
        modes_to_keep_lower = {mode.lower() for mode in modes_to_keep if isinstance(mode, str)}
        self.__modes = [mode for mode in self.__modes if isinstance(mode, str) and mode.lower() in modes_to_keep_lower]

class Target:
    """
    Represents a target with an id and a name.
    """
    def __init__(self, dec_id: str, name: str, distance:float) -> None:
        self.__dec_id: str = dec_id
        self.__name: str = name
        self.__distance: str = distance

    @property
    def dec_id(self) -> str:
        return self.__dec_id

    @property
    def name(self) -> str:
        return self.__name
    
    @property
    def distance(self) -> float:
        return self.__distance

    def get_name_by_dec_id(self, dec_id: str) -> str:
        """
        Returns the name associated with the given dec_id.

        Args:
            dec_id (str): The dec_id to look up.

        Returns:
            str: The name associated with the dec_id, or an error message if it doesn't match.
        """
        if self.__dec_id == dec_id:
            return self.__name
        else:
            return "No matching name found for the provided dec_id."




class Source:
    """
    Represents a source with an id and a name.
    """
    def __init__(self, dec_id: str, name: str) -> None:
        self.__dec_id: str = dec_id
        self.__name: str = name

    @property
    def dec_id(self) -> str:
        return self.__dec_id

    @property
    def name(self) -> str:
        return self.__name
    
    def get_name_by_dec_id(self, dec_id: str) -> str:
        """
        Returns the name associated with the given dec_id.

        Args:
            dec_id (str): The dec_id to look up.

        Returns:
            str: The name associated with the dec_id, or an error message if it doesn't match.
        """
        if self.__dec_id == dec_id:
            return self.__name
        else:
            return "No matching name found for the provided dec_id."


class LLMFunction:
    def __init__(
        self,
        GPT_func_name: str,
        GPT_func_description: str,
        function_parameters: dict,
        GPT_required: list,
        allowed_games: list,
        is_generic_npc_function: bool = False,
        is_follower_function: bool = False,
        is_settler_function: bool = False,
        # New properties with default values
        is_pre_dialogue: bool = True,
        is_post_dialogue: bool = False,
        key: str = '',
        is_interrupting: bool = False,
        is_one_on_one: bool = True,
        is_multi_npc: bool = False,
        is_radiant: bool = False,
        llm_feedback: str = '',
        parameter_package_key: list = '',
        system_prompt_info: str = '',
        veto_warning: str = '',
        # Context Payload (defaulting to a ContextPayload object)
        context_payload: ContextPayload = None,
        conditions: list = None,  
    ) -> None:
        if context_payload is None:
            context_payload = ContextPayload()
        if conditions is None:
            conditions = []
        
        self.__GPT_func_name: str = GPT_func_name
        self.__GPT_func_description: str = GPT_func_description
        self.__GPT_func_parameters: dict = function_parameters
        self.__GPT_required: list = GPT_required
        self.__allowed_games: list = allowed_games

        self.__is_generic_npc_function: bool = is_generic_npc_function  
        self.__is_follower_function: bool = is_follower_function        
        self.__is_settler_function: bool = is_settler_function         

        # New properties initialization
        self.__is_pre_dialogue: bool = is_pre_dialogue  # still wip
        self.__is_post_dialogue: bool = is_post_dialogue    # still wip
        self.__key: str = key
        self.__is_interrupting: bool = is_interrupting
        self.__is_one_on_one: bool = is_one_on_one
        self.__is_multi_npc: bool = is_multi_npc
        self.__is_radiant: bool = is_radiant
        self.__llm_feedback: str = llm_feedback
        self.__parameter_package_key: list = parameter_package_key
        self.__system_prompt_info: str = system_prompt_info
        self.__veto_warning: str = veto_warning
        self.__conditions = conditions
        
        # Context Payload
        self.__context_payload: ContextPayload = context_payload
        

    @property
    def GPT_func_name(self) -> str:
        return self.__GPT_func_name

    @property
    def GPT_func_description(self) -> str:
        return self.__GPT_func_description

    @property
    def GPT_func_parameters(self) -> dict:
        return self.__GPT_func_parameters

    @property
    def GPT_required(self) -> list:
        return self.__GPT_required

    @property
    def allowed_games(self) -> list:
        return self.__allowed_games

    @property
    def is_generic_npc_function(self) -> bool:
        return self.__is_generic_npc_function

    @property
    def is_follower_function(self) -> bool:
        return self.__is_follower_function

    @property
    def is_settler_function(self) -> bool:
        return self.__is_settler_function

    # New property methods
    @property
    def is_pre_dialogue(self) -> bool:
        return self.__is_pre_dialogue

    @property
    def is_post_dialogue(self) -> bool:
        return self.__is_post_dialogue

    @property
    def key(self) -> str:
        return self.__key

    @property
    def is_interrupting(self) -> bool:
        return self.__is_interrupting

    @property
    def is_one_on_one(self) -> bool:
        return self.__is_one_on_one

    @property
    def is_multi_npc(self) -> bool:
        return self.__is_multi_npc

    @property
    def is_radiant(self) -> bool:
        return self.__is_radiant

    @property
    def llm_feedback(self) -> str:
        return self.__llm_feedback

    @property
    def parameter_package_key(self) -> list:
        return self.__parameter_package_key

    @property
    def system_prompt_info(self) -> str:
        return self.__system_prompt_info

    @property
    def veto_warning(self) -> str:
        return self.__veto_warning
    
    @property
    def conditions(self) -> list:
        return self.__conditions
    
    @conditions.setter
    def conditions(self, new_conditions: list) -> None:
        if isinstance(new_conditions, list):
            self.__conditions = new_conditions
        else:
            raise TypeError("conditions must be a list of LLMFunctionCondition objects")

    @property
    def context_payload(self) -> ContextPayload:
        return self.__context_payload
    
    @context_payload.setter
    def context_payload(self, new_context_payload: ContextPayload) -> None:
        if new_context_payload is None or isinstance(new_context_payload, ContextPayload):
            self.__context_payload = new_context_payload
        else:
            raise TypeError("context_payload must be an instance of ContextPayload or None")


    def get_formatted_LLMFunction(self) -> dict:
        """
        Returns a dictionary formatted for an LLM function,
        suitable for use with language models.
        """
        return {
            "type": "function",
            "function": {
                "name": self.__GPT_func_name,
                "description": self.__GPT_func_description,
                "parameters": {
                    "type": "object",
                    "properties": self.__GPT_func_parameters,
                    "required": self.__GPT_required,
                },
            },
        }


class LLMOpenAIfunction(LLMFunction):
    def __init__(
        self,
        GPT_func_name: str,
        GPT_func_description: str,
        function_parameters: dict,
        GPT_required: list,
        allowed_games: list,
        additionalProperties: bool = False,
        strict: bool = False,
        parallel_tool_calls: bool = False,
        is_generic_npc_function: bool = False,
        is_follower_function: bool = False,
        is_settler_function: bool = False,
        # New properties with default values
        is_pre_dialogue: bool = True,
        is_post_dialogue: bool = False,
        key: str = '',
        is_interrupting: bool = False,
        is_one_on_one: bool = True,
        is_multi_npc: bool = False,
        is_radiant: bool = False,
        llm_feedback: str = '',
        parameter_package_key: list = '',
        system_prompt_info: str = '',
        veto_warning: str = '',
        conditions: list = None,  
        # Context Payload (defaulting to a ContextPayload object)
        context_payload: ContextPayload = None,
    ) -> None:
        # Pass context_payload into the parent constructor
        super().__init__(
            GPT_func_name=GPT_func_name,
            GPT_func_description=GPT_func_description,
            function_parameters=function_parameters,
            GPT_required=GPT_required,
            allowed_games=allowed_games,
            is_generic_npc_function=is_generic_npc_function,
            is_follower_function=is_follower_function,
            is_settler_function=is_settler_function,
            is_pre_dialogue=is_pre_dialogue,
            is_post_dialogue=is_post_dialogue,
            key=key,
            is_interrupting=is_interrupting,
            is_one_on_one=is_one_on_one,
            is_multi_npc=is_multi_npc,
            is_radiant=is_radiant,
            llm_feedback=llm_feedback,
            parameter_package_key=parameter_package_key,
            system_prompt_info=system_prompt_info,
            veto_warning=veto_warning,
            context_payload=context_payload,
            conditions=conditions,
        )

        self.__additionalProperties: bool = additionalProperties
        self.__strict: bool = strict
        self.__parallel_tool_calls: bool = parallel_tool_calls

    @property
    def additionalProperties(self) -> bool:
        return self.__additionalProperties

    @property
    def strict(self) -> bool:
        return self.__strict

    @property
    def parallel_tool_calls(self) -> bool:
        return self.__parallel_tool_calls

    def get_formatted_LLMFunction(self) -> dict:
        """
        Returns a dictionary formatted for an OpenAI LLM function,
        including OpenAI-specific parameters.
        """
        return {
            "type": "function",
            "function": {
                "name": self.GPT_func_name,
                "description": self.GPT_func_description,
                "parameters": {
                    "type": "object",
                    "properties": self.GPT_func_parameters,
                    "required": self.GPT_required,
                    "additionalProperties": self.additionalProperties,
                },
                "strict": self.strict,
                "parallel_tool_calls": self.parallel_tool_calls,
            },
        }

class LLMFunctionCondition:
    def __init__(self, condition_name, condition_type, operator_type, keys_to_check):
        self.condition_name = condition_name
        self.condition_type = condition_type
        self.operator_type = operator_type
        self.keys_to_check = keys_to_check

    import os
import json
import logging

class LLMFunctionCondition:
    def __init__(self, condition_name, condition_type, operator_type, keys_to_check):
        self._condition_name = condition_name
        self._condition_type = condition_type
        self._operator_type = operator_type
        self._keys_to_check = keys_to_check

    @property
    def condition_name(self):
        return self._condition_name

    @condition_name.setter
    def condition_name(self, value):
        self._condition_name = value

    @property
    def condition_type(self):
        return self._condition_type

    @condition_type.setter
    def condition_type(self, value):
        self._condition_type = value

    @property
    def operator_type(self):
        return self._operator_type

    @operator_type.setter
    def operator_type(self, value):
        self._operator_type = value

    @property
    def keys_to_check(self):
        return self._keys_to_check

    @keys_to_check.setter
    def keys_to_check(self, value):
        self._keys_to_check = value

    def evaluate(self, conversation_context:context):
        """
        Evaluates the condition based on the provided data.
        Assumes the condition_type is 'boolean_check' and all keys_to_check exist in data.
        """

        

        if self.condition_type != "boolean_check":
            logging.warning(f"Function Class : Condition Object {self.condition_name} Unsupported condition type")
        
        values = [bool(self.check_context_value(conversation_context, key)) for key in self.keys_to_check]
        
        if self.operator_type == "and":
            #logging.debug(f"{self.condition_name} evaluates according to 'and' to {all(values)}")
            return all(values)
        elif self.operator_type == "or":
            #logging.debug(f"{self.condition_name} evaluates according to 'or' to {any(values)}")
            return any(values)
        else:
            logging.warning(f"Function class : condition object {self.condition_name} : Unsupported operator type")
        
    
    def check_context_value(self, conversation_context:context, context_key):
    #'''Utility function that adds an extra try block to the context value check before returning it'''
        try:
            return conversation_context.get_custom_context_value(context_key)
        except AttributeError as e:
            logging.warning(f"Function class : condition object {self.condition_name} : Missing context value for key {context_key} . Error type : {e}")
            return False

    def __repr__(self):
        return (f"LLMFunctionCondition(condition_name='{self.condition_name}', "
                f"condition_type='{self.condition_type}', "
                f"operator_type='{self.operator_type}', "
                f"keys_to_check={self.keys_to_check})")