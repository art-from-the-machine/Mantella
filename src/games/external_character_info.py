class external_character_info:
    """_summary_
    """
    def __init__(self, name: str, is_generic_npc: bool, bio: str, ingame_voice_model: str, tts_voice_model: str) -> None:
        self.__name: str = name
        self.__is_generic_npc: bool = is_generic_npc
        self.__bio: str = bio
        self.__ingame_voice_model: str = ingame_voice_model
        self.__tts_voice_model: str = tts_voice_model       
    
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