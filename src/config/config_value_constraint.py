from abc import ABC, abstractmethod
from typing import Generic, TypeVar


class ConfigValueConstraintResult:
    def __init__(self, error_message: str | None = None) -> None:
        self.__error_message: str | None = error_message

    @property
    def Is_success(self) -> bool:
        return self.__error_message == None
    
    @property
    def Error_message(self) -> str:
        if self.__error_message:
            return self.__error_message
        else:
            return ""

T = TypeVar('T')
class ConfigValueConstraint(Generic[T], ABC):
    def __init__(self, description: str) -> None:
        super().__init__()
        self.__description: str = description
    
    @property
    def Description(self) -> str:
        return self.__description
    
    @abstractmethod
    def apply_contraint(self, value_to_apply_to: T) -> ConfigValueConstraintResult:
        pass