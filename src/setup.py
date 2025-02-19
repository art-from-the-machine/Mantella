import configparser
import logging
import os
import platform
from typing import Hashable
import winreg
import src.color_formatter as cf
import src.utils as utils
import pandas as pd
import sys
from pathlib import Path
from src.config.config_loader import ConfigLoader

def initialise(config_file, logging_file, language_file) -> tuple[ConfigLoader, dict[Hashable, str]]:
    
    def set_cwd_to_exe_dir():
        if getattr(sys, 'frozen', False): # if exe and not Python script
            # change the current working directory to the executable's directory
            os.chdir(os.path.dirname(sys.executable))

    def get_custom_user_folder() -> str:
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

    def get_my_games_directory():
        documents_path = get_custom_user_folder()        
        if documents_path == "":
            if platform.system() == "Windows":
                reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
                documents_path = winreg.QueryValueEx(reg_key, "Personal")[0]
                winreg.CloseKey(reg_key)
            else:
                homepath = os.getenv('HOMEPATH')
                if homepath:
                    documents_path = os.path.realpath(homepath+'/Documents')
            if documents_path == "":
                print("ERROR: Could not find 'Documents' folder or equivalent!")
            save_dir = Path(os.path.join(documents_path,"My Games","Mantella"))
        else:
            save_dir = Path(documents_path)
        save_dir.mkdir(parents=True, exist_ok=True)
        return str(save_dir)+'\\'
    
    def setup_logging(file_name, config: ConfigLoader):
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s', handlers=[], encoding='utf-8')

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
        # logging.getLogger().addHandler(jsonHandler)

        #logging.debug("debug message")
        #logging.info("info message")
        #logging.warning("warning message")
        #logging.error("error message")
        #logging.critical("critical message")

        # custom levels
        logging.addLevelName(21, "INFO")
        logging.addLevelName(22, "INFO")
        logging.addLevelName(23, "INFO")
        logging.addLevelName(24, "Startup")

        #logging.log(21, "Player transcription")
        #logging.log(22, "NPC voiceline")
        #logging.log(23, "NPC info")


        logging.addLevelName(27, "STT")
        logging.addLevelName(28, "LLM")
        logging.addLevelName(29, "TTS")

        #logging.log(27, "Speech-To-Text related")
        #logging.log(28, "Large Language Model related")
        #logging.log(29, "Text-To-Speech related")

        logging.addLevelName(41, "HTTP-in")
        logging.addLevelName(42, "HTTP-out")
        logging.addLevelName(43, "Queue")
        # logging.log(40, "JSON coming from game")
        # logging.log(41, "JSON sent back to game")
        # logging.log(42, "Sentence queue access")
    
    def get_language_info(file_name) -> dict[Hashable, str]:
        language_df = pd.read_csv(file_name)
        try:
            language_info: dict[Hashable, str] = language_df.loc[language_df['alpha2']==config.language].to_dict('records')[0]
            return language_info
        except:
            logging.error(f"Could not load language '{config.language}'. Please set a valid language in config.ini\n")
            return {}
    set_cwd_to_exe_dir()
    save_folder = get_my_games_directory()
    config = ConfigLoader(save_folder, config_file)    
    setup_logging(os.path.join(save_folder,logging_file), config)
    
    logging.log(23, f'''Mantella.exe running in: 
{os.getcwd()}
config.ini, logging.log, and conversation histories available in:
{save_folder}''')
    logging.log(23, f'''Mantella currently running for {config.game}. Mantella mod files located in: 
{config.mod_path}''')
    if not config.have_all_config_values_loaded_correctly:
        logging.error("Cannot start Mantella. Not all settings that are required are set to correct values. This error often occurs when you start Mantella.exe manually without setting up the `Game` tab in the Mantella UI.")

    # clean up old instances of exe runtime files
    utils.cleanup_mei(config.remove_mei_folders)
    utils.cleanup_tmp(config.save_folder+'data\\tmp')
    utils.cleanup_tmp(os.getenv('TMP')+'\\voicelines') # cleanup temp voicelines

    language_info = get_language_info(language_file)
    
    return config, language_info
