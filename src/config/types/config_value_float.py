from src.config.types.config_value import ConvigValueTag
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value_numeric import ConfigValueNumeric


class ConfigValueFloat(ConfigValueNumeric[float]):
    def __init__(self, identifier: str, name: str, description: str, defaultValue: float, min_value: float, max_value: float, constraints: list[ConfigValueConstraint[float]] = [], is_hidden: bool = False, tags: list[ConvigValueTag] = []):
        super().__init__(identifier, name, description, defaultValue, min_value, max_value, constraints, is_hidden, tags)

    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        try:
            value_to_use = float(config_value)
            result = self.does_value_cause_error(value_to_use)
            if result.Is_success:
                self.Value = value_to_use
                return ConfigValueConstraintResult()
            else:
                return result
        except ValueError:
            return ConfigValueConstraintResult(f"Error when reading config value '{self.Identifier}'. '{config_value}' is no valid float!")
        
    def accept_visitor(self, visitor: ConfigValueVisitor):
        visitor.visit_ConfigValueFloat(self)