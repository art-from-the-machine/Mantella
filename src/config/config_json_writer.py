import json
from typing import Any
from src.config.types.config_value import ConfigValue
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_group import ConfigValueGroup
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_path import ConfigValuePath
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_visitor import ConfigValueVisitor


class ConfigJsonWriter(ConfigValueVisitor):
    NEWLINE = "\n"
    KEY_TYPE = "type"
    KEY_ID = "id"
    KEY_NAME = "name"
    KEY_DESCRIPTION = "description"
    KEY_VALUE = "value"
    KEY_CONSTRAINTS = "constraints"
    KEY_ERRORMESSAGES = "errorMessages"    
    KEY_NUMERIC_MIN = "min"
    KEY_NUMERIC_MAX = "max"
    KEY_COUNTDECIMALPLACES = "countDecimalPlaces"    
    KEY_SELECTION_OPTIONS = "options"
    KEY_PATH_MUST_BE_PRESENT = "mandatory"

    def __init__(self):
        self.__content: list[dict[str, Any]] = []
    
    def get_Json(self) -> str:
        return json.dumps(self.__content)

    def reset_json_string(self):
        self.__content = []

    def visit_ConfigValueGroup(self, config_value: ConfigValueGroup):
        result: dict[str, Any] = {}
        result[self.KEY_TYPE] = "group"
        self.__add_id_name_and_description(result, config_value)
        recursive: ConfigJsonWriter = ConfigJsonWriter()
        for cf in config_value.value:
            cf.accept_visitor(recursive)
        result[self.KEY_VALUE] = recursive.get_Json()
        self.__content.append(result)

    def visit_ConfigValueInt(self, config_value: ConfigValueInt):
        result: dict[str, Any] = {}
        result[self.KEY_TYPE] = "int"
        self.__add_id_name_and_description(result, config_value)
        result[self.KEY_NUMERIC_MIN] = config_value.min_value
        result[self.KEY_NUMERIC_MAX] = config_value.max_value
        result[self.KEY_COUNTDECIMALPLACES] = 0
        result[self.KEY_VALUE] = config_value.value
        self.__add_constraints(result, config_value)
        self.__content.append(result)

    def visit_ConfigValueFloat(self, config_value: ConfigValueFloat):
        result: dict[str, Any] = {}
        result[self.KEY_TYPE] = "float"
        self.__add_id_name_and_description(result, config_value)
        result[self.KEY_NUMERIC_MIN] = config_value.min_value
        result[self.KEY_NUMERIC_MAX] = config_value.max_value
        result[self.KEY_COUNTDECIMALPLACES] = 2
        result[self.KEY_VALUE] = config_value.value
        self.__add_constraints(result, config_value)
        self.__content.append(result)

    def visit_ConfigValueBool(self, config_value: ConfigValueBool):
        result: dict[str, Any] = {}
        result[self.KEY_TYPE] = "bool"
        self.__add_id_name_and_description(result, config_value)
        result[self.KEY_VALUE] = config_value.value
        self.__content.append(result)

    def visit_ConfigValueString(self, config_value: ConfigValueString):
        result: dict[str, Any] = {}
        result[self.KEY_TYPE] = "text"
        self.__add_id_name_and_description(result, config_value)
        result[self.KEY_VALUE] = config_value.value
        self.__add_constraints(result, config_value)
        self.__content.append(result)

    def visit_ConfigValueSelection(self, config_value: ConfigValueSelection):
        result: dict[str, Any] = {}
        result[self.KEY_TYPE] = "selection"
        self.__add_id_name_and_description(result, config_value)
        result[self.KEY_VALUE] = config_value.value
        result[self.KEY_SELECTION_OPTIONS] = config_value.options
        self.__add_constraints(result, config_value)
        self.__content.append(result)

    def visit_ConfigValuePath(self, config_value: ConfigValuePath):
        result: dict[str, Any] = {}
        result[self.KEY_TYPE] = "path"
        self.__add_id_name_and_description(result, config_value)
        result[self.KEY_VALUE] = config_value.value
        result[self.KEY_PATH_MUST_BE_PRESENT] = config_value.File_or_folder_that_must_be_present
        self.__add_constraints(result, config_value)
        self.__content.append(result)

    def __add_id_name_and_description(self, dictionary: dict[str, Any], config_value: ConfigValue):
        dictionary[self.KEY_ID] = config_value.identifier
        dictionary[self.KEY_NAME] = config_value.name
        dictionary[self.KEY_DESCRIPTION] = config_value.description

    def __add_constraints(self, dictionary: dict[str, Any], config_value: ConfigValue):
        list_contraints = []
        for constraint in config_value.constraints:
            list_contraints.append(constraint.description)
        if len(list_contraints) > 0:
            dictionary[self.KEY_CONSTRAINTS] = list_contraints