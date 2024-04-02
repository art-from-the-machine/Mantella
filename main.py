from src.http.http_server import http_server
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
    game, config, language_info, llm_client = setup.initialise(
        config_file='config.ini',
        logging_file='logging.log', 
        secret_key_file='GPT_SECRET_KEY.txt', 
        language_file='data/language_support.csv',
    )

    mantella_version = '0.11'
    logging.log(24, f'\nMantella v{mantella_version}')
    should_debug_http = config.show_http_debug_messages

    mantella_http_server = http_server()
    chat_manager = ChatManager(game, config, Synthesizer(config), llm_client)
    game_state_manager = game_manager.GameStateManager(game, chat_manager, config, language_info, llm_client)
    
    #start the http server
    routes: list[routeable] = [mantella_route(game_state_manager, should_debug_http), 
                               stt_route(config, llm_client.api_key, should_debug_http)]
    
    mantella_http_server.start(int(config.port), routes, config.show_http_debug_messages)

except Exception as e:
    logging.error("".join(traceback.format_exception(e)))
    input("Press Enter to exit.")
