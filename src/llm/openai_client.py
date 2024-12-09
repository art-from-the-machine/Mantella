from threading import Lock
import src.utils as utils
from typing import AsyncGenerator, List
from openai import APIConnectionError, BadRequestError, OpenAI, AsyncOpenAI, RateLimitError
import json
import logging
import time
import tiktoken
import requests
from src.llm.message_thread import message_thread
from src.llm.messages import message
from src.config.config_loader import ConfigLoader
from src.image.image_manager import ImageManager
import os
from pathlib import Path

        
class LLMModelList:            
    def __init__(self, available_models: list[tuple[str, str]], default_model: str, allows_manual_model_input: bool) -> None:
        self.__available_models = available_models
        self.__default_model = default_model
        self.__allows_manual_model_input = allows_manual_model_input

    @property
    def available_models(self) -> list[tuple[str, str]]:
        return self.__available_models

    @property
    def default_model(self) -> str:
        return self.__default_model
    
    @property
    def allows_manual_model_input(self) -> bool:
        return self.__allows_manual_model_input
    
    def is_model_in_list(self, model: str) -> bool:
        if self.__allows_manual_model_input:
            return True
        for model_in_list in self.__available_models:
            if model_in_list[1] == model:
                return True
        return False

class openai_client:
    """Joint setup for sync and async access to the LLMs
    """
    api_token_limits = {}
    tiktoken_cache_dir = "data"
    os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir

    

        
    @utils.time_it
    def __init__(self, config: ConfigLoader, secret_key_file: str, skip_api_setup: bool = False) -> None:
        
        self._generation_lock: Lock = Lock()
        self._api_key = None
        self._is_local = None
         #######################
       
        

        
        if not skip_api_setup:
            endpoint = self.__get_endpoint(config.llm_api) 
            if (endpoint == 'none') or ("https" in endpoint):
                #cloud LLM
                self._is_local: bool = False
                self._api_key = self.get_secret_key(secret_key_file)
                logging.log(23, f"Running Mantella with '{config.llm}'. The language model can be changed in MantellaSoftware/config.ini")
            else:
                #local LLM
                self._is_local: bool = True
                self._api_key: str = 'abc123'
                logging.info(f"Running Mantella with local language model")
            self._encoding = self.__get_model_encoding(endpoint, config.llm)

            self._set_llm_api_and_key(config.llm, config.llm_api, self._endpoints, secret_key_file)
            self._base_url: str | None = self._endpoint if self._endpoint != 'none' else None
            self._stop: str | List[str] = config.stop
            self._temperature: float = config.temperature
            self._top_p: float = config.top_p
            self._frequency_penalty: float = config.frequency_penalty
            self._max_tokens: int = config.max_tokens
            self._model_name: str = config.llm
            self._token_limit: int = self._get_token_limit(config.llm, config.custom_token_count, self._is_local)
            self._startup_async_client = self.generate_async_client() # initialize first client in advance of sending first LLM request to save time
            
        
        self.TOKEN_LIMIT_PERCENT = 0.45 # TODO: review this variable
        referer = "https://art-from-the-machine.github.io/Mantella/"
        xtitle = "Mantella"
        self._header: dict[str, str] = {"HTTP-Referer": referer, "X-Title": xtitle, }

        self.__vision_enabled = config.vision_enabled
        if self.__vision_enabled:
            self.__image_manager = ImageManager(config.game, 
                                                config.save_folder, 
                                                config.save_screenshot, 
                                                config.image_quality, 
                                                config.low_resolution_mode, 
                                                config.resize_method, 
                                                config.capture_offset)


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
            
    def _set_llm_api_and_key(self, llm, llm_api, endpoints, secret_key_file, fallback_secret_key=None):
        cleaned_llm_api = llm_api.strip().lower().replace(' ', '')
        # if cleaned_llm_api == 'auto':
        #     endpoint = auto_resolve_endpoint(config.llm, endpoints)
        if cleaned_llm_api == 'openai':
            self._endpoint = endpoints['openai']
            logging.info(f"Running LLM with OpenAI")
        elif cleaned_llm_api == 'openrouter':
            self._endpoint = endpoints['openrouter']
            logging.info(f"Running LLM with OpenRouter")
        elif cleaned_llm_api in ['kobold','koboldcpp']:
            self._endpoint = endpoints['kobold']
            logging.info(f"Running LLM with koboldcpp")
        elif cleaned_llm_api in ['textgenwebui','text-gen-web-ui','textgenerationwebui','text-generation-web-ui']:
            self._endpoint = endpoints['textgenwebui']
            logging.info(f"Running LLM with Text generation web UI")
        else: # if endpoint isn't named, assume it is a direct URL
            self._endpoint = llm_api

        if (self._endpoint == 'none') or ("https" in self._endpoint):
            #cloud LLM
            self._is_local: bool = False

            self._api_key = self.get_secret_key(secret_key_file)
            # Attempt to use fallback_secret_key if initial retrieval failed
            if not self._api_key and fallback_secret_key:
                logging.info(f"Attempting to use the fallback secret key from : {fallback_secret_key}")
                self._api_key = self.get_secret_key(fallback_secret_key)
            logging.log(23, f"Running Mantella with '{config.llm}'. The language model can be changed in MantellaSoftware/config.ini")
        else:
            #local LLM
            self._is_local: bool = True
            self._api_key: str = 'abc123'
            logging.info(f"Running Mantella with local language model")
    @property
    def endpoints(self) -> dict:
        """Available endpoints"""
        return self._endpoints

    @property
    def endpoint(self) -> str:
        """Available endpoint"""
        return self._endpoint    
    @property
    def token_limit(self) -> int:
        """The token limit of the model
        """
        return self._token_limit
    
    @property
    def model_name(self) -> str:
        """The name of the model
        """
        return self._model_name
    
    @property
    def is_local(self) -> bool:
        """Is the model run locally?
        """
        return self._is_local
    
    @property
    def api_key(self) -> str:
        """The secret key
        """
        return self._api_key
    
    @utils.time_it
    def generate_async_client(self) -> AsyncOpenAI:
        """Generates a new AsyncOpenAI client already setup to be used right away.
        Close the client after usage using 'await client.close()'

        The client needs to be closed after every call (and a new one created for the next call) to avoid connection issues

        Use :func:`~openai_client.openai_client.streaming_call` for a normal streaming call to the LLM

        Returns:
            AsyncOpenAI: The new async client object
        """
        if self._base_url:
            return AsyncOpenAI(api_key=self._api_key, base_url=self._base_url, default_headers=self._header)
        else:
            return AsyncOpenAI(api_key=self._api_key, default_headers=self._header)

    @utils.time_it
    def generate_sync_client(self) -> OpenAI:
        """Generates a new OpenAI client already setup to be used right away.
        Close the client after usage using 'client.close()'

        Use :func:`~openai_client.openai_client.request_call` for a normal call to the LLM

        Returns:
            OpenAI: The new sync client object
        """
        if self._base_url:
            return OpenAI(api_key=self._api_key, base_url=self._base_url, default_headers=self._header)
        else:
            return OpenAI(api_key=self._api_key, default_headers=self._header)
    
    @utils.time_it
    async def streaming_call(self, messages: message_thread, is_multi_npc: bool) -> AsyncGenerator[str | None, None]:
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
        with self._generation_lock:
            logging.info('Getting LLM response...')

            if self._startup_async_client:
                async_client = self._startup_async_client
                self._startup_async_client = None # do not reuse the same client
            else:
                async_client = self.generate_async_client()
            
            max_tokens = self.__max_tokens
            if is_multi_npc: # override max_tokens in radiant / multi-NPC conversations
                max_tokens = 250
            try:
                # Prepare the messages including the image if provided
                openai_messages = messages.get_openai_messages()
                if self.__vision_enabled:
                    openai_messages = self.__image_manager.add_image_to_messages(openai_messages)

                async for chunk in await async_client.chat.completions.create(
                    model=self.model_name, 
                    messages=openai_messages, 
                    stream=True,
                    stop=self._stop,
                    temperature=self._temperature,
                    top_p=self._top_p,
                    frequency_penalty=self._frequency_penalty, 
                    max_tokens=max_tokens
                ):
                    if chunk and chunk.choices and chunk.choices.__len__() > 0 and chunk.choices[0].delta:
                        yield chunk.choices[0].delta.content
                    else:
                        break
            except Exception as e:
                if isinstance(e, APIConnectionError):
                    if e.code in [401, 'invalid_api_key']: # incorrect API key
                        if self._base_url == None: # None = OpenAI
                            service_connection_attempt = 'OpenRouter' # check if player means to connect to OpenRouter
                        else:
                            service_connection_attempt = 'OpenAI' # check if player means to connect to OpenAI
                        logging.error(f"Invalid API key. If you are trying to connect to {service_connection_attempt}, please choose an {service_connection_attempt} model via the 'model' setting in MantellaSoftware/config.ini. If you are instead trying to connect to a local model, please ensure the service is running.")
                    else:
                        logging.error(f"LLM API Error: {e}")
                elif isinstance(e, BadRequestError):
                    if (e.type == 'invalid_request_error') and (self.__vision_enabled): # invalid request
                        logging.error(f"Invalid request. Try disabling Vision in Mantella's settings and try again.")
                    else:
                        logging.error(f"LLM API Error: {e}")
                else:
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
        with self._generation_lock:
            sync_client = self.generate_sync_client()        
            chat_completion = None
            logging.info('Getting LLM response...')
            
            try:            
                chat_completion = sync_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages.get_openai_messages(),
                    max_tokens=1_000
                )
            except RateLimitError:
                logging.warning('Could not connect to LLM API, retrying in 5 seconds...')
                time.sleep(5)
            finally:
                sync_client.close()

            if not chat_completion or chat_completion.choices.__len__() < 1 or not chat_completion.choices[0].message.content:
                logging.info(f"LLM Response failed")
                return None
            
            reply = chat_completion.choices[0].message.content
            return reply
    
    @utils.time_it
    def num_tokens_from_messages(self, messages: message_thread | list[message]) -> int:
        """Returns the number of tokens used by a list of messages
        """
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
                    num_tokens += len(self._encoding.encode(value))
                    if key == "name":  # if there's a name, the role is omitted
                        num_tokens += -1  # role is always required and always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    
    @utils.time_it
    def num_tokens_from_message(self, message_to_measure: message | str) -> int:
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

    @utils.time_it
    def calculate_tokens_from_messages(self, messages: message_thread) -> int:
        return self.num_tokens_from_messages(messages)
    
    @utils.time_it
    def calculate_tokens_from_text(self, text: str) -> int:
        return len(self._encoding.encode(text))
    
    @utils.time_it
    def is_text_too_long(self, text: str, token_limit_percent: float) -> bool:
        countTokens: int = self.calculate_tokens_from_text(text)
        return  countTokens > self.token_limit * token_limit_percent
        
    @utils.time_it
    def are_messages_too_long(self, messages: message_thread, token_limit_percent: float) -> bool:
        countTokens: int = self.calculate_tokens_from_messages(messages)
        return countTokens > self.token_limit * token_limit_percent
            
    
     
    @utils.time_it
    def _get_token_limit(self, llm, custom_token_count, is_local):
        manual_limits = utils.get_model_token_limits()
        token_limit_dict = {**self.api_token_limits, **manual_limits}

        if '/' in llm:
            llm = llm.split('/')[-1]

        if llm in token_limit_dict:
            token_limit = token_limit_dict[llm]
        else:
            logging.log(23, f"Could not find number of available tokens for {llm}. Defaulting to token count of {custom_token_count} (this number can be changed via the `custom_token_count` setting in config.ini)")
            try:
                token_limit = int(custom_token_count)
            except ValueError:
                logging.error(f"Invalid custom_token_count value: {custom_token_count}. It should be a valid integer. Please update your configuration.")
                token_limit = 4096  # Default to 4096 in case of an error.
        if token_limit <= 4096:
            if is_local:
                llm = 'Local language model'
            logging.warning(f"{llm} has a low token count of {token_limit}. For better NPC memories, try changing to a model with a higher token count")
        
        return token_limit
    
    # --- Private methods ---   
    @utils.time_it
    def __get_endpoint(self, llm_api: str) -> str:
        endpoints = {
            'openai': 'none', # don't set an endpoint, just use the OpenAI default
            'openrouter': 'https://openrouter.ai/api/v1',
            'kobold': 'http://127.0.0.1:5001/v1',
            'textgenwebui': 'http://127.0.0.1:5000/v1',
        }
        
        cleaned_llm_api = llm_api.strip().lower().replace(' ', '')
        if cleaned_llm_api == 'openai':
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
            endpoint = llm_api

        return endpoint
    

    @utils.time_it
    def __get_model_encoding(self, endpoint: str, llm: str) -> tiktoken.Encoding:
        chosenmodel = llm
        # if using an alternative API to OpenAI, use encoding for GPT-3.5 by default
        # NOTE: this encoding may not be the same for all models, leading to incorrect token counts
        #       this can lead to the token limit of the given model being overrun
        try:
            if endpoint == 'none': # 'none' == OpenAI endpoint
                encoding = tiktoken.encoding_for_model(chosenmodel) # get encoding for specific model
            else:
                encoding = tiktoken.get_encoding('cl100k_base') # get generic encoding
        except:
            try:
                encoding = tiktoken.get_encoding('cl100k_base') # try loading a generic encoding
            except:
                logging.error('Error loading model. If you are using an alternative to OpenAI, please find the setting `Large Language Model`->`LLM Service` in the Mantella UI and follow the instructions to change this setting')
                raise
        
        return encoding

    
    @staticmethod
    @utils.time_it
    def get_secret_key(secret_key_file: str) -> str | None:
        secret_key = None
        # First, try to open the secret key file in the mod folder
        try:
            mod_parent_folder = str(Path(utils.resolve_path()).parent.parent.parent)
            secret_key_path = Path(mod_parent_folder) / secret_key_file
            with open(secret_key_path, 'r') as f:
                secret_key = f.readline().strip()
        except FileNotFoundError:
            # Try to open the secret key file in the local folder
            try:
                secret_key_path = Path(secret_key_file)
                with open(secret_key_path, 'r') as f:
                    secret_key = f.readline().strip()
            except FileNotFoundError:
                # File not found in either location
                secret_key = None
            except Exception as e:
                logging.error(f"Error reading secret key file at {secret_key_file}: {e}")
                secret_key = None
        except Exception as e:
            logging.error(f"Error reading secret key file at {secret_key_path}: {e}")
            secret_key = None

        if not secret_key:
            logging.critical(f'''No secret key found in {secret_key_file}.
    Please create a secret key and paste it in your Mantella mod folder's {secret_key_file} file.
    If you are using OpenRouter (default), you can create a secret key in Account -> Keys once you have created an account: https://openrouter.ai/
    If using OpenAI, see here on how to create a secret key: https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key
    If you are running a model locally, please ensure the service (Kobold / Text generation web UI) is selected and running.
    For more information, see here: https://art-from-the-machine.github.io/Mantella/''')
            return None
        else:
            return secret_key

    @staticmethod
    def get_model_list(service: str) -> LLMModelList:
        if service not in ['OpenAI', 'OpenRouter']:
            return LLMModelList([("Custom model","Custom model")], "Custom model", allows_manual_model_input=True)
        try:
            if service == "OpenAI":
                default_model = "gpt-4o-mini"
                models = utils.get_openai_model_list()
                # OpenAI models are not a "live" list, so manual input needs to be allowed for when new models not listed are released
                allow_manual_model_input = True
            elif service == "OpenRouter":
                default_model = "google/gemma-2-9b-it:free"
                secret_key = openai_client.get_secret_key('GPT_SECRET_KEY.txt')
                if not secret_key:
                    return LLMModelList([("No secret key found in GPT_SECRET_KEY.txt", "Custom model")], "Custom model", allows_manual_model_input=True)
                # NOTE: while a secret key is not needed for this request, this may change in the future
                client = OpenAI(api_key=secret_key, base_url='https://openrouter.ai/api/v1')
                # don't log initial 'HTTP Request: GET https://openrouter.ai/api/v1/models "HTTP/1.1 200 OK"'
                logging.getLogger('openai').setLevel(logging.ERROR)
                logging.getLogger("httpx").setLevel(logging.ERROR)
                models = client.models.list()
                logging.getLogger('openai').setLevel(logging.INFO)
                logging.getLogger("httpx").setLevel(logging.INFO)
                client.close()
                allow_manual_model_input = False

            options = []
            multiplier = 1_000_000
            for model in models.data:
                try:
                    if model.model_extra:
                        context_size: int = model.model_extra["context_length"]
                        prompt_cost: float = float(model.model_extra["pricing"]["prompt"]) * multiplier
                        completion_cost: float = float(model.model_extra["pricing"]["completion"]) * multiplier
                        vision_available: str = ' | Vision Available' if model.model_extra["architecture"]["modality"] == 'text+image->text' else ''
                        model_display_name = f"{model.id} | Context: {utils.format_context_size(context_size)} | Cost per 1M tokens: Prompt: {utils.format_price(prompt_cost)}. Completion: {utils.format_price(completion_cost)}{vision_available}"
                        
                        openai_client.api_token_limits[model.id.split('/')[-1]] = context_size
                    else:
                        model_display_name = model.id
                except:
                    model_display_name = model.id
                options.append((model_display_name, model.id))
            return LLMModelList(options, default_model, allows_manual_model_input=allow_manual_model_input)
        except Exception as e:
            error = f"Failed to retrieve list of models from {service}. A valid API key in 'GPT_SECRET_KEY.txt' is required. The file is in your mod folder of Mantella. Error: {e}"
            return LLMModelList([(error,"error")], "error", allows_manual_model_input=False)

class function_client(openai_client):
    """Setup for sync and async access to image generation models"""
    def __init__(self, config: ConfigLoader, secret_key_file: str, fallback_secret_key: str) -> None:
        super().__init__(config, secret_key_file, skip_api_setup=True)
        
        endpoint = self.__get_endpoint(config.function_llm_api) 
        if (endpoint == 'none') or ("https" in endpoint):
            #cloud LLM
            self._is_local: bool = False
            self._api_key = self.get_secret_key(secret_key_file)
            if not self._api_key and fallback_secret_key:
                logging.info(f"Attempting to use the fallback secret key from : {fallback_secret_key}")
                self._api_key = self.get_secret_key(fallback_secret_key)
            logging.log(23, f"Running Mantella Function calling with '{config.function_llm}'. The function LLM can be changed in MantellaSoftware/config.ini")
        else:
            #local LLM
            self._is_local: bool = True
            self._api_key: str = 'abc123'
            logging.info(f"Running Mantella Function calling with local language model")
        self._encoding = self.__get_model_encoding(endpoint, config.function_llm)
        self._token_limit: int = self._get_token_limit(
            config.function_llm, 
            config.function_llm_custom_token_count, 
            self._is_local
        )
        
        self._base_url: str | None = self._endpoint if self._endpoint != 'none' else None
        self._stop: str | List[str] = config.function_llm_stop
        self._temperature: float = config.function_llm_temperature
        self._top_p: float = config.function_llm_top_p
        self._frequency_penalty: float = config.function_llm_frequency_penalty
        self._max_tokens: int = config.function_llm_max_tokens
        self._model_name: str = config.function_llm
        self._startup_sync_client = self.generate_sync_client()  # initialize first client in advance of sending first LLM request to save time
            

    def request_call(self, messages: message_thread, tools_list: ["tools list"]) -> str | None:
        """A standard sync request call to the LLM. 
        This method generates a new client, calls 'client.chat.completions.create', returns the result and closes when finished

        Args:
            messages (conversation_thread): The message thread of the conversation

        Returns:
            str | None: The reply of the LLM
        """
        with self._generation_lock:
            if self._startup_sync_client:
                sync_client = self._startup_sync_client
                self._startup_sync_client = None # do not reuse the same client
            else:
                sync_client = self.generate_sync_client()     
            chat_completion = None
            logging.info('Getting LLM response...')
            openai_messages = messages.get_openai_messages()
            print(openai_messages)
            try:            
                params = {
                'model': self.model_name,
                'messages': openai_messages,
                'stop': self._stop,
                'temperature': self._temperature,
                'top_p': self._top_p,
                'frequency_penalty': self._frequency_penalty,
                'max_tokens': self._max_tokens,
                }
            
                if not self._base_url:
                    params['tools'] = tools_list  # Include tools only if self._base_url is False or None

                chat_completion = sync_client.chat.completions.create(**params)
       
            except Exception as e:
                    if isinstance(e, APIConnectionError):
                        if e.code in [401, 'invalid_api_key']: # incorrect API key
                            if self._base_url == None: # None = OpenAI
                                service_connection_attempt = 'OpenRouter' # check if player means to connect to OpenRouter
                            else:
                                service_connection_attempt = 'OpenAI' # check if player means to connect to OpenAI
                            logging.error(f"Invalid API key. If you are trying to connect to {service_connection_attempt}, please choose an {service_connection_attempt} model via the 'model' setting in MantellaSoftware/config.ini. If you are instead trying to connect to a local model, please ensure the service is running.")
                        else:
                            logging.error(f"LLM API Error: {e}")
                    elif isinstance(e, BadRequestError):
                        if (e.type == 'invalid_request_error') : # invalid request
                            logging.error(f"Invalid request. Double check the functions submitted.")
                        else:
                            logging.error(f"LLM API Error: {e}")
                    else:
                        logging.error(f"LLM API Error: {e}")
            finally:
                sync_client.close()
            
            if not chat_completion or chat_completion.choices.__len__() < 1 :
            #if not chat_completion or chat_completion.choices.__len__() < 1 or not chat_completion.choices[0].message.content:
                logging.info(f"LLM Response failed")
                return None           
            chat_completion_json = json.dumps(chat_completion, default=lambda o: o.__dict__)
            print(f"chat completion_json is {chat_completion_json}")
            return chat_completion_json