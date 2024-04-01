import ast
import json
import os
from pathlib import Path
from threading import Thread
import time
from typing import Any
import requests

class file_communication_compatibility:
    COMMUNICATION_FILE_NAME: str = "_mantella_communication.txt"
    BASE_URL: str = "http://localhost:"
    KEY_ROUTE: str = "mantella_route"

    def __init__(self, path_to_file: str, port: int) -> None:
        self.__file: str = os.path.join(path_to_file, self.COMMUNICATION_FILE_NAME)
        if not Path.exists(Path(self.__file)):
            self.__write_response("")
        self.__url: str = self.BASE_URL + str(port) + "/"
        self.__monitor_thread = Thread(None, self.__monitor, None, []).start()

    def __monitor(self):
        reply: str = ""
        while True:
            json_text = self.__load_request_when_available(reply)
            # json_text_single_quotes_fixed = ast.literal_eval(json_text)
            json_request = json.loads(json_text)
            if not json_request.__contains__(self.KEY_ROUTE):
                continue
            route: str = json_request[self.KEY_ROUTE]
            reply = self.__send_request_to_mantella(route, json_request)
            self.__write_response(reply)
    
    def __send_request_to_mantella(self, route: str, json_object: dict[str, Any]) -> str:
        url: str = self.__url + route
        header = {
            "Content-Type": "application/json",
            "accept": "application/json"
        }
        reply: Any = requests.post(url=url, headers=header, json= json_object).json()
        return json.dumps(reply)

    def __load_request_when_available(self, last_reply: str) -> str:
        text = ""
        while text == '' or text == last_reply:
            with open(self.__file, 'r', encoding='utf-8') as f:
                text = f.read().strip()
            # decrease stress on CPU while waiting for file to populate
            time.sleep(0.01)
        return text
    
    def __write_response(self, response: str):
        max_attempts = 2
        delay_between_attempts = 5

        for attempt in range(max_attempts):
            try:
                with open(self.__file, 'w', encoding='utf-8') as f:
                    f.write(response)
                break
            except PermissionError:
                print(f'Permission denied to write to {self.__file}. Retrying...')
                if attempt + 1 == max_attempts:
                    raise
                else:
                    time.sleep(delay_between_attempts)
        return None