import os
from pathlib import Path

from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue


class ConfigValuePath(ConfigValue[str]):
    def __init__(self, identifier: str, name: str, description: str, defaultValue: str, file_or_folder_that_must_be_present: str | None, constraints: list[ConfigValueConstraint[str]] = [], is_hidden: bool = False):
        super().__init__(identifier, name, description, defaultValue, constraints, is_hidden)
        self.__file_or_folder_that_must_be_present: str | None = file_or_folder_that_must_be_present
    
    @property
    def File_or_folder_that_must_be_present(self) -> str | None:
        return self.__file_or_folder_that_must_be_present
    
    def does_value_cause_error(self, valueToCheck: str) -> ConfigValueConstraintResult:
        if not os.path.exists(valueToCheck):
            return ConfigValueConstraintResult(f"The selected folder '{valueToCheck}' for config value '{self.Name}' does not exist!")

        if self.__file_or_folder_that_must_be_present:             
            if '.' in self.__file_or_folder_that_must_be_present: #means we are looking for a file
                path_plus_file_name = os.path.join(valueToCheck, self.__file_or_folder_that_must_be_present)
                if not os.path.exists(path_plus_file_name) or not os.path.isfile(path_plus_file_name):
                    return ConfigValueConstraintResult(f"{valueToCheck} is not a file!")
                file_name = Path(path_plus_file_name).name
                if file_name != self.__file_or_folder_that_must_be_present:
                    return ConfigValueConstraintResult(f"Selected file {valueToCheck} is not '{self.__file_or_folder_that_must_be_present}'!")
            else :#We are looking for a folder
                if not os.path.isdir(valueToCheck):
                    return ConfigValueConstraintResult(f"{valueToCheck} is not a folder!")
                folder_name = os.path.join(valueToCheck, self.__file_or_folder_that_must_be_present)
                if not os.path.exists(folder_name) or not os.path.isdir(folder_name):
                    return ConfigValueConstraintResult(f"Selected folder {valueToCheck} does not contain subfolder '{self.__file_or_folder_that_must_be_present}'!")
        
        result = super().does_value_cause_error(valueToCheck)
        if not result.Is_success:
            return result
        else:
            return ConfigValueConstraintResult()
        
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
        visitor.visit_ConfigValuePath(self)
