from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue, ConvigValueTag


class ConfigValueMultiSelection(ConfigValue[list[str]]):
    def __init__(self, identifier: str, name: str, description: str, default_value: list[str], options: list[str], constraints: list[ConfigValueConstraint[list[str]]] = [], is_hidden: bool = False, tags: list[ConvigValueTag] = []):
        super().__init__(identifier, name, description, default_value, constraints, is_hidden, tags)
        self.__options: list[str] = options

    @property
    def options(self) -> list[str]:
        return self.__options
    
    def does_value_cause_error(self, value_to_check: list[str]) -> ConfigValueConstraintResult:
        result = super().does_value_cause_error(value_to_check)
        if not result.is_success:
            return result
        if all(e in self.__options for e in value_to_check):
            return ConfigValueConstraintResult()
        return ConfigValueConstraintResult(f"All chosen elements for {self.__name} must be from {', '.join(self.__options[:-1]) + ' or ' + self.__options[-1]}")
    
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        try:
            value_to_use: list[str] = list(x.strip() for x in config_value.split(","))
            result = self.does_value_cause_error(value_to_use)
            if result.is_success:
                self.value = value_to_use
                return ConfigValueConstraintResult()
            else:
                return result
        except ValueError:
            return ConfigValueConstraintResult(f"Error when reading config value '{self.identifier}'.")
        
    def accept_visitor(self, visitor: ConfigValueVisitor):
        visitor.visit_ConfigValueMultiSelection(self)