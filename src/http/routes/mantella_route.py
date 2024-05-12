import json
import logging
from typing import Any, Hashable

from fastapi import FastAPI, Request
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
        super().__init__(config, show_debug_messages)
        self.__language_info: dict[Hashable, str] = language_info
        self.__secret_key_file: str = secret_key_file
        self.__game: GameStateManager | None = None

    def _setup_route(self):
        if self.__game:
            self.__game.end_conversation({})

        client = openai_client(self._config, self.__secret_key_file)

         # Determine which game we're running for and select the appropriate character file
        game: gameable
        formatted_game_name = self._config.game.lower().replace(' ', '').replace('_', '')
        if formatted_game_name in ("fallout4", "fallout4vr"):
            game = fallout4(self._config)
        else:
            game = skyrim(self._config)
        
        chat_manager = ChatManager(game, self._config, Synthesizer(self._config), client)
        self.__game = GameStateManager(game, chat_manager, self._config, self.__language_info, client)
        
        logging.log(24, '\nConversations not starting when you select an NPC? See here:\nhttps://art-from-the-machine.github.io/Mantella/pages/issues_qna')
        logging.log(24, '\nWaiting for player to select an NPC...')

    def add_route_to_server(self, app: FastAPI):
        @app.post("/mantella")
        async def mantella(request: Request):
            if not self._can_route_be_used():
                error_message = "MantellaSoftware settings faulty! Please check MantellaSoftware's window or log!"
                logging.error(error_message)
                return self.error_message(error_message)
            if not self.__game:
                error_message = "Game manager setup failed! There is most likely an issue with the config.ini!"
                logging.error(error_message)
                return self.error_message(error_message)
            reply = {}
            receivedJson: dict[str, Any] | None = await request.json()
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
            return reply