from src.character_manager import Character
from src.llm.sentence_content import SentenceTypeEnum, SentenceContent

class Sentence:
    """Collection of all the things that make up a sentence said by a character"""
    def __init__(self, content: SentenceContent, voice_file: str, voice_line_duration: float, error_message: str | None = None, played_externally: bool = False, synthesis_start_time: float | None = None) -> None:
        self.__content: SentenceContent = content
        self.__voice_file: str = voice_file
        self.__voice_line_duration: float = voice_line_duration
        self.__error_message: str | None = error_message
        self.__played_externally: bool = played_externally
        self.__synthesis_start_time: float | None = synthesis_start_time

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
    def actions(self) -> list[dict]:
        return self.__content.actions
    
    @property
    def is_system_generated_sentence(self) -> bool:
        return self.__content.is_system_generated_sentence
    
    @property
    def error_message(self) -> str | None:
        return self.__error_message

    @property
    def played_externally(self) -> bool:
        """Whether the TTS already played this voiceline externally during synthesis (streamed fast response)"""
        return self.__played_externally

    @property
    def synthesis_start_time(self) -> float | None:
        """The time.perf_counter() timestamp taken just before TTS synthesis of this voiceline began"""
        return self.__synthesis_start_time