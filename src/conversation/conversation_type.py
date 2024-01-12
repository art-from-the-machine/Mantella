from abc import ABC, abstractmethod
from enum import Enum
from llm.message_thread import message_thread
from conversation.context import context
from src.stt import Transcriber


class conversation_type_enum(Enum):
    PC2NPC = 1
    MULTINPC = 2
    NPC2NPC = 3
    
class conversation_type(ABC):
    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt
    
    @abstractmethod
    def generate_prompt(self, context_for_conversation: context) -> str:
        pass

    @abstractmethod
    def proceed_conversation(self, settings: context, messages: message_thread):
        pass

    def get_user_text(self, stt: Transcriber, messages: message_thread) -> str:
        pass

    @property
    def is_radiant(self) -> bool:
        return False
        

class pc_to_npc(conversation_type):
    def __init__(self, prompt: str) -> None:
        super().__init__(prompt)

    def generate_prompt(self, context_for_conversation: context) -> str:
        return context_for_conversation.generate_system_message(self._prompt, True)

    def proceed_conversation(self, settings: context, messages: message_thread):
        pass

class multi_npc(conversation_type):
    def __init__(self, prompt: str) -> None:
        super().__init__(prompt)

    def generate_prompt(self, context_for_conversation: context) -> str:
        return context_for_conversation.generate_system_message(self._prompt, True)

    def proceed_conversation(self, settings: context, messages: message_thread):
        pass

class radiant(conversation_type):
    __user_text_message1 = '*Please begin / continue a conversation topic (greetings are not needed). Ensure to change the topic if the current one is losing steam. The conversation should steer towards topics which reveal information about the characters and who they are, or instead drive forward conversations previously discussed in their memory.*'
    __user_text_message2 = '*Please wrap up the current topic between the NPCs in a natural way. Nobody is leaving, so no formal goodbyes.*'

    def __init__(self, prompt: str) -> None:
        super().__init__(prompt)

    def generate_prompt(self, context_for_conversation: context) -> str:
        return context_for_conversation.generate_system_message(self._prompt, False)

    def proceed_conversation(self, settings: context, messages: message_thread):
        pass
    
    def get_user_text(self, stt: Transcriber, messages: message_thread) -> str:
        pass

    @property
    def is_radiant(self) -> bool:
        return True