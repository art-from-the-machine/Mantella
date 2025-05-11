from threading import Lock
from typing import AsyncGenerator, Any
from openai import APIConnectionError, BadRequestError, OpenAI, AsyncOpenAI, RateLimitError
import logging
import time
import tiktoken
import os
from pathlib import Path
from src.llm.ai_client import AIClient
from src.llm.message_thread import message_thread
from src.llm.messages import Message, ImageMessage, UserMessage
from src.llm.llm_model_list import LLMModelList
import src.utils as utils

class ClientBase(AIClient):
    '''Base class for connecting to OpenAI-compatible endpoints

    Handles API key management, client generation (sync/async), request execution,
    token counting, endpoint resolution, and model list retrieval
    '''
    api_token_limits = {}
    tiktoken_cache_dir = "data"
    os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir

    def __init__(self, api_url: str, llm: str, llm_params: dict[str, Any] | None, custom_token_count: int, secret_key_files: list[str]) -> None:
        '''
        Args:
            api_url (str): The API endpoint URL or a known service name (e.g., 'OpenAI', 'OpenRouter')
            llm (str): The name of the language model to use
            llm_params (dict[str, Any] | None): Additional parameters for the LLM requests (eg temperature, max_tokens)
            custom_token_count (int): A fallback token limit if the model's limit isn't known
            secret_key_files (list[str]): A list of filenames to search for the API key, in order of priority
        '''
        super().__init__()
        self._generation_lock: Lock = Lock()
        self._model_name: str = llm
        self._base_url = self.__get_endpoint(api_url)
        self._startup_async_client: AsyncOpenAI | None = None
        self._request_params: dict[str, Any] | None = llm_params
        self._image_client = None

        if 'https' in self._base_url: # Cloud LLM
            self._is_local: bool = False
            api_key = ClientBase._get_api_key(secret_key_files)
            if api_key:
                self._api_key = api_key
            else:
                self._api_key: str = 'abc123'
        else: # Local LLM
            self._is_local: bool = True
            self._api_key: str = 'abc123'

        referer = "https://art-from-the-machine.github.io/Mantella/"
        xtitle = "Mantella"
        self._header: dict[str, str] = {"HTTP-Referer": referer, "X-Title": xtitle}
        self._token_limit: int = self.__get_token_limit(self._model_name, custom_token_count, self._is_local)
        self._encoding = self.__get_model_encoding(api_url, self._model_name)


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

    @property
    def max_tokens_param(self) -> int:
        """Returns the max_tokens value from request params, or defaults to 250"""
        return self._request_params.get("max_tokens", 250) if self._request_params else 250


    @utils.time_it
    def generate_async_client(self) -> AsyncOpenAI:
        """Generates a new AsyncOpenAI client already setup to be used right away.
        Close the client after usage using 'await client.close()'

        The client needs to be closed after every call (and a new one created for the next call) to avoid connection issues

        Use :func:`streaming_call` for a normal streaming call to the LLM

        Returns:
            AsyncOpenAI: The new async client object
        """
        return AsyncOpenAI(api_key=self._api_key, base_url=self._base_url, default_headers=self._header)


    @utils.time_it
    def generate_sync_client(self) -> OpenAI:
        """Generates a new OpenAI client already setup to be used right away.
        Close the client after usage using 'client.close()'

        Use :func:`request_call` for a normal call to the LLM

        Returns:
            OpenAI: The new sync client object
        """
        return OpenAI(api_key=self._api_key, base_url=self._base_url, default_headers=self._header)


    @utils.time_it
    def request_call(self, messages: Message | message_thread) -> str | None:
        with self._generation_lock:
            sync_client = self.generate_sync_client()        
            chat_completion = None
            logging.log(28, 'Getting LLM response...')

            if isinstance(messages, Message) or isinstance(messages, ImageMessage):
                openai_messages = [messages.get_openai_message()]
            else:
                openai_messages = messages.get_openai_messages()
            
            if self._request_params:
                request_params = self._request_params
            else:
                request_params: dict[str, Any] = {}
            try:
                chat_completion = sync_client.chat.completions.create(
                    model=self.model_name,
                    messages=openai_messages,
                    **request_params,
                )
            except RateLimitError:
                logging.warning('Could not connect to LLM API, retrying in 5 seconds...')
                time.sleep(5)
            finally:
                sync_client.close()

            if (
                not chat_completion or 
                not chat_completion.choices or 
                chat_completion.choices.__len__() < 1 or 
                not chat_completion.choices[0].message.content
            ):
                logging.info(f"LLM Response failed")
                return None
            
            reply = chat_completion.choices[0].message.content
            return reply
        

    @utils.time_it
    async def streaming_call(self, messages: Message | message_thread, is_multi_npc: bool) -> AsyncGenerator[str | None, None]:
        with self._generation_lock:
            logging.log(28, 'Getting LLM response...')

            if self._startup_async_client:
                async_client = self._startup_async_client
                self._startup_async_client = None # do not reuse the same client
            else:
                async_client = self.generate_async_client()

            if self._request_params:
                request_params = self._request_params.copy() # copy of self._request_params to allow temporary override
            else:
                request_params: dict[str, Any] = {}
            if is_multi_npc: # override max_tokens to be at least 250 in radiant / multi-NPC conversations
                request_params["max_tokens"] = max(self.max_tokens_param, 250)
            try:
                # Prepare the messages including the image if provided
                vision_hints = ''
                if isinstance(messages, Message):
                    openai_messages = [messages.get_openai_message()]
                    if isinstance(messages, UserMessage):
                        vision_hints = messages.get_ingame_events_text()
                else:
                    openai_messages = messages.get_openai_messages()
                    last_message = messages.get_last_message()
                    if isinstance(last_message, UserMessage):
                        vision_hints = last_message.get_ingame_events_text()
                if self._image_client:
                    openai_messages = self._image_client.add_image_to_messages(openai_messages, vision_hints)

                async for chunk in await async_client.chat.completions.create(
                    model=self.model_name, 
                    messages=openai_messages, 
                    stream=True,
                    **request_params,
                ):
                    try:
                        if chunk and chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                    except Exception as e:
                        logging.error(f"LLM API Connection Error: {e}")
                        break
            except Exception as e:
                utils.play_error_sound()
                if isinstance(e, APIConnectionError):
                    if e.code in [401, 'invalid_api_key']: # incorrect API key
                        if self._base_url == 'https://api.openai.com/v1':
                            service_connection_attempt = 'OpenRouter' # check if player means to connect to OpenRouter
                        else:
                            service_connection_attempt = 'OpenAI' # check if player means to connect to OpenAI
                        logging.error(f"Invalid API key. If you are trying to connect to {service_connection_attempt}, please choose an {service_connection_attempt} model via the 'model' setting in MantellaSoftware/config.ini. If you are instead trying to connect to a local model, please ensure the service is running.")
                    else:
                        logging.error(f"LLM API Error: {e}")
                elif isinstance(e, BadRequestError):
                    if (e.type == 'invalid_request_error') and (self._image_client): # invalid request
                        logging.error(f"Invalid request. Try disabling Vision in Mantella's settings and try again.")
                    else:
                        logging.error(f"LLM API Error: {e}")
                else:
                    logging.error(f"LLM API Error: {e}")
            finally:
                await async_client.close()


    @utils.time_it
    def __get_endpoint(self, api_url_or_name: str) -> str:
        '''
        Resolves a service name (eg 'openai', 'koboldcpp') if known, or else assumes the input is a direct URL

        Args:
            api_url_or_name (str): The service name or the direct API base URL

        Returns:
            endpoint (str): The resolved API endpoint URL
        '''
        endpoints = {
            'openai': 'https://api.openai.com/v1', # don't set an endpoint, just use the OpenAI default
            'openrouter': 'https://openrouter.ai/api/v1',
            'kobold': 'http://127.0.0.1:5001/v1',
            'textgenwebui': 'http://127.0.0.1:5000/v1',
        }

        cleaned_api_url_or_name = api_url_or_name.strip().lower().replace(' ', '')
        if cleaned_api_url_or_name == 'openai':
            endpoint = endpoints['openai']
        elif cleaned_api_url_or_name == 'openrouter':
            endpoint = endpoints['openrouter']
        elif cleaned_api_url_or_name in ['kobold','koboldcpp']:
            endpoint = endpoints['kobold']
        elif cleaned_api_url_or_name in ['textgenwebui','text-gen-web-ui','textgenerationwebui','text-generation-web-ui']:
            endpoint = endpoints['textgenwebui']
        else: # if endpoint isn't named, assume it is a direct URL
            endpoint = api_url_or_name

        return endpoint
    

    def __get_llm_priority(self, llm: str, priority: str, api_url: str) -> str:
        '''https://openrouter.ai/docs/features/provider-routing'''
        # Priority is only compatible with OpenRouter
        if api_url.strip().lower().replace(' ', '') != 'openrouter':
            return ''
        
        # Free models cannot have a priority
        if llm.endswith(':free'):
            return ''
        
        priorities = {
            'Balanced': '',
            'Price': ':price', 
            'Speed': ':nitro'
        }
        return priorities.get(priority, '')
    

    @utils.time_it
    @staticmethod
    def _get_api_key(key_files: str | list[str], show_error: bool = True) -> str | None:
        '''
        Attempts to read an API key from a list of files in order of priority.

        Args:
            key_files (list[str]): A list of file names to check for the API key, in order of priority.
        '''
        if isinstance(key_files, str):
            key_files = [key_files]
        
        mod_parent_folder = Path(utils.resolve_path()).parent.parent.parent
        
        api_key = None
        for key_file in key_files:
            # try to check the mod folder first
            try:
                with open(mod_parent_folder / key_file, 'r') as f:
                    api_key = f.readline().strip()
                    if api_key:
                        break
            except (FileNotFoundError, PermissionError):
                pass
            
            # try to check locally (same folder as executable)
            try:
                with open(key_file, 'r') as f:
                    api_key = f.readline().strip()
                    if api_key:
                        break
            except (FileNotFoundError, PermissionError):
                pass

        if not api_key or api_key == '':
                if show_error:
                    utils.play_error_sound()
                    logging.critical(f'''No secret key found in GPT_SECRET_KEY.txt.
Please create a secret key and paste it in your Mantella mod folder's GPT_SECRET_KEY.txt file.
If you are using OpenRouter (default), you can create a secret key in Account -> Keys once you have created an account: https://openrouter.ai/
If using OpenAI, see here on how to create a secret key: https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key
If you are running a model locally, please ensure the service (eg Kobold / Text generation web UI) is selected and running via: http://localhost:4999/ui
For more information, see here: https://art-from-the-machine.github.io/Mantella/''')
                    time.sleep(3)

        return api_key
    

    @utils.time_it
    def __get_token_limit(self, llm, custom_token_count: int, is_local):
        '''Determines the token limit for the given LLM, using known values, manual overrides, or a default

        Args:
            llm (str): The name of the language model
            custom_token_count (int): A user-defined fallback token count from the config
            is_local (bool): Whether the model is running locally

        Returns:
            token_limit (int): The determined token limit for the model
        '''
        manual_limits = utils.get_model_token_limits()
        token_limit_dict = {**self.api_token_limits, **manual_limits}

        if '/' in llm:
            llm = llm.split('/')[-1]

        if llm in token_limit_dict:
            token_limit = token_limit_dict[llm]
        else:
            logging.log(23, f"Could not find number of available tokens for {llm}. Defaulting to token count of {custom_token_count} (this number can be changed via the `custom_token_count` setting in config.ini)")
            try:
                token_limit = custom_token_count
            except ValueError:
                logging.error(f"Invalid custom_token_count value: {custom_token_count}. It should be a valid integer. Please update your configuration.")
                token_limit = 4096  # Default to 4096 in case of an error.
        if token_limit <= 4096:
            if is_local:
                llm = 'Local language model'
            logging.warning(f"{llm} has a low token count of {token_limit}. For better NPC memories, try changing to a model with a higher token count")
        
        return token_limit
    

    @utils.time_it
    def __get_model_encoding(self, api_url: str, llm: str) -> tiktoken.Encoding:
        '''Gets the appropriate tiktoken encoding for the specified model or a sensible default

        Args:
            api_url (str): The API service/URL being used
            llm (str): The name of the language model

        Returns:
            tiktoken.Encoding: The encoding object for token counting
        '''
        chosenmodel = llm
        # if using an alternative API to OpenAI, use encoding for GPT-3.5 by default
        # NOTE: this encoding may not be the same for all models, leading to incorrect token counts
        #       this can lead to the token limit of the given model being overrun
        try:
            if api_url == 'OpenAI':
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
    
    @utils.time_it
    def get_count_tokens(self, messages: message_thread | list[Message] | Message | str) -> int:
        if isinstance(messages, message_thread | list) :
            return self.__num_tokens_from_messages(messages)
        elif isinstance(messages, Message):
            return self.__num_tokens_from_message(messages)
        else:
            return len(self._encoding.encode(messages))

    @utils.time_it
    def is_too_long(self, messages: message_thread | list[Message] | Message | str, token_limit_percent: float) -> bool:
        countTokens: int = self.get_count_tokens(messages)
        return countTokens > self.token_limit * token_limit_percent

    @utils.time_it
    def __num_tokens_from_messages(self, messages: message_thread | list[Message]) -> int:
        '''Calculates token count for a list of messages formatted for OpenAI API calls

        Args:
            messages (message_thread | list[Message]): The messages to count tokens for

        Returns:
            num_tokens (int): The estimated total token count
        '''
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
    def __num_tokens_from_message(self, message_to_measure: Message | str) -> int:
        '''Calculates the approximate token count for a single Message object or string,
        considering the overhead of the message structure

        Args:
            message_to_measure (Message | str): The message or string content

        Returns:
            num_tokens (int): Estimated token count
        '''
        text: str = ""
        if isinstance(message_to_measure, Message):
            text = message_to_measure.get_formatted_content()
        else:
            text = message_to_measure

        num_tokens = 4 # every message follows <im_start>{role/name}\n{content}<im_end>\n
        num_tokens += len(text)
        if isinstance(message_to_measure, Message) and message_to_measure.get_openai_message().__contains__("name"):# if there's a name, the role is omitted
            num_tokens += -1# role is always required and always 1 token
        
        return num_tokens
    
    @staticmethod
    def get_model_list(service: str, secret_key_file: str, default_model: str = "google/gemma-2-9b-it:free", is_vision: bool = False) -> LLMModelList:
        if service not in ['OpenAI', 'OpenRouter']:
            return LLMModelList([("Custom model","Custom model")], "Custom model", allows_manual_model_input=True)
        try:
            if service == "OpenAI":
                default_model = "gpt-4o-mini"
                models = utils.get_openai_model_list()
                # OpenAI models are not a "live" list, so manual input needs to be allowed for when new models not listed are released
                allow_manual_model_input = True
            elif service == "OpenRouter":
                default_model = default_model
                secret_key_files = [secret_key_file, 'GPT_SECRET_KEY.txt'] if secret_key_file != 'GPT_SECRET_KEY.txt' else [secret_key_file]
                secret_key = ClientBase._get_api_key(secret_key_files, not is_vision)
                if not secret_key:
                    return LLMModelList([(f"No secret key found in {secret_key_file}", "Custom model")], "Custom model", allows_manual_model_input=True)
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
                        
                        ClientBase.api_token_limits[model.id.split('/')[-1]] = context_size
                    else:
                        model_display_name = model.id
                except:
                    model_display_name = model.id
                options.append((model_display_name, model.id))
            
            # check if any models are marked as vision-capable
            has_vision_models = any(' | Vision Available' in name for name, _ in options)
            # filter model list if this is supposed to be a vision model list and there are models explicitly marked as such
            if is_vision and has_vision_models:
                options = [(name, model_id) for name, model_id in options if ' | Vision Available' in name]
            
            return LLMModelList(options, default_model, allows_manual_model_input=allow_manual_model_input)
        except Exception as e:
            utils.play_error_sound()
            error = f"Failed to retrieve list of models from {service}. A valid API key in 'GPT_SECRET_KEY.txt' is required. The file is in your mod folder of Mantella. Error: {e}"
            return LLMModelList([(error,"error")], "error", allows_manual_model_input=False)