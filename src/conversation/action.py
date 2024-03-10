class action:
    def __init__(self, game_action_identifier: str, keyword: str, info_text: str) -> None:
        self.__game_action_identifier = game_action_identifier
        self.__keyword = keyword
        self.__info_text = info_text

    @property
    def Game_action_identifier(self) -> str:
        return self.__game_action_identifier

    @property
    def Keyword(self) -> str:
        return self.__keyword
    
    @property
    def Info_text(self) -> str:
        return self.__info_text