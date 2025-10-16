from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, Callable, Generic, TypeVar
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult

class ConfigValueTag(StrEnum):
    advanced = "advanced"
    basic = "basic"
    share_row = "share_row"

T = TypeVar('T')
class ConfigValue(ABC, Generic[T]):
    def __init__(self, identifier: str, name: str, description: str, default_value: T, constraints: list[ConfigValueConstraint[T]], is_hidden: bool, tags: list[ConfigValueTag] = [], row_group: str | None = None) -> None:
        super().__init__()
        self.__identifier = identifier
        self.__name = name
        self.__description = description
        self.__value: T = default_value
        self.__default_value:T = default_value
        self.__constraints: list[ConfigValueConstraint[T]] = constraints
        self.__is_hidden: bool = is_hidden
        self.__tags: list[ConfigValueTag] = tags
        self.__row_group: str | None = row_group
        self._on_value_change_callback: Callable[..., Any] | None = None
    
    @property
    def identifier(self) -> str:
        return self.__identifier
    
    @property
    def name(self) -> str:
        return self.__name
    
    @property
    def description(self) -> str:
        return self.__description
    
    @property
    def value(self) -> T:
        return self.__value
    
    @value.setter
    def value(self, value:T):        
        self.__value = value
        if self._on_value_change_callback:
            self._on_value_change_callback()
    
    @property
    def default_value(self) -> T:
        return self.__default_value
    
    @property
    def constraints(self) -> list[ConfigValueConstraint[T]]:
        return self.__constraints
    
    @property
    def is_hidden(self) -> bool:
        return self.__is_hidden
    
    @property
    def tags(self) -> list[ConfigValueTag]:
        return self.__tags
    
    @property
    def row_group(self) -> str | None:
        return self.__row_group
    
    def set_on_value_change_callback(self, on_value_change_callback: Callable[..., Any] | None):
        self._on_value_change_callback = on_value_change_callback
    
    def does_value_cause_error(self, value_to_check: T) -> ConfigValueConstraintResult:
        for constraint in self.__constraints:
            result = constraint.apply_constraint(value_to_check)
            if not result.is_success:
                return result
        return ConfigValueConstraintResult()

    @abstractmethod
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        pass

    @abstractmethod
    def accept_visitor(self, visitor: ConfigValueVisitor):
        pass