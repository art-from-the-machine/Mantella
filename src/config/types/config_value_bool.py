from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue, ConvigValueTag


class ConfigValueBool(ConfigValue[bool]):
    def __init__(self, identifier: str, name: str, description: str, defaultValue: bool, constraints: list[ConfigValueConstraint[bool]] = [], is_hidden: bool = False, tags: list[ConvigValueTag] = []):
        super().__init__(identifier, name, description, defaultValue, constraints, is_hidden, tags)
    
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        try:
            self.Value = config_value == 'True' or config_value == '1'
            return ConfigValueConstraintResult()
        except ValueError:
            return ConfigValueConstraintResult(f"Error when reading config value '{self.Identifier}'. Must be either 'True' or 'False'!")
        
    def accept_visitor(self, visitor: ConfigValueVisitor):
        visitor.visit_ConfigValueBool(self)