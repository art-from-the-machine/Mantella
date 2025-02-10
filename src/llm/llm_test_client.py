from typing import AsyncGenerator
from src.llm.llm_model_list import LLMModelList
from src.llm.ai_client import AIClient
from src.llm.message_thread import message_thread
from src.llm.messages import message


class LLMTestClient(AIClient):
    '''LLM class to handle NPC responses
    '''
    def __init__(self, replies: list[str]) -> None:
        self.__replies = replies
        self.__counter = 0

    async def streaming_call(self, messages: message | message_thread, is_multi_npc: bool) -> AsyncGenerator[str | None, None]:
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
        if self.__counter > len(self.__replies):
            yield "Out of prepared replies"
        else:            
            reply = self.__replies[self.__counter].split() #Split by spaces to simulate words/tokens get yielded one by one
            for word in reply:
                yield word + " "

    def request_call(self, messages: message | message_thread) -> str | None:
        """A standard sync request call to the LLM. 
        This method generates a new client, calls 'client.chat.completions.create', returns the result and closes when finished

        Args:
            messages (conversation_thread): The message thread of the conversation

        Returns:
            str | None: The reply of the LLM
        """
        pass
    
    def get_count_tokens(self, messages: message_thread | list[message] | message | str) -> int:
        """Returns the number of tokens used by a list of messages
        """
        return 0  

    def is_too_long(self, messages: message_thread | list[message] | message | str, token_limit_percent: float) -> bool:
        """Verifies that an input is within token_limit_percent of the context size of the model
        """
        return False

    @staticmethod
    def get_model_list(service: str, secret_key_file: str, default_model: str = "google/gemma-2-9b-it:free", is_vision: bool = False) -> LLMModelList:
        """Returns a list of available LLM models

        Args:
            service (str): the service to query for LLM models
            secret_key_file (str): _description_
            default_model (_type_, optional): _description_. Defaults to "google/gemma-2-9b-it:free".
            is_vision (bool, optional): _description_. Defaults to False.

        Returns:
            LLMModelList: _description_
        """
        return LLMModelList([("test","test")],"test", False)
