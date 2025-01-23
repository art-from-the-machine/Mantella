from src.conversation.action import action
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_multi_selection import ConfigValueMultiSelection


class OtherDefinitions:
    #Base
    @staticmethod
    def get_show_first_time_setup_config_value() -> ConfigValue:
        return ConfigValueBool("first_time_setup","","Show Setup Guide on Startup",True, [], True)
    
    #UI
    @staticmethod
    def get_auto_launch_ui_config_value() -> ConfigValue:
        auto_launch_ui_description = """Whether the Mantella UI should launch automatically in your browser."""
        return ConfigValueBool("auto_launch_ui","Auto Launch UI",auto_launch_ui_description,True,tags=[ConfigValueTag.share_row])
    
    @staticmethod
    def get_play_startup_sound_config_value() -> ConfigValue:
        description = """Whether to play a startup sound when Mantella is ready."""
        return ConfigValueBool("play_startup_sound", "Play Startup Sound", description, False, tags=[ConfigValueTag.share_row])
    
    @staticmethod
    def get_automatic_greeting_config_value() -> ConfigValue:
        automatic_greeting_description = """Should a conversation be started with an automatic greeting from the LLM / NPC.
                                        - If enabled: Conversations are always started by the LLM.
                                        - If disabled: The LLM will not respond until the player speaks first."""
        return ConfigValueBool("automatic_greeting","Automatic Greeting",automatic_greeting_description,True,tags=[ConfigValueTag.share_row])
    
    @staticmethod
    def get_remove_mei_folders_config_value() -> ConfigValue:
        remove_mei_folders_description = """Clean up older instances of Mantella runtime folders from /data/tmp/_MEIxxxxxx.
                                            These folders build up over time when Mantella.exe is run.
                                            Enable this option to clean up these previous folders automatically when Mantella.exe is run.
                                            Disable this option if running this cleanup inteferes with other Python exes.
                                            For more details on what this is, see here: https://github.com/pyinstaller/pyinstaller/issues/2379"""
        return ConfigValueBool("remove_mei_folders","Cleanup MEI Folders",remove_mei_folders_description,True,tags=[ConfigValueTag.share_row])

    #Conversation        
    @staticmethod
    def get_active_actions(actions: list[action]) -> ConfigValue:
        description = "The actions Mantella will provide."
        default_value:list[str] = [a.name for a in actions]
        return ConfigValueMultiSelection("active_actions","Actions",description, default_value, default_value)
    
    @staticmethod
    def get_max_count_events_config_value() -> ConfigValue:
        max_count_events_description = """Maximum number of in-game events that are sent to the LLM per player message. 
                                    If the maximum number is reached, the oldest events will be dropped.
                                    Increasing this number will cost more prompt tokens and lead to the context limit being reached faster."""
        return ConfigValueInt("max_count_events","Max Count Events",max_count_events_description,5,0,999999,tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_events_refresh_time_config_value() -> ConfigValue:
        max_count_events_description = """Determines how much time (in seconds) can pass between the last NPC's response and the player's input before in-game events need to be refreshed.
                                        Note that updating in-game events increases response times. If the player responds before this set number in seconds, response times will be reduced.
                                        Increase this value to allow more time for the player to respond before events need to be refreshed. Decrease this value to make in-game events more up to date."""
        return ConfigValueInt("events_refresh_time","Time to Wait before Updating Events",max_count_events_description,10,0,999999,tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_hourly_time_config_value() -> ConfigValue:
        description = """If enabled, NPCs will be made aware of the time every in-game hour. Otherwise, time updates will be less granular (eg 'The conversation now takes place in the morning' / 'at night' etc).
                        To remove mentions of the hour entirely, prompts also need to be edited from 'The time is {time} {time_group}.' to 'The conversation takes place {time_group}.'"""
        return ConfigValueBool("hourly_time","Report In-Game Time Hourly",description,False,tags=[ConfigValueTag.advanced])
    
    #Player Character
    @staticmethod
    def get_player_character_description() -> ConfigValue:
        player_character_description_description = """A description of your player character in-game. This is sent to the LLM as part of the prompt using the '{player_description}' variable.
                                                    This is not meant to be a bio but rather a description how the NPC(s) perceive the player character when they speak to them.
                                                    e.g. 'A tall man with long red hair.'
                                                    If the in-game MCM offers to set this option the text sent from the game takes precendence over this."""
        return ConfigValueString("player_character_description","Player Character Description",player_character_description_description,"",tags=[ConfigValueTag.advanced])

    @staticmethod
    def get_voice_player_input() -> ConfigValue:
        voice_player_input_description = """Should the input of the player (both by text or voice) be spoken by the player character in-game?
                                            Can be used for immersion or to fill the initial gap between input and reply.
                                            Use the 'Player Voice Model' setting to select the voice model of the TTS for the player character."""
        return ConfigValueBool("voice_player_input","Voice Player Input",voice_player_input_description,False,tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_player_voice_model() -> ConfigValue:
        player_voice_model_description = """The voice model for the player character to use if 'Voice player input' is activated."""
        return ConfigValueString("player_voice_model","Player Voice Model",player_voice_model_description,"",tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    #HTTP
    @staticmethod
    def get_port_config_value() -> ConfigValue:
        return ConfigValueInt("port","Port","The port for the Mantella HTTP server to use.",4999, 0, 65535, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_show_http_debug_messages_config_value() -> ConfigValue:
        return ConfigValueBool("show_http_debug_messages","Show HTTP Debug Messages","Display the JSON going in and out of the server in Mantella.exe's log.", False, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    #Debugging
    @staticmethod
    def get_debugging_config_value() -> ConfigValue:
        return ConfigValueBool("debugging","Activate Debugging","Whether debugging is enabled.\nIf this is enabled, the values of all other variables in this section are ignored.", False, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_play_audio_from_script_config_value() -> ConfigValue:
        return ConfigValueBool("play_audio_from_script","Play Audio From Script","Whether to play the generated voicelines directly from the exe.\nEnable this value if testing Mantella while Skyrim is not running.", True, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_debugging_npc_config_value() -> ConfigValue:
        return ConfigValueString("debugging_npc","Debugging NPC","Selects the NPC to test.\nSet this value to None if you would instead prefer to select an NPC via the mod's spell / gun.", "Hulda", tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_use_default_player_response_config_value() -> ConfigValue:
        description = """Whether a default response is sent on the player's behalf (good for quickly testing if Mantella works without player input).
                        When this value is enabled, the sentence contained in default_player_response (see below) will be repeatedly sent to the LLM.
                        When this value is disabled, allows you to use mic / text input (depending on microphone_enabled setting)."""
        return ConfigValueBool("use_default_player_response","Use Default Player Response",description, False, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_default_player_response_config_value() -> ConfigValue:
        return ConfigValueString("default_player_response","Default Player Response","The default text sent to the LLM if 'Use Default Player Response' is enabled.", "Can you tell me something about yourself?", tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_exit_on_first_exchange_config_value() -> ConfigValue:
        description = """Whether to end the conversation after the first back and forth exchange.
                        Enable this value if testing conversation saving on exit functionality."""
        return ConfigValueBool("exit_on_first_exchange","Exit on First Exchange",description, False, tags=[ConfigValueTag.advanced])