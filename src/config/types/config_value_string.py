from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue, ConfigValueTag


class ConfigValueString(ConfigValue[str]):
    def __init__(self, identifier: str, name: str, description: str, default_value: str, constraints: list[ConfigValueConstraint[str]] = [], is_hidden: bool = False, tags: list[ConfigValueTag] = []):
        super().__init__(identifier, name, description, self.__strip_lines(default_value), constraints, is_hidden, tags)
    
    def parse(self, config_value: str) -> ConfigValueConstraintResult:
        try:
            result = self.does_value_cause_error(config_value)
            if result.is_success:
                self.value = config_value
                return ConfigValueConstraintResult()
            else:
                return result
        except ValueError:
            return ConfigValueConstraintResult(f"Error when reading config value '{self.identifier}'. {config_value} not valid!")
        
    def accept_visitor(self, visitor: ConfigValueVisitor):
        visitor.visit_ConfigValueString(self)
    
    def __strip_lines(self, text: str) -> str:
        # Preserve user-intended indentation. Remove only trailing whitespace and
        # normalize common code indentation introduced by triple-quoted strings.
        try:
            import textwrap
            dedented = textwrap.dedent(text)
        except Exception:
            dedented = text
        return "\n".join(line.rstrip() for line in dedented.splitlines())