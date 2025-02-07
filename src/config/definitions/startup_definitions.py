from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_bool import ConfigValueBool

class StartupDefinitions:
    @staticmethod
    def get_auto_launch_ui_config_value() -> ConfigValue:
        description = """Whether the Mantella UI should launch automatically in your browser."""
        return ConfigValueBool("auto_launch_ui","Auto Launch UI", description, True, tags=[ConfigValueTag.share_row])
    
    @staticmethod
    def get_play_startup_sound_config_value() -> ConfigValue:
        description = """Whether to play a startup sound to let you know when Mantella is ready."""
        return ConfigValueBool("play_startup_sound", "Play Startup Sound", description, True, tags=[ConfigValueTag.share_row])
    
    @staticmethod
    def get_remove_mei_folders_config_value() -> ConfigValue:
        description = """Clean up older instances of Mantella runtime folders from /data/tmp/_MEIxxxxxx.
                                            These folders build up over time when Mantella.exe is run.
                                            Enable this option to clean up these previous folders automatically when Mantella.exe is run.
                                            Disable this option if running this cleanup inteferes with other Python exes.
                                            For more details on what this is, see here: https://github.com/pyinstaller/pyinstaller/issues/2379"""
        return ConfigValueBool("remove_mei_folders","Cleanup MEI Folders", description, True, tags=[ConfigValueTag.advanced])