from abc import ABC, abstractmethod
from enum import Enum

from src.character_manager import Character
from src.llm.sentence_content import SentenceTypeEnum, SentenceContent

class MarkedTextStateEnum(Enum):
    UNMARKED = 1
    MARKED_SPEECH = 2
    MARKED_NARRATION = 3

class sentence_generation_settings:
    """Data holding class to contain any information that need to be exchanged between parsers
    """
    def __init__(self, current_speaker: Character) -> None:
        self.__sentence_type: SentenceTypeEnum = SentenceTypeEnum.SPEECH
        self.__unmarked_text: SentenceTypeEnum = SentenceTypeEnum.SPEECH
        self.__current_text_state: MarkedTextStateEnum = MarkedTextStateEnum.UNMARKED
        self.__current_speaker: Character = current_speaker
        self.__stop_generation: bool = False
    
    @property
    def sentence_type(self) -> SentenceTypeEnum:
        return self.__sentence_type
    
    @sentence_type.setter
    def sentence_type(self, sentence_type: SentenceTypeEnum):
        self.__sentence_type = sentence_type

    @property
    def unmarked_text(self) -> SentenceTypeEnum:
        return self.__unmarked_text
    
    @unmarked_text.setter
    def unmarked_text(self, unmarked_text_is: SentenceTypeEnum):
        self.__unmarked_text = unmarked_text_is

    @property
    def current_text_state(self) -> MarkedTextStateEnum:
        return self.__current_text_state
    
    @current_text_state.setter
    def current_text_state(self, current_text_state: MarkedTextStateEnum):
        self.__current_text_state = current_text_state

    @property
    def current_speaker(self) -> Character:
        return self.__current_speaker
    
    @current_speaker.setter
    def current_speaker(self, current_speaker: Character):
        self.__current_speaker = current_speaker

    @property
    def stop_generation(self) -> bool:
        return self.__stop_generation
    
    @stop_generation.setter
    def stop_generation(self, stop_generation: bool):
        self.__stop_generation = stop_generation

class output_parser(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[SentenceContent|None, str]:
        pass

    @abstractmethod
    def modify_sentence_content(self, cut_content: SentenceContent, last_content: SentenceContent | None, settings: sentence_generation_settings) -> tuple[SentenceContent | None, SentenceContent | None]:
        return cut_content, last_content
    
    def get_cut_indicators(self) -> list[str]:
        return []
