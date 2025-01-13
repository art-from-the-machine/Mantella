import configparser
import logging
import os
import sys
from src.conversation.action import action
from src.config.config_values import ConfigValues
from src.config.mantella_config_value_definitions_new import MantellaConfigValueDefinitionsNew
from src.config.config_json_writer import ConfigJsonWriter
from src.config.config_file_writer import ConfigFileWriter
import src.utils as utils
from pathlib import Path
import json

class ConfigLoader:
    def __init__(self, mygame_folder_path: str, file_name='config.ini'):
        self.is_run_integrated = "--integrated" in sys.argv
        self.save_folder = mygame_folder_path
        self.__has_any_value_changed: bool = False        
        self.__is_initial_load: bool = True
        self.__file_name = os.path.join(mygame_folder_path, file_name)
        path_to_actions = os.path.join(utils.resolve_path(),"data","actions")
        self.__actions = self.load_actions_from_json(path_to_actions)
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
                    config_value.parse(each_value)
                except:
                    create_back_up_configini = True
                    # TODO: filter out warnings for ['game', 'skyrim_mod_folder', 'skyrimvr_mod_folder', 'fallout4_mod_folder', 'fallout4vr_mod_folder', fallout4vr_folder]
                    logging.warning(f"Could not identify config value '{each_key} = {each_value}' in current config.ini. Value will not be loaded. A backup of this config.ini will be created.")

        if create_back_up_configini:
            self.__write_config_state(self.__definitions, True)
        
        self.__is_initial_load = False
        self.__update_config_values_from_current_state()
    
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
                self.game_path = str(Path(utils.resolve_path()).parent.parent.parent.parent)
                self.mod_path = str(Path(utils.resolve_path()).parent.parent.parent)

                game_parent_folder_name = os.path.basename(self.game_path).lower()
                if 'vr' in game_parent_folder_name:
                    if 'fallout' in game_parent_folder_name:
                        self.game = 'Fallout4VR'
                    elif 'skyrim' in game_parent_folder_name:
                        self.game = 'SkyrimVR'
                else:
                    if 'fallout' in game_parent_folder_name:
                        self.game = 'Fallout4'
                    elif 'skyrim' in game_parent_folder_name:
                        self.game = 'Skyrim'
                    else: # default to Skyrim
                        self.game = 'Skyrim'

                self.facefx_path = str(Path(utils.resolve_path()).parent.parent.parent)
                self.facefx_path += "\\Sound\\Voice\\Processing\\"
                #self.xvasynth_path = str(Path(utils.resolve_path())) + "\\xVASynth"
                self.piper_path = str(Path(utils.resolve_path())) + "\\piper"

            else:
                #Adjusting game and mod paths according to the game being ran
                self.game: str = self.__definitions.get_string_value("game")# config['Game']['game']
                self.game = str(self.game).lower().replace(' ', '').replace('_', '')
                if self.game =="fallout4":
                    self.game ="Fallout4"
                    self.game_path: str = self.__definitions.get_string_value("fallout4_folder")
                    self.mod_path: str = self.__definitions.get_string_value("fallout4_mod_folder") #config['Paths']['fallout4_mod_folder']
                elif self.game =="fallout4vr":
                    self.game ="Fallout4VR"
                    self.game_path: str = self.__definitions.get_string_value("fallout4vr_folder") #config['Paths']['fallout4vr_folder']
                    self.mod_path: str = self.__definitions.get_string_value("fallout4vr_mod_folder") #config['Paths']['fallout4vr_mod_folder']
                elif self.game =="skyrimvr":
                    self.game ="SkyrimVR"
                    self.game_path = None
                    self.mod_path: str = self.__definitions.get_string_value("skyrimvr_mod_folder") #config['Paths']['skyrimvr_mod_folder']
                #if the game is not recognized Mantella will assume it's Skyrim since that's the most frequent one.
                else:
                    self.game ="Skyrim"
                    self.game_path = None
                    self.mod_path: str = self.__definitions.get_string_value("skyrim_mod_folder") #config['Paths']['skyrim_mod_folder']

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
            # self.offended_npc_response = self.__definitions.get_string_value("offended_npc_response")
            # self.forgiven_npc_response = self.__definitions.get_string_value("forgiven_npc_response")
            # self.follow_npc_response = self.__definitions.get_string_value("follow_npc_response")
            # self.inventory_npc_response = self.__definitions.get_string_value("inventory_npc_response")

            #TTS
            self.tts_service = self.__definitions.get_string_value("tts_service").strip().lower()
            if self.tts_service == "xtts":
                self.xtts_url = self.__definitions.get_string_value("xtts_url").rstrip('/')
                if 'http://127.0.0.1:8020' in self.xtts_url: # if running locally, get the XTTS folder
                    self.xtts_server_path = self.__definitions.get_string_value("xtts_server_folder")
                else:
                    self.xtts_server_path = ""
                self.xvasynth_path = ""
                self.piper_path = ""
            elif self.tts_service == "xvasynth":
                self.xvasynth_path = self.__definitions.get_string_value("xvasynth_folder")
                self.xtts_server_path = ""
                self.piper_path = ""
            elif self.tts_service == "piper":
                if not hasattr(self, 'piper_path'):
                    self.piper_path = self.__definitions.get_string_value("piper_folder")
                self.xvasynth_path = ""
                self.xtts_server_path = ""
            else: # default to Piper
                if not hasattr(self, 'piper_path'):
                    self.piper_path = self.__definitions.get_string_value("piper_folder")
                self.xvasynth_path = ""
                self.xtts_server_path = ""

            self.lip_generation = self.__definitions.get_string_value("lip_generation").strip().lower()

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
            self.whisper_model = self.__definitions.get_string_value("whisper_model_size")
            self.whisper_process_device = self.__definitions.get_string_value("process_device")
            self.stt_language = self.__definitions.get_string_value("stt_language")
            if (self.stt_language == 'default'):
                self.stt_language = self.language
            self.stt_translate = self.__definitions.get_bool_value("stt_translate")
            if self.__definitions.get_bool_value("use_automatic_audio_threshold"):
                self.audio_threshold = "auto"
            else:
                self.audio_threshold = str(self.__definitions.get_int_value("audio_threshold"))
            self.pause_threshold = self.__definitions.get_float_value("pause_threshold")
            self.listen_timeout = self.__definitions.get_int_value("listen_timeout")
            self.external_whisper_service = self.__definitions.get_bool_value("external_whisper_service")
            self.whisper_url = self.__definitions.get_string_value("whisper_url")

            #LLM
            self.max_response_sentences = self.__definitions.get_int_value("max_response_sentences")
            self.llm = self.__definitions.get_string_value("model")
            self.llm = self.llm.split(' |')[0] if ' |' in self.llm else self.llm
            self.wait_time_buffer = self.__definitions.get_float_value("wait_time_buffer")
            self.llm_api = self.__definitions.get_string_value("llm_api")
            # if self.llm_api == "Custom":
            #     self.llm_api = self.__definitions.get_string_value("llm_custom_service_url")
            self.custom_token_count = self.__definitions.get_int_value("custom_token_count")
            try:
                self.llm_params = json.loads(self.__definitions.get_string_value("llm_params").replace('\n', ''))
            except Exception as e:
                logging.error(f"""Error in parsing LLM parameter list: {e}
LLM parameter list must follow the Python dictionary format: https://www.w3schools.com/python/python_dictionaries.asp""")
                self.llm_params = None

            # self.stop_llm_generation_on_assist_keyword: bool = self.__definitions.get_bool_value("stop_llm_generation_on_assist_keyword")
            self.try_filter_narration: bool = self.__definitions.get_bool_value("try_filter_narration")

            

            self.remove_mei_folders = self.__definitions.get_bool_value("remove_mei_folders")
            #Debugging
            # self.debug_mode = self.__definitions.get_bool_value("debugging")
            # self.play_audio_from_script = self.__definitions.get_bool_value("play_audio_from_script")
            # self.debug_character_name = self.__definitions.get_string_value("debugging_npc")
            # self.debug_use_default_player_response = self.__definitions.get_bool_value("use_default_player_response")
            # self.default_player_response = self.__definitions.get_string_value("default_player_response")
            # self.debug_exit_on_first_exchange = self.__definitions.get_bool_value("exit_on_first_exchange")

            #UI
            self.auto_launch_ui = self.__definitions.get_bool_value("auto_launch_ui")

            self.play_startup_sound = self.__definitions.get_bool_value("play_startup_sound")

            #Conversation
            self.automatic_greeting = self.__definitions.get_bool_value("automatic_greeting")
            self.max_count_events = self.__definitions.get_int_value("max_count_events")
            self.hourly_time = self.__definitions.get_bool_value("hourly_time")
            self.player_character_description: str = self.__definitions.get_string_value("player_character_description")
            self.voice_player_input: bool = self.__definitions.get_bool_value("voice_player_input")
            self.player_voice_model: str = self.__definitions.get_string_value("player_voice_model")

            #HTTP
            self.port = self.__definitions.get_int_value("port")
            self.show_http_debug_messages: bool = self.__definitions.get_bool_value("show_http_debug_messages")

            #new separate prompts for Fallout 4 have been added 
            if self.game == "Fallout4" or self.game == "Fallout4VR":
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
    
    def load_actions_from_json(self, actions_folder: str) -> list[action]:
        result = []
        if not os.path.exists(actions_folder):
            os.makedirs(actions_folder)
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
                            identifier: str = content.get("identifier", "")
                            name: str = content.get("name", "")
                            key: str = content.get("key", "")
                            description: str = content.get("description", "")
                            prompt: str = content.get("prompt", "")
                            is_interrupting: bool = bool(content.get("is-interrupting", ""))
                            one_on_one: bool = bool(content.get("one-on-one", ""))
                            multi_npc: bool = bool(content.get("multi-npc", ""))
                            radiant: bool = bool(content.get("radiant", ""))
                            info_text: str = content.get("info-text", "")
                            result.append(action(identifier, name, key,description,prompt,is_interrupting, one_on_one,multi_npc,radiant,info_text))
            except Exception as e:
                utils.play_error_sound()
                logging.log(logging.WARNING, f"Could not load action definition file '{file}' in '{actions_folder}'. Most likely there is an error in the formating of the file. Error: {e}")
        return result
    
    # def get_config_value_json(self) -> str:
    #     json_writer = ConfigJsonWriter()
    #     for definition in self.__definitions.base_groups:
    #         definition.accept_visitor(json_writer)
    #     return json_writer.get_Json()

        


        
