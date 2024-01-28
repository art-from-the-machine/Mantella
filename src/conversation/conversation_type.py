from abc import ABC, abstractmethod
from src.game_manager import GameStateManager
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

    def can_proceed(self, context_for_conversation: context) -> bool:
        """Called to determine if the conversations can proceed at the moment.

        Args:
            settings (context): the current context of the conversation

        Returns:
            bool: Returns True if the conversation can proceed right away, False otherwise
        """
        return True
    
    @abstractmethod
    def pre_proceed_conversation(self, context_for_conversation: context, messages: message_thread, game_state: GameStateManager):
        """Called after can_proceed but before generating the user or assistant messages. Allows the conversation type to set things up

        Args:
            settings (context): the current context of the conversation
            messages (message_thread): the current messages of the conversation
            game_state (GameStateManager): the GameStateManager to make inquiries or send messages to Skyrim if needed
        """
        pass    

    def get_user_message(self, context_for_conversation: context, stt: Transcriber, messages: message_thread) -> user_message:
        """Gets the next user message for the conversation. Default implementation gets the input from the player

        Args:
            settings (context): the current context of the conversation
            stt (Transcriber): the transcriber to get the voice input
            messages (message_thread): the current messages of the conversation

        Returns:
            user_message: the text for the next user message
        """
        player_name = context_for_conversation.config.player_name


        names_in_conversation = ', '.join([player_name] + context_for_conversation.npcs_in_conversation.get_all_names())
        transcribed_text, _ = stt.get_player_response(False, names_in_conversation)
        if isinstance(transcribed_text, str):
            return user_message(transcribed_text, player_name)
        else:
            return user_message("*Complete gibberish*")
    
    def should_end(self, context_for_conversation: context, messages: message_thread, game_state: GameStateManager) -> bool:
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

    def pre_proceed_conversation(self, context_for_conversation: context, messages: message_thread, game_state: GameStateManager):
        aggro = game_state.load_data_when_available('_mantella_actor_is_in_combat', '').lower()
        character = context_for_conversation.npcs_in_conversation.last_added_character
        if character:
            if aggro == 'true':
                character.is_in_combat = 1
            else:
                character.is_in_combat = 0
    
    def get_user_message(self, context_for_conversation: context, stt: Transcriber, messages: message_thread) -> user_message:
        if len(messages) == 1 and context_for_conversation.config.automatic_greeting == '1' and context_for_conversation.npcs_in_conversation.last_added_character:
            return user_message(f"{context_for_conversation.language['hello']} {context_for_conversation.npcs_in_conversation.last_added_character.name}.", context_for_conversation.config.player_name, True)
        else:
            return super().get_user_message(context_for_conversation, stt, messages)
    
    def can_proceed(self, settings: context) -> bool:
        return len(settings.npcs_in_conversation) == 1

class multi_npc(conversation_type):
    """Group conversation between the PC and multiple NPCs"""
    def __init__(self, prompt: str) -> None:
        super().__init__(prompt)

    def generate_prompt(self, context_for_conversation: context) -> str:
        return context_for_conversation.generate_system_message(self._prompt, True)

    def pre_proceed_conversation(self, settings: context, messages: message_thread, game_state: GameStateManager):
        pass
    
    def get_user_message(self, context_for_conversation: context, stt: Transcriber, messages: message_thread) -> user_message:
        new_message = super().get_user_message(context_for_conversation, stt, messages)
        new_message.is_multi_npc_message = True
        return new_message
    
    def can_proceed(self, context_for_conversation: context) -> bool:
        return len(context_for_conversation.npcs_in_conversation) > 1

class radiant(conversation_type):
    """ Conversation between two NPCs without the player"""
    def __init__(self, context_for_conversation: context) -> None:
        super().__init__(context_for_conversation.config.multi_npc_prompt)
        self.__user_start_prompt = context_for_conversation.config.radiant_start_prompt
        self.__user_end_prompt = context_for_conversation.config.radiant_end_prompt

    def generate_prompt(self, context_for_conversation: context) -> str:
        return context_for_conversation.generate_system_message(self._prompt, False)

    def pre_proceed_conversation(self, context_for_conversation: context, messages: message_thread, game_state: GameStateManager):
        # check if radiant dialogue has switched to multi NPC
            with open(f'{context_for_conversation.config.game_path}/_mantella_radiant_dialogue.txt', 'r', encoding='utf-8') as f:
                context_for_conversation.should_switch_to_multi_npc_conversation = f.readline().strip().lower() != 'true'
    
    def get_user_message(self, context_for_conversation: context, stt: Transcriber, messages: message_thread) -> user_message:
        text = ""
        if len(messages) == 1:
            text = self.__user_start_prompt
        elif len(messages) == 3:
            text = self.__user_end_prompt
        reply = user_message(text, context_for_conversation.config.player_name, True)
        reply.is_multi_npc_message = False # Don't flag these as multi-npc messages. Don't want a 'Player:' in front of the instruction messages
        return reply
    
    def can_proceed(self, context_for_conversation: context) -> bool:
        return len(context_for_conversation.npcs_in_conversation) > 1
    
    def should_end(self, context_for_conversation: context, messages: message_thread, game_state: GameStateManager) -> bool:
        return len(messages) > 4