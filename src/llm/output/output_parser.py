from abc import ABC, abstractmethod

from src.character_manager import Character
from src.llm.sentence_content import sentence_content

class sentence_generation_settings:
    def __init__(self, current_speaker: Character) -> None:
        self.__is_narration = False
        self.__current_speaker: Character = current_speaker
        self.__stop_generation: bool = False
    
    @property
    def is_narration(self) -> bool:
        return self.__is_narration
    
    @is_narration.setter
    def is_narration(self, is_narration: bool):
        self.__is_narration = is_narration

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
    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[sentence_content|None, str]:
        pass

    @abstractmethod
    def modify_sentence_content(self, content: sentence_content, settings: sentence_generation_settings) -> bool:
        pass
