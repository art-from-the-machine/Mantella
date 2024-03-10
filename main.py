from flask import Flask
from src.output_manager import ChatManager
import traceback
from src.http.routes.routeable import routeable
from src.http.routes.mantella_route import mantella_route
from src.http.routes.stt_route import stt_route
import logging
import src.game_manager as game_manager
import src.setup as setup
from src.tts import Synthesizer

try:
    config, character_df, language_info, llm_client = setup.initialise(
        config_file='config.ini',
        logging_file='logging.log', 
        secret_key_file='GPT_SECRET_KEY.txt', 
        character_df_file='data/skyrim_characters.csv', 
        language_file='data/language_support.csv'
    )

    mantella_version = '0.11'
    logging.info(f'\nMantella v{mantella_version}')

    sync_http_server = Flask(__name__)
    chat_manager = ChatManager(config, Synthesizer(config), llm_client)
    game_state_manager = game_manager.GameStateManager(chat_manager, config, language_info, llm_client, character_df)
    
    #start the http server
    should_log_http_in_and_output = True
    routes: list[routeable] = [mantella_route(game_state_manager, should_log_http_in_and_output), 
                               stt_route(config, llm_client.api_key, should_log_http_in_and_output)]
    for route in routes:
        route.add_route_to_server(sync_http_server)
    
    sync_http_server.run(debug=True)

except Exception as e:
    logging.error("".join(traceback.format_exception(e)))
    input("Press Enter to exit.")
