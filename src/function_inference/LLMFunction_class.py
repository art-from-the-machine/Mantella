class LLMFunction:
    def __init__(
        self,
        GPT_func_name: str,
        GPT_func_description: str,
        function_parameters: dict,
        GPT_required: float,
        is_generic_npc_function: bool = False,
        is_follower_function: bool = False,
        is_settler_function: bool = False,
    ) -> None:
        self.__GPT_func_name: str = GPT_func_name
        self.__GPT_func_description: str = GPT_func_description
        self.__GPT_func_parameters: dict = function_parameters
        self.__GPT_required: float = GPT_required
        self.__is_generic_npc_function: bool = is_generic_npc_function
        self.__is_follower_function: bool = is_follower_function
        self.__is_settler_function: bool = is_settler_function

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
    def GPT_required(self) -> float:
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
        GPT_required: float,
        additionalProperties: bool = False,
        strict: bool = False,
        parallel_tool_calls: bool = False,
        is_generic_npc_function: bool = False,
        is_follower_function: bool = False,
        is_settler_function: bool = False,
    ) -> None:
        super().__init__(
            GPT_func_name,
            GPT_func_description,
            function_parameters,
            GPT_required,
            is_generic_npc_function,
            is_follower_function,
            is_settler_function,
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