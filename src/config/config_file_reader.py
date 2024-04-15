
import configparser
import logging
import sys

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
        self.__category: str = "'config.ini' is malformed! No initial category found!"
        self.__int_values: dict[str, tuple[ConfigValueInt, str]] = {}
        self.__float_values: dict[str, tuple[ConfigValueFloat, str]] = {}
        self.__bool_values: dict[str, tuple[ConfigValueBool, str]] = {}
        self.__string_values: dict[str, tuple[ConfigValueString, str]] = {}
        self.__selection_values: dict[str, tuple[ConfigValueSelection, str]] = {}
        self.__path_values: dict[str, tuple[ConfigValuePath, str]] = {}

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

    def __parse(self, config_value: ConfigValue, category: str) -> bool:
        if not self.__config.has_section(category):
            logging.log(24, f"Looking for config value '{config_value.Identifier}' in category '{category}' in 'config.ini', but this category does not exist. 'config.ini' is most likely malformed after a manual edit.")
            return False
        elif not self.__config.has_option(category, config_value.Identifier):
            logging.log(24, f"Looking for config value '{config_value.Identifier}' in category '{category}' in 'config.ini', but this config value does not exist. 'config.ini' is most likely malformed after a manual edit.")
            return False
        parse_result: ConfigValueConstraintResult = config_value.parse(self.__config[category][config_value.Identifier])
        if not parse_result.Is_success:
            logging.log(24, parse_result.Error_message)
            input('\nPress any key to exit...')
            sys.exit(0)
        return True        

    def get_int_value(self, identifier: str) -> int:
        if self.__int_values.__contains__(identifier):
            config_value, category = self.__int_values[identifier]
            if self.__parse(config_value, category):
                return config_value.Value
        raise Exception(f"Could not find config value {identifier} in 'config.ini'" )
        
    def get_float_value(self, identifier: str) -> float:
        if self.__float_values.__contains__(identifier):
            config_value, category = self.__float_values[identifier]
            if self.__parse(config_value, category):
                return config_value.Value
        raise Exception(f"Could not find config value {identifier} in 'config.ini'" )
        
    def get_bool_value(self, identifier: str) -> bool:
        if self.__bool_values.__contains__(identifier):
            config_value, category = self.__bool_values[identifier]
            if self.__parse(config_value, category):
                return config_value.Value
        raise Exception(f"Could not find config value {identifier} in 'config.ini'" )
        
    def get_string_value(self, identifier: str) -> str:
        if self.__string_values.__contains__(identifier):
            config_value, category = self.__string_values[identifier]
            if self.__parse(config_value, category):
                return config_value.Value
        elif self.__selection_values.__contains__(identifier):
            config_value, category = self.__selection_values[identifier]
            if self.__parse(config_value, category):
                return config_value.Value
        elif self.__path_values.__contains__(identifier):
            config_value, category = self.__path_values[identifier]
            if self.__parse(config_value, category):
                return config_value.Value
        raise Exception(f"Could not find config value {identifier} in 'config.ini'" )
