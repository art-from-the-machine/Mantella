import json
import logging
from typing import Any
from flask import Flask, request
from src.config_loader import ConfigLoader
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

    def __init__(self, config: ConfigLoader, api_key: str, show_debug_messages: bool = False) -> None:
        super().__init__(show_debug_messages)
        self.__stt: Transcriber | None = None
        self.__config = config
        self.__api_key = api_key

    def add_route_to_server(self, app: Flask):
        @app.route("/stt", methods=['POST'])
        def stt():
            if not self.__stt:
                self.__stt = Transcriber(self.__config, self.__api_key)
            received_json: dict[str, Any] | None = request.json
            if received_json and received_json[self.KEY_REQUESTTYPE] == self.KEY_REQUESTTYPE_TTS:
                if self._show_debug_messages:
                    logging.log(self._log_level_http_in, json.dumps(received_json, indent=4))
                names: list[str] = received_json[self.KEY_INPUT_NAMESINCONVERSATION]
                names_in_conversation = ', '.join(names)
                transcribed_text = self.__stt.recognize_input(names_in_conversation)
                if isinstance(transcribed_text, str):
                    return json.dumps(self.construct_return_json(transcribed_text))
            
            return json.dumps(self.construct_return_json("*Complete gibberish*"))
    
    def construct_return_json(self, transcribe: str) -> dict:
        reply = {
            self.KEY_REPLYTYPE: self.KEY_REQUESTTYPE_TTS,
            self.KEY_TRANSCRIBE: transcribe,
        }
        if self._show_debug_messages:
            logging.log(self._log_level_http_out, json.dumps(reply, indent=4))
        return reply