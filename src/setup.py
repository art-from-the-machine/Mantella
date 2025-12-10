import configparser
import logging
import os
from typing import Hashable
import src.color_formatter as cf
import src.utils as utils
import pandas as pd
import sys
from src.config.config_loader import ConfigLoader
from src.actions.function_manager import FunctionManager

class MantellaSetup:
    def __init__(self):
        self.save_folder = ""
        self.config = None
        self.language_info = {}

    def initialise(self, config_file, logging_file, language_file) -> tuple[ConfigLoader, dict[Hashable, str]]:
        '''Initialize Mantella with configuration, logging, and language settings'''
        self._set_cwd_to_exe_dir()
        self.save_folder = utils.get_my_games_directory(self._get_custom_user_folder())
        self.config = ConfigLoader(self.save_folder, config_file)    
        self._setup_logging(os.path.join(self.save_folder,logging_file), self.config.advanced_logs)
        
        FunctionManager.load_all_actions()
        FunctionManager.log_actions_enabled(self.config.advanced_actions_enabled)
        self.config.actions = FunctionManager.get_legacy_actions()
        
        logging.log(23, f'''Mantella.exe running in: 
    {os.getcwd()}
Conversation histories, config.ini, and logging.log available in:
    {self.save_folder}''')
        logging.log(23, f'''Mantella currently running for {self.config.game.display_name}. Mantella mod files located in: 
    {self.config.mod_path}''')
        if not self.config.have_all_config_values_loaded_correctly:
            logging.error("Cannot start Mantella. Not all settings that are required are set to correct values. This error often occurs when you start Mantella.exe manually without setting up the `Game` tab in the Mantella UI.")

        # clean up old instances of exe runtime files
        utils.cleanup_mei(self.config.remove_mei_folders)
        utils.cleanup_tmp(self.config.save_folder+'data\\tmp')
        utils.cleanup_tmp(os.getenv('TMP')+'\\voicelines') # cleanup temp voicelines

        self.language_info = self._get_language_info(language_file, self.config.language)
        
        return self.config, self.language_info

    def _set_cwd_to_exe_dir(self):
        '''Set the current working directory to the executable's directory if running as exe'''
        if getattr(sys, 'frozen', False): # if exe and not Python script
            # change the current working directory to the executable's directory
            os.chdir(os.path.dirname(sys.executable))

    def _get_custom_user_folder(self) -> str:
        '''Find Mantella's saved data folder from configuration file if it exists'''
        file_name = "custom_user_folder.ini"
        if not os.path.exists(file_name):
            return ""

        user_folder_config = configparser.ConfigParser()
        try:
            user_folder_config.read(file_name, encoding='utf-8')
            
        except Exception as e:
            utils.play_error_sound()
            logging.error(repr(e))
            logging.error(f"Unable to read / open '{file_name}'. If you have recently edited this file, please try reverting to a previous version. This error is normally due to using special characters.")
            logging.log(logging.WARNING, "Using default user folder in '../Documents/My Games/Mantella/'.")
            return ""      
        
        try:
            return user_folder_config.get("UserFolder","custom_user_folder")
        except Exception as e:
            utils.play_error_sound()
            logging.error(f"Could not find option 'custom_user_folder' in section 'UserFolder' in '{file_name}'.")
            logging.log(logging.WARNING, "Using default user folder in '../Documents/My Games/Mantella/'.")
            return ""

    def _setup_logging(self, file_name, advanced_logs=False):
        '''Configure logging with custom levels and formatters'''
        logging_level = logging.DEBUG if advanced_logs else logging.INFO
        logging.basicConfig(level=logging_level, format='%(levelname)s: %(message)s', handlers=[], encoding='utf-8')

        # create custom formatter
        formatter = cf.CustomFormatter()

        # add formatter to ch
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        # Create a formatter for file output
        file_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')

        # Create a file handler and set the formatter
        file_handler = logging.FileHandler(file_name, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)

        # Add the handlers to the logger
        logging.getLogger().addHandler(console_handler)
        logging.getLogger().addHandler(file_handler)

        # custom levels
        logging.addLevelName(21, "INFO")
        logging.addLevelName(22, "INFO")
        logging.addLevelName(23, "INFO")
        logging.addLevelName(24, "Startup")

        logging.addLevelName(27, "STT")
        logging.addLevelName(28, "LLM")
        logging.addLevelName(29, "TTS")

        logging.addLevelName(41, "HTTP-in")
        logging.addLevelName(42, "HTTP-out")
        logging.addLevelName(43, "Queue")

    def _get_language_info(self, file_name, language) -> dict[Hashable, str]:
        language_df = pd.read_csv(file_name)
        try:
            language_info: dict[Hashable, str] = language_df.loc[language_df['alpha2']==language].to_dict('records')[0]
            return language_info
        except:
            logging.error(f"Could not load language '{language}'. Please set a valid language in config.ini\n")
            return {}
