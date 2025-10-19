from abc import ABC, abstractmethod
from typing import AsyncGenerator

from src.llm.message_thread import message_thread
from src.llm.messages import Message
from src.llm.llm_model_list import LLMModelList


class AIClient(ABC):

    @abstractmethod
    def request_call(self, messages: Message | message_thread) -> str | None:
        """A standard sync request call to the LLM. 
        This method generates a new client, calls 'client.chat.completions.create', returns the result and closes when finished

        Args:
            messages (conversation_thread): The message thread of the conversation

        Returns:
            str | None: The reply of the LLM
        """
        pass

    @abstractmethod
    def streaming_call(self, messages: Message | message_thread, is_multi_npc: bool) -> AsyncGenerator[str | None, None]:
        """A standard streaming call to the LLM. Forwards the output of 'client.chat.completions.create' 
        This method generates a new client, calls 'client.chat.completions.create' in a streaming way, yields the result immediately and closes when finished

        Args:
            messages (message_thread): The message thread of the conversation
            num_characters (int): Number of characters in the conversation

        Returns:
            AsyncGenerator[str | None, None]: Returns an iterable object. Iterate over this using 'async for'

        Yields:
            Iterator[AsyncGenerator[str | None, None]]: Yields the return of the 'client.chat.completions.create' method immediately
        """
        pass
    
    @abstractmethod
    def get_count_tokens(self, messages: message_thread | list[Message] | Message | str) -> int:
        """Returns the number of tokens used by a list of messages
        """
        pass   

    @abstractmethod
    def is_too_long(self, messages: message_thread | list[Message] | Message | str, token_limit_percent: float) -> bool:
        """Verifies that an input is within token_limit_percent of the context size of the model
        """
        pass

    @staticmethod
    @abstractmethod
    def get_model_list(service: str, secret_key_file: str, default_model: str = "google/gemma-3-27b-it:free", is_vision: bool = False, is_tool_calling: bool = False) -> LLMModelList:
        """Returns a list of available LLM models

        Args:
            service (str): the service to query for LLM models
            secret_key_file (str): _description_
            default_model (_type_, optional): _description_. Defaults to "google/gemma-3-27b-it:free".
            is_vision (bool, optional): _description_. Defaults to False.
            is_tool_calling (bool, optional): _description_. Defaults to False.

        Returns:
            LLMModelList: _description_
        """
        pass