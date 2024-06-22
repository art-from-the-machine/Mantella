import configparser
import logging
import os
import sys
from src.config.config_values import ConfigValues
from src.config.mantella_config_value_definitions_new import MantellaConfigValueDefinitionsNew
from src.config.config_json_writer import ConfigJsonWriter
from src.config.config_file_writer import ConfigFileWriter
import src.utils as utils
from pathlib import Path

class ConfigLoader:
    def __init__(self, file_name='config.ini'):
        self.__has_any_value_changed: bool = False
        self.__is_initial_load: bool = True
        self.__file_name = file_name
        self.__definitions: ConfigValues = MantellaConfigValueDefinitionsNew.get_config_values(self.__on_config_value_change)
        if not os.path.exists(self.__file_name):
            logging.log(24,"Cannot find 'config.ini'. Assuming first time usage of MantellaSoftware and creating it.")
            self.__write_config_state(self.__definitions)

        config = configparser.ConfigParser()
        try:
            config.read(file_name, encoding='utf-8')
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
            logging.error(24, f"Failed to write default 'config.ini'. Possible reason: MantellaSoftware does not have rights to write at its location. Exception: {repr(e)}")    

    def __update_config_values_from_current_state(self):
        self.__definitions.clear_constraint_violations()
        try:
            # if the exe is being run by another process, replace config.ini paths with relative paths
            if "--integrated" in sys.argv:
                self.game_path = str(Path(utils.resolve_path()).parent.parent.parent.parent)
                self.mod_path = str(Path(utils.resolve_path()).parent.parent.parent)

                game_parent_folder_name = os.path.basename(self.game_path)
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
                    self.mod_path: str = self.__definitions.get_string_value("fallout4_mod_folder") #config['Paths']['fallout4_mod_folder']
                elif self.game =="fallout4vr":
                    self.game ="Fallout4VR"
                    self.game_path: str = self.__definitions.get_string_value("fallout4vr_folder") #config['Paths']['fallout4vr_folder']
                    self.mod_path: str = self.__definitions.get_string_value("fallout4vr_mod_folder") #config['Paths']['fallout4vr_mod_folder']
                elif self.game =="skyrimvr":
                    self.game ="SkyrimVR"
                    self.mod_path: str = self.__definitions.get_string_value("skyrimvr_mod_folder") #config['Paths']['skyrimvr_mod_folder']
                #if the game is not recognized Mantella will assume it's Skyrim since that's the most frequent one.
                else:
                    self.game ="Skyrim"
                    self.mod_path: str = self.__definitions.get_string_value("skyrim_mod_folder") #config['Paths']['skyrim_mod_folder']

                self.facefx_path = self.__definitions.get_string_value("facefx_folder")

            self.mod_path += "\\Sound\\Voice\\Mantella.esp"

            self.language = self.__definitions.get_string_value("language")
            self.end_conversation_keyword = self.__definitions.get_string_value("end_conversation_keyword")
            self.goodbye_npc_response = self.__definitions.get_string_value("goodbye_npc_response")
            self.collecting_thoughts_npc_response = self.__definitions.get_string_value("collecting_thoughts_npc_response")
            self.offended_npc_response = self.__definitions.get_string_value("offended_npc_response")
            self.forgiven_npc_response = self.__definitions.get_string_value("forgiven_npc_response")
            self.follow_npc_response = self.__definitions.get_string_value("follow_npc_response")

            #TTS
            self.tts_service = self.__definitions.get_string_value("tts_service").strip().lower()
            if self.tts_service == "xtts":
                self.xtts_server_path = self.__definitions.get_string_value("xtts_server_folder")
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

            #Added from xTTS implementation
            self.xtts_default_model = self.__definitions.get_string_value("xtts_default_model")
            self.xtts_deepspeed = self.__definitions.get_bool_value("xtts_deepspeed")
            self.xtts_lowvram = self.__definitions.get_bool_value("xtts_lowvram")
            self.xtts_device = self.__definitions.get_string_value("xtts_device")
            self.number_words_tts = self.__definitions.get_int_value("number_words_tts")
            self.xtts_url = self.__definitions.get_string_value("xtts_url")
            self.xtts_data = self.__definitions.get_string_value("xtts_data")
            self.xtts_accent = self.__definitions.get_bool_value("xtts_accent")
        
            self.xvasynth_process_device = self.__definitions.get_string_value("tts_process_device")
            self.pace = self.__definitions.get_float_value("pace")
            self.use_cleanup = self.__definitions.get_bool_value("use_cleanup")
            self.use_sr = self.__definitions.get_bool_value("use_sr")

            self.FO4Volume = self.__definitions.get_int_value("fo4_npc_response_volume")
            self.tts_print = self.__definitions.get_bool_value("tts_print")

            #STT
            self.whisper_model = self.__definitions.get_string_value("model_size")
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
            self.whisper_type = self.__definitions.get_string_value("whisper_type")
            self.whisper_url = self.__definitions.get_string_value("whisper_url")

            #LLM
            self.max_response_sentences = self.__definitions.get_int_value("max_response_sentences")
            self.llm = self.__definitions.get_string_value("model")
            self.wait_time_buffer = self.__definitions.get_float_value("wait_time_buffer")
            self.llm_api = self.__definitions.get_string_value("llm_api")
            if self.llm_api == "Custom":
                self.llm_api = self.__definitions.get_string_value("llm_custom_service_url")
            self.custom_token_count = self.__definitions.get_int_value("custom_token_count")
            self.temperature = self.__definitions.get_float_value("temperature")
            self.top_p = self.__definitions.get_float_value("top_p")

            stop_value = self.__definitions.get_string_value("stop")
            if ',' in stop_value:
                # If there are commas in the stop value, split the string by commas and store the values in a list
                self.stop = stop_value.split(',')
            else:
                # If there are no commas, put the single value into a list
                self.stop = [stop_value]

            self.frequency_penalty = self.__definitions.get_float_value("frequency_penalty")
            self.max_tokens = self.__definitions.get_int_value("max_tokens")

            

            self.remove_mei_folders = self.__definitions.get_bool_value("remove_mei_folders")
            #Debugging
            # self.debug_mode = self.__definitions.get_bool_value("debugging")
            # self.play_audio_from_script = self.__definitions.get_bool_value("play_audio_from_script")
            # self.debug_character_name = self.__definitions.get_string_value("debugging_npc")
            # self.debug_use_default_player_response = self.__definitions.get_bool_value("use_default_player_response")
            # self.default_player_response = self.__definitions.get_string_value("default_player_response")
            # self.debug_exit_on_first_exchange = self.__definitions.get_bool_value("exit_on_first_exchange")
            self.add_voicelines_to_all_voice_folders = self.__definitions.get_bool_value("add_voicelines_to_all_voice_folders")

            #HTTP
            self.port = self.__definitions.get_int_value("port")
            self.show_http_debug_messages: bool = self.__definitions.get_bool_value("show_http_debug_messages")

            #UI
            self.auto_launch_ui = self.__definitions.get_bool_value("auto_launch_ui")

            #Conversation
            self.automatic_greeting = self.__definitions.get_bool_value("automatic_greeting")
            self.use_voice_player_input: bool = self.__definitions.get_bool_value("voice_player_input")
            self.player_voice_model: str = self.__definitions.get_string_value("player_voice_model")

            #new separate prompts for Fallout 4 have been added 
            if self.game == "Fallout4" or self.game == "Fallout4VR":
                self.prompt = self.__definitions.get_string_value("fallout4_prompt")
                self.multi_npc_prompt = self.__definitions.get_string_value("fallout4_multi_npc_prompt")
            else:
                self.prompt = self.__definitions.get_string_value("skyrim_prompt")
                self.multi_npc_prompt = self.__definitions.get_string_value("skyrim_multi_npc_prompt")

            self.radiant_start_prompt = self.__definitions.get_string_value("radiant_start_prompt")
            self.radiant_end_prompt = self.__definitions.get_string_value("radiant_end_prompt")
            self.memory_prompt = self.__definitions.get_string_value("memory_prompt")
            self.resummarize_prompt = self.__definitions.get_string_value("resummarize_prompt")
            pass
        except Exception as e:
            logging.error('Parameter missing/invalid in config.ini file!')
            raise e
    
    def get_config_value_json(self) -> str:
        json_writer = ConfigJsonWriter()
        for definition in self.__definitions.base_groups:
            definition.accept_visitor(json_writer)
        return json_writer.get_Json()

        


        
