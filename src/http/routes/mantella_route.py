import json
from typing import Any, Hashable

from fastapi import FastAPI, Request
from src.config.config_loader import ConfigLoader
from src.games.fallout4 import Fallout4
from src.games.gameable import Gameable
from src.games.skyrim import Skyrim
from src.output_manager import ChatManager
from src.llm.llm_client import LLMClient
from src.llm.summary_client import SummaryLLMClient
from src.game_manager import GameStateManager
from src.http.routes.routeable import routeable
from src.http.communication_constants import communication_constants as comm_consts
from src.tts.ttsable import TTSable
from src.tts.tts_factory import create_tts
from src import utils
from src.config.definitions.game_definitions import GameEnum
from src.config.definitions.tts_definitions import TTSEnum
from src.actions.function_manager import FunctionManager

logger = utils.get_logger()


class mantella_route(routeable):
    """Main route for Mantella conversations

    Args:
        routeable (_type_): _description_
    """
    def __init__(self, config: ConfigLoader, language_info: dict[Hashable, str]) -> None:
        super().__init__(config)
        self.__language_info: dict[Hashable, str] = language_info
        self.__game: GameStateManager | None = None
        self.__route_reinitialization_pending: bool = False
        self.__request_sequence: int = 0

        # if not self._can_route_be_used():
        #     error_message = "MantellaSoftware settings faulty. Please check MantellaSoftware's window or log."
        #     logger.error(error_message)

    @utils.time_it
    def _setup_route(self):
        if self.__game:
            # A config edit can be observed on the first request after a new
            # conversation starts (including its first STT input). Never let
            # route reinitialization terminate that live session and swallow
            # its input. The next clean start will rebuild the clients.
            if self.__game.has_active_conversation:
                logger.info(f"Protocol route reinitialization deferred: {self.__game.diagnostic_state}")
                self.__route_reinitialization_pending = True
                return
            self.__game.end_conversation({})

        game: Gameable
        game_enum = self._config.game
        if game_enum.base_game == GameEnum.FALLOUT4:
            game = Fallout4(self._config)
        else:
            game = Skyrim(self._config)

        tts: TTSable = create_tts(self._config.tts_service, self._config, game)

        dialogue_client = LLMClient(self._config)

        summary_client: SummaryLLMClient | None = None
        if self._config.summary_llm_enabled:
            summary_client = SummaryLLMClient(self._config)

        chat_manager = ChatManager(self._config, tts, dialogue_client, game)
        self.__game = GameStateManager(game, chat_manager, self._config, self.__language_info, dialogue_client, summary_client)
        logger.info(f"Protocol route manager ready: {self.__game.diagnostic_state}")

    @utils.time_it
    def add_route_to_server(self, app: FastAPI):
        @app.post("/mantella")
        async def mantella(request: Request):
            received_json: dict[str, Any] | None = await request.json()
            self.__request_sequence += 1
            request_sequence = self.__request_sequence
            request_type = received_json.get(comm_consts.KEY_REQUESTTYPE, "<missing>") if received_json else "<empty>"
            before_state = self.__game.diagnostic_state if self.__game else "manager=None"
            has_player_text = bool(received_json and received_json.get(comm_consts.KEY_REQUESTTYPE_PLAYERINPUT))
            incoming_session = received_json.get(comm_consts.KEY_CONVERSATION_SESSION) if received_json else None
            logger.info(f"Protocol request #{request_sequence} received: type={request_type} incoming_session={incoming_session} before={before_state} has_player_input={has_player_text}")
            if not self._can_route_be_used():
                error_message = "MantellaSoftware settings faulty. Please check MantellaSoftware's window or log."
                logger.error(error_message)
                logger.info(f"Protocol request #{request_sequence} rejected: route unavailable after={self.__game.diagnostic_state if self.__game else 'manager=None'}")
                return self.error_message(error_message)
            if not self.__game:
                error_message = "Game manager setup failed. There is most likely an issue with the config.ini."
                logger.error(error_message)
                return self.error_message(error_message)
            reply = {}
            if received_json:
                logger.debug('Processing request...')
                if self._config.show_http_debug_messages:
                    logger.log(self._log_level_http_in, json.dumps(received_json, indent=4))
                request_type: str = received_json[comm_consts.KEY_REQUESTTYPE]
                incoming_session = received_json.get(comm_consts.KEY_CONVERSATION_SESSION)
                if (request_type != comm_consts.KEY_REQUESTTYPE_STARTCONVERSATION
                        and incoming_session is not None
                        and not self.__game.request_session_matches(received_json)):
                    reply = self.__game.stale_request_reply(request_type, incoming_session)
                    logger.info(f"Protocol request #{request_sequence} stale: type={request_type} incoming_session={incoming_session} active={self.__game.protocol_session_id}")
                    return reply
                if request_type == comm_consts.KEY_REQUESTTYPE_STARTCONVERSATION and self.__route_reinitialization_pending:
                    # The old conversation is replaced as part of this start;
                    # rebuild clients before creating the new session.
                    self.__game = None
                    self.__route_reinitialization_pending = False
                    self._setup_route()
                match request_type:
                    case comm_consts.KEY_REQUESTTYPE_INIT:
                        # nothing needs to be done for this request aside from self._can_route_be_used() being triggered
                        logger.debug('Mantella settings initialized')
                        reply = {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTTYPE_INITCOMPLETED}
                    case comm_consts.KEY_REQUESTTYPE_STARTCONVERSATION:
                        reply = self.__game.start_conversation(received_json)
                    case comm_consts.KEY_REQUESTTYPE_CONTINUECONVERSATION:
                        reply = self.__game.continue_conversation(received_json)
                    case comm_consts.KEY_REQUESTTYPE_PLAYERINPUT:
                        reply = self.__game.player_input(received_json)
                    case comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION:
                        reply = self.__game.end_conversation(received_json)
                    case _:
                        reply = self.error_message(f"Request type '{request_type}' was not recognized")
            else:
                reply = self.error_message(f"Request did not contain properly formatted json!")

            if self._config.show_http_debug_messages:
                logger.log(self._log_level_http_out, json.dumps(reply, indent=4))
            logger.info(f"Protocol request #{request_sequence} completed: type={request_type} after={self.__game.diagnostic_state if self.__game else 'manager=None'} reply_type={reply.get(comm_consts.KEY_REPLYTYPE, '<missing>')}")
            if self.__game and comm_consts.KEY_CONVERSATION_SESSION not in reply:
                reply[comm_consts.KEY_CONVERSATION_SESSION] = self.__game.protocol_session_id
            return reply
