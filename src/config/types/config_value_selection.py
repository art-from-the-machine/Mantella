from enum import Enum
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue, ConfigValueTag

class ConfigValueSelection(ConfigValue[str]):
    def __init__(self, identifier: str, name: str, description: str, default_value: str, options: list[str], corresponding_enums: list[Enum] | None = None, allows_free_edit: bool = False, allows_values_not_in_options: bool = False, constraints: list[ConfigValueConstraint[str]] = [], is_hidden: bool = False, tags: list[ConfigValueTag] = [], row_group: str | None = None,
                 option_descriptions: dict[str, str] | None = None, option_labels: dict[str, str] | None = None):
        """
        Args:
            option_descriptions (dict[str, str] | None): what each option does, by option. The UI shows the one of the picked option under the dropdown
            option_labels (dict[str, str] | None): the text the dropdown shows for an option, by option, when it differs from the option. The option is still what is saved
        """
        super().__init__(identifier, name, description, default_value, constraints, is_hidden, tags, row_group)
        self.__options: list[str] = options
        self.__corresponding_enums: list[Enum] | None = corresponding_enums
        self.__allows_free_edit = allows_free_edit
        self.__allows_values_not_in_options = allows_values_not_in_options
        self.__option_descriptions: dict[str, str] = option_descriptions or {}
        self.__option_labels: dict[str, str] = option_labels or {}

    @property
    def options(self) -> list[str]:
        return self.__options

    @property
    def option_descriptions(self) -> dict[str, str]:
        return self.__option_descriptions

    @property
    def option_labels(self) -> dict[str, str]:
        return self.__option_labels
    
    @property
    def has_corresponding_enums(self) -> bool:
        return self.__corresponding_enums != None
    
    @property
    def allows_custom_value(self) -> bool:
        return self.__allows_free_edit
        
    @property
    def allows_values_not_in_options(self) -> bool:
        return self.__allows_values_not_in_options
    
    def get_corresponding_enum(self) -> Enum | None:
        if not self.__corresponding_enums:
            return None
        elif isinstance(self.value, Enum):
            if self.value in self.__corresponding_enums:
                return self.value
        else:
            try:
                index = self.__options.index(self.value)
                return self.__corresponding_enums[index]
            except:
                return None
    
    def does_value_cause_error(self, value_to_check: str) -> ConfigValueConstraintResult:
        result = super().does_value_cause_error(value_to_check)
        if not result.is_success:
            return result
        if value_to_check in self.__options or self.__allows_free_edit or self.__allows_values_not_in_options:
            return ConfigValueConstraintResult()
        return ConfigValueConstraintResult(f"{self.name} must be either {', '.join(self.__options[:-1]) + ' or ' + self.__options[-1]}")
    
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
        visitor.visit_ConfigValueSelection(self)