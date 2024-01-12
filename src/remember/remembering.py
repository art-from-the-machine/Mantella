from abc import ABC, abstractmethod
from src.character_manager import Character
from src.llm.message_thread import message_thread


class remembering(ABC):
    @abstractmethod
    def get_prompt_text(self, characters: set[Character]) -> str:
        pass

    @abstractmethod
    def save_conversation_state(self, messages: message_thread, characters: set[Character]):
        pass