from abc import ABC, abstractmethod
from typing import Any

from fastapi import FastAPI
from src.config.config_loader import ConfigLoader
from src.http.communication_constants import communication_constants as comm_consts
from src import utils

class routeable(ABC):
    """Base class for different http server routes
    """
    def __init__(self, config: ConfigLoader, show_debug_messages: bool = False) -> None:
        super().__init__()
        self._config: ConfigLoader = config
        self._has_route_been_initialized: bool = False
        self._show_debug_messages: bool = show_debug_messages
        self._log_level_http_in = 41
        self._log_level_http_out = 42

    @abstractmethod
    def add_route_to_server(self, app: FastAPI):
        """Adds the route that is configured within to the supplied FastAPI app

        Args:
            app (FastAPI): The FastAPI app to add the route to
        """
        pass

    @utils.time_it
    def _can_route_be_used(self) -> bool:        
        if not self._has_route_been_initialized or self._config.has_any_config_value_changed:
            self._config.update_config_loader_with_changed_config_values()
            if self._config.have_all_config_values_loaded_correctly:
                if self._has_route_been_initialized:
                    # Route is already initialized, check if hot-swapping is enabled and supported
                    try:
                        hot_swap_enabled = self._config.definitions.get_bool_value("hot_swap_enabled")
                    except:
                        # If hot_swap_enabled setting doesn't exist, default to False (safe fallback)
                        hot_swap_enabled = False
                    
                    if (hot_swap_enabled and 
                        self._supports_hot_swap() and 
                        self._hot_swap_settings()):
                        return True
                    else:
                        # Hot-swap disabled, failed, or not supported, fall back to full reinitalization
                        self._setup_route()
                        self._has_route_been_initialized = True
                        return True
                else:
                    # Route not initialized yet, do full setup
                    self._setup_route()
                    self._has_route_been_initialized = True
                    return True
            else:
                self._has_route_been_initialized = False
                return False
        return self._has_route_been_initialized
    
    @abstractmethod
    def _setup_route(self):
        """Sets up the route with current configuration values"""
        pass

    def _supports_hot_swap(self) -> bool:
        """Returns whether this route supports hot-swapping settings without full reinitialization.
        
        Returns:
            bool: True if hot-swapping is supported, False otherwise
        """
        return False

    def _hot_swap_settings(self) -> bool:
        """Attempts to hot-swap settings without full reinitialization.
        
        Returns:
            bool: True if hot-swap was successful, False if full reinitialization is needed
        """
        return False

    def error_message(self, message: str) -> dict[str, Any]:
        return {
                comm_consts.KEY_REPLYTYPE: "error",
                "mantella_message": message
            }  
