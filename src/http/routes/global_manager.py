# global_manager.py

from src.game_manager import GameStateManager

class GlobalManager:
    __instance = None  # Single instance of GameStateManager

    @staticmethod
    def get_instance() -> GameStateManager:
        """Returns the single instance of GameStateManager."""
        if GlobalManager.__instance is None:
            raise Exception("GameStateManager is not initialized.")
        return GlobalManager.__instance

    
    @staticmethod
    def initialize(game_manager: GameStateManager):
        """Initializes the GameStateManager instance."""
        if GlobalManager.__instance is not None:
            raise Exception("GameStateManager has already been initialized.")
        GlobalManager.__instance = game_manager
