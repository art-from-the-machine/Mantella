from typing import Any, TypeVar
from src.config.config_value_constraint import ConfigValueConstraintResult
from src.config.types.config_value import ConfigValue
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_group import ConfigValueGroup
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_path import ConfigValuePath
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_visitor import ConfigValueVisitor


class ConfigValues(ConfigValueVisitor):
    def __init__(self) -> None:
        self.__base_groups: list[ConfigValueGroup] = []
        self.__all_config_values: dict[str, ConfigValue] = {}
        self.__int_values: dict[str, tuple[ConfigValueInt, str]] = {}
        self.__float_values: dict[str, tuple[ConfigValueFloat, str]] = {}
        self.__bool_values: dict[str, tuple[ConfigValueBool, str]] = {}
        self.__string_values: dict[str, tuple[ConfigValueString, str]] = {}
        self.__selection_values: dict[str, tuple[ConfigValueSelection, str]] = {}
        self.__path_values: dict[str, tuple[ConfigValuePath, str]] = {}
        self.__contraint_violations: dict[str, list[str]] = {}
        self.__last_section_id: str = ""

    @property
    def Base_groups(self) ->list[ConfigValueGroup]:
        return self.__base_groups

    @property
    def Have_all_loaded_values_succeded(self) -> bool:
        return len(self.__contraint_violations) == 0
    
    @property
    def Constraint_violations(self) -> dict[str, list[str]]:
        return self.__contraint_violations
    
    def add_base_group(self, new_section: ConfigValueGroup):
        self.__base_groups.append(new_section)
        self.__last_section_id = new_section.Identifier
        for cf in new_section.Value:
            cf.accept_visitor(self)
    
    def get_config_value_definition(self, identifier: str) -> ConfigValue:
        if self.__all_config_values.__contains__(identifier):
            return self.__all_config_values[identifier]
        raise Exception(f"Could not find config value {identifier} in list of definitions" )

    def get_int_value(self, identifier: str) -> int:
        return self.__get_value(self.__int_values, identifier)
        
    def get_float_value(self, identifier: str) -> float:
        return self.__get_value(self.__float_values, identifier)
        
    def get_bool_value(self, identifier: str) -> bool:
        return self.__get_value(self.__bool_values, identifier)
        
    def get_string_value(self, identifier: str) -> str:
        try:
            return self.__get_value(self.__string_values, identifier)
        except:
            try:
                return self.__get_value(self.__selection_values, identifier)
            except:
                return self.__get_value(self.__path_values, identifier)
    
    def clear_constraint_violations(self):
        self.__contraint_violations.clear()

    def visit_ConfigValueGroup(self, config_value: ConfigValueGroup):
        self.__last_section_id = config_value.Identifier
        for cv in config_value.Value:
            cv.accept_visitor(self)

    def visit_ConfigValueInt(self, config_value: ConfigValueInt):
        self.__int_values[config_value.Identifier] = config_value, self.__last_section_id
        self.__all_config_values[config_value.Identifier] = config_value

    def visit_ConfigValueFloat(self, config_value: ConfigValueFloat):
        self.__float_values[config_value.Identifier] = config_value, self.__last_section_id
        self.__all_config_values[config_value.Identifier] = config_value

    def visit_ConfigValueBool(self, config_value: ConfigValueBool):
        self.__bool_values[config_value.Identifier] = config_value, self.__last_section_id
        self.__all_config_values[config_value.Identifier] = config_value

    def visit_ConfigValueString(self, config_value: ConfigValueString):
        self.__string_values[config_value.Identifier] = config_value, self.__last_section_id
        self.__all_config_values[config_value.Identifier] = config_value

    def visit_ConfigValueSelection(self, config_value: ConfigValueSelection):
        self.__selection_values[config_value.Identifier] = config_value, self.__last_section_id
        self.__all_config_values[config_value.Identifier] = config_value

    def visit_ConfigValuePath(self, config_value: ConfigValuePath):
        self.__path_values[config_value.Identifier] = config_value, self.__last_section_id
        self.__all_config_values[config_value.Identifier] = config_value

    def __add_constraint_violation(self, config_value: ConfigValue, text: str):
        if not self.__contraint_violations.__contains__(config_value.Identifier):
            self.__contraint_violations[config_value.Identifier] = []
        self.__contraint_violations[config_value.Identifier].append(text)
    
    T = TypeVar('T', int, float, bool, str)
    def __get_value(self, dictionary_to_check: dict[str, tuple[Any, str]], identifier: str) -> T:
        if dictionary_to_check.__contains__(identifier):
            config_value, category = dictionary_to_check[identifier]
            config_value: ConfigValue = config_value
            result: ConfigValueConstraintResult = config_value.does_value_cause_error(config_value.Value)
            if not result.Is_success:
                self.__add_constraint_violation(config_value, result.Error_message)
            return config_value.Value
        raise Exception(f"Could not find config value {identifier} in list of definitions" )
   
    