import configparser
import logging
import os
import sys

class ConfigLoader:
    def __init__(self, file_name='config.ini'):
        config = configparser.ConfigParser()
        config.read(file_name)

        def invalid_path(set_path, tested_path):
            logging.error(f"\"{tested_path}\" does not exist!\n\nThe path set in config.ini: \"{set_path}\"")
            input('\nPress any key to exit...')
            sys.exit(0)
            return

        try:
            self.language = config['Language']['language']
            self.end_conversation_keyword = config['Language']['end_conversation_keyword']
            self.goodbye_npc_response = config['Language']['goodbye_npc_response']
            self.collecting_thoughts_npc_response = config['Language']['collecting_thoughts_npc_response']

            self.game_path = config['Paths']['skyrim_folder']
            self.xvasynth_path = config['Paths']['xvasynth_folder']
            self.mod_path = config['Paths']['mod_folder']

            self.mic_enabled = config['Microphone']['microphone_enabled']
            self.whisper_model = config['Microphone']['model_size']
            self.whisper_process_device = config['Microphone']['process_device']
            self.audio_threshold = config['Microphone']['audio_threshold']
            self.pause_threshold = float(config['Microphone']['pause_threshold'])
            self.listen_timeout = int(config['Microphone']['listen_timeout'])

            self.max_response_sentences = int(config['LanguageModel']['max_response_sentences'])
            self.llm = config['LanguageModel']['model']
            self.alternative_openai_api_base = config['LanguageModel']['alternative_openai_api_base']

            self.xvasynth_process_device = config['Speech']['tts_process_device']
            self.pace = float(config['Speech']['pace'])
            self.use_cleanup = int(config['Speech']['use_cleanup'])
            self.use_sr = int(config['Speech']['use_sr'])

            self.subtitles_enabled = config['HUD']['subtitles']

            self.remove_mei_folders = config['Cleanup']['remove_mei_folders']

            self.debug_mode = config['Debugging']['debugging']
            self.play_audio_from_script = config['Debugging']['play_audio_from_script']
            self.debug_character_name = config['Debugging']['debugging_npc']
            self.debug_use_mic = config['Debugging']['use_mic']
            self.default_player_response = config['Debugging']['default_player_response']
            self.debug_exit_on_first_exchange = config['Debugging']['exit_on_first_exchange']

            self.prompt = config['Prompt']['prompt']
            pass
        except Exception as e:
            logging.error('Parameter missing/invalid in config.ini file!')
            raise e

        # don't trust; verify; test subfolders
        if not os.path.exists(f"{self.game_path}\\Data\\"):
            invalid_path(self.game_path, f"{self.game_path}\\Data\\")
        if not os.path.exists(f"{self.xvasynth_path}\\resources\\"):
            invalid_path(self.xvasynth_path, f"{self.xvasynth_path}\\resources\\")
        if not os.path.exists(f"{self.mod_path}\\Sound\\Voice\\Mantella.esp"):
            invalid_path(self.mod_path, f"{self.mod_path}\\Sound\\Voice\\Mantella.esp")

        self.mod_path += "\\Sound\\Voice\\Mantella.esp"
