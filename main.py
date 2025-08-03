from src.http.http_server import http_server
import traceback
from src.http.routes.routeable import routeable
from src.http.routes.mantella_route import mantella_route
import logging
from src.setup import MantellaSetup
from src.ui.start_ui import StartUI

def main():
    try:
        config, language_info = MantellaSetup().initialise(
            config_file='config.ini',
            logging_file='logging.log', 
            language_file='data/language_support.csv')

        mantella_version = '0.13.1'
        logging.log(24, f'\nMantella v{mantella_version}')

        mantella_http_server = http_server()

        should_debug_http = config.show_http_debug_messages
        conversation = mantella_route(
            config=config, 
            stt_secret_key_file='STT_SECRET_KEY.txt', 
            image_secret_key_file='IMAGE_SECRET_KEY.txt', 
            function_llm_secret_key_file='FUNCTION_GPT_SECRET_KEY.txt'
            secret_key_file='GPT_SECRET_KEY.txt', 
            language_info=language_info, 
            show_debug_messages=should_debug_http
        )
        ui = StartUI(config)
        routes: list[routeable] = [conversation, ui]
        
        mantella_http_server.start(int(config.port), routes, config.play_startup_sound, should_debug_http)

    except Exception as e:
        logging.error("".join(traceback.format_exception(e)))
        input("Press Enter to exit.")

if __name__ == '__main__':
    main()
