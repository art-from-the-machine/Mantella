class Action:
    def __init__(self, identifier: str, name: str, keyword: str, description: str, prompt_text: str, 
                 requires_response: bool, is_interrupting: bool, one_on_one: bool, multi_npc: bool, radiant: bool,
                 legacy_argument: str = "", legacy_action_group: str = "",
                 legacy_action_hints: list[str] | None = None) -> None:
        self.__identifier = identifier
        self.__name = name
        self.__keyword = keyword
        self.__description = description
        self.__prompt_text = prompt_text
        self.__requires_response = requires_response
        self.__is_interrupting = is_interrupting
        self.__one_on_one = one_on_one
        self.__multi_npc = multi_npc
        self.__radiant = radiant
        self.__legacy_argument = legacy_argument
        self.__legacy_action_group = legacy_action_group
        self.__legacy_action_hints = legacy_action_hints or []

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
    def legacy_argument(self) -> str:
        return self.__legacy_argument

    @property
    def legacy_action_group(self) -> str:
        return self.__legacy_action_group

    @property
    def legacy_action_hints(self) -> list[str]:
        return self.__legacy_action_hints
    
    @property
    def requires_response(self) -> bool:
        return self.__requires_response
    
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
