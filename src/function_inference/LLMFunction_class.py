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
        parameter_package_key: str = '',
        system_prompt_info: str = '',
        veto_warning: str = '',
        
    ) -> None:
        self.__GPT_func_name: str = GPT_func_name
        self.__GPT_func_description: str = GPT_func_description
        self.__GPT_func_parameters: dict = function_parameters
        self.__GPT_required: list = GPT_required
        self.__is_generic_npc_function: bool = is_generic_npc_function
        self.__is_follower_function: bool = is_follower_function
        self.__is_settler_function: bool = is_settler_function
        # New properties initialization
        self.__is_pre_dialogue: bool = is_pre_dialogue
        self.__is_post_dialogue: bool = is_post_dialogue
        self.__key: str = key
        self.__is_interrupting: bool = is_interrupting
        self.__is_one_on_one: bool = is_one_on_one
        self.__is_multi_npc: bool = is_multi_npc
        self.__is_radiant: bool = is_radiant
        self.__llm_feedback: str = llm_feedback
        self.__parameter_package_key: str = parameter_package_key
        self.__system_prompt_info: str = system_prompt_info
        self.__veto_warning: str = veto_warning
        self.__allowed_games: str = allowed_games


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
    def parameter_package_key(self) -> str:
        return self.__parameter_package_key

    @property
    def system_prompt_info(self) -> str:
        return self.__system_prompt_info
    
    @property
    def veto_warning(self) -> str:
        return self.__veto_warning 
    
    @property
    def allowed_games(self) -> list:
        return self.__allowed_games

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
        parameter_package_key: str = '',
        system_prompt_info: str = '',
        veto_warning: str = '',

    ) -> None:
        super().__init__(
            GPT_func_name=GPT_func_name,
            GPT_func_description=GPT_func_description,
            function_parameters=function_parameters,
            GPT_required=GPT_required,
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
            veto_warning = veto_warning,
            allowed_games = allowed_games
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