from abc import ABC, abstractmethod
from src.characters_manager import Characters
from src.character_manager import Character
from src.llm.message_thread import message_thread


class Remembering(ABC):
    @abstractmethod
    def get_prompt_text(self, npcs_in_conversation: Characters, world_id: str, include_private_thoughts: bool = True) -> str:
        """ Generates a text that explains the previous interactions of the npcs with the player. 
            Text is passed as part of the prompt to the LLM

        Args:
            npcs_in_conversation (Characters): the NPCs in question
            include_private_thoughts: When False, omit saved private thoughts. Summary generation uses this.

        Returns:
            str: a single text
        """
        pass

    @abstractmethod
    def get_character_summary(self, character: Character, world_id: str) -> str:
        """ Gets the summary for a specific character
        
        Args:
            character (Character): the character to get the summary for
            world_id (str): the world ID
            
        Returns:
            str: the summary text for this character, or empty string if no summary exists
        """
        pass

    @abstractmethod
    def get_private_thoughts_text(self, npcs_in_conversation: Characters, world_id: str) -> str:
        """Single-NPC {private_thoughts} fill. Empty for multi-NPC / radiant."""
        pass

    @abstractmethod
    def get_character_private_thought(self, character: Character, world_id: str) -> str:
        """Latest private thought for one character, or empty string."""
        pass

    @abstractmethod
    def get_character_personal_reflection(self, character: Character, world_id: str) -> str:
        """Latest personal reflection for one character, or empty string."""
        pass

    @abstractmethod
    def save_conversation_state(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, is_reload=False, save_timestamp: int | None = None, save_thoughts: bool | None = None, save_reflections: bool | None = None):
        """Saves the current state of the conversation.

        Args:
            messages (message_thread): The messages in the conversation
            npcs_in_conversation (Characters): the NPCs to save for
            save_thoughts: If set, overrides Save Private Thoughts for this save.
            save_reflections: If set, overrides Save Personal Reflection for this save.
        """
        pass

    @abstractmethod
    def save_thoughts_only(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, save_timestamp: int | None = None):
        """Generate and save private thoughts without writing a new conversation summary."""
        pass

    @abstractmethod
    def save_reflections_only(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, save_timestamp: int | None = None):
        """Generate and save personal reflections without writing a new conversation summary."""
        pass