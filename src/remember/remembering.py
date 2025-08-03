from abc import ABC, abstractmethod
from src.characters_manager import Characters
from src.llm.message_thread import message_thread


class Remembering(ABC):
    @abstractmethod
    def get_prompt_text(self, npcs_in_conversation: Characters, world_id: str) -> str:
        """ Generates a text that explains the previous interactions of the npcs with the player. 
            Text is passed as part of the prompt to the LLM

        Args:
            npcs_in_conversation (Characters): the NPCs in question

        Returns:
            str: a single text
        """
        pass

    @abstractmethod
    def save_conversation_state(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, is_reload=False):
        """Saves the current state of the conversation.

        Args:
            messages (message_thread): The messages in the conversation
            npcs_in_conversation (Characters): the NPCs to save for
        """
        pass