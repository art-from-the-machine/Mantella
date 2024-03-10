from abc import ABC, abstractmethod
from flask import Flask

class routeable(ABC):
    """Base class for different http server routes
    """
    def __init__(self, show_debug_messages: bool = False) -> None:
        super().__init__()
        self._show_debug_messages: bool = show_debug_messages
        self._log_level_http_in = 40
        self._log_level_http_out = 41

    @abstractmethod
    def add_route_to_server(self, app: Flask):
        """Adds the route thast is configured within to the supplied Quart server

        Args:
            app (Flask): The Flask server to add the route to
        """
        pass