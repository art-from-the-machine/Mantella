import os
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_path import ConfigValuePath
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from enum import Enum, auto

class GameEnum(Enum):
    SKYRIM = auto()
    SKYRIM_VR = auto()
    FALLOUT4 = auto()
    FALLOUT4_VR = auto()

    @property
    def display_name(self) -> str:
        return {
            self.SKYRIM: 'Skyrim',
            self.SKYRIM_VR: 'SkyrimVR',
            self.FALLOUT4: 'Fallout4',
            self.FALLOUT4_VR: 'Fallout4VR',
        }[self]
    
    @property
    def is_vr(self) -> bool:
        return self in [
            self.SKYRIM_VR, 
            self.FALLOUT4_VR,
        ]
    
    @property
    def base_game(self) -> 'GameEnum':
        return {
            self.SKYRIM: GameEnum.SKYRIM,
            self.SKYRIM_VR: GameEnum.SKYRIM,
            self.FALLOUT4: GameEnum.FALLOUT4,
            self.FALLOUT4_VR: GameEnum.FALLOUT4,
        }[self]


class GameDefinitions:
    MOD_FOLDER_DESCRIPTION = """If you are using Mod Organizer 2, this path can be found by right-clicking the Mantella mod in your mod list and selecting 'Open in Explorer'.
        If you are using Vortex, this path needs to be set to your {0}\\Data folder.
        eg C:\\Games\\Steam\\steamapps\\common\\{0}\\Data.
        If this path is incorrect, NPCs will say the same voiceline on repeat."""
    
    class ProgramFilesChecker(ConfigValueConstraint[str]):
        def __init__(self, game_name: str) -> None:
            super().__init__()
            self.__game_name = game_name

        def apply_constraint(self, value_to_apply_to: str) -> ConfigValueConstraintResult:
            if 'Program Files' in value_to_apply_to:
                return ConfigValueConstraintResult(f'''
{self.__game_name} is installed in Program Files. Mantella is unlikely to work. 
See here to learn how to move your game's installation folder: https://art-from-the-machine.github.io/Mantella/pages/installation.html#skyrim''')
            else:
                return ConfigValueConstraintResult()
    
    class ModFolderChecker(ConfigValueConstraint[str]):
        def __init__(self, mod_folder_config_value: str) -> None:
            super().__init__()
            self.__mod_folder_config_value = mod_folder_config_value

        def apply_constraint(self, value_to_apply_to: str) -> ConfigValueConstraintResult:
            if not os.path.exists(f"{value_to_apply_to}\\Sound\\Voice\\Mantella.esp"):
                return ConfigValueConstraintResult(f"""Error setting '{self.__mod_folder_config_value} = {value_to_apply_to}' 
Expected subfolders '{value_to_apply_to}\\Sound\\Voice\\Mantella.esp' do not seem to exist.
The correct location to set this config value to depends on your mod manager. 
Please see here to learn where to set this value: https://art-from-the-machine.github.io/Mantella/pages/installation.html#setup-configuration""")
            return ConfigValueConstraintResult()

    @staticmethod
    def get_game_config_value() -> ConfigValue:
        options = [e.display_name for e in GameEnum]
        return ConfigValueSelection("game","Game","Choose the game to run with Mantella.",GameEnum.SKYRIM_VR.display_name,options,list(GameEnum))
    
    @staticmethod
    def get_skyrim_mod_folder_config_value() -> ConfigValue:
        identifier = "skyrim_mod_folder"
        game_folder = "Skyrim Special Edition"
        return ConfigValuePath(identifier, f"{game_folder}: Path to Mantella Spell Mod", GameDefinitions.MOD_FOLDER_DESCRIPTION.format(game_folder), "C:\\Modding\\MO2\\Skyrim\\mods\\Mantella","Sound",[GameDefinitions.ModFolderChecker(identifier)])

    @staticmethod
    def get_skyrimvr_mod_folder_config_value() -> ConfigValue:
        identifier = "skyrimvr_mod_folder"
        game_folder = "Skyrim VR"
        return ConfigValuePath(identifier, f"{game_folder}: Path to Mantella Spell Mod", GameDefinitions.MOD_FOLDER_DESCRIPTION.format(game_folder), "C:\\Modding\\MO2\\SkyrimVR\\mods\\Mantella","Sound",[GameDefinitions.ModFolderChecker(identifier)])

    @staticmethod
    def get_fallout4_mod_folder_config_value() -> ConfigValue:
        identifier = "fallout4_mod_folder"
        game_folder = "Fallout 4"
        return ConfigValuePath(identifier, f"{game_folder}: Path to Mantella Gun Mod", GameDefinitions.MOD_FOLDER_DESCRIPTION.format(game_folder), "C:\\Modding\\MO2\\Fallout4\\mods\\Mantella","Sound",[GameDefinitions.ModFolderChecker(identifier)])

    @staticmethod
    def get_fallout4vr_mod_folder_config_value() -> ConfigValue:
        identifier = "fallout4vr_mod_folder"
        game_folder = "Fallout 4 VR"
        return ConfigValuePath(identifier, f"{game_folder}: Path to Mantella Gun Mod", GameDefinitions.MOD_FOLDER_DESCRIPTION.format(game_folder), "C:\\Modding\\MO2\\Fallout4VR\\mods\\Mantella","Sound",[GameDefinitions.ProgramFilesChecker(game_folder), GameDefinitions.ModFolderChecker(identifier)])
    
    @staticmethod
    def get_fallout4_folder_config_value() -> ConfigValue:
        description = """The filepath of the Fallout 4 (desktop) directory where the executable is located.
                        This path only needs to be set if `Vision`->`Use Game Screenshots` is enabled."""
        return ConfigValuePath("fallout4_folder", "Fallout 4: Path to Fallout 4 Folder", description, "C:\\Games\\Steam\\steamapps\\common\\Fallout 4", "Fallout4.exe", [GameDefinitions.ProgramFilesChecker("Fallout4")], tags=[ConfigValueTag.advanced])

    @staticmethod
    def get_fallout4vr_folder_config_value() -> ConfigValue:
        fallout4vr_folder_description = """The filepath of the Fallout 4 VR directory where the executable is located.
                        This path only needs to be set if `Vision`->`Use Game Screenshots` is enabled."""
        return ConfigValuePath("fallout4vr_folder", "Fallout 4 VR: Path to Fallout 4 VR Folder", fallout4vr_folder_description, "C:\\Games\\Steam\\steamapps\\common\\Fallout4VR","Fallout4VR.exe",[GameDefinitions.ProgramFilesChecker("Fallout4VR")], tags=[ConfigValueTag.advanced])