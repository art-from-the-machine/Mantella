from abc import ABC, abstractmethod


class ConfigValueVisitor(ABC):
    @abstractmethod
    def visit_ConfigValueGroup(self, config_value):
        pass

    @abstractmethod
    def visit_ConfigValueInt(self, config_value):
        pass

    @abstractmethod
    def visit_ConfigValueFloat(self, config_value):
        pass

    @abstractmethod
    def visit_ConfigValueBool(self, config_value):
        pass

    @abstractmethod
    def visit_ConfigValueString(self, config_value):
        pass

    @abstractmethod
    def visit_ConfigValueSelection(self, config_value):
        pass

    @abstractmethod
    def visit_ConfigValueMultiSelection(self, config_value):
        pass

    @abstractmethod
    def visit_ConfigValuePath(self, config_value):
        pass