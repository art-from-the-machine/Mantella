from flask import Flask
import click
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
    logging.info(f'\nMantella v{mantella_version}')
    should_debug_http = False

    sync_http_server = Flask(__name__)
    chat_manager = ChatManager(config, Synthesizer(config), llm_client)
    game_state_manager = game_manager.GameStateManager(game, chat_manager, config, language_info, llm_client)

    ### Deactivate the logging to console by Flask
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    def secho(text, file=None, nl=None, err=None, color=None, **styles):
        pass

    def echo(text, file=None, nl=None, err=None, color=None, **styles):
        pass

    click.echo = echo
    click.secho = secho
    ### End of deactivate logging
    
    #start the http server
    routes: list[routeable] = [mantella_route(game_state_manager, should_debug_http), 
                               stt_route(config, llm_client.api_key, should_debug_http)]
    for route in routes:
        route.add_route_to_server(sync_http_server)
    
    sync_http_server.run(debug=should_debug_http)

except Exception as e:
    logging.error("".join(traceback.format_exception(e)))
    input("Press Enter to exit.")
