from src.config.config_value_constraint import ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue


class ConfigValueGroup(ConfigValue[list[ConfigValue]]):
    def __init__(self, identifier: str, name: str, description: str, is_hidden: bool = False):
        super().__init__(identifier, name, description, [],[], is_hidden)

    def add_config_value(self, new_value: ConfigValue):
        self.Value.append(new_value)
    
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        return ConfigValueConstraintResult()
    
    def accept_visitor(self, visitor: ConfigValueVisitor):
        visitor.visit_ConfigValueGroup(self)