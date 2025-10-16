from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue, ConfigValueTag


class ConfigValueBool(ConfigValue[bool]):
    def __init__(self, identifier: str, name: str, description: str, default_value: bool, constraints: list[ConfigValueConstraint[bool]] = [], is_hidden: bool = False, tags: list[ConfigValueTag] = [], row_group: str | None = None):
        super().__init__(identifier, name, description, default_value, constraints, is_hidden, tags, row_group)
    
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        try:
            self.value = config_value == 'True' or config_value == '1'
            return ConfigValueConstraintResult()
        except ValueError:
            return ConfigValueConstraintResult(f"Error when reading config value '{self.identifier}'. Must be either 'True' or 'False'!")
        
    def accept_visitor(self, visitor: ConfigValueVisitor):
        visitor.visit_ConfigValueBool(self)