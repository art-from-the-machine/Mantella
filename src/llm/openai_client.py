from openai import OpenAI, AsyncOpenAI
import logging
from src.config_loader import ConfigLoader

class openai_client:
    """Joint setup for sync and async access to the LLMs
    """
    __sync_client: OpenAI
    __async_client: AsyncOpenAI
    __token_limit: int
    __model_name: str
    __is_local: bool

    def __init__(self, config: ConfigLoader, secret_key_file: str) -> None:
        if (config.alternative_openai_api_base == 'none') or (config.alternative_openai_api_base == 'https://openrouter.ai/api/v1'):
            #cloud LLM
            self.__is_local = False
            with open(secret_key_file, 'r') as f:
                api_key = f.readline().strip()
            logging.info(f"Running Mantella with '{config.llm}'. The language model chosen can be changed via config.ini")
        else:
            #local LLM
            self.__is_local = True
            api_key = 'abc123'
            logging.info(f"Running Mantella with local language model")

        self.__model_name = config.llm
        self.__token_limit = self.__get_token_limit(config.llm, config.custom_token_count, self.__is_local)
        self.__sync_client = OpenAI(api_key=api_key, base_url=config.alternative_openai_api_base)#should the header for openrouter be added to the sync call as well? It wasn't in the original
        self.__async_client = AsyncOpenAI(api_key=api_key, base_url=config.alternative_openai_api_base, default_headers={"HTTP-Referer": 'https://github.com/art-from-the-machine/Mantella', "X-Title": 'mantella'})
    
    @property
    def sync_client(self) -> OpenAI:
        """Provides sync acess to the OpenAI client
        """
        return self.__sync_client
    
    @property
    def async_client(self) -> AsyncOpenAI:
        """Provides async acess to the OpenAI client
        """
        return self.__async_client
    
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