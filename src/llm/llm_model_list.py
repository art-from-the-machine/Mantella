class LLMModelList:            
    def __init__(self, available_models: list[tuple[str, str]], default_model: str, allows_manual_model_input: bool) -> None:
        self.__available_models = available_models
        self.__default_model = default_model
        self.__allows_manual_model_input = allows_manual_model_input

    @property
    def available_models(self) -> list[tuple[str, str]]:
        return self.__available_models

    @property
    def default_model(self) -> str:
        return self.__default_model
    
    @property
    def allows_manual_model_input(self) -> bool:
        return self.__allows_manual_model_input
    
    def is_model_in_list(self, model: str) -> bool:
        if self.__allows_manual_model_input:
            return True
        for model_in_list in self.__available_models:
            if model_in_list[1] == model:
                return True
        return False