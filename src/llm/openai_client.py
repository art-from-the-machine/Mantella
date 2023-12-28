from typing import AsyncGenerator, List
from openai import OpenAI, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionAssistantMessageParam, ChatCompletionUserMessageParam, ChatCompletionSystemMessageParam
import logging
import time
from src.config_loader import ConfigLoader

class openai_client:
    """Joint setup for sync and async access to the LLMs
    """
    __token_limit: int
    __model_name: str
    __is_local: bool
    __api_key: str
    __base_url: str
    __header: dict[str, str]
    __stop : str | List[str]
    __temperature: float
    __top_p : float
    __frequency_penalty : float
    __max_tokens: int

    def __init__(self, config: ConfigLoader, secret_key_file: str) -> None:
        if (config.alternative_openai_api_base == 'none') or (config.alternative_openai_api_base == 'https://openrouter.ai/api/v1'):
            #cloud LLM
            self.__is_local = False
            with open(secret_key_file, 'r') as f:
                self.__api_key = f.readline().strip()
            logging.info(f"Running Mantella with '{config.llm}'. The language model chosen can be changed via config.ini")
        else:
            #local LLM
            self.__is_local = True
            self.__api_key = 'abc123'
            logging.info(f"Running Mantella with local language model")

        self.__base_url = config.alternative_openai_api_base
        self.__stop = config.stop
        self.__temperature = config.temperature
        self.__top_p = config.top_p
        self.__frequency_penalty = config.frequency_penalty
        self.__max_tokens = config.max_tokens
        self.__model_name = config.llm
        self.__token_limit = self.__get_token_limit(config.llm, config.custom_token_count, self.__is_local)
        # timeout = httpx.Timeout(60.0, read=60.0, write=60.0, connect=15.0)
        referrer = "https://github.com/art-from-the-machine/Mantella"
        xtitle = "mantella"
        self.__header = {"HTTP-Referer": referrer, "X-Title": xtitle, }
    
    @property
    def token_limit(self) -> int:
        """The token limit of the model
        """
        return self.__token_limit
    
    @property
    def model_name(self) -> str:
        """The name of the model
        """
        return self.__model_name
    
    @property
    def is_local(self) -> bool:
        """Is the model run locally?
        """
        return self.__is_local
    
    def generate_async_client(self) -> AsyncOpenAI:
        """Generates a new AsyncOpenAI client already setup to be used right away.
        Close the client after usage using 'await client.close()'

        At the time of this writing (28.Dec.2023), calling OpenRouter using this client tends to 'break' at some point.
        To circumvent this, use a new client for each call to 'client.chat.completions.create'

        Use :func:`~openai_client.openai_client.streaming_call` for a normal streaming call to the LLM

        Returns:
            AsyncOpenAI: The new async client object
        """
        return AsyncOpenAI(api_key=self.__api_key, base_url=self.__base_url, default_headers=self.__header)

    def generate_sync_client(self) -> OpenAI:
        """Generates a new OpenAI client already setup to be used right away.
        Close the client after usage using 'client.close()'

        Use :func:`~openai_client.openai_client.request_call` for a normal call to the LLM

        Returns:
            OpenAI: The new sync client object
        """
        return OpenAI(api_key=self.__api_key, base_url=self.__base_url, default_headers=self.__header)
    
    async def streaming_call(self, messages: list[dict[str,str]]) -> AsyncGenerator[str | None, None]:
        """A standard streaming call to the LLM. Forwards the output of 'client.chat.completions.create' 
        This method generates a new client, calls 'client.chat.completions.create' in a streaming way, yields the result immediately and closes when finished

        Args:
            messages (list[dict[str,str]]): The message thread of the conversation

        Returns:
            AsyncGenerator[str | None, None]: Returns an iterable object. Iterate over this using 'async for'

        Yields:
            Iterator[AsyncGenerator[str | None, None]]: Yields the return of the 'client.chat.completions.create' method immediately
        """
        message_thread = self.__convert_messages(messages)
        async_client = self.generate_async_client()
        logging.info('Getting LLM response...')
        try:
            async for chunk in await async_client.chat.completions.create(model=self.model_name, 
                                                                            messages=message_thread, 
                                                                            stream=True,
                                                                            stop=self.__stop,
                                                                            temperature=self.__temperature,
                                                                            top_p=self.__top_p,
                                                                            frequency_penalty=self.__frequency_penalty, 
                                                                            max_tokens=self.__max_tokens):
                if chunk and chunk.choices and chunk.choices.__len__() > 0 and chunk.choices[0].delta:
                    yield chunk.choices[0].delta.content
                else:
                    break
        except Exception as e:
            logging.error(f"LLM API Error: {e}")
        finally:
            await async_client.close()

    def request_call(self, messages: list[dict[str,str]]) -> str | None:
        """A standard sync request call to the LLM. 
        This method generates a new client, calls 'client.chat.completions.create', returns the result and closes when finished

        Args:
            messages (list[dict[str,str]]): The message thread of the conversation

        Returns:
            str | None: The reply of the LLM
        """
        message_thread = self.__convert_messages(messages)
        sync_client = self.generate_sync_client()        
        chat_completion = None
        logging.info('Getting LLM response...')
        try:
            chat_completion = sync_client.chat.completions.create(model=self.model_name, messages=message_thread, max_tokens=1_000)
        except RateLimitError:
            logging.warning('Could not connect to LLM API, retrying in 5 seconds...') #Do we really retry here?
            time.sleep(5)

        sync_client.close()

        if not chat_completion or chat_completion.choices.__len__() < 1 or not chat_completion.choices[0].message.content:
            logging.info(f"LLM Response failed")
            return None
        
        reply = chat_completion.choices[0].message.content
        logging.info(f"LLM Response: {reply}")
        return reply
    
    
    # --- Private methods ---    
    def __convert_messages(self, messages: list[dict[str,str]]) -> list[ChatCompletionMessageParam]:
        result = []
        for message in messages:
            if message["role"] == "user":
                result.append(ChatCompletionUserMessageParam(role = "user", content=message["content"]))
            if message["role"] == "assistant":
                result.append(ChatCompletionAssistantMessageParam(role = "assistant", content=message["content"]))
            if message["role"] == "system":
                result.append(ChatCompletionSystemMessageParam(role = "system", content=message["content"]))
        return result

    def __get_token_limit(self, llm, custom_token_count, is_local):
        if '/' in llm:
            llm = llm.split('/')[-1]

        if llm == 'gpt-3.5-turbo':
            token_limit = 4096
        elif llm == 'gpt-3.5-turbo-16k':
            token_limit = 16384
        elif llm == 'gpt-4':
            token_limit = 8192
        elif llm == 'gpt-4-32k':
            token_limit = 32768
        elif llm == 'claude-2':
            token_limit = 100_000
        elif llm == 'claude-instant-v1':
            token_limit = 100_000
        elif llm == 'palm-2-chat-bison':
            token_limit = 8000
        elif llm == 'palm-2-codechat-bison':
            token_limit = 8000
        elif llm == 'llama-2-7b-chat':
            token_limit = 4096
        elif llm == 'llama-2-13b-chat':
            token_limit = 4096
        elif llm == 'llama-2-70b-chat':
            token_limit = 4096
        elif llm == 'codellama-34b-instruct':
            token_limit = 16000
        elif llm == 'nous-hermes-llama2-13b':
            token_limit = 4096
        elif llm == 'weaver':
            token_limit = 8000
        elif llm == 'mythomax-L2-13b':
            token_limit = 8192
        elif llm == 'airoboros-l2-70b-2.1':
            token_limit = 4096
        elif llm == 'gpt-3.5-turbo-1106':
            token_limit = 16_385
        elif llm == 'gpt-4-1106-preview':
            token_limit = 128_000
        else:
            logging.info(f"Could not find number of available tokens for {llm}. Defaulting to token count of {custom_token_count} (this number can be changed via the `custom_token_count` setting in config.ini)")
            try:
                token_limit = int(custom_token_count)
            except ValueError:
                logging.error(f"Invalid custom_token_count value: {custom_token_count}. It should be a valid integer. Please update your configuration.")
                token_limit = 4096  # Default to 4096 in case of an error.
        if token_limit <= 4096:
            if is_local:
                llm = 'Local language model'
            logging.info(f"{llm} has a low token count of {token_limit}. For better NPC memories, try changing to a model with a higher token count")
        
        return token_limit