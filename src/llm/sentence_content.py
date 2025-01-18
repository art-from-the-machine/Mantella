from src.character_manager import Character

class sentence_content:
    """The LLM relevant part of a sentence"""
    def __init__(self, speaker: Character, text: str, is_narration: bool, is_system_generated_sentence: bool = False) -> None:
        self.__speaker: Character = speaker
        self.__text: str = text
        self.__is_narration: bool = is_narration
        self.__actions: list[str] = []
        self.__is_system_generated_sentence: bool = is_system_generated_sentence

    @property
    def speaker(self) -> Character:
        return self.__speaker
    
    @property
    def text(self) -> str:
        return self.__text
    
    @text.setter
    def text(self, text: str):
        self.__text = text
    
    @property
    def is_narration(self) -> bool:
        return self.__is_narration

    @property
    def actions(self) -> list[str]:
        return self.__actions
    
    @property
    def is_system_generated_sentence(self) -> bool:
        return self.__is_system_generated_sentence
    
    def append_other_sentence_content(self, text_to_append: str, actions_to_append: list[str]):
        self.__text += " " + text_to_append
        for action in actions_to_append:
            if not action in self.__actions:
                self.__actions.append(action)