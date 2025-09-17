import configparser
import logging
import os
import sys
from typing import Any
from src.config.definitions.llm_definitions import NarrationHandlingEnum, NarrationIndicatorsEnum
from src.config.definitions.game_definitions import GameEnum
from src.config.definitions.tts_definitions import TTSEnum
from src.conversation.action import Action
from src.config.config_values import ConfigValues
from src.config.mantella_config_value_definitions_new import MantellaConfigValueDefinitionsNew
from src.config.config_json_writer import ConfigJsonWriter
from src.config.config_file_writer import ConfigFileWriter
from src.config.types.config_value_string import ConfigValueString
import src.utils as utils
from pathlib import Path
import json

class ConfigLoader:
    def __init__(self, mygame_folder_path: str, file_name='config.ini', game_override: GameEnum | None = None):
        self.is_run_integrated = "--integrated" in sys.argv
        self.save_folder = mygame_folder_path
        self.__has_any_value_changed: bool = False        
        self.__is_initial_load: bool = True
        self.__file_name = os.path.join(mygame_folder_path, file_name)
        self.__game_override = game_override
        path_to_actions = os.path.join(utils.resolve_path(),"data","actions")
        self.__actions = ConfigLoader.load_actions_from_json(path_to_actions)
        self.__definitions: ConfigValues = MantellaConfigValueDefinitionsNew.get_config_values(self.is_run_integrated, self.__actions, self.__on_config_value_change)
        if not os.path.exists(self.__file_name):
            logging.log(24,"Cannot find 'config.ini'. Assuming first time usage of MantellaSoftware and creating it.")
            self.__write_config_state(self.__definitions)

        config = configparser.ConfigParser()
        try:
            config.read(self.__file_name, encoding='utf-8')
        except Exception as e:
            logging.error(repr(e))
            logging.error(f'Unable to read / open config.ini. If you have recently edited this file, please try reverting to a previous version. This error is normally due to using special characters.')
            input("Press Enter to exit.")

        create_back_up_configini = False
        for section_name in config.sections():
            for (each_key, each_value) in config.items(section_name):
                try:
                    config_value = self.__definitions.get_config_value_definition(each_key)
                    # Unescape hash symbols that were escaped for INI file storage
                    unescaped_value = ConfigFileWriter.unescape_hash_symbols(each_value)
                    # Attempt to JSON-decode string values first if they were encoded to preserve whitespace
                    if isinstance(config_value, ConfigValueString):
                        try:
                            import json
                            decoded = json.loads(unescaped_value)
                            # Only accept if decoding produced a string
                            if isinstance(decoded, str):
                                config_value.parse(decoded)
                                continue
                        except Exception:
                            pass
                    config_value.parse(unescaped_value)
                except:
                    create_back_up_configini = True
                    # TODO: filter out warnings for ['game', 'skyrim_mod_folder', 'skyrimvr_mod_folder', 'fallout4_mod_folder', 'fallout4vr_mod_folder', fallout4vr_folder]
                    utils.play_error_sound()
                    logging.warning(f"Could not identify config value '{each_key} = {each_value}' in current config.ini. Value will not be loaded. A backup of this config.ini will be created.")

        if create_back_up_configini:
            self.__write_config_state(self.__definitions, True)
        
        self.__is_initial_load = False
        self.__update_config_values_from_current_state()
        self.__has_any_value_changed = False
    
    @property
    def have_all_config_values_loaded_correctly(self) -> bool:
        return self.__definitions.have_all_loaded_values_succeded
    
    @property
    def has_any_config_value_changed(self) -> bool:
        return self.__has_any_value_changed
    
    @property
    def definitions(self) -> ConfigValues:
        return self.__definitions
    
    def update_config_loader_with_changed_config_values(self):
        self.__update_config_values_from_current_state()
        self.__has_any_value_changed = False
    
    def __on_config_value_change(self):
        self.__has_any_value_changed = True
        if not self.__is_initial_load:
            self.__write_config_state(self.__definitions)
    
    def __write_config_state(self, definitions: ConfigValues, create_back_up_configini: bool = False):
        try:
            writer: ConfigFileWriter = ConfigFileWriter()
            writer.write(self.__file_name, definitions, create_back_up_configini)
        except Exception as e:
            utils.play_error_sound()
            logging.error(24, f"Failed to write default 'config.ini'. Possible reason: MantellaSoftware does not have rights to write at its location. Exception: {repr(e)}")    

    def __update_config_values_from_current_state(self):
        self.__definitions.clear_constraint_violations()
        try:
            # if the exe is being run by another process, replace config.ini paths with relative paths
            if "--integrated" in sys.argv:
                # Plugins/MantellaSoftware folder
                exe_folder = Path(utils.resolve_path())
                # Working backwards from MantellaSoftware (where the .exe runs) -> Plugins -> F4SE/SKSE -> Data (mod folder) -> Game
                self.game_path = str(exe_folder.parent.parent.parent.parent)
                # Working backwards from MantellaSoftware (where the .exe runs) -> Plugins -> F4SE/SKSE -> Data (mod folder)
                self.mod_path = str(exe_folder.parent.parent.parent)

                self.lipgen_path = self.game_path+"\\Tools\\LipGen\\"
                self.facefx_path = self.mod_path+"\\Sound\\Voice\\Processing\\"
                self.piper_path = str(Path(utils.resolve_path())) + "\\piper"
                self.moonshine_folder = str(Path(utils.resolve_path()))

                game_parent_folder_name = os.path.basename(self.game_path).lower()
                if 'vr' in game_parent_folder_name:
                    if 'fallout' in game_parent_folder_name:
                        self.game = GameEnum.FALLOUT4_VR
                        # Fallout 4 VR uses the same creation kit as Fallout 4, so the lip gen folder needs to be set to the Fallout 4 folder
                        # Note that this path assumes that both Fallout 4 versions are installed in the same directory
                        # Working backwards from MantellaSoftware (where the .exe runs) -> Plugins -> F4SE -> Data -> Fallout 4 VR -> common (Steam folder for all games)
                        if not os.path.exists(self.lipgen_path):
                            self.lipgen_path = str(exe_folder.parent.parent.parent.parent.parent)+"\\Fallout 4"+"\\Tools\\LipGen\\"
                            if not os.path.exists(self.lipgen_path):
                                self.lipgen_path = ''
                    elif 'skyrim' in game_parent_folder_name:
                        self.game = GameEnum.SKYRIM_VR
                        # Skyrim VR uses the same creation kit as Skyrim Special Edition, so the lip gen folder needs to be set to the Skyrim Special Edition folder
                        # Note that this path assumes that both Skyrim versions are installed in the same directory
                        # Working backwards from MantellaSoftware (where the .exe runs) -> Plugins -> SKSE -> Data -> Skyrim VR -> common (Steam folder for all games)
                        if not os.path.exists(self.lipgen_path):
                            self.lipgen_path = str(exe_folder.parent.parent.parent.parent.parent)+"\\Skyrim Special Edition"+"\\Tools\\LipGen\\"
                            if not os.path.exists(self.lipgen_path):
                                self.lipgen_path = ''
                else:
                    if 'fallout' in game_parent_folder_name:
                        self.game = GameEnum.FALLOUT4
                    elif 'skyrim' in game_parent_folder_name:
                        self.game = GameEnum.SKYRIM
                    else: # default to Skyrim
                        self.game = GameEnum.SKYRIM

            else:
                # Allow chosen game to be overriden for testing purposes
                if self.__game_override:
                    self.game = self.__game_override
                else:
                    self.game: GameEnum = self.__definitions.get_enum_value("game", GameEnum)
                
                if self.game == GameEnum.FALLOUT4:
                    self.game_path: str = self.__definitions.get_string_value("fallout4_folder")
                    self.mod_path: str = self.__definitions.get_string_value("fallout4_mod_folder")
                elif self.game == GameEnum.FALLOUT4_VR:
                    self.game_path: str = self.__definitions.get_string_value("fallout4vr_folder")
                    self.mod_path: str = self.__definitions.get_string_value("fallout4vr_mod_folder")
                elif self.game == GameEnum.SKYRIM_VR:
                    self.game_path = None
                    self.mod_path: str = self.__definitions.get_string_value("skyrimvr_mod_folder")
                #if the game is not recognized Mantella will assume it's Skyrim since that's the most frequent one.
                else:
                    self.game = GameEnum.SKYRIM
                    self.game_path = None
                    self.mod_path: str = self.__definitions.get_string_value("skyrim_mod_folder")

                self.lipgen_path = self.__definitions.get_string_value("lipgen_folder")
                self.facefx_path = self.__definitions.get_string_value("facefx_folder")

            self.mod_path_base = self.mod_path
            self.mod_path += "\\Sound\\Voice\\Mantella.esp"

            selected_actions = self.__definitions.get_string_list_value("active_actions")
            self.actions = [a for a in self.__actions if a.name in selected_actions]

            self.language = self.__definitions.get_string_value("language")
            self.end_conversation_keyword = self.__definitions.get_string_value("end_conversation_keyword")
            self.goodbye_npc_response = self.__definitions.get_string_value("goodbye_npc_response")
            self.collecting_thoughts_npc_response = self.__definitions.get_string_value("collecting_thoughts_npc_response")
            for a in self.__actions:
                identifier = a.identifier.lstrip("mantella_").lstrip("npc_")
                a.keyword = self.__definitions.get_string_value(f"{identifier}_npc_response")

            #TTS
            self.tts_service: TTSEnum = self.__definitions.get_enum_value("tts_service", TTSEnum)
            self.xtts_url = self.__definitions.get_string_value("xtts_url").rstrip('/')

            # Do not check if a given path exists unless the TTS service is actually selected
            validate_xtts_path = validate_xvasynth_path = validate_piper_path = False

            if self.tts_service == TTSEnum.XTTS:
                if 'http://127.0.0.1:8020' in self.xtts_url: # Only validate the XTTS folder if running locally
                   validate_xtts_path = True
            elif self.tts_service == TTSEnum.XVASYNTH:
                validate_xvasynth_path = True
            elif self.tts_service == TTSEnum.PIPER:
                validate_piper_path = True

            self.xtts_server_path = self.__definitions.get_string_value("xtts_server_folder", validate_xtts_path)
            self.xvasynth_path = self.__definitions.get_string_value("xvasynth_folder", validate_xvasynth_path)
            if not hasattr(self, 'piper_path'): # assign Piper path from config if not running integrated
                self.piper_path = self.__definitions.get_string_value("piper_folder", validate_piper_path)

            self.lip_generation = self.__definitions.get_string_value("lip_generation").strip().lower()
            self.fast_response_mode = self.__definitions.get_bool_value("fast_response_mode")
            self.fast_response_mode_volume = self.__definitions.get_int_value("fast_response_mode_volume")

            #Added from xTTS implementation
            self.xtts_default_model = self.__definitions.get_string_value("xtts_default_model")
            self.xtts_deepspeed = self.__definitions.get_bool_value("xtts_deepspeed")
            self.xtts_lowvram = self.__definitions.get_bool_value("xtts_lowvram")
            self.xtts_device = self.__definitions.get_string_value("xtts_device")
            self.number_words_tts = self.__definitions.get_int_value("number_words_tts")
            self.xtts_data = self.__definitions.get_string_value("xtts_data")
            self.xtts_accent = self.__definitions.get_bool_value("xtts_accent")

            self.tts_print = self.__definitions.get_bool_value("tts_print")
        
            self.xvasynth_process_device = self.__definitions.get_string_value("tts_process_device")
            self.pace = self.__definitions.get_float_value("pace")
            self.use_cleanup = self.__definitions.get_bool_value("use_cleanup")
            self.use_sr = self.__definitions.get_bool_value("use_sr")

            #STT
            self.stt_service = self.__definitions.get_string_value("stt_service").lower()
            self.moonshine_model = self.__definitions.get_string_value("moonshine_model_size")
            if not hasattr(self, 'moonshine_folder'):
                try:
                    self.moonshine_folder = str(Path(self.__definitions.get_string_value("moonshine_folder")).parent) # go up one folder since moonshine/ is in the model name
                except:
                    self.moonshine_folder = ''
            self.whisper_model = self.__definitions.get_string_value("whisper_model_size")
            self.whisper_process_device = self.__definitions.get_string_value("process_device")
            self.stt_language = self.__definitions.get_string_value("stt_language")
            if (self.stt_language == 'default'):
                self.stt_language = self.language
            self.stt_translate = self.__definitions.get_bool_value("stt_translate")
            self.audio_threshold = self.__definitions.get_float_value("audio_threshold")
            self.proactive_mic_mode = self.__definitions.get_bool_value("proactive_mic_mode")
            self.min_refresh_secs = self.__definitions.get_float_value("min_refresh_secs")
            self.play_cough_sound = self.__definitions.get_bool_value("play_cough_sound")
            self.allow_interruption = self.__definitions.get_bool_value("allow_interruption")
            self.ptt_enabled = self.__definitions.get_bool_value("ptt_enabled")
            self.ptt_hotkey = self.__definitions.get_string_value("ptt_hotkey")
            self.save_mic_input = self.__definitions.get_bool_value("save_mic_input")
            self.pause_threshold = self.__definitions.get_float_value("pause_threshold")
            self.listen_timeout = self.__definitions.get_int_value("listen_timeout")
            self.external_whisper_service = self.__definitions.get_bool_value("external_whisper_service")
            self.whisper_url = self.__definitions.get_string_value("whisper_url")

            #LLM
            self.max_response_sentences_single = self.__definitions.get_int_value("max_response_sentences_single")
            self.max_response_sentences_multi = self.__definitions.get_int_value("max_response_sentences_multi")
            self.llm = self.__definitions.get_string_value("model")
            self.llm = self.llm.split(' |')[0] if ' |' in self.llm else self.llm
            self.wait_time_buffer = self.__definitions.get_float_value("wait_time_buffer")
            self.llm_api = self.__definitions.get_string_value("llm_api")
            # self.llm_priority = self.__definitions.get_string_value("llm_priority")
            # if self.llm_api == "Custom":
            #     self.llm_api = self.__definitions.get_string_value("llm_custom_service_url")
            self.custom_token_count = self.__definitions.get_int_value("custom_token_count")
            try:
                self.llm_params: dict[str, Any] | None = json.loads(self.__definitions.get_string_value("llm_params").replace('\n', ''))
            except Exception as e:
                logging.error(f"""Error in parsing LLM parameter list: {e}
LLM parameter list must follow the Python dictionary format: https://www.w3schools.com/python/python_dictionaries.asp""")
                self.llm_params = None

            self.allow_per_character_llm_overrides = self.__definitions.get_bool_value("allow_per_character_llm_overrides")
            self.enable_character_tag_reading = self.__definitions.get_bool_value("enable_character_tag_reading")

            # Profile application settings
            self.apply_profile_one_on_one = self.__definitions.get_bool_value("apply_profile_one_on_one")
            self.apply_profile_multi_npc = self.__definitions.get_bool_value("apply_profile_multi_npc")
            self.apply_profile_summaries = self.__definitions.get_bool_value("apply_profile_summaries")

            # Multi-NPC LLM Configuration
            self.multi_npc_llm_api = self.__definitions.get_string_value("multi_npc_llm_api")
            self.multi_npc_llm = self.__definitions.get_string_value("multi_npc_model")
            self.multi_npc_llm = self.multi_npc_llm.split(' |')[0] if ' |' in self.multi_npc_llm else self.multi_npc_llm
            self.multi_npc_custom_token_count = self.__definitions.get_int_value("multi_npc_custom_token_count")
            try:
                self.multi_npc_llm_params: dict[str, Any] | None = json.loads(self.__definitions.get_string_value("multi_npc_llm_params").replace('\n', ''))
            except Exception as e:
                logging.error(f"""Error in parsing Multi-NPC LLM parameter list: {e}
Multi-NPC LLM parameter list must follow the Python dictionary format: https://www.w3schools.com/python/python_dictionaries.asp""")
                self.multi_npc_llm_params = None

            # Summary LLM Configuration
            self.summary_llm_api = self.__definitions.get_string_value("summary_llm_api")
            self.summary_llm = self.__definitions.get_string_value("summary_model")
            self.summary_llm = self.summary_llm.split(' |')[0] if ' |' in self.summary_llm else self.summary_llm
            self.summary_custom_token_count = self.__definitions.get_int_value("summary_custom_token_count")
            try:
                self.summary_llm_params: dict[str, Any] | None = json.loads(self.__definitions.get_string_value("summary_llm_params").replace('\n', ''))
            except Exception as e:
                logging.error(f"""Error in parsing Summary LLM parameter list: {e}
Summary LLM parameter list must follow the Python dictionary format: https://www.w3schools.com/python/python_dictionaries.asp""")
                self.summary_llm_params = None

            # self.stop_llm_generation_on_assist_keyword: bool = self.__definitions.get_bool_value("stop_llm_generation_on_assist_keyword")

            self.narration_handling: NarrationHandlingEnum = self.__definitions.get_enum_value("narration_handling", NarrationHandlingEnum)
            self.narrator_voice = self.__definitions.get_string_value("narrator_voice")
            self.narration_start_indicators = self.__definitions.get_string_list_value("narration_start_indicators")
            self.narration_end_indicators = self.__definitions.get_string_list_value("narration_end_indicators")
            self.speech_start_indicators = self.__definitions.get_string_list_value("speech_start_indicators")
            self.speech_end_indicators = self.__definitions.get_string_list_value("speech_end_indicators")
            self.narration_indicators: NarrationIndicatorsEnum = self.__definitions.get_enum_value("narration_indicators", NarrationIndicatorsEnum)
            
            self.remove_mei_folders = self.__definitions.get_bool_value("remove_mei_folders")

            #UI
            self.auto_launch_ui = self.__definitions.get_bool_value("auto_launch_ui")

            self.play_startup_sound = self.__definitions.get_bool_value("play_startup_sound")

            #Conversation
            self.automatic_greeting = self.__definitions.get_bool_value("automatic_greeting")
            self.conversation_summary_enabled = self.__definitions.get_bool_value("conversation_summary_enabled")
            
            # Random LLM Selection
            self.random_llm_one_on_one_enabled = self.__definitions.get_bool_value("random_llm_one_on_one_enabled")
            self.random_llm_multi_npc_enabled = self.__definitions.get_bool_value("random_llm_multi_npc_enabled")
            self.random_llm_one_on_one_per_request_enabled = self.__definitions.get_bool_value("random_llm_one_on_one_per_request_enabled")
            self.random_llm_multi_npc_per_request_enabled = self.__definitions.get_bool_value("random_llm_multi_npc_per_request_enabled")
            try:
                self.llm_pool_one_on_one = json.loads(self.__definitions.get_string_value("llm_pool_one_on_one"))
            except Exception as e:
                logging.error(f"Error parsing one-on-one LLM pool: {e}")
                self.llm_pool_one_on_one = []
            try:
                self.llm_pool_multi_npc = json.loads(self.__definitions.get_string_value("llm_pool_multi_npc"))
            except Exception as e:
                logging.error(f"Error parsing multi-NPC LLM pool: {e}")
                self.llm_pool_multi_npc = []
            
            self.max_count_events = self.__definitions.get_int_value("max_count_events")
            self.events_refresh_time = self.__definitions.get_int_value("events_refresh_time")
            self.hourly_time = self.__definitions.get_bool_value("hourly_time")
            self.player_character_description: str = self.__definitions.get_string_value("player_character_description")
            self.voice_player_input: bool = self.__definitions.get_bool_value("voice_player_input")
            self.player_voice_model: str = self.__definitions.get_string_value("player_voice_model")

            #HTTP
            self.port = self.__definitions.get_int_value("port")
            self.show_http_debug_messages: bool = self.__definitions.get_bool_value("show_http_debug_messages")

            self.advanced_logs = self.__definitions.get_bool_value("advanced_logs")

            self.save_audio_data_to_character_folder = self.__definitions.get_bool_value("save_audio_data_to_character_folder")

            #new separate prompts for Fallout 4 have been added 
            if self.game.base_game == GameEnum.FALLOUT4:
                self.prompt = self.__definitions.get_string_value("fallout4_prompt")
                self.multi_npc_prompt = self.__definitions.get_string_value("fallout4_multi_npc_prompt")
                self.radiant_prompt = self.__definitions.get_string_value("fallout4_radiant_prompt")
            else:
                self.prompt = self.__definitions.get_string_value("skyrim_prompt")
                self.multi_npc_prompt = self.__definitions.get_string_value("skyrim_multi_npc_prompt")
                self.radiant_prompt = self.__definitions.get_string_value("skyrim_radiant_prompt")

            self.radiant_start_prompt = self.__definitions.get_string_value("radiant_start_prompt")
            self.radiant_end_prompt = self.__definitions.get_string_value("radiant_end_prompt")
            self.memory_prompt = self.__definitions.get_string_value("memory_prompt")
            self.resummarize_prompt = self.__definitions.get_string_value("resummarize_prompt")
            self.vision_prompt = self.__definitions.get_string_value("vision_prompt")

            # Vision
            self.vision_enabled = self.__definitions.get_bool_value('vision_enabled')
            self.low_resolution_mode = self.__definitions.get_bool_value("low_resolution_mode")
            self.save_screenshot = self.__definitions.get_bool_value('save_screenshot')
            self.image_quality = self.__definitions.get_int_value("image_quality")
            self.resize_method = self.__definitions.get_string_value("resize_method")
            self.capture_offset = json.loads(self.__definitions.get_string_value("capture_offset"))
            self.use_game_screenshots = self.__definitions.get_bool_value("use_game_screenshots")

            # Custom Vision Model
            self.custom_vision_model = self.__definitions.get_bool_value("custom_vision_model")
            self.vision_llm_api = self.__definitions.get_string_value("vision_llm_api")
            self.vision_llm = self.__definitions.get_string_value("vision_model")
            self.vision_llm = self.vision_llm.split(' |')[0] if ' |' in self.vision_llm else self.vision_llm
            self.vision_custom_token_count = self.__definitions.get_int_value("vision_custom_token_count")
            try:
                self.vision_llm_params = json.loads(self.__definitions.get_string_value("vision_llm_params").replace('\n', ''))
            except Exception as e:
                logging.error(f"""Error in parsing LLM parameter list: {e}
LLM parameter list must follow the Python dictionary format: https://www.w3schools.com/python/python_dictionaries.asp""")
                self.vision_llm_params = None
            
            pass
        except Exception as e:
            utils.play_error_sound()
            logging.error('Parameter missing/invalid in config.ini file!')
            raise e
    
    @staticmethod
    def load_actions_from_json(actions_folder: str) -> list[Action]:
        result = []
        os.makedirs(actions_folder, exist_ok=True)
        override_files: list[str] = os.listdir(actions_folder)
        for file in override_files:
            try:
                filename, extension = os.path.splitext(file)
                full_path_file = os.path.join(actions_folder,file)
                if extension == ".json":
                    with open(full_path_file) as fp:
                        json_object = json.load(fp)
                        if isinstance(json_object, dict):#Otherwise it is already a list
                            json_object = [json_object]
                        for json_content in json_object:
                            content: dict[str, str] = json_content
                            identifier: str = content.get("identifier", "").lower() # IDs must be lower case to avoid issues with case sensitivity
                            name: str = content.get("name", "")
                            key: str = content.get("key", "")
                            description: str = content.get("description", "")
                            prompt: str = content.get("prompt", "")
                            is_interrupting: bool = bool(content.get("is-interrupting", ""))
                            one_on_one: bool = bool(content.get("one-on-one", ""))
                            multi_npc: bool = bool(content.get("multi-npc", ""))
                            radiant: bool = bool(content.get("radiant", ""))
                            info_text: str = content.get("info-text", "")
                            result.append(Action(identifier, name, key,description,prompt,is_interrupting, one_on_one,multi_npc,radiant,info_text))
            except Exception as e:
                utils.play_error_sound()
                logging.log(logging.WARNING, f"Could not load action definition file '{file}' in '{actions_folder}'. Most likely there is an error in the formating of the file. Error: {e}")
        return result