from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult


T = TypeVar('T')
class ConfigValue(ABC, Generic[T]):
    def __init__(self, identifier: str, name: str, description: str, defaultValue: T, constraints: list[ConfigValueConstraint[T]], is_hidden: bool) -> None:
        super().__init__()
        self.__identifier = identifier
        self.__name = name
        self.__description = description
        self.__value: T = defaultValue
        self.__defaultValue:T = defaultValue
        self.__constraints: list[ConfigValueConstraint[T]] = constraints
        self.__is_hidden: bool = is_hidden
    
    @property
    def Identifier(self) -> str:
        return self.__identifier
    
    @property
    def Name(self) -> str:
        return self.__name
    
    @property
    def Description(self) -> str:
        return self.__description
    
    @property
    def Value(self) -> T:
        return self.__value
    
    @Value.setter
    def Value(self, value:T):
        self.__value = value
    
    @property
    def DefaultValue(self) -> T:
        return self.__defaultValue
    
    @property
    def Constraints(self) -> list[ConfigValueConstraint[T]]:
        return self.__constraints
    
    @property
    def Is_hidden(self) -> bool:
        return self.__is_hidden
    
    def does_value_cause_error(self, valueToCheck: T) -> ConfigValueConstraintResult:
        for constraint in self.__constraints:
            result = constraint.apply_contraint(valueToCheck)
            if not result.Is_success:
                return result
        return ConfigValueConstraintResult()

    @abstractmethod
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        pass

    @abstractmethod
    def accept_visitor(self, visitor: ConfigValueVisitor):
        pass