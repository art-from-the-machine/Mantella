import src.utils as utils
from typing import AsyncGenerator, List
from openai import OpenAI, AsyncOpenAI, RateLimitError
import logging
import time
import tiktoken
import requests
from src.llm.message_thread import message_thread
from src.llm.messages import message
from src.config_loader import ConfigLoader

class openai_client:
    """Joint setup for sync and async access to the LLMs
    """
    def __init__(self, config: ConfigLoader, secret_key_file: str) -> None:
        def auto_resolve_endpoint(model_name, endpoints):
            # attempt connection to Kobold
            try:
                response = requests.get(endpoints['kobold'])
                if response.status_code == 200:
                    return endpoints['kobold']
            except requests.RequestException:
                # attempt connection to textgenwebui
                try:
                    response = requests.get(endpoints['textgenwebui'] + '/models')
                    if response.status_code == 200:
                        return endpoints['textgenwebui']
                except requests.RequestException:
                    pass
            
            # OpenRouter model names always have slashes (/), whereas OpenAI model names never have slashes
            # if this assumption changes, then this code will be inaccurate
            if '/' in model_name:
                return endpoints['openrouter']
            else:
                return endpoints['openai']
        
        endpoints = {
            'openai': 'none', # don't set an endpoint, just use the OpenAI default
            'openrouter': 'https://openrouter.ai/api/v1',
            'kobold': 'http://127.0.0.1:5001/v1',
            'textgenwebui': 'http://127.0.0.1:5000/v1',
        }
        
        cleaned_llm_api = config.llm_api.strip().lower().replace(' ', '')
        if cleaned_llm_api == 'auto':
            endpoint = auto_resolve_endpoint(config.llm, endpoints)
        elif cleaned_llm_api == 'openai':
            endpoint = endpoints['openai']
            logging.info(f"Running LLM with OpenAI")
        elif cleaned_llm_api == 'openrouter':
            endpoint = endpoints['openrouter']
            logging.info(f"Running LLM with OpenRouter")
        elif cleaned_llm_api in ['kobold','koboldcpp']:
            endpoint = endpoints['kobold']
            logging.info(f"Running LLM with koboldcpp")
        elif cleaned_llm_api in ['textgenwebui','text-gen-web-ui','textgenerationwebui','text-generation-web-ui']:
            endpoint = endpoints['textgenwebui']
            logging.info(f"Running LLM with Text generation web UI")
        else: # if endpoint isn't named, assume it is a direct URL
            endpoint = config.llm_api


        if (endpoint == 'none') or ("https" in endpoint):
            #cloud LLM
            self.__is_local: bool = False
            with open(secret_key_file, 'r') as f:
                self.__api_key: str = f.readline().strip()
            logging.info(f"Running Mantella with '{config.llm}'. The language model chosen can be changed via config.ini")
        else:
            #local LLM
            self.__is_local: bool = True
            self.__api_key: str = 'abc123'
            logging.info(f"Running Mantella with local language model")

        self.__base_url: str = endpoint if endpoint != 'none' else None
        self.__stop: str | List[str] = config.stop
        self.__temperature: float = config.temperature
        self.__top_p: float = config.top_p
        self.__frequency_penalty: float = config.frequency_penalty
        self.__max_tokens: int = config.max_tokens
        self.__model_name: str = config.llm
        self.__token_limit: int = self.__get_token_limit(config.llm, config.custom_token_count, self.__is_local)
        referer = "https://art-from-the-machine.github.io/Mantella/"
        xtitle = "Mantella"
        self.__header: dict[str, str] = {"HTTP-Referer": referer, "X-Title": xtitle, }

        chosenmodel = config.llm
        # if using an alternative API, use encoding for GPT-3.5 by default
        # NOTE: this encoding may not be the same for all models, leading to incorrect token counts
        #       this can lead to the token limit of the given model being overrun
        if endpoint != 'none':
            chosenmodel = 'gpt-3.5-turbo'
        try:
            self.__encoding = tiktoken.encoding_for_model(chosenmodel)
        except:
            logging.error('Error loading model. If you are using an alternative to OpenAI, please find the setting `llm_api` in MantellaSoftware/config.ini and follow the instructions to change this setting')
            raise
    
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
    
    @property
    def api_key(self) -> str:
        """The secret key
        """
        return self.__api_key
    
    def generate_async_client(self) -> AsyncOpenAI:
        """Generates a new AsyncOpenAI client already setup to be used right away.
        Close the client after usage using 'await client.close()'

        At the time of this writing (28.Dec.2023), calling OpenRouter using this client tends to 'break' at some point.
        To circumvent this, use a new client for each call to 'client.chat.completions.create'

        Use :func:`~openai_client.openai_client.streaming_call` for a normal streaming call to the LLM

        Returns:
            AsyncOpenAI: The new async client object
        """
        if self.__base_url:
            return AsyncOpenAI(api_key=self.__api_key, base_url=self.__base_url, default_headers=self.__header)
        else:
            return AsyncOpenAI(api_key=self.__api_key, default_headers=self.__header)

    def generate_sync_client(self) -> OpenAI:
        """Generates a new OpenAI client already setup to be used right away.
        Close the client after usage using 'client.close()'

        Use :func:`~openai_client.openai_client.request_call` for a normal call to the LLM

        Returns:
            OpenAI: The new sync client object
        """
        if self.__base_url:
            return OpenAI(api_key=self.__api_key, base_url=self.__base_url, default_headers=self.__header)
        else:
            return OpenAI(api_key=self.__api_key, default_headers=self.__header)
    
    async def streaming_call(self, messages: list[dict[str,str]]) -> AsyncGenerator[str | None, None]:
        """A standard streaming call to the LLM. Forwards the output of 'client.chat.completions.create' 
        This method generates a new client, calls 'client.chat.completions.create' in a streaming way, yields the result immediately and closes when finished

        Args:
            messages (conversation_thread): The message thread of the conversation

        Returns:
            AsyncGenerator[str | None, None]: Returns an iterable object. Iterate over this using 'async for'

        Yields:
            Iterator[AsyncGenerator[str | None, None]]: Yields the return of the 'client.chat.completions.create' method immediately
        """
        async_client = self.generate_async_client()
        logging.info('Getting LLM response...')
        try:
            async for chunk in await async_client.chat.completions.create(model=self.model_name, 
                                                                            messages=messages.get_openai_messages(), 
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

    @utils.time_it
    def request_call(self, messages: message_thread) -> str | None:
        """A standard sync request call to the LLM. 
        This method generates a new client, calls 'client.chat.completions.create', returns the result and closes when finished

        Args:
            messages (conversation_thread): The message thread of the conversation

        Returns:
            str | None: The reply of the LLM
        """
        sync_client = self.generate_sync_client()        
        chat_completion = None
        logging.info('Getting LLM response...')
        try:
            chat_completion = sync_client.chat.completions.create(model=self.model_name, messages=messages.get_openai_messages(), max_tokens=1_000)
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
    
    @staticmethod
    def num_tokens_from_messages(messages: message_thread | list[message], model="gpt-3.5-turbo") -> int:
        """Returns the number of tokens used by a list of messages
        """
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        
        messages_to_check = []
        if isinstance(messages, message_thread):
            messages_to_check = messages.get_openai_messages()
        else:
            for m in messages:
                messages_to_check.append(m.get_openai_message())

        # note: this calculation is based on GPT-3.5, future models may deviate from this
        num_tokens = 0
        for message in messages_to_check:
            num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
            for key, value in message.items():
                if isinstance(value, str):
                    num_tokens += len(encoding.encode(value))
                    if key == "name":  # if there's a name, the role is omitted
                        num_tokens += -1  # role is always required and always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    
    @staticmethod
    def num_tokens_from_message(message_to_measure: message | str, encoding: tiktoken.Encoding | None, model="gpt-3.5-turbo") -> int:
        if not encoding:
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                encoding = tiktoken.get_encoding("cl100k_base")
        
        text: str = ""
        if isinstance(message_to_measure, message):
            text = message_to_measure.get_formatted_content()
        else:
            text = message_to_measure

        num_tokens = 4 # every message follows <im_start>{role/name}\n{content}<im_end>\n
        num_tokens += len(text)
        if isinstance(message_to_measure, message) and message_to_measure.get_openai_message().__contains__("name"):# if there's a name, the role is omitted
            num_tokens += -1# role is always required and always 1 token
        
        return num_tokens

    
    def calculate_tokens_from_messages(self, messages: message_thread) -> int:
        return openai_client.num_tokens_from_messages(messages, self.__model_name)
    
    def calculate_tokens_from_text(self, text: str) -> int:
        return len(self.__encoding.encode(text))
    
    # --- Private methods ---    
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