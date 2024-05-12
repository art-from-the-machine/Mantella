import json
import logging
from typing import Any

from fastapi import FastAPI, Request
from src.config.config_loader import ConfigLoader
from src.http.routes.routeable import routeable
from src.stt import Transcriber

class stt_route(routeable):
    """Route that can be called to get a transcribe from the mic

    Args:
        routeable (_type_): _description_

    Returns:
        _type_: _description_
    """
    PREFIX: str = "mantella_" 
    KEY_REQUESTTYPE: str = PREFIX + "request_type"
    KEY_REQUESTTYPE_TTS: str = PREFIX + "tts"
    KEY_INPUT_NAMESINCONVERSATION: str = PREFIX + "names_in_conversation"

    KEY_REPLYTYPE: str = PREFIX + "reply_type"
    KEY_TRANSCRIBE: str = PREFIX + "transcribe"

    def __init__(self, config: ConfigLoader, secret_key_file: str, show_debug_messages: bool = False) -> None:
        super().__init__(config, show_debug_messages)
        self.__stt: Transcriber | None = None
        self.__secret_key_file = secret_key_file

    def _setup_route(self):
        if not self.__stt:
            self.__stt = Transcriber(self._config, self.__secret_key_file)

    def add_route_to_server(self, app: FastAPI):
        @app.post("/stt")
        async def stt(request: Request):
            if not self._can_route_be_used():
                error_message = "MantellaSoftware settings faulty! Please check MantellaSoftware's window or log!"
                logging.error(error_message)
                return self.error_message(error_message)
            if not self.__stt:
                error_message = "STT/Whisper setup failed! There is most likely an issue with the config.ini!"
                logging.error(error_message)
                return self.error_message(error_message)
            receivedJson: dict[str, Any] | None = await request.json()
            if receivedJson and receivedJson[self.KEY_REQUESTTYPE] == self.KEY_REQUESTTYPE_TTS:
                if self._show_debug_messages:
                    logging.log(self._log_level_http_in, json.dumps(receivedJson, indent=4))
                names: list[str] = receivedJson[self.KEY_INPUT_NAMESINCONVERSATION]
                names_in_conversation = ', '.join(names)
                transcribed_text = self.__stt.recognize_input(names_in_conversation)
                if isinstance(transcribed_text, str):
                    return self.construct_return_json(transcribed_text)
            
            return self.construct_return_json("*Complete gibberish*")
    
    def construct_return_json(self, transcribe: str) -> dict:
        reply = {
            self.KEY_REPLYTYPE: self.KEY_REQUESTTYPE_TTS,
            self.KEY_TRANSCRIBE: transcribe,
        }
        if self._show_debug_messages:
            logging.log(self._log_level_http_out, json.dumps(reply, indent=4))
        return reply