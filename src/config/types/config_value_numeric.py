from abc import ABC, abstractmethod
from typing import TypeVar

from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value import ConfigValue


T = TypeVar('T', int, float)
class ConfigValueNumeric(ConfigValue[T], ABC):
    def __init__(self, identifier: str, name: str, description: str, defaultValue: T, min_value: T, max_value: T, constraints: list[ConfigValueConstraint[T]] = [],is_hidden: bool = False):
        super().__init__(identifier, name, description, defaultValue, constraints, is_hidden)
        self.__min_value: T = min_value
        self.__max_value: T = max_value

    @property
    def MinValue(self) -> T:
        return self.__min_value
    
    @property
    def MaxValue(self) -> T:
        return self.__max_value
    
    def does_value_cause_error(self, valueToCheck: T) -> ConfigValueConstraintResult:
        result = super().does_value_cause_error(valueToCheck)
        if not result.Is_success:
            return result
        if valueToCheck >= self.__min_value and valueToCheck <= self.__max_value:
            return ConfigValueConstraintResult()
        return ConfigValueConstraintResult(f"{self.__name} must be between {self.__min_value} and {self.__max_value}!")
    
    @abstractmethod
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        pass