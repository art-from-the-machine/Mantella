from flask import Flask
from src.output_manager import ChatManager
import traceback
from src.http.routes.routeable import routeable
from src.http.routes.mantella_route import mantella_route
from src.http.routes.stt_route import stt_route
import logging
import os
import time
import src.output_manager as output_manager
import src.game_manager as game_manager
import src.setup as setup
from src.tts import Synthesizer

try:
    config, character_df, language_info, llm_client, FO4_Voice_folder_and_models_df = setup.initialise(
        config_file='config.ini',
        logging_file='logging.log', 
        secret_key_file='GPT_SECRET_KEY.txt', 
        #Additional df_file added to support Fallout 4 data/fallout4_characters.csv, keep in mind there's also a new file in data\FO4_data\FO4_Voice_folder_XVASynth_matches.csv
        character_df_files=('data/skyrim_characters.csv', 'data/fallout4_characters.csv'), 
        language_file='data/language_support.csv',
        FO4_XVASynth_file='data\\FO4_data\\FO4_Voice_folder_XVASynth_matches.csv'
    )

    mantella_version = '0.11'
    logging.info(f'\nMantella v{mantella_version}')
    should_debug_http = False

    sync_http_server = Flask(__name__)
    chat_manager = ChatManager(config, Synthesizer(config), llm_client)
    game_state_manager = game_manager.GameStateManager(chat_manager, config, language_info, llm_client, character_df)
    
    #start the http server
    routes: list[routeable] = [mantella_route(game_state_manager, should_debug_http), 
                               stt_route(config, llm_client.api_key, should_debug_http)]
    for route in routes:
        route.add_route_to_server(sync_http_server)
    
    sync_http_server.run(debug=should_debug_http)

except Exception as e:
    logging.error("".join(traceback.format_exception(e)))
    input("Press Enter to exit.")
