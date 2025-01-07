class action:
    def __init__(self, identifier: str, name: str, keyword: str, description: str, prompt_text: str, 
                 is_interrupting: bool, one_on_one: bool, multi_npc: bool, radiant: bool, info_text: str) -> None:
        self.__identifier = identifier
        self.__name = name
        self.__keyword = keyword
        self.__description = description
        self.__prompt_text = prompt_text
        self.__is_interrupting = is_interrupting
        self.__one_on_one = one_on_one
        self.__multi_npc = multi_npc
        self.__radiant = radiant
        self.__info_text = info_text

    @property
    def identifier(self) -> str:
        return self.__identifier
    
    @property
    def name(self) -> str:
        return self.__name

    @property
    def keyword(self) -> str:
        return self.__keyword
    
    @property
    def description(self) -> str:
        return self.__description
    
    @keyword.setter
    def keyword(self, value: str):
        self.__keyword = value

    @property
    def prompt_text(self) -> str:
        return self.__prompt_text
    
    @property
    def is_interrupting(self) -> bool:
        return self.__is_interrupting
    
    @property
    def use_in_on_on_one(self) -> bool:
        return self.__one_on_one
    
    @property
    def use_in_multi_npc(self) -> bool:
        return self.__multi_npc
    
    @property
    def use_in_radiant(self) -> bool:
        return self.__radiant
    
    @property
    def info_text(self) -> str:
        return self.__info_text