from abc import ABC, abstractmethod
from src.llm.message_thread import message_thread
from src.conversation.context import context
from src.llm.messages import user_message
from src.stt import Transcriber

class conversation_type(ABC):
    """Base class for different forms of conversations.
    """
    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt
    
    @abstractmethod
    def generate_prompt(self, context_for_conversation: context) -> str:
        """Generates the text for the initial system_message. 

        Args:
            context_for_conversation (context): The context for the conversations. Provides tools to construct the prompt

        Returns:
            str: the prompt as a text
        """
        pass
    
    def get_user_message(self, context_for_conversation: context, messages: message_thread) -> user_message | None:
        """Gets the next user message for the conversation. Default implementation gets the input from the player

        Args:
            settings (context): the current context of the conversation
            stt (Transcriber): the transcriber to get the voice input
            messages (message_thread): the current messages of the conversation

        Returns:
            user_message: the text for the next user message
        """
        return None
    
    def should_end(self, context_for_conversation: context, messages: message_thread) -> bool:
        """Called after a message has been generated. Allows the conversation_type to stop the conversation at any point

        Args:
            settings (context): the current context of the conversation
            messages (message_thread): the current messages of the conversation
            game_state (GameStateManager): the GameStateManager to make inquiries or send messages to Skyrim if needed

        Returns:
            bool: True if the conversation should end, False otherwise
        """
        return False

class pc_to_npc(conversation_type):
    """PC talks to a single NPC. The classic conversation"""
    def __init__(self, prompt: str) -> None:
        super().__init__(prompt)

    def generate_prompt(self, context_for_conversation: context) -> str:
        return context_for_conversation.generate_system_message(self._prompt, True)
    
    def get_user_message(self, context_for_conversation: context, messages: message_thread) -> user_message | None:
        if len(messages) == 1 and context_for_conversation.config.automatic_greeting == '1':
            for actor in context_for_conversation.npcs_in_conversation.get_all_characters():
                if not actor.Is_player_character:
                    return user_message(f"{context_for_conversation.Language['hello']} {actor.Name}.", context_for_conversation.config.player_name, True)
            return None
        else:
            return super().get_user_message(context_for_conversation, messages)

class multi_npc(conversation_type):
    """Group conversation between the PC and multiple NPCs"""
    def __init__(self, prompt: str) -> None:
        super().__init__(prompt)

    def generate_prompt(self, context_for_conversation: context) -> str:
        return context_for_conversation.generate_system_message(self._prompt, True)

class radiant(conversation_type):
    """ Conversation between two NPCs without the player"""
    def __init__(self, context_for_conversation: context) -> None:
        super().__init__(context_for_conversation.config.multi_npc_prompt)
        self.__user_start_prompt = context_for_conversation.config.radiant_start_prompt
        self.__user_end_prompt = context_for_conversation.config.radiant_end_prompt

    def generate_prompt(self, context_for_conversation: context) -> str:
        return context_for_conversation.generate_system_message(self._prompt, False)
    
    def get_user_message(self, context_for_conversation: context, messages: message_thread) -> user_message | None:
        text = ""
        if len(messages) == 1:
            text = self.__user_start_prompt
        elif len(messages) == 3:
            text = self.__user_end_prompt
        else:
            return None
        reply = user_message(text, context_for_conversation.config.player_name, True)
        reply.is_multi_npc_message = False # Don't flag these as multi-npc messages. Don't want a 'Player:' in front of the instruction messages
        return reply
    
    def should_end(self, context_for_conversation: context, messages: message_thread) -> bool:
        return len(messages) > 4