import json
import logging
from typing import Any

from flask import Flask, request
from src.game_manager import GameStateManager
from src.http.routes.routeable import routeable
from src.http.communication_constants import communication_constants as comm_consts

class mantella_route(routeable):

    def __init__(self, game: GameStateManager, show_debug_messages: bool = False) -> None:
        super().__init__(show_debug_messages)
        self.__game = game        

    def add_route_to_server(self, app: Flask):
        @app.route("/mantella", methods=['POST'])
        def mantella():
            reply = {}
            receivedJson: dict[str, Any] | None = request.json
            if receivedJson:
                if self._show_debug_messages:
                    logging.log(self._log_level_http_in, receivedJson)
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
                        reply = self.__game.error_message(f"Request type '{request_type}' was not recognized")
            else:
                reply = self.__game.error_message(f"Request did not contain properly formatted json!")

            if self._show_debug_messages:
                logging.log(self._log_level_http_out, reply)
            return json.dumps(reply)
    

            # #time.sleep(10)
            # if request.json:
            #     request_type: str = request.json["requesttype"]
            #     npcs: list[dict] = request.json["npcs"]
            #     test_float: float = request.json["testfloat"]
            #     test_string_array: list[str] = request.json["teststringarray"]
            #     test_int_array: list[int] = request.json["testintarray"]
            #     test_float_array: list[float] = request.json["testfloatarray"]
            #     test_bool_array: list[bool] = request.json["testboolarray"]
            #     location: str = request.json["context"]["location"]
            #     skyrim_time: int = request.json["context"]["time"]

            #     modifiedNPCs: list[dict] = []
            #     for npc in npcs:
            #         modifiedNPCs.append({
            #             "name": f"{npc['name']} the housecarl",
            #             "gender": f"I guess {npc['gender']}",
            #             "npclikesplayer":  not npc['isincombatwithplayer']
            #         })

            #     if request_type == "startConversation":
            #         test_string_array.append("dumdideldei")
            #         test_int_array.append(24)
            #         test_float_array.append(0.789)
            #         test_bool_array.append(False)
            #         reply = {
            #             "replytype": "conversationResponse",
            #             "npcs": modifiedNPCs,
            #             "testFloat": test_float * 3,
            #             "teststringarray": test_string_array,
            #             "testintarray": test_int_array,
            #             "testfloatarray": test_float_array,
            #             "testboolarray": test_bool_array,
            #             "context": {
            #                 "location": f"Still {location}",
            #                 "time": skyrim_time + 2
            #             }
            #         }

            #         return json.dumps(reply)
            
            # reply = {}
            # reply["error"] = "Received request without json"
            # return json.dumps(reply)