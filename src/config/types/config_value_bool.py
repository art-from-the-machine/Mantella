from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue


class ConfigValueBool(ConfigValue[bool]):
    def __init__(self, identifier: str, name: str, description: str, defaultValue: bool, constraints: list[ConfigValueConstraint[bool]] = [], is_hidden: bool = False):
        super().__init__(identifier, name, description, defaultValue, constraints, is_hidden)
    
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        try:
            self.Value = bool(config_value)
            return ConfigValueConstraintResult()
        except ValueError:
            return ConfigValueConstraintResult(f"Error when reading config value '{self.Identifier}'. Must be either 'True' or 'False'!")
        
    def accept_visitor(self, visitor: ConfigValueVisitor):
        visitor.visit_ConfigValueBool(self)