import logging
import os
from typing import Hashable
from src.games.fallout4 import fallout4
from src.games.skyrim import skyrim
from src.games.gameable import gameable
import src.color_formatter as cf
import src.utils as utils
import pandas as pd
import sys
import os

import src.config.config_loader as config_loader
from src.llm.openai_client import openai_client

def initialise(config_file, logging_file, language_file) -> tuple[config_loader.ConfigLoader, dict[Hashable, str]]:
    
    def set_cwd_to_exe_dir():
        if getattr(sys, 'frozen', False): # if exe and not Python script
            # change the current working directory to the executable's directory
            os.chdir(os.path.dirname(sys.executable))
    
    def setup_logging(file_name):
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s', handlers=[])

        # create custom formatter
        formatter = cf.CustomFormatter()

        # add formatter to ch
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        # Create a formatter for file output
        file_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')

        # Create a file handler and set the formatter
        file_handler = logging.FileHandler(file_name)
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

        logging.addLevelName(40, "HTTP-in")
        logging.addLevelName(41, "HTTP-out")
        logging.addLevelName(42, "Queue")
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
    setup_logging(logging_file)
    config = config_loader.ConfigLoader(config_file)
    if not config.have_all_config_values_loaded_correctly:
        logging.error("Cannot start Mantella. Not all settings that are required are set to correct values. Please check the above error messages and correct the corresponding settings!")

    # clean up old instances of exe runtime files
    utils.cleanup_mei(config.remove_mei_folders)

    language_info = get_language_info(language_file)
    
    return config, language_info
