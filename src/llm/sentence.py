from src.character_manager import Character
from src.llm.sentence_content import SentenceTypeEnum, SentenceContent

class Sentence:
    """Collection of all the things that make up a sentence said by a character"""
    def __init__(self, content: SentenceContent, voice_file: str, voice_line_duration: float,  error_message: str | None = None) -> None:
        self.__content: SentenceContent = content
        self.__voice_file: str = voice_file
        self.__voice_line_duration: float = voice_line_duration
        self.__error_message: str | None = error_message

        self.__target_ids: list[int] = []
        self.__target_names: list[str] = []
        self.__source_ids: list[str] = []
        self.__function_call_modes: list[str] = []
        self.__has_veto: bool = False

    @property
    def content(self) -> SentenceContent:
        return self.__content

    @property
    def speaker(self) -> Character:
        return self.__content.speaker
    
    @property
    def text(self) -> str:
        return self.__content.text
    
    @property
    def is_narration(self) -> bool:
        return self.__content.sentence_type == SentenceTypeEnum.NARRATION
    
    @property
    def voice_file(self) -> str:
        return self.__voice_file

    @property
    def voice_line_duration(self) -> float:
        return self.__voice_line_duration
    
    @property
    def actions(self) -> list[str]:
        return self.__content.actions
    
    @property
    def is_system_generated_sentence(self) -> bool:
        return self.__content.is_system_generated_sentence
    
    @property
    def error_message(self) -> str | None:
        return self.__error_message

    @property
    def target_ids(self) -> list[str] | None:
        return self.__target_ids

    @property
    def target_names(self) -> list[str] | None:
        return self.__target_names
    
    @property
    def source_ids(self) -> list[str] | None:
        return self.__source_ids
    
    @property
    def function_call_modes(self) -> list[str] | None:
        return self.__function_call_modes
    
    @property
    def has_veto(self) -> bool:
        return self.__has_veto
    
    @has_veto.setter
    def has_veto(self, value):
        self.__has_veto = value
    