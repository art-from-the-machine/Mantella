from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue, ConvigValueTag


class ConfigValueSelection(ConfigValue[str]):
    def __init__(self, identifier: str, name: str, description: str, defaultValue: str, options: list[str], constraints: list[ConfigValueConstraint[str]] = [], is_hidden: bool = False, tags: list[ConvigValueTag] = []):
        super().__init__(identifier, name, description, defaultValue, constraints, is_hidden, tags)
        self.__options: list[str] = options

    @property
    def Options(self) -> list[str]:
        return self.__options
    
    def does_value_cause_error(self, valueToCheck: str) -> ConfigValueConstraintResult:
        result = super().does_value_cause_error(valueToCheck)
        if not result.Is_success:
            return result
        if valueToCheck in self.__options:
            return ConfigValueConstraintResult()
        return ConfigValueConstraintResult(f"{self.__name} must be either {', '.join(self.__options[:-1]) + ' or ' + self.__options[-1]}")
    
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        try:
            result = self.does_value_cause_error(config_value)
            if result.Is_success:
                self.Value = config_value
                return ConfigValueConstraintResult()
            else:
                return result
        except ValueError:
            return ConfigValueConstraintResult(f"Error when reading config value '{self.Identifier}'. {config_value} not valid!")
        
    def accept_visitor(self, visitor: ConfigValueVisitor):
        visitor.visit_ConfigValueSelection(self)