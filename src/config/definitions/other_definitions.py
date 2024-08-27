from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_string import ConfigValueString


class OtherDefinitions:
    #Base
    @staticmethod
    def get_show_first_time_setup_config_value() -> ConfigValue:
        return ConfigValueBool("first_time_setup","","Show Setup Guide on Startup",True, [], True)
    
    #UI
    @staticmethod
    def get_auto_launch_ui_config_value() -> ConfigValue:
        auto_launch_ui_description = """Whether the Mantella UI should launch automatically in your browser."""
        return ConfigValueBool("auto_launch_ui","Auto Launch UI",auto_launch_ui_description,True)

    #Conversation
    @staticmethod
    def get_automatic_greeting_config_value() -> ConfigValue:
        automatic_greeting_description = """Should a conversation be started with an automatic greeting from the LLM / NPC.
                                        - If enabled: Conversations are always started by the LLM.
                                        - If disabled: The LLM will not respond until the player speaks first."""
        return ConfigValueBool("automatic_greeting","Automatic Greeting",automatic_greeting_description,True)
    
    @staticmethod
    def get_max_count_events_config_value() -> ConfigValue:
        max_count_events_description = """Maximum number of in-game events that can are sent to the LLM with one player message. 
                                    If the maximum number is reached, the oldest events will be dropped.
                                    Increasing this number will cost more prompt tokens and lead to the context limit being reached faster."""
        return ConfigValueInt("max_count_events","Max Count Events",max_count_events_description,5,0,999999)
    
    @staticmethod
    def get_hourly_time_config_value() -> ConfigValue:
        description = """If enabled, NPCs will be made aware of the time every in-game hour. Otherwise, time updates will be less granular (eg 'The conversation now takes place in the morning' / 'at night' etc).
                        To remove mentions of the hour entirely, prompts also need to be edited from 'The time is {time} {time_group}.' to 'The conversation takes place {time_group}.'"""
        return ConfigValueBool("hourly_time","Report In-Game Time Hourly",description,False)
    
    #Player Character
    @staticmethod
    def get_player_character_description() -> ConfigValue:
        player_character_description_description = """A description of your player character ingame. This is sent to the LLM as part of the prompt using the '{{player_description}}' variable.
                                                    This is not meant to be a bio but rather a description how the NPC(s) perceive the player character when they speak to them.
                                                    e.g. 'A tall man with long red hair.'
                                                    If the in-game MCM offers to set this option the text sent from the game takes precendence over this."""
        return ConfigValueString("player_character_description","Player Character Description",player_character_description_description,"")

    #MEI
    @staticmethod
    def get_remove_mei_folders_config_value() -> ConfigValue:
        remove_mei_folders_description = """Clean up older instances of Mantella runtime folders from /data/tmp/_MEIxxxxxx.
                                            These folders build up over time when Mantella.exe is run.
                                            Enable this option to clean up these previous folders automatically when Mantella.exe is run.
                                            Disable this option if running this cleanup inteferes with other Python exes.
                                            For more details on what this is, see here: https://github.com/pyinstaller/pyinstaller/issues/2379"""
        return ConfigValueBool("remove_mei_folders","Cleanup MEI Folders",remove_mei_folders_description,True)
    
    #HTTP
    @staticmethod
    def get_port_config_value() -> ConfigValue:
        return ConfigValueInt("port","Port","The port for the Mantella HTTP server to use.",4999, 0, 65535, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_show_http_debug_messages_config_value() -> ConfigValue:
        return ConfigValueBool("show_http_debug_messages","Show HTTP Debug Messages","Display the JSON going in and out of the server in Mantella.exe's log.", False, tags=[ConvigValueTag.advanced])
    
    #Debugging
    @staticmethod
    def get_debugging_config_value() -> ConfigValue:
        return ConfigValueBool("debugging","Activate Debugging","Whether debugging is enabled.\nIf this is enabled, the values of all other variables in this section are ignored.", False, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_play_audio_from_script_config_value() -> ConfigValue:
        return ConfigValueBool("play_audio_from_script","Play Audio From Script","Whether to play the generated voicelines directly from the exe.\nEnable this value if testing Mantella while Skyrim is not running.", True, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_debugging_npc_config_value() -> ConfigValue:
        return ConfigValueString("debugging_npc","Debugging NPC","Selects the NPC to test.\nSet this value to None if you would instead prefer to select an NPC via the mod's spell / gun.", "Hulda", tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_use_default_player_response_config_value() -> ConfigValue:
        description = """Whether a default response is sent on the player's behalf (good for quickly testing if Mantella works without player input).
                        When this value is enabled, the sentence contained in default_player_response (see below) will be repeatedly sent to the LLM.
                        When this value is disabled, allows you to use mic / text input (depending on microphone_enabled setting)."""
        return ConfigValueBool("use_default_player_response","Use Default Player Response",description, False, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_default_player_response_config_value() -> ConfigValue:
        return ConfigValueString("default_player_response","Default Player Response","The default text sent to the LLM if 'Use Default Player Response' is enabled.", "Can you tell me something about yourself?", tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_exit_on_first_exchange_config_value() -> ConfigValue:
        description = """Whether to end the conversation after the first back and forth exchange.
                        Enable this value if testing conversation saving on exit functionality."""
        return ConfigValueBool("exit_on_first_exchange","Exit on First Exchange",description, False, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_add_voicelines_to_all_voice_folders_config_value() -> ConfigValue:
        description = """Whether to add all generated voicelines to all Skyrim voice folders.
                        If you are experiencing issues with some NPCs not speaking, try enabling this value."""
        return ConfigValueBool("add_voicelines_to_all_voice_folders","Add Voicelines to All Voice Folders",description, False, tags=[ConvigValueTag.advanced])
    

