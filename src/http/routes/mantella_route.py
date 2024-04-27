import json
import logging
from typing import Any, Hashable

from flask import Flask, request
from src.config.config_loader import ConfigLoader
from src.games.fallout4 import fallout4
from src.games.gameable import gameable
from src.games.skyrim import skyrim
from src.output_manager import ChatManager
from src.llm.openai_client import openai_client
from src.game_manager import GameStateManager
from src.http.routes.routeable import routeable
from src.http.communication_constants import communication_constants as comm_consts
from src.tts import Synthesizer

class mantella_route(routeable):
    """Main route for mantella conversations

    Args:
        routeable (_type_): _description_
    """
    def __init__(self, config: ConfigLoader, secret_key_file: str, language_info: dict[Hashable, str], show_debug_messages: bool = False) -> None:
        super().__init__(show_debug_messages)
        self.__config: ConfigLoader = config
        self.__language_info: dict[Hashable, str] = language_info
        self.__secret_key_file: str = secret_key_file
        self.__game: GameStateManager | None = None

    def __load_current_config_state(self):
        client = openai_client(self.__config, self.__secret_key_file)

         # Determine which game we're running for and select the appropriate character file
        game: gameable
        formatted_game_name = self.__config.game.lower().replace(' ', '').replace('_', '')
        if formatted_game_name in ("fallout4", "fallout4vr"):
            game = fallout4(self.__config)
        else:
            game = skyrim(self.__config)
        
        chat_manager = ChatManager(game, self.__config, Synthesizer(self.__config), client)
        self.__game = GameStateManager(game, chat_manager, self.__config, self.__language_info, client)
        
        logging.log(24, '\nConversations not starting when you select an NPC? See here:\nhttps://art-from-the-machine.github.io/Mantella/pages/issues_qna')
        logging.log(24, '\nWaiting for player to select an NPC...')

    def __can_conversation_route_be_used(self) -> bool:
        if self.__config.Has_any_config_value_changed:
            if self.__game:
                self.__game.end_conversation({})
            self.__config.update_config_loader_with_changed_config_values()
            if self.__config.Have_all_config_values_loaded_correctly:
                self.__load_current_config_state()
                return True
            else:
                return False
        return self.__config.Have_all_config_values_loaded_correctly

    def add_route_to_server(self, app: Flask):
        @app.route("/mantella", methods=['POST'])
        def mantella():
            if not self.__can_conversation_route_be_used():
                error_message = "MantellaSoftware settings faulty! Please check MantellaSoftware's window or log!"
                logging.error(error_message)
                return json.dumps(self.error_message(error_message))
            if not self.__game:
                error_message = "Game manager setup failed! There is most likely an issue with the config.ini!"
                logging.error(error_message)
                return json.dumps(self.error_message(error_message))
            reply = {}
            receivedJson: dict[str, Any] | None = request.json
            if receivedJson:
                if self._show_debug_messages:
                    logging.log(self._log_level_http_in, json.dumps(receivedJson, indent=4))
                request_type: str = receivedJson[comm_consts.KEY_REQUESTTYPE]
                match request_type:
                    case comm_consts.KEY_REQUESTTYPE_STARTCONVERSATION:
                        reply = self.__game.start_conversation(receivedJson)
                    case comm_consts.KEY_REQUESTTYPE_CONTINUECONVERSATION:
                        reply = self.__game.continue_conversation(receivedJson)
                    case comm_consts.KEY_REQUESTTYPE_PLAYERINPUT:
                        reply = self.__game.player_input(receivedJson)
                    case comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION:
                        reply = self.__game.end_conversation(receivedJson)
                    case _:
                        reply = self.error_message(f"Request type '{request_type}' was not recognized")
            else:
                reply = self.error_message(f"Request did not contain properly formatted json!")

            if self._show_debug_messages:
                logging.log(self._log_level_http_out, json.dumps(reply, indent=4))
            return json.dumps(reply)