from abc import ABC, abstractmethod
from typing import TypeVar

from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value import ConfigValue, ConvigValueTag


T = TypeVar('T', int, float)
class ConfigValueNumeric(ConfigValue[T], ABC):
    def __init__(self, identifier: str, name: str, description: str, default_value: T, min_value: T, max_value: T, constraints: list[ConfigValueConstraint[T]] = [],is_hidden: bool = False, tags: list[ConvigValueTag] = []):
        super().__init__(identifier, name, description, default_value, constraints, is_hidden, tags)
        self.__min_value: T = min_value
        self.__max_value: T = max_value

    @property
    def min_value(self) -> T:
        return self.__min_value
    
    @property
    def max_value(self) -> T:
        return self.__max_value
    
    def does_value_cause_error(self, value_to_check: T) -> ConfigValueConstraintResult:
        result = super().does_value_cause_error(value_to_check)
        if not result.is_success:
            return result
        if value_to_check >= self.__min_value and value_to_check <= self.__max_value:
            return ConfigValueConstraintResult()
        return ConfigValueConstraintResult(f"{self.__name} must be between {self.__min_value} and {self.__max_value}!")
    
    @abstractmethod
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        pass