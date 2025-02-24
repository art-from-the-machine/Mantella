import json
import logging
from fastapi import FastAPI, Request
from src.config.config_loader import ConfigLoader
from src.http.routes.routeable import routeable
from src import utils

class config_route(routeable):
    """Route that can be called to reload configuration from file

    Args:
        routeable (_type_): Base route class
    """
    PREFIX: str = "mantella_"
    KEY_REQUESTTYPE: str = PREFIX + "request_type"
    KEY_REQUESTTYPE_RELOAD: str = PREFIX + "reload_config"
    KEY_REPLYTYPE: str = PREFIX + "reply_type"
    KEY_STATUS: str = PREFIX + "status"

    def __init__(self, config: ConfigLoader, show_debug_messages: bool = False) -> None:
        super().__init__(config, show_debug_messages)

    @utils.time_it
    def _setup_route(self):
        pass

    @utils.time_it
    def add_route_to_server(self, app: FastAPI):
        @app.post("/config/reload")
        async def reload_config(request: Request):
            if not self._can_route_be_used():
                error_message = "MantellaSoftware settings faulty. Please check MantellaSoftware's window or log."
                logging.error(error_message)
                return self.error_message(error_message)

            try:
                # Reload config from file
                self._config.update_config_loader_with_changed_config_values()
                
                reply = {
                    self.KEY_REPLYTYPE: self.KEY_REQUESTTYPE_RELOAD,
                    self.KEY_STATUS: "success"
                }
                
                if self._show_debug_messages:
                    logging.log(self._log_level_http_out, json.dumps(reply, indent=4))
                return reply
            except Exception as e:
                error_message = f"Failed to reload configuration: {str(e)}"
                logging.error(error_message)
                return self.error_message(error_message)
