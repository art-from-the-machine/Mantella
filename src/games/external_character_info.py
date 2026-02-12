from typing import List, Tuple


class external_character_info:
    """_summary_
    """
    def __init__(self, name: str, is_generic_npc: bool, bio: str, ingame_voice_model: str, tts_voice_model: str, csv_in_game_voice_model: str, advanced_voice_model: str, voice_accent: str, tts_service: str = "", llm_service: str = "", llm_model: str = "", dynamic_tag_events: List[Tuple[int, str]] | None = None) -> None:
        self.__name: str = name
        self.__is_generic_npc: bool = is_generic_npc
        self.__bio: str = bio
        self.__ingame_voice_model: str = ingame_voice_model
        self.__tts_voice_model: str = tts_voice_model  
        self.__csv_in_game_voice_model: str = csv_in_game_voice_model
        self.__advanced_voice_model: str = advanced_voice_model
        self.__voice_accent: str = voice_accent
        self.__tts_service: str = tts_service
        self.__llm_service: str = llm_service
        self.__llm_model: str = llm_model
        self.__dynamic_tag_events: List[Tuple[int, str]] = dynamic_tag_events if dynamic_tag_events is not None else []
    
    @property
    def name(self) -> str:
        return self.__name
    
    @property
    def is_generic_npc(self) -> bool:
        return self.__is_generic_npc
    
    @property
    def bio(self) -> str:
        return self.__bio
    
    @property
    def ingame_voice_model(self) -> str:
        return self.__ingame_voice_model
    
    @property
    def tts_voice_model(self) -> str:
        return self.__tts_voice_model
    
    @property
    def csv_in_game_voice_model(self) -> str:
        return self.__csv_in_game_voice_model
    
    @property
    def advanced_voice_model(self) -> str:
        return self.__advanced_voice_model
    
    @property
    def voice_accent(self) -> str:
        return self.__voice_accent
    
    @property
    def tts_service(self) -> str:
        return self.__tts_service
    
    @property
    def llm_service(self) -> str:
        return self.__llm_service
    
    @property
    def llm_model(self) -> str:
        return self.__llm_model
    
    @property
    def dynamic_tag_events(self) -> List[Tuple[int, str]]:
        """Dynamic event lines extracted from tag descriptions.

        Each entry is a ``(timestamp, event_text)`` tuple.
        """
        return self.__dynamic_tag_events
