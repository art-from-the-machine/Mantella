import configparser
import logging
import os
import sys
import src.utils as utils
from pathlib import Path

class ConfigLoader:
    def __init__(self, file_name='config.ini'):
        config = configparser.ConfigParser()
        config.read(file_name, encoding='utf-8')

        def invalid_path(set_path, tested_path):
            logging.error(f"\"{tested_path}\" does not exist!\n\nThe path set in config.ini: \"{set_path}\"")
            input('\nPress any key to exit...')
            sys.exit(0)

        def check_program_files(set_path):
            skyrim_in_program_files = False
            if 'Program Files' in set_path:
                logging.warn(f'''
{self.game} is installed in Program Files. Mantella is unlikely to work. 
See here to learn how to move your game's installation folder: https://art-from-the-machine.github.io/Mantella/pages/installation.html#skyrim''')
                skyrim_in_program_files = True
            return skyrim_in_program_files 

        def check_missing_mantella_file(set_path):
            if self.game == "Fallout4" or self.game == "Fallout4VR":
                txtPrefix='fallout4'
                modnameSufix='gun'
            else:
                txtPrefix='skyrim'
                modnameSufix='Spell'
            
            try:
                with open(set_path+'/_mantella__'+txtPrefix+'_folder.txt') as f:
                    check = f.readline().strip()
            except:
                #Reworked the warning to include correct names depending on the game being ran.
                logging.warn(f'''
Warning: Could not find _mantella__{txtPrefix}_folder.txt in {set_path}. 
If you have not yet used the Mantella {modnameSufix} in-game you can safely ignore this message. 
If you have used the Mantella {modnameSufix} please check that your 
MantellaSoftware/config.ini "{txtPrefix}_folder" has been set correctly 
(instructions on how to set this up are in the config file itself).
If you are still having issues, a list of solutions can be found here: 
https://github.com/art-from-the-machine/Mantella#issues-qa
''')
                input("Press Enter to confirm these warnings...")

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
            if int(config['Startup']['open_config_editor']) == 1:
                run_config_editor()

            #Adjusting game and mod paths according to the game being ran
            self.game = config['Game']['game']
            self.game = str(self.game).lower().replace(' ', '').replace('_', '')
            if self.game =="fallout4":
                self.game ="Fallout4"
                self.game_path = config['Paths']['fallout4_folder']
                self.mod_path = config['Paths']['fallout4_mod_folder']
            elif self.game =="fallout4vr":
                self.game ="Fallout4VR"
                self.game_path = config['Paths']['fallout4VR_folder'] 
                self.mod_path = config['Paths']['fallout4VR_mod_folder']
            elif self.game =="skyrimvr":
                self.game ="SkyrimVR"
                self.game_path = config['Paths']['skyrimVR_folder']
                self.mod_path = config['Paths']['skyrimVR_mod_folder']
            #if the game is not recognized Mantella will assume it's Skyrim since that's the most frequent one.
            else:
                self.game ="Skyrim"
                self.game_path = config['Paths']['skyrim_folder']
                self.mod_path = config['Paths']['skyrim_mod_folder']
            
            logging.info(f'Mantella currently running for {self.game} located in {self.game_path}. Mantella esp located in {self.mod_path}.  \n')
            self.language = config['Language']['language']
            self.end_conversation_keyword = config['Language']['end_conversation_keyword']
            self.goodbye_npc_response = config['Language']['goodbye_npc_response']
            self.collecting_thoughts_npc_response = config['Language']['collecting_thoughts_npc_response']
            self.offended_npc_response = config['Language']['offended_npc_response']
            self.forgiven_npc_response = config['Language']['forgiven_npc_response']
            self.follow_npc_response = config['Language']['follow_npc_response']

            self.xvasynth_path = config['Paths']['xvasynth_folder']
            self.facefx_path = config['Paths']['facefx_folder']
            #Added from xTTS implementation
            self.xtts_server_path = config['Paths']['xtts_server_folder']

            self.mic_enabled = config['Microphone']['microphone_enabled']
            self.whisper_model = config['Microphone']['model_size']
            self.whisper_process_device = config['Microphone']['process_device']
            self.stt_language = config['Microphone']['stt_language']
            if (self.stt_language == 'default'):
                self.stt_language = self.language
            self.stt_translate = int(config['Microphone']['stt_translate'])
            self.audio_threshold = config['Microphone']['audio_threshold']
            self.pause_threshold = float(config['Microphone']['pause_threshold'])
            self.listen_timeout = int(config['Microphone']['listen_timeout'])
            self.whisper_type = config['Microphone']['whisper_type']
            self.whisper_url = config['Microphone']['whisper_url']

            #self.hotkey = config['Hotkey']['hotkey']
            #self.textbox_timer = config['Hotkey']['textbox_timer']

            self.max_response_sentences = int(config['LanguageModel']['max_response_sentences'])
            self.llm = config['LanguageModel']['model']
            self.wait_time_buffer = float(config['LanguageModel']['wait_time_buffer'])
            self.llm_api = config['LanguageModel']['llm_api']
            self.custom_token_count = config['LanguageModel']['custom_token_count']
            self.temperature = float(config['LanguageModel']['temperature'])
            self.top_p = float(config['LanguageModel']['top_p'])

            stop_value = config['LanguageModel']['stop']
            if ',' in stop_value:
                # If there are commas in the stop value, split the string by commas and store the values in a list
                self.stop = stop_value.split(',')
            else:
                # If there are no commas, put the single value into a list
                self.stop = [stop_value]

            self.frequency_penalty = float(config['LanguageModel']['frequency_penalty'])
            self.max_tokens = int(config['LanguageModel']['max_tokens'])

            #Added from xTTS implementation
            self.use_external_xtts = int(config['Speech']['use_external_xtts'])
            self.xtts_default_model = config['Speech']['xtts_default_model']
            self.xtts_deepspeed = int(config['Speech']['xtts_deepspeed'])
            self.xtts_lowvram = int(config['Speech']['xtts_lowvram'])
            self.xtts_device = config['Speech']['xtts_device']
            self.number_words_tts = int(config['Speech']['number_words_tts'])
            self.xtts_url = config['Speech']['xtts_url']
            self.xtts_data = config['Speech']['xtts_data']
            
            self.xvasynth_process_device = config['Speech']['tts_process_device']
            self.pace = float(config['Speech']['pace'])
            self.use_cleanup = int(config['Speech']['use_cleanup'])
            self.use_sr = int(config['Speech']['use_sr'])
            self.FO4Volume = int(config['Speech']['FO4_NPC_response_volume'])
            self.tts_print = int(config['Speech']['tts_print'])

            self.remove_mei_folders = config['Cleanup']['remove_mei_folders']
            #Debugging
            self.debug_mode = config['Debugging']['debugging']
            self.play_audio_from_script = config['Debugging']['play_audio_from_script']
            self.debug_character_name = config['Debugging']['debugging_npc']
            self.debug_use_default_player_response = config['Debugging']['use_default_player_response']
            self.default_player_response = config['Debugging']['default_player_response']
            self.debug_exit_on_first_exchange = config['Debugging']['exit_on_first_exchange']
            self.add_voicelines_to_all_voice_folders = config['Debugging']['add_voicelines_to_all_voice_folders']

            #Conversation
            self.player_name = config['Conversation']['player_name']
            self.automatic_greeting = config['Conversation']['automatic_greeting']

            #new separate prompts for Fallout 4 have been added 
            if self.game == "Fallout4" or self.game == "Fallout4VR":
                self.prompt = config['Prompt']['fallout4_prompt']
                self.multi_npc_prompt = config['Prompt']['fallout4_multi_npc_prompt']
            else:
                self.prompt = config['Prompt']['skyrim_prompt']
                self.multi_npc_prompt = config['Prompt']['skyrim_multi_npc_prompt']

            self.radiant_start_prompt = config['Prompt']['radiant_start_prompt']
            self.radiant_end_prompt = config['Prompt']['radiant_end_prompt']
            self.memory_prompt = config['Prompt']['memory_prompt']
            self.resummarize_prompt = config['Prompt']['resummarize_prompt']
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

        # don't trust; verify; test subfolders
        if not os.path.exists(f"{self.game_path}"):
            invalid_path(self.game_path, f"{self.game_path}")
        else:
            skyrim_in_program_files = check_program_files(self.game_path)
            check_missing_mantella_file(self.game_path)

        if not os.path.exists(f"{self.xvasynth_path}\\resources\\"):
            invalid_path(self.xvasynth_path, f"{self.xvasynth_path}\\resources\\")
        
        if not os.path.exists(f"{self.mod_path}\\Sound\\Voice\\Mantella.esp"):
            invalid_path(self.mod_path, f"{self.mod_path}\\Sound\\Voice\\Mantella.esp")
        self.mod_path += "\\Sound\\Voice\\Mantella.esp"
