from abc import ABC, abstractmethod
from typing import TypeVar

from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value import ConfigValue


U = TypeVar('U', int, float)
class ConfigValueNumeric(ConfigValue[U], ABC):
    def __init__(self, identifier: str, name: str, description: str, defaultValue: U, min_value: U, max_value: U, constraints: list[ConfigValueConstraint[U]] = [],is_hidden: bool = False):
        super().__init__(identifier, name, description, defaultValue, constraints, is_hidden)
        self.__min_value: U = min_value
        self.__max_value: U = max_value

    @property
    def MinValue(self) -> U:
        return self.__min_value
    
    @property
    def MaxValue(self) -> U:
        return self.__max_value
    
    def does_value_cause_error(self, valueToCheck: U) -> ConfigValueConstraintResult:
        result = super().does_value_cause_error(valueToCheck)
        if not result.Is_success:
            return result
        if valueToCheck >= self.__min_value and valueToCheck <= self.__max_value:
            return ConfigValueConstraintResult()
        return ConfigValueConstraintResult(f"{self.__name} must be between {self.__min_value} and {self.__max_value}!")
    
    @abstractmethod
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        pass