from abc import ABC, abstractmethod
from typing import Any

from fastapi import FastAPI
from src.http.communication_constants import communication_constants as comm_consts

class routeable(ABC):
    """Base class for different http server routes
    """
    def __init__(self, show_debug_messages: bool = False) -> None:
        super().__init__()
        self._show_debug_messages: bool = show_debug_messages
        self._log_level_http_in = 40
        self._log_level_http_out = 41

    @abstractmethod
    def add_route_to_server(self, app: FastAPI):
        """Adds the route that is configured within to the supplied FastAPI app

        Args:
            app (FastAPI): The FastAPI app to add the route to
        """
        pass

    def error_message(self, message: str) -> dict[str, Any]:
        return {
                comm_consts.KEY_REPLYTYPE: "error",
                "mantella_message": message
            }  