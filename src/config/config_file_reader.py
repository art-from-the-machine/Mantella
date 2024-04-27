
import configparser
import logging
import sys
from typing import Any, TypeVar

from src.config.types.config_value import ConfigValue
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_group import ConfigValueGroup
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_path import ConfigValuePath
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.config_value_constraint import ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor

class ConfigFileReader(ConfigValueVisitor):
    def __init__(self, config: configparser.ConfigParser) -> None:
        super().__init__()
        self.__config = config
        self.__contraint_violations: dict[str, list[str]] = {}
        self.__category: str = "'config.ini' is malformed! No initial category found!"
        self.__int_values: dict[str, tuple[ConfigValueInt, str]] = {}
        self.__float_values: dict[str, tuple[ConfigValueFloat, str]] = {}
        self.__bool_values: dict[str, tuple[ConfigValueBool, str]] = {}
        self.__string_values: dict[str, tuple[ConfigValueString, str]] = {}
        self.__selection_values: dict[str, tuple[ConfigValueSelection, str]] = {}
        self.__path_values: dict[str, tuple[ConfigValuePath, str]] = {}

    @property
    def Have_all_loaded_values_succeded(self) -> bool:
        return len(self.__contraint_violations) == 0
    
    @property
    def Constraint_violations(self) -> dict[str, list[str]]:
        return self.__contraint_violations
    
    def clear_constraint_violations(self):
        self.__contraint_violations.clear()

    def visit_ConfigValueGroup(self, config_value: ConfigValueGroup):
        self.__category = config_value.Identifier
        for cv in config_value.Value:
            cv.accept_visitor(self)

    def visit_ConfigValueInt(self, config_value: ConfigValueInt):
        self.__int_values[config_value.Identifier] = config_value, self.__category

    def visit_ConfigValueFloat(self, config_value: ConfigValueFloat):
        self.__float_values[config_value.Identifier] = config_value, self.__category

    def visit_ConfigValueBool(self, config_value: ConfigValueBool):
        self.__bool_values[config_value.Identifier] = config_value, self.__category

    def visit_ConfigValueString(self, config_value: ConfigValueString):
        self.__string_values[config_value.Identifier] = config_value, self.__category

    def visit_ConfigValueSelection(self, config_value: ConfigValueSelection):
        self.__selection_values[config_value.Identifier] = config_value, self.__category

    def visit_ConfigValuePath(self, config_value: ConfigValuePath):
        self.__path_values[config_value.Identifier] = config_value, self.__category

    def __add_constraint_violation(self, config_value: ConfigValue, text: str):
        if not self.__contraint_violations.__contains__(config_value.Identifier):
            self.__contraint_violations[config_value.Identifier] = []
        self.__contraint_violations[config_value.Identifier].append(text)

    def __parse(self, config_value: ConfigValue, category: str) -> bool:
        error_text: str | None = None
        if not self.__config.has_section(category):
            error_text = f"Looking for config value '{config_value.Identifier}' in category '{category}' in 'config.ini', but this category does not exist. 'config.ini' is most likely malformed after a manual edit."
        elif not self.__config.has_option(category, config_value.Identifier):
            error_text = f"Looking for config value '{config_value.Identifier}' in category '{category}' in 'config.ini', but this config value does not exist. 'config.ini' is most likely malformed after a manual edit."
        parse_result: ConfigValueConstraintResult = config_value.parse(self.__config[category][config_value.Identifier])
        if not parse_result.Is_success:
            error_text = parse_result.Error_message
            # input('\nPress any key to exit...')
            # sys.exit(0)
        
        if error_text:
            logging.critical(error_text)
            self.__add_constraint_violation(config_value, error_text)
            return False
        else:            
            return True        

    T = TypeVar('T', int, float, bool, str)
    def __get_value(self, dictionary_to_check: dict[str, tuple[Any, str]], identifier: str, value_on_error: T) -> T:
        if dictionary_to_check.__contains__(identifier):
            config_value, category = dictionary_to_check[identifier]
            if self.__parse(config_value, category):
                return config_value.Value
            else:
                return value_on_error
        raise Exception(f"Could not find config value {identifier} in list of definitions" )

    def get_int_value(self, identifier: str) -> int:
        return self.__get_value(self.__int_values, identifier, int(0))
        # if self.__int_values.__contains__(identifier):
        #     config_value, category = self.__int_values[identifier]
        #     if self.__parse(config_value, category):
        #         return config_value.Value
        # raise Exception(f"Could not find config value {identifier} in 'config.ini'" )
        
    def get_float_value(self, identifier: str) -> float:
        return self.__get_value(self.__float_values, identifier, float(0))
        # if self.__float_values.__contains__(identifier):
        #     config_value, category = self.__float_values[identifier]
        #     if self.__parse(config_value, category):
        #         return config_value.Value
        # raise Exception(f"Could not find config value {identifier} in 'config.ini'" )
        
    def get_bool_value(self, identifier: str) -> bool:
        return self.__get_value(self.__bool_values, identifier, False)
        # if self.__bool_values.__contains__(identifier):
        #     config_value, category = self.__bool_values[identifier]
        #     if self.__parse(config_value, category):
        #         return config_value.Value
        # raise Exception(f"Could not find config value {identifier} in 'config.ini'" )
        
    def get_string_value(self, identifier: str) -> str:
        try:
            return self.__get_value(self.__string_values, identifier, "")
        except:
            try:
                return self.__get_value(self.__selection_values, identifier, "")
            except:
                return self.__get_value(self.__path_values, identifier, "")

        # if self.__string_values.__contains__(identifier):
        #     config_value, category = self.__string_values[identifier]
        #     if self.__parse(config_value, category):
        #         return config_value.Value
        # elif self.__selection_values.__contains__(identifier):
        #     config_value, category = self.__selection_values[identifier]
        #     if self.__parse(config_value, category):
        #         return config_value.Value
        # elif self.__path_values.__contains__(identifier):
        #     config_value, category = self.__path_values[identifier]
        #     if self.__parse(config_value, category):
        #         return config_value.Value
        # raise Exception(f"Could not find config value {identifier} in 'config.ini'" )
