from enum import Enum
from src.character_manager import Character

class SentenceTypeEnum(Enum):
    SPEECH = 1
    NARRATION = 2

class SentenceContent:
    """The LLM relevant part of a sentence"""
    def __init__(self, speaker: Character, text: str, sentence_type: SentenceTypeEnum, is_system_generated_sentence: bool = False, actions: list[str] = None) -> None:
        self.__speaker: Character = speaker
        self.__text: str = text
        self.__sentence_type: SentenceTypeEnum = sentence_type
        self.__actions: list[dict] = [] if actions is None else actions
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
    def sentence_type(self) -> SentenceTypeEnum:
        return self.__sentence_type
    
    @sentence_type.setter
    def sentence_type(self, value: SentenceTypeEnum):
        self.__sentence_type = value

    @property
    def actions(self) -> list[dict]:
        return self.__actions
    
    @actions.setter
    def actions(self, value: list[dict]):
        self.__actions = value
    
    @property
    def is_system_generated_sentence(self) -> bool:
        return self.__is_system_generated_sentence
    
    def append_other_sentence_content(self, text_to_append: str, actions_to_append: list[str]):
        self.__text += " " + text_to_append
        for action in actions_to_append:
            if not action in self.__actions:
                self.__actions.append(action)