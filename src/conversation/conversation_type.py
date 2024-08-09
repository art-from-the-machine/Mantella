from abc import ABC, abstractmethod
from src.character_manager import Character
from src.llm.message_thread import message_thread
from src.conversation.context import context
from src.llm.messages import user_message

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

    @abstractmethod
    def adjust_existing_message_thread(self, message_thread_to_adjust: message_thread):
        """Adjusts a given message_thread to one needed for the conversation type

        Args:
            message_thread_to_adjust (message_thread): The message_thread to adjust
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
        return context_for_conversation.generate_system_message(self._prompt)
    
    def adjust_existing_message_thread(self, message_thread_to_adjust: message_thread, context_for_conversation: context):
        message_thread_to_adjust.modify_messages(self.generate_prompt(context_for_conversation), multi_npc_conversation=False, remove_system_flagged_messages=True)
    
    def get_user_message(self, context_for_conversation: context, messages: message_thread) -> user_message | None:
        if len(messages) == 1 and context_for_conversation.config.automatic_greeting:
            player_character: Character | None = context_for_conversation.npcs_in_conversation.get_player_character()
            if player_character:
                for actor in context_for_conversation.npcs_in_conversation.get_all_characters():
                    if not actor.is_player_character:
                        message = user_message(f"{context_for_conversation.language['hello']} {actor.name}.", player_character.name, True)
                        message.is_multi_npc_message = False
                        return message
            return None
        else:
            return super().get_user_message(context_for_conversation, messages)

class multi_npc(conversation_type):
    """Group conversation between the PC and multiple NPCs"""
    def __init__(self, prompt: str) -> None:
        super().__init__(prompt)

    def generate_prompt(self, context_for_conversation: context) -> str:
        return context_for_conversation.generate_system_message(self._prompt)
    
    def adjust_existing_message_thread(self, message_thread_to_adjust: message_thread, context_for_conversation: context):
        message_thread_to_adjust.modify_messages(self.generate_prompt(context_for_conversation), True, True)

class radiant(conversation_type):
    """ Conversation between two NPCs without the player"""
    def __init__(self, context_for_conversation: context) -> None:
        super().__init__(context_for_conversation.config.radiant_prompt)
        self.__user_start_prompt = context_for_conversation.config.radiant_start_prompt
        self.__user_end_prompt = context_for_conversation.config.radiant_end_prompt

    def generate_prompt(self, context_for_conversation: context) -> str:
        return context_for_conversation.generate_system_message(self._prompt)
    
    def adjust_existing_message_thread(self, message_thread_to_adjust: message_thread, context_for_conversation: context):
        message_thread_to_adjust.modify_messages(self.generate_prompt(context_for_conversation), True, True)
    
    def get_user_message(self, context_for_conversation: context, messages: message_thread) -> user_message | None:        
        text = ""
        if len(messages) == 1:
            text = self.__user_start_prompt
        elif len(messages) == 3:
            text = self.__user_end_prompt
        else:
            return None
        reply = user_message(text, "", True)
        reply.is_multi_npc_message = False # Don't flag these as multi-npc messages. Don't want a 'Player:' in front of the instruction messages
        return reply
    
    def should_end(self, context_for_conversation: context, messages: message_thread) -> bool:
        return len(messages) > 4