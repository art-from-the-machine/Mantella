from enum import Enum
import os
from pathlib import Path
from tkinter import Tk, filedialog

from threading import Thread
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value_visitor import ConfigValueVisitor
from src.config.types.config_value import ConfigValue

class FileOrFolder(Enum):
    FILE = 1
    FOLDER = 2

class ConfigValuePath(ConfigValue[str]):
    def __init__(self, identifier: str, name: str, description: str, defaultValue: str, file_or_folder_that_must_be_present: str | None, constraints: list[ConfigValueConstraint[str]] = [], is_hidden: bool = False):
        super().__init__(identifier, name, description, defaultValue, constraints, is_hidden)
        self.__file_or_folder_that_must_be_present: str | None = file_or_folder_that_must_be_present
    
    @property
    def File_or_folder_that_must_be_present(self) -> str | None:
        return self.__file_or_folder_that_must_be_present

    @property
    def Type_to_look_for(self) -> FileOrFolder | None:
        if self.__file_or_folder_that_must_be_present:
            if '.' in self.__file_or_folder_that_must_be_present:
                return FileOrFolder.FILE
            else:
                return FileOrFolder.FOLDER
        return None

    def show_file_or_path_picker_dialog(self) -> str | None:
        result: list[str|None] = []
        t = Thread(target=self.__show_file_or_path_picker_dialog(result))
        t.setDaemon(True)
        t.start()
        t.join()
        if len(result) > 0:
            return result[0]
        return None

    def __show_file_or_path_picker_dialog(self, result: list[str| None]):
        root = Tk()
        root.attributes("-topmost", True)
        root.withdraw()
        if self.__file_or_folder_that_must_be_present and self.Type_to_look_for == FileOrFolder.FILE:
            filename, extension = os.path.splitext(self.__file_or_folder_that_must_be_present)
            filenames = filedialog.askopenfilename(parent=None,                                                    
                                                    title=f"Select file '{self.__file_or_folder_that_must_be_present}'",
                                                    initialdir=self.Value,
                                                    filetypes=[(self.__file_or_folder_that_must_be_present,f"*{extension}")])
            if len(filenames) > 0:
                root.destroy()
                result.append(str(os.path.dirname(filenames)))
            else:
                filename = "Files not seleceted"
                root.destroy()
                result.append(str(filename))
        else:
            filename = filedialog.askdirectory(parent= None,
                                                mustexist=True,
                                                title=f"Select folder for '{self.Name}'",
                                                initialdir=self.Value)
            if filename:
                if os.path.isdir(filename):
                    root.destroy()
                    result.append(str(filename))
                else:
                    root.destroy()
                    result.append(str(filename))
            else:
                filename = "Folder not seleceted"
                root.destroy()
                result.append(str(filename))        
    
    def does_value_cause_error(self, valueToCheck: str) -> ConfigValueConstraintResult:
        if not os.path.exists(valueToCheck):
            return ConfigValueConstraintResult(f"The selected folder '{valueToCheck}' for config value '{self.Name}' does not exist!")

        if self.__file_or_folder_that_must_be_present:             
            if self.Type_to_look_for == FileOrFolder.FILE:
                path_plus_file_name = os.path.join(valueToCheck, self.__file_or_folder_that_must_be_present)
                if not os.path.exists(path_plus_file_name) or not os.path.isfile(path_plus_file_name):
                    return ConfigValueConstraintResult(f"{valueToCheck} is not a file!")
                file_name = Path(path_plus_file_name).name
                if file_name != self.__file_or_folder_that_must_be_present:
                    return ConfigValueConstraintResult(f"Selected file {valueToCheck} is not '{self.__file_or_folder_that_must_be_present}'!")
            elif self.Type_to_look_for == FileOrFolder.FOLDER:
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
