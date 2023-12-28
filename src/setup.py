import logging
import src.utils as utils
import pandas as pd
import tiktoken
import src.config_loader as config_loader
from src.llm.openai_client import openai_client

def initialise(config_file, logging_file, secret_key_file, character_df_file, language_file):
    
    def setup_logging(file_name):
        logging.basicConfig(filename=file_name, format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        logging.getLogger('').addHandler(console)

    def get_character_df(file_name):
        encoding = utils.get_file_encoding(file_name)
        character_df = pd.read_csv(file_name, engine='python', encoding=encoding)
        character_df = character_df.loc[character_df['voice_model'].notna()]

        return character_df
    
    def get_language_info(file_name):
        language_df = pd.read_csv(file_name)
        try:
            language_info = language_df.loc[language_df['alpha2']==config.language].to_dict('records')[0]
            return language_info
        except:
            logging.error(f"Could not load language '{config.language}'. Please set a valid language in config.ini\n")

    setup_logging(logging_file)
    config = config_loader.ConfigLoader(config_file)

    # clean up old instances of exe runtime files
    utils.cleanup_mei(config.remove_mei_folders)
    
    character_df = get_character_df(character_df_file)
    language_info = get_language_info(language_file)

    
    chosenmodel = config.llm
    # if using an alternative API, use encoding for GPT-3.5 by default
    # NOTE: this encoding may not be the same for all models, leading to incorrect token counts
    #       this can lead to the token limit of the given model being overrun
    if config.alternative_openai_api_base != 'none':
        chosenmodel = 'gpt-3.5-turbo'
    try:
        encoding = tiktoken.encoding_for_model(chosenmodel)
    except:
        logging.error('Error loading model. If you are using an alternative to OpenAI, please find the setting `alternative_openai_api_base` in MantellaSoftware/config.ini and follow the instructions to change this setting')
        raise
    client = openai_client(config, secret_key_file)

    return config, character_df, language_info, encoding, client