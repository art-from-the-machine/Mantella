from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_string import ConfigValueString


class OtherDefinitions:
    #Base
    @staticmethod
    def get_show_first_time_setup_config_value() -> ConfigValue:
        return ConfigValueBool("first_time_setup","","Show setup guide on startup?",True, [], True)
    
    #Conversation
    @staticmethod
    def get_automatic_greeting_folder_config_value() -> ConfigValue:
        automatic_greeting_description = """Should a pc-to-npc conversation be started by an automatic greeting from the player
                                        If True: A conversation is always started by a language specific "Hello npc_name" from the side of the player
                                            -> followed by a first reply from the LLM
                                            -> followed by the first actual message of the player
                                        If False: A conversation is started right away by a message the player can submit"""
        return ConfigValueBool("automatic_greeting","Automatic greeting",automatic_greeting_description,True)

    #MEI
    @staticmethod
    def get_remove_mei_folders_config_value() -> ConfigValue:
        remove_mei_folders_description = """Clean up older instances of Mantella runtime folders from MantellaSoftware/data/tmp/_MEIxxxxxx
                                            These folders build up over time when Mantella.exe is run
                                            Enable this option to clean up these previous folders automatically when Mantella.exe is run
                                            Disable this option if running this cleanup inteferes with other Python exes
                                            For more details on what this is, see here: https://github.com/pyinstaller/pyinstaller/issues/2379"""
        return ConfigValueBool("remove_mei_folders","Remove mei folders",remove_mei_folders_description,False, tags=[ConvigValueTag.advanced])
    
    #HTTP
    @staticmethod
    def get_port_config_value() -> ConfigValue:
        return ConfigValueInt("port","Port","The port for the http server to use",4999, 0, 65535, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_show_http_debug_messages_config_value() -> ConfigValue:
        return ConfigValueBool("show_http_debug_messages","Show http debug messages","Display the JSON going in and out of the server in MantellaSoftware's log", False, tags=[ConvigValueTag.advanced])
    
    #Debugging
    @staticmethod
    def get_debugging_config_value() -> ConfigValue:
        return ConfigValueBool("debugging","Activate debugging","Whether debugging is enabled.\nIf this is set to True, the values of all other variables in this section are ignored", False, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_play_audio_from_script_config_value() -> ConfigValue:
        return ConfigValueBool("play_audio_from_script","Play audio from script","Whether to play the generated voicelines directly from the script / exe.\nSet this value to True if testing Mantella while Skyrim is not running", True, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_debugging_npc_config_value() -> ConfigValue:
        return ConfigValueString("debugging_npc","Debugging NPC","Selects the NPC to test.\nSet this value to None if you would instead prefer to select an NPC via the mod's spell", "Hulda", tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_use_default_player_response_config_value() -> ConfigValue:
        description = """Whether a default response is sent on the player's behalf (good for quickly testing if Mantella works without player input)
                        When this value is set to True, the sentence contained in default_player_response (see below) will be repeatedly sent to the LLM.
                        When this value is set to False, allows you to use mic / text input (depending on microphone_enabled setting)"""
        return ConfigValueBool("use_default_player_response","Use default player response",description, False, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_default_player_response_config_value() -> ConfigValue:
        return ConfigValueString("default_player_response","Default player response","The default text sent to the LLM if use_default_player_response is enabled", "Can you tell me something about yourself?", tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_exit_on_first_exchange_config_value() -> ConfigValue:
        description = """Whether to end the conversation after the first back and forth exchange
                        Set this value to True if testing conversation saving on exit functionality"""
        return ConfigValueBool("exit_on_first_exchange","Exit on first exchange",description, False, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_add_voicelines_to_all_voice_folders_config_value() -> ConfigValue:
        description = """Whether to add all generated voicelines to all Skyrim voice folders
                        If you are experiencing issues with some NPCs not speaking, try setting this value to True"""
        return ConfigValueBool("add_voicelines_to_all_voice_folders","Add voicelines to all voice folders",description, False, tags=[ConvigValueTag.advanced])
    

