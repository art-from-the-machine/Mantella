from io import TextIOWrapper
from src.config.types.config_value import ConfigValue
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_group import ConfigValueGroup
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_path import ConfigValuePath
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_visitor import ConfigValueVisitor


class ConfigFileWriter(ConfigValueVisitor):
    NEWLINE = "\n"

    def __init__(self):        
        self.__writer: TextIOWrapper | None = None

    def write(self, config_file_path: str, definitions: list[ConfigValue]):
        with open(config_file_path, 'w', encoding='utf-8', newline="\r\n") as self.__writer:
            for definition in definitions:
                definition.accept_visitor(self)                

    def visit_ConfigValueGroup(self, config_value: ConfigValueGroup):
        lines_to_write = [f"[{config_value.Identifier}]{self.NEWLINE}"]
        lines_to_write.extend(ConfigFileWriter.parse_multi_line_string(config_value.Description,"; "))
        self.write_setting_block_to_file(lines_to_write)
        for cv in config_value.Value:
            cv.accept_visitor(self)

    def visit_ConfigValueInt(self, config_value: ConfigValueInt):
        lines_to_write = self.__generate_name_and_description_lines(config_value)
        lines_to_write.append(f";   {config_value.Identifier} must be an integer between {config_value.MinValue} and {config_value.MaxValue}{self.NEWLINE}")
        lines_to_write.extend(self.__generate_default_and_config_value_lines(config_value))
        self.write_setting_block_to_file(lines_to_write)

    def visit_ConfigValueFloat(self, config_value: ConfigValueFloat):
        lines_to_write = self.__generate_name_and_description_lines(config_value)
        lines_to_write.append(f";   {config_value.Identifier} must be a floatint point number between {config_value.MinValue} and {config_value.MaxValue}{self.NEWLINE}")
        lines_to_write.extend(self.__generate_default_and_config_value_lines(config_value))
        self.write_setting_block_to_file(lines_to_write)

    def visit_ConfigValueBool(self, config_value: ConfigValueBool):
        lines_to_write = self.__generate_name_and_description_lines(config_value)
        lines_to_write.append(f";   {config_value.Identifier} must either be 'True' or 'False'{self.NEWLINE}")
        lines_to_write.extend(self.__generate_default_and_config_value_lines(config_value))
        self.write_setting_block_to_file(lines_to_write)

    def visit_ConfigValueString(self, config_value: ConfigValueString):
        lines_to_write = self.__generate_name_and_description_lines(config_value)
        lines_to_write.extend(self.__generate_default_and_config_value_lines(config_value))
        self.write_setting_block_to_file(lines_to_write)

    def visit_ConfigValueSelection(self, config_value: ConfigValueSelection):
        lines_to_write = self.__generate_name_and_description_lines(config_value)
        lines_to_write.append(f";   Options: {', '.join(config_value.Options[:])}{self.NEWLINE}")
        lines_to_write.extend(self.__generate_default_and_config_value_lines(config_value))
        self.write_setting_block_to_file(lines_to_write)

    def visit_ConfigValuePath(self, config_value: ConfigValuePath):
        lines_to_write = self.__generate_name_and_description_lines(config_value)
        required_target_text = ""
        if config_value.File_or_folder_that_must_be_present:
            if "." in config_value.File_or_folder_that_must_be_present:
                required_target_text = f"Target folder must contain file '{config_value.File_or_folder_that_must_be_present}'!"
            else:
                required_target_text = f"Target folder must contain folder '{config_value.File_or_folder_that_must_be_present}'!"
        lines_to_write.append(f";   Must be a valid system path. {required_target_text}{self.NEWLINE}")
        lines_to_write.extend(self.__generate_default_and_config_value_lines(config_value))
        self.write_setting_block_to_file(lines_to_write)

    def __generate_name_and_description_lines(self, config_value: ConfigValue) -> list[str]:
        lines_to_write = []
        if len(config_value.Name) > 0:
            lines_to_write.append(f"; {config_value.Identifier}{self.NEWLINE}")
        lines_to_write.extend(ConfigFileWriter.parse_multi_line_string(config_value.Description, ";   "))
        lines_to_write.extend(self.__generate_constraint_description_lines(config_value))
        return lines_to_write
    
    def __generate_constraint_description_lines(self, config_value: ConfigValue) -> list[str]:
        lines_to_write = []
        for constraint in config_value.Constraints:
            lines_to_write.extend(self.parse_multi_line_string(constraint.Description,";   "))
        return lines_to_write
    
    def __generate_default_and_config_value_lines(self, config_value: ConfigValue) -> list[str]:
        default_value = ConfigFileWriter.parse_multi_line_string(str(config_value.DefaultValue), ";   ")
        if len(default_value) > 0:
            default_value[0] = default_value[0].replace(";   ", ";   default = ")
        
        parsed_value = str(config_value.Value)
        if len(parsed_value) == 0:
            default_value.append(f"{config_value.Identifier} =\n")
        else:   
            value = ConfigFileWriter.parse_multi_line_string(parsed_value, "    ")
            if len(value) > 0:
                value[0] = value[0].replace("    ", f"{config_value.Identifier} = ")
            default_value.extend(value)
        return default_value

    def write_setting_block_to_file(self, lines: list[str]):
        lines.append(self.NEWLINE) #Add the empty line between settings
        if self.__writer:
            self.__writer.writelines(lines)
    
    @staticmethod
    def parse_multi_line_string(potential_multi_line_string: str, prefix: str) -> list[str]:
        if len(potential_multi_line_string) < 1:
            return []
        result = []
        split = potential_multi_line_string.split("\n")
        for s in split:
            result.append(prefix + s.strip() + ConfigFileWriter.NEWLINE)
        return result