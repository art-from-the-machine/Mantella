from typing import Any, Callable
from src.config.config_value_constraint import ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue, ConfigValueTag


class ConfigValueGroup(ConfigValue[list[ConfigValue]]):
    def __init__(self, identifier: str, name: str, description: str, on_value_change_callback: Callable[..., Any] | None = None, is_hidden: bool = False, tags: list[ConfigValueTag] = []):
        super().__init__(identifier, name, description, [],[], is_hidden, tags)
        self.set_on_value_change_callback(on_value_change_callback)

    def add_config_value(self, new_value: ConfigValue):
        self.value.append(new_value)
        new_value.set_on_value_change_callback(self._on_value_change_callback)
    
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        return ConfigValueConstraintResult()
    
    def accept_visitor(self, visitor: ConfigValueVisitor):
        visitor.visit_ConfigValueGroup(self)