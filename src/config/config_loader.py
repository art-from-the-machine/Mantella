import configparser
import logging
import os
import sys
from src.config.config_file_writer import ConfigFileWriter
from src.config.types.config_value import ConfigValue
from src.config.mantella_config_value_definitions_classic import MantellaConfigValueDefinitionsClassic
from src.config.config_file_reader import ConfigFileReader
import src.utils as utils
from pathlib import Path

class ConfigLoader:
    def __init__(self, file_name='config.ini'):
        definitions: list[ConfigValue] = MantellaConfigValueDefinitionsClassic.get_config_values()
        if not os.path.exists(file_name):
            logging.log(24,"Can't find 'config.ini'. Assuming first time usage of MantellaSoftware and creating it.")
            try:
                writer: ConfigFileWriter = ConfigFileWriter()
                writer.write(file_name, definitions)
            except Exception as e:
                logging.error(24, f"Failed to write default 'config.ini'. Possible reason: MantellaSoftware does not have rights to write at its location. Exception: {repr(e)}")    
        
        config = configparser.ConfigParser()
        try:
            config.read(file_name, encoding='utf-8')
        except Exception as e:
            logging.error(repr(e))
            logging.error(f'Unable to read / open config.ini. If you have recently edited this file, please try reverting to a previous version. This error is normally due to using special characters.')
            input("Press Enter to exit.")
        
        self.__reader: ConfigFileReader = ConfigFileReader(config)
        for definition in definitions:
            definition.accept_visitor(self.__reader)

#         def check_missing_mantella_file(set_path):
#             if self.game == "Fallout4" or self.game == "Fallout4VR":
#                 txtPrefix='fallout4'
#                 modnameSufix='gun'
#             else:
#                 txtPrefix='skyrim'
#                 modnameSufix='Spell'
            
#             try:
#                 with open(set_path+'/_mantella__'+txtPrefix+'_folder.txt') as f:
#                     check = f.readline().strip()
#             except:
#                 #Reworked the warning to include correct names depending on the game being ran.
#                 logging.warn(f'''
# Warning: Could not find _mantella__{txtPrefix}_folder.txt in {set_path}. 
# If you have not yet used the Mantella {modnameSufix} in-game you can safely ignore this message. 
# If you have used the Mantella {modnameSufix} please check that your 
# MantellaSoftware/config.ini "{txtPrefix}_folder" has been set correctly 
# (instructions on how to set this up are in the config file itself).
# If you are still having issues, a list of solutions can be found here: 
# https://github.com/art-from-the-machine/Mantella#issues-qa
# ''')
#                 input("Press Enter to confirm these warnings...")

        def run_config_editor():
            try:
                import src.config_editor as configeditor

                logging.info('Launching config editor...')
                configeditor.start()
                logging.info(f'Config editor closed. Re-reading {file_name} file...')

                config.read(file_name)
            except Exception as e:
                logging.error('Unable to run config editor!')
                raise e

        try:
            # run config editor if config.ini has the parameter
            # temporarily removed for Mantella v0.11
            #if int(config['Startup']['open_config_editor']) == 1:
            #    run_config_editor()

            #Adjusting game and mod paths according to the game being ran
            self.game: str = self.__reader.get_string_value("game")# config['Game']['game']
            self.game = str(self.game).lower().replace(' ', '').replace('_', '')
            if self.game =="fallout4":
                self.game ="Fallout4"
                self.mod_path: str = self.__reader.get_string_value("fallout4_mod_folder") #config['Paths']['fallout4_mod_folder']
            elif self.game =="fallout4vr":
                self.game ="Fallout4VR"
                self.game_path: str = self.__reader.get_string_value("fallout4vr_folder") #config['Paths']['fallout4vr_folder']
                self.mod_path: str = self.__reader.get_string_value("fallout4vr_mod_folder") #config['Paths']['fallout4vr_mod_folder']
            elif self.game =="skyrimvr":
                self.game ="SkyrimVR"
                self.mod_path: str = self.__reader.get_string_value("skyrimvr_mod_folder") #config['Paths']['skyrimvr_mod_folder']
            #if the game is not recognized Mantella will assume it's Skyrim since that's the most frequent one.
            else:
                self.game ="Skyrim"
                self.mod_path: str = self.__reader.get_string_value("skyrim_mod_folder") #config['Paths']['skyrim_mod_folder']
            
            self.mod_path += "\\Sound\\Voice\\Mantella.esp"

            logging.log(24, f'Mantella currently running for {self.game}. Mantella esp located in {self.mod_path}.  \n')
            self.language = self.__reader.get_string_value("language")
            self.end_conversation_keyword = self.__reader.get_string_value("end_conversation_keyword")
            self.goodbye_npc_response = self.__reader.get_string_value("goodbye_npc_response")
            self.collecting_thoughts_npc_response = self.__reader.get_string_value("collecting_thoughts_npc_response")
            self.offended_npc_response = self.__reader.get_string_value("offended_npc_response")
            self.forgiven_npc_response = self.__reader.get_string_value("forgiven_npc_response")
            self.follow_npc_response = self.__reader.get_string_value("follow_npc_response")

            #TTS
            self.tts_service = self.__reader.get_string_value("tts_service").strip().lower()
            self.facefx_path = self.__reader.get_string_value("facefx_folder")
            if self.tts_service == "XTTS":
                self.xtts_server_path = self.__reader.get_string_value("xtts_server_folder")
                self.xvasynth_path = ""
            else:
                self.xvasynth_path = self.__reader.get_string_value("xvasynth_folder")
                self.xtts_server_path = ""
            #Added from xTTS implementation
            self.xtts_default_model = self.__reader.get_string_value("xtts_default_model")
            self.xtts_deepspeed = self.__reader.get_bool_value("xtts_deepspeed")
            self.xtts_lowvram = self.__reader.get_bool_value("xtts_lowvram")
            self.xtts_device = self.__reader.get_string_value("xtts_device")
            self.number_words_tts = self.__reader.get_int_value("number_words_tts")
            self.xtts_url = self.__reader.get_string_value("xtts_url")
            self.xtts_data = self.__reader.get_string_value("xtts_data")
        
            self.xvasynth_process_device = self.__reader.get_string_value("tts_process_device")
            self.pace = self.__reader.get_float_value("pace")
            self.use_cleanup = self.__reader.get_bool_value("use_cleanup")
            self.use_sr = self.__reader.get_bool_value("use_sr")

            self.FO4Volume = self.__reader.get_int_value("FO4_NPC_response_volume")
            self.tts_print = self.__reader.get_bool_value("tts_print")

            #STT
            self.whisper_model = self.__reader.get_string_value("model_size")
            self.whisper_process_device = self.__reader.get_string_value("process_device")
            self.stt_language = self.__reader.get_string_value("stt_language")
            if (self.stt_language == 'default'):
                self.stt_language = self.language
            self.stt_translate = self.__reader.get_bool_value("stt_translate")
            if self.__reader.get_bool_value("use_automatic_audio_threshold"):
                self.audio_threshold = "auto"
            else:
                self.audio_threshold = str(self.__reader.get_int_value("audio_threshold"))
            self.pause_threshold = self.__reader.get_float_value("pause_threshold")
            self.listen_timeout = self.__reader.get_int_value("listen_timeout")
            self.whisper_type = self.__reader.get_string_value("whisper_type")
            self.whisper_url = self.__reader.get_string_value("whisper_url")

            #LLM
            self.max_response_sentences = self.__reader.get_int_value("max_response_sentences")
            self.llm = self.__reader.get_string_value("model")
            self.wait_time_buffer = self.__reader.get_float_value("wait_time_buffer")
            self.llm_api = self.__reader.get_string_value("llm_api")
            self.custom_token_count = self.__reader.get_int_value("custom_token_count")
            self.temperature = self.__reader.get_float_value("temperature")
            self.top_p = self.__reader.get_float_value("top_p")

            stop_value = self.__reader.get_string_value("stop")
            if ',' in stop_value:
                # If there are commas in the stop value, split the string by commas and store the values in a list
                self.stop = stop_value.split(',')
            else:
                # If there are no commas, put the single value into a list
                self.stop = [stop_value]

            self.frequency_penalty = self.__reader.get_float_value("frequency_penalty")
            self.max_tokens = self.__reader.get_int_value("max_tokens")

            

            self.remove_mei_folders = self.__reader.get_bool_value("remove_mei_folders")
            #Debugging
            self.debug_mode = self.__reader.get_bool_value("debugging")
            self.play_audio_from_script = self.__reader.get_bool_value("play_audio_from_script")
            self.debug_character_name = self.__reader.get_string_value("debugging_npc")
            self.debug_use_default_player_response = self.__reader.get_bool_value("use_default_player_response")
            self.default_player_response = self.__reader.get_string_value("default_player_response")
            self.debug_exit_on_first_exchange = self.__reader.get_bool_value("exit_on_first_exchange")
            self.add_voicelines_to_all_voice_folders = self.__reader.get_bool_value("add_voicelines_to_all_voice_folders")

            #HTTP
            self.port = self.__reader.get_int_value("port")
            self.show_http_debug_messages: bool = self.__reader.get_bool_value("show_http_debug_messages")

            #Conversation
            self.automatic_greeting = self.__reader.get_bool_value("automatic_greeting")

            #new separate prompts for Fallout 4 have been added 
            if self.game == "Fallout4" or self.game == "Fallout4VR":
                self.prompt = self.__reader.get_string_value("fallout4_prompt")
                self.multi_npc_prompt = self.__reader.get_string_value("fallout4_multi_npc_prompt")
            else:
                self.prompt = self.__reader.get_string_value("skyrim_prompt")
                self.multi_npc_prompt = self.__reader.get_string_value("skyrim_multi_npc_prompt")

            self.radiant_start_prompt = self.__reader.get_string_value("radiant_start_prompt")
            self.radiant_end_prompt = self.__reader.get_string_value("radiant_end_prompt")
            self.memory_prompt = self.__reader.get_string_value("memory_prompt")
            self.resummarize_prompt = self.__reader.get_string_value("resummarize_prompt")
            pass
        except Exception as e:
            logging.error('Parameter missing/invalid in config.ini file!')
            raise e
        
        # if the exe is being run by another process, replace config.ini paths with relative paths
        if "--integrated" in sys.argv:
            self.game_path = str(Path(utils.resolve_path()).parent.parent.parent.parent)
            self.mod_path = str(Path(utils.resolve_path()).parent.parent.parent)

            self.facefx_path = str(Path(utils.resolve_path()).parent.parent.parent)
            self.facefx_path += "\\Sound\\Voice\\Processing\\"
            
            self.xvasynth_path = str(Path(utils.resolve_path())) + "\\xVASynth"
        
