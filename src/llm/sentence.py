from src.character_manager import Character

class sentence:
    """Collection of all the things that make up a sentence said by a character"""
    def __init__(self, speaker: Character, sentence: str, voice_file: str, voice_line_duration: float, is_system_generated_sentence: bool = False) -> None:
        self.__speaker: Character = speaker
        self.__sentence: str = sentence
        self.__voice_file: str = voice_file
        self.__voice_line_duration: float = voice_line_duration
        self.__actions: list[str] = []
        self.__is_system_generated_sentence: bool = is_system_generated_sentence

    @property
    def Speaker(self) -> Character:
        return self.__speaker
    
    @property
    def Sentence(self) -> str:
        return self.__sentence
    
    @property
    def Voice_file(self) -> str:
        return self.__voice_file

    @property
    def Voice_line_duration(self) -> float:
        return self.__voice_line_duration
    
    @property
    def Actions(self) -> list[str]:
        return self.__actions
    
    @property
    def Is_system_generated_sentence(self) -> bool:
        return self.__is_system_generated_sentence