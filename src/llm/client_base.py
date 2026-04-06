# =============================================================================
# client_base.py
# =============================================================================
# Original file by art-from-the-machine (Mantella project)
# https://github.com/art-from-the-machine/Mantella
#
# PLAYER2 INTEGRATION — Added by community contributor
# Changes are clearly marked with:
#   # --- PLAYER2 START ---
#   # --- PLAYER2 END ---
#
# Summary of changes:
#   1. New import for Player2 auth helpers (src/llm/player2_auth.py)
#   2. Added 'player2' to _KNOWN_SERVICES pointing to https://api.player2.game/v1
#   3. Modified _get_api_key() to auto-detect Player2 App on localhost:4315
#      before falling back to manual key lookup
#   4. Added 'Player2' branch to get_model_list() — Player2 manages model
#      selection internally, so no model list is fetched
#   5. Modified streaming_call() to strip non-standard JSON Schema fields
#      ('scope', 'default', 'minimum', 'maximum') from tool parameters before
#      sending to Player2, which strictly validates against the OpenAI spec
#
# NOTE FOR MAINTAINER:
#   The Player2 GAME_CLIENT_ID used for auto-detection is a development/test ID.
#   To use this integration officially, register Mantella at:
#   https://developer.player2.game and update PLAYER2_GAME_CLIENT_ID
#   in src/llm/player2_auth.py
# =============================================================================

from threading import Lock
from typing import AsyncGenerator, Any
from enum import Enum
from openai import APIConnectionError, BadRequestError, OpenAI, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletion
import time
import tiktoken
import json
import os
import copy
import requests
from pathlib import Path
from src.llm.ai_client import AIClient
from src.llm.message_thread import message_thread
from src.llm.messages import Message, ImageMessage, UserMessage
from src.llm.llm_model_list import LLMModelList
import src.utils as utils
from src.telemetry.telemetry import create_span_from_thread
from src.actions.function_manager import FunctionManager
from src.llm.claude_cache_connector import ClaudeCacheConnector

# --- PLAYER2 START ---
# Import Player2 auth helpers. See src/llm/player2_auth.py for details.
from src.llm.player2_auth import (
    get_key_from_local_app,
    is_player2_service,
    PLAYER2_API_BASE_URL,
    PLAYER2_DASHBOARD_URL
)
# --- PLAYER2 END ---

logger = utils.get_logger()


class VisionMode(Enum):
    """Vision operating modes for LLM image context"""
    DISABLED = "disabled" # No image client configured
    ALWAYS_ON = "always_on" # Image client active, no Vision action active
    ON_DEMAND = "on_demand" # Image client active, Vision action controls enablement


class ClientBase(AIClient):
    '''Base class for connecting to OpenAI-compatible endpoints

    Handles API key management, client generation (sync/async), request execution,
    token counting, endpoint resolution, and model list retrieval
    '''
    api_token_limits = {}
    tiktoken_cache_dir = "data"
    os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir

    def __init__(self, api_url: str, llm: str, llm_params: dict[str, Any] | None, custom_token_count: int, prompt_caching_enabled: bool = False) -> None:
        super().__init__()
        self._generation_lock: Lock = Lock()
        self._model_name: str = llm
        self._base_url = self._get_endpoint(api_url)
        self._startup_async_client: AsyncOpenAI | None = None
        self._request_params: dict[str, Any] | None = llm_params
        self._image_client = None
        self._function_client = None
        self._enable_vision_next_call: bool = False
        self._vision_mode: VisionMode = VisionMode.DISABLED

        if not utils.is_local_url(self._base_url): # Cloud LLM
            self._is_local: bool = False
            api_key = ClientBase._get_api_key(api_url)
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
        self._claude_cache = ClaudeCacheConnector()
        self._caching_enabled: bool = prompt_caching_enabled
        self._token_limit: int = self.__get_token_limit(self._model_name, custom_token_count, self._is_local)
        self._encoding = self.__get_model_encoding(api_url, self._model_name)


    def _determine_vision_mode(self) -> VisionMode:
        if not self._image_client:
            return VisionMode.DISABLED
        if FunctionManager.is_vision_action_active():
            return VisionMode.ON_DEMAND
        else:
            return VisionMode.ALWAYS_ON

    def enable_vision_for_next_call(self):
        self._enable_vision_next_call = True

    def _should_enable_vision(self) -> bool:
        if self._vision_mode == VisionMode.ALWAYS_ON:
            return True
        elif self._enable_vision_next_call:
            return True
        else:
            return False

    @property
    def token_limit(self) -> int:
        return self._token_limit

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_local(self) -> bool:
        return self._is_local

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def max_tokens_param(self) -> int:
        return self._request_params.get("max_tokens", 250) if self._request_params else 250


    @utils.time_it
    def generate_async_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self._api_key, base_url=self._base_url, default_headers=self._header)

    @utils.time_it
    def generate_sync_client(self) -> OpenAI:
        return OpenAI(api_key=self._api_key, base_url=self._base_url, default_headers=self._header)


    @utils.time_it
    def _request_call_full(self, messages: Message | message_thread) -> ChatCompletion | None:
        with self._generation_lock:
            sync_client = self.generate_sync_client()
            chat_completion: ChatCompletion = None
            logger.log(28, 'Getting LLM response...')

            if isinstance(messages, Message) or isinstance(messages, ImageMessage):
                openai_messages = [messages.get_openai_message()]
            else:
                openai_messages = messages.get_openai_messages()

            if self._request_params:
                request_params = self._request_params
            else:
                request_params: dict[str, Any] = {}

            if self._caching_enabled and self._claude_cache.is_applicable(self._base_url, self._model_name):
                try:
                    openai_messages = self._claude_cache.transform_messages(openai_messages)
                except Exception as e:
                    logger.debug(f"Claude caching transform failed: {e}")

            try:
                chat_completion = sync_client.chat.completions.create(
                    model=self.model_name,
                    messages=openai_messages,
                    **request_params,
                )
            except RateLimitError:
                logger.warning('Could not connect to LLM API, retrying in 5 seconds...')
                time.sleep(5)
            finally:
                sync_client.close()

            return chat_completion


    @utils.time_it
    def request_call(self, messages: Message | message_thread) -> str | None:
        chat_completion: ChatCompletion = self._request_call_full(messages)

        if (
            not chat_completion or
            not chat_completion.choices or
            chat_completion.choices.__len__() < 1 or
            not chat_completion.choices[0].message.content
        ):
            logger.info(f"LLM Response failed")
            return None

        reply = chat_completion.choices[0].message.content
        return reply


    @utils.time_it
    async def streaming_call(self, messages: Message | message_thread, is_multi_npc: bool, tools: list[dict] = None) -> AsyncGenerator[tuple[str, str | list] | None, None]:
        with create_span_from_thread("llm_streaming_call") as span:
            with self._generation_lock:
                logger.log(28, 'Getting LLM response...')

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
                    
                    # Determine if vision should be enabled for this call
                    if self._should_enable_vision():
                        if self._image_client:
                            openai_messages = self._image_client.add_image_to_messages(openai_messages, vision_hints)
                            logger.log(23, f"Vision enabled for this LLM call")
                        else:
                            logger.warning("Vision tool called but Vision not enabled in config - ignoring")
                        self._enable_vision_next_call = False  # Reset flag after use

                    # Handle tool calling: use dedicated function client if available, otherwise use main LLM
                    if tools:
                        if self._function_client:
                            pre_fetched_tool_calls = self._function_client.check_for_actions(messages, tools)
                            if pre_fetched_tool_calls:
                                yield ("tool_calls", pre_fetched_tool_calls)
                        else:
                            # If custom function LLM isn't enabled, let the main LLM handle tool calling as well as text generation

                            # --- PLAYER2 START ---
                            # Player2 strictly validates tool definitions against the OpenAI spec.
                            # Unlike OpenAI, Player2 requires the 'properties' field to always be
                            # present in tool 'parameters', even for functions that take no arguments.
                            #
                            # For example, Mantella's CancelTravel action sends:
                            #   "parameters": { "type": "object" }
                            #
                            # But Player2 requires:
                            #   "parameters": { "type": "object", "properties": {} }
                            #
                            # This block ensures all tool definitions are valid before sending to Player2.
                            # Other LLM services (OpenAI, OpenRouter, etc.) are not affected.
                            if is_player2_service(self._base_url):
                                import copy
                                cleaned_tools = []
                                for tool in tools:
                                    clean_tool = copy.deepcopy(tool)
                                    params = clean_tool.get("function", {}).get("parameters", {})
                                    if "properties" not in params:
                                        params["properties"] = {}
                                    cleaned_tools.append(clean_tool)
                                request_params["tools"] = cleaned_tools
                            else:
                                request_params["tools"] = tools
                            # --- PLAYER2 END ---

                    # Apply Claude cache breakpoint after all message transformations
                    if self._caching_enabled and self._claude_cache.is_applicable(self._base_url, self._model_name):
                        try:
                            openai_messages = self._claude_cache.transform_messages(openai_messages)
                        except Exception as e:
                            logger.debug(f"Claude caching transform failed: {e}")

                    # --- PLAYER2 START ---
                    # Player2 does not support messages with role 'tool' (tool call results),
                    # nor assistant messages with null content (which occur after a tool call).
                    # Sending these causes a deserialization error on Player2's end:
                    #   "data did not match any variant of untagged enum MessageContent"
                    #
                    # These messages are used by OpenAI-compatible APIs to maintain awareness
                    # of which actions were executed. Without them, the NPC may not reference
                    # recent actions in its next response, but all gameplay actions still execute
                    # correctly in-game. This is a known limitation of Player2's current API.
                    #
                    # Other LLM services (OpenAI, OpenRouter, etc.) are not affected.
                    if is_player2_service(self._base_url):
                        cleaned_messages = []
                        for msg in openai_messages:
                            if msg.get("role") == "tool":
                                continue
                            if msg.get("role") == "assistant" and msg.get("content") is None:
                                continue
                            cleaned_messages.append(msg)
                        openai_messages = cleaned_messages
                    # --- PLAYER2 END ---

                    # Create async client for main LLM streaming (after function client has run if applicable)
                    if self._startup_async_client:
                        async_client = self._startup_async_client
                        self._startup_async_client = None # do not reuse the same client
                    else:
                        async_client = self.generate_async_client()
                    
                    # Dict to track partial tool calls by index
                    accumulated_tool_calls = {}
                    async for chunk in await async_client.chat.completions.create(
                        model=self.model_name, 
                        messages=openai_messages, 
                        stream=True,
                        **request_params,
                    ):
                        try:
                            if chunk and chunk.choices and chunk.choices[0].delta:
                                delta = chunk.choices[0].delta
                                
                                # Handle regular content
                                if delta.content:
                                    # --- PLAYER2 START ---
                                    # Player2 returns tool calls as a JSON array in delta.content
                                    # instead of using the standard delta.tool_calls field.
                                    # This block detects that pattern and converts it to the
                                    # tool_calls format that Mantella expects, so actions are
                                    # executed correctly in-game rather than being spoken aloud.
                                    if is_player2_service(self._base_url) and delta.content.strip().startswith('[{'):
                                        try:
                                            import json
                                            parsed = json.loads(delta.content.strip())
                                            if isinstance(parsed, list) and parsed and 'function' in parsed[0]:
                                                yield ("tool_calls", parsed)
                                                continue
                                        except (json.JSONDecodeError, KeyError):
                                            pass
                                    # --- PLAYER2 END ---
                                    yield ("content", delta.content)
                                
                                # Accumulate tool calls by index
                                if delta.tool_calls:
                                    for tool_call in delta.tool_calls:
                                        idx = tool_call.index
                                        if idx not in accumulated_tool_calls:
                                            accumulated_tool_calls[idx] = {
                                                "id": tool_call.id if tool_call.id else "",
                                                "type": "function",
                                                "function": {
                                                    "name": "",
                                                    "arguments": ""
                                                }
                                            }
                                        
                                        # Accumulate the parts
                                        if tool_call.id:
                                            accumulated_tool_calls[idx]["id"] = tool_call.id
                                        if tool_call.function and tool_call.function.name:
                                            accumulated_tool_calls[idx]["function"]["name"] += tool_call.function.name
                                        if tool_call.function and tool_call.function.arguments:
                                            accumulated_tool_calls[idx]["function"]["arguments"] += tool_call.function.arguments
                                
                        except Exception as e:
                            logger.error(f"LLM API Connection Error: {e}")
                            break
                    
                    # After streaming completes, yield any accumulated tool calls
                    if accumulated_tool_calls:
                        tool_calls_list = [accumulated_tool_calls[i] for i in sorted(accumulated_tool_calls.keys())]
                        yield ("tool_calls", tool_calls_list)
                except Exception as e:
                    utils.play_error_sound()
                    if isinstance(e, APIConnectionError):
                        if e.code in [401, 'invalid_api_key']: # incorrect API key
                            if self._base_url == 'https://api.openai.com/v1':
                                service_connection_attempt = 'OpenRouter' # check if player means to connect to OpenRouter
                            else:
                                service_connection_attempt = 'OpenAI' # check if player means to connect to OpenAI
                            logger.error(f"Invalid API key. If you are trying to connect to {service_connection_attempt}, please choose an {service_connection_attempt} model via the 'model' setting in MantellaSoftware/config.ini. If you are instead trying to connect to a local model, please ensure the service is running.")
                        else:
                            logger.error(f"LLM API Error: {e}")
                    elif isinstance(e, BadRequestError):
                        if (e.type == 'invalid_request_error') and (self._image_client): # invalid request
                            logger.error(f"Invalid request. Try disabling Vision in Mantella's settings and try again.")
                        else:
                            logger.error(f"LLM API Streaming Error: {e}")
                    else:
                        logger.error(f"LLM API Streaming Error: {e}")
                finally:
                    if async_client:
                        await async_client.close()
    @classmethod
    @utils.time_it
    def _get_endpoint(cls, value: str) -> str:
        '''Resolve a service name or alias to an endpoint URL.
        Returns the normalized input as-is if not a known service (assumed to be a direct URL).'''
        return utils.resolve_service_endpoint(value)
    

    def __get_llm_priority(self, llm: str, priority: str, api_url: str) -> str:
        if self._get_endpoint(api_url) != 'https://openrouter.ai/api/v1':
            return ''
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
    def _get_api_key(service: str, show_error: bool = True) -> str | None:
        mod_parent_folder = Path(utils.resolve_path()).parent.parent.parent
        target_service = ClientBase._get_endpoint(service)

        # --- PLAYER2 START ---
        # For Player2, first try to get the API key automatically from the
        # locally running Player2 App (POST localhost:4315/v1/login/web/{client_id}).
        # If the app is not running, fall through to the standard key lookup below.
        if is_player2_service(service) or is_player2_service(target_service):
            local_key = get_key_from_local_app()
            if local_key:
                return local_key
            logger.info("Player2: Local app not available. Looking for manual API key in secret_keys.json...")
        # --- PLAYER2 END ---

        api_key = None
        for folder in [mod_parent_folder, Path('.')]:
            json_path = folder / 'secret_keys.json'
            try:
                with open(json_path, 'r') as f:
                    keys_dict: dict = json.load(f)
                for api_name, api_key_val in keys_dict.items():
                    if ClientBase._get_endpoint(str(api_name)) == target_service:
                        matching_api_key = str(api_key_val).strip()
                        if matching_api_key:
                            api_key = matching_api_key
                            break
                if api_key:
                    break
            except (FileNotFoundError, PermissionError, json.JSONDecodeError):
                pass

        if not api_key:
            for folder in [mod_parent_folder, Path('.')]:
                try:
                    with open(folder / 'GPT_SECRET_KEY.txt', 'r') as f:
                        val = f.readline().strip()
                        if val:
                            api_key = val
                            break
                except (FileNotFoundError, PermissionError):
                    pass

        if not api_key or api_key == '':
            if show_error:
                utils.play_error_sound()
                # --- PLAYER2 START ---
                # Show a Player2-specific error message with clear instructions
                # for both authentication methods (app and manual key).
                if is_player2_service(service) or is_player2_service(target_service):
                    logger.critical(f'''No Player2 API key found and Player2 App was not detected.
Options:
  1. Install the Player2 App and make sure it is running: https://player2.game
  2. Or generate an API key via the Mantella UI (Player2 section) and save it to secret_keys.json.
  3. Or manually create an API key at {PLAYER2_DASHBOARD_URL} and paste it in secret_keys.json:
       {{"https://api.player2.game/v1": "YOUR_P2_KEY"}}''')
                else:
                # --- PLAYER2 END ---
                    logger.critical(f'''No secret key found for service '{service}' in GPT_SECRET_KEY.txt.
Please create a secret key and paste it in your Mantella mod folder's GPT_SECRET_KEY.txt file.
If you are using OpenRouter (default), you can create a secret key in Account -> Keys once you have created an account: https://openrouter.ai/
If using OpenAI, see here on how to create a secret key: https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key
If you are running a model locally, please ensure the service (eg Kobold / Text generation web UI) is selected and running.
For more information, see here: https://art-from-the-machine.github.io/Mantella/''')
                time.sleep(3)

        return api_key


    @utils.time_it
    def __get_token_limit(self, llm, custom_token_count: int, is_local):
        manual_limits = utils.get_model_token_limits()
        token_limit_dict = {**self.api_token_limits, **manual_limits}

        if '/' in llm:
            llm = llm.split('/')[-1]

        if llm in token_limit_dict:
            token_limit = token_limit_dict[llm]
        else:
            logger.log(23, f"Could not find number of available tokens for {llm}. Defaulting to token count of {custom_token_count}. This number can be changed via the `Large Language Model`->`Custom Token Count` / `Vision`->`Custom Vision Model Token Count` settings in the Mantella UI")
            try:
                token_limit = custom_token_count
            except ValueError:
                logger.error(f"Invalid custom_token_count value: {custom_token_count}. It should be a valid integer. Please update your configuration.")
                token_limit = 4096
        if token_limit <= 4096:
            if is_local:
                llm = 'Local language model'
            logger.warning(f"{llm} has a low token count of {token_limit}. For better NPC memories, try changing to a model with a higher token count")

        return token_limit


    @utils.time_it
    def __get_model_encoding(self, api_url: str, llm: str) -> tiktoken.Encoding:
        chosenmodel = llm
        try:
            if api_url == 'OpenAI':
                encoding = tiktoken.encoding_for_model(chosenmodel)
            else:
                encoding = tiktoken.get_encoding('cl100k_base')
        except:
            try:
                encoding = tiktoken.get_encoding('cl100k_base')
            except:
                logger.error('Error loading model. If you are using an alternative to OpenAI, please find the setting `Large Language Model`->`LLM Service` in the Mantella UI and follow the instructions to change this setting')
                raise

        return encoding

    @utils.time_it
    def get_count_tokens(self, messages: message_thread | list[Message] | Message | str) -> int:
        if isinstance(messages, message_thread | list):
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
        messages_to_check = []
        if isinstance(messages, message_thread):
            messages_to_check = messages.get_openai_messages()
        else:
            for m in messages:
                messages_to_check.append(m.get_openai_message())

        num_tokens = 0
        for message in messages_to_check:
            num_tokens += 4
            for key, value in message.items():
                if isinstance(value, str):
                    num_tokens += len(self._encoding.encode(value))
                    if key == "name":
                        num_tokens += -1
        num_tokens += 2
        return num_tokens

    @utils.time_it
    def __num_tokens_from_message(self, message_to_measure: Message | str) -> int:
        text: str = ""
        if isinstance(message_to_measure, Message):
            text = message_to_measure.get_formatted_content()
        else:
            text = message_to_measure

        num_tokens = 4
        num_tokens += len(text)
        if isinstance(message_to_measure, Message) and message_to_measure.get_openai_message().__contains__("name"):
            num_tokens += -1

        return num_tokens

    @staticmethod
    def get_model_list(service: str, default_model: str = "mistralai/mistral-small-3.1-24b-instruct:free", is_vision: bool = False, is_tool_calling: bool = False) -> LLMModelList:
        # --- PLAYER2 START ---
        # 'Player2' added to the list of services with special model handling
        if service not in ['OpenAI', 'OpenRouter', 'NanoGPT', 'Player2']:
        # --- PLAYER2 END ---
    def get_model_list(service: str, default_model: str = "mistralai/mistral-small-3.1-24b-instruct:free", is_vision: bool = False, is_tool_calling: bool = False, show_key_error: bool = False) -> LLMModelList:
        if service not in ['OpenAI', 'OpenRouter', 'NanoGPT']:
            return LLMModelList([("Custom model","Custom model")], "Custom model", allows_manual_model_input=True)
        try:
            if service == "OpenAI":
                default_model = "gpt-4o-mini"
                models = utils.get_openai_model_list()
                allow_manual_model_input = True

            elif service == "OpenRouter":
                default_model = default_model
                secret_key = ClientBase._get_api_key("OpenRouter", show_error=show_key_error)
                if not secret_key:
                    return LLMModelList([(f"No secret key found for OpenRouter", "Custom model")], "Custom model", allows_manual_model_input=True)
                client = OpenAI(api_key=secret_key, base_url='https://openrouter.ai/api/v1')
                models = client.models.list()
                client.close()
                allow_manual_model_input = False

            elif service == "NanoGPT":
                default_model = "mistral-small-31-24b-instruct"
                secret_key = ClientBase._get_api_key("NanoGPT", show_error=show_key_error)
                if not secret_key:
                    return LLMModelList([(f"No secret key found for NanoGPT", "Custom model")], "Custom model", allows_manual_model_input=True)
                headers = {"Authorization": f"Bearer {secret_key}"}
                url = "https://nano-gpt.com/api/v1/models?detailed=true"
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    raise Exception(f"NanoGPT API returned status {response.status_code}: {response.text}")
                models_data = response.json()
                allow_manual_model_input = False

            # --- PLAYER2 START ---
            elif service == "Player2":
                # Player2 does not expose a /models endpoint.
                # Model selection is handled internally by the Player2 app —
                # the user changes it directly in the app without any API call.
                # We use "gpt-3.5-turbo" as a placeholder model name since
                # Player2 follows the OpenAI API spec but ignores the model field internally.
                return LLMModelList(
                    [("Managed by Player2", "gpt-3.5-turbo")],
                    "gpt-3.5-turbo",
                    allows_manual_model_input=False
                )
            # --- PLAYER2 END ---

            options = []
            multiplier = 1_000_000

            if service == "NanoGPT":
                models_list = models_data.get("data", [])
                for model in models_list:
                    try:
                        model_id = model.get("id", "unknown")
                        model_name = model.get("name", model_id)
                        context_size = model.get("context_length", 0)
                        pricing = model.get("pricing", {})
                        capabilities = model.get("capabilities", {})

                        model_display_parts = [f"{model_name} ({model_id})"]

                        if context_size and context_size > 0:
                            model_display_parts.append(f"Context: {utils.format_context_size(context_size)}")
                            ClientBase.api_token_limits[model_id.split('/')[-1]] = context_size

                        if pricing:
                            prompt_cost = float(pricing.get("prompt", 0))
                            completion_cost = float(pricing.get("completion", 0))
                            if prompt_cost >= 0 or completion_cost >= 0:
                                cost_parts = []
                                cost_parts.append(f"Prompt: {utils.format_price(prompt_cost)}")
                                cost_parts.append(f"Completion: {utils.format_price(completion_cost)}")
                                model_display_parts.append(f"Cost per 1M tokens: {'. '.join(cost_parts)}")

                        if capabilities.get("vision"):
                            model_display_parts.append("✅ Vision")
                        if capabilities.get("tool_calling"):
                            model_display_parts.append("✅ Advanced Actions")
                        if capabilities.get("reasoning"):
                            model_display_parts.append("⚠️ Reasoning")

                        model_display_name = " | ".join(model_display_parts)

                    except Exception as e:
                        model_display_name = model.get("id", "unknown")

                    options.append((model_display_name, model.get("id", "unknown")))

            else:
                for model in models.data:
                    try:
                        if model.model_extra:
                            context_size: int = model.model_extra["context_length"]
                            prompt_cost: float = float(model.model_extra["pricing"]["prompt"]) * multiplier
                            completion_cost: float = float(model.model_extra["pricing"]["completion"]) * multiplier
                            vision_available: str = ' | ✅ Vision' if model.model_extra["architecture"]["modality"] == 'text+image->text' else ''
                            tool_calling_available: str = ' | ✅ Advanced Actions' if 'tools' in model.model_extra['supported_parameters'] else ''
                            reasoning_model: str = ' | ⚠️ Reasoning' if 'reasoning' in model.model_extra['supported_parameters'] else ''
                            model_display_name = f"{model.id} | Context: {utils.format_context_size(context_size)} | Cost per 1M tokens: Prompt: {utils.format_price(prompt_cost)}. Completion: {utils.format_price(completion_cost)}{vision_available}{tool_calling_available}{reasoning_model}"
                            ClientBase.api_token_limits[model.id.split('/')[-1]] = context_size
                        else:
                            model_display_name = model.id
                    except:
                        model_display_name = model.id
                    options.append((model_display_name, model.id))

            has_vision_models = any('✅ Vision' in name for name, _ in options)
            if is_vision and has_vision_models:
                options = [(name, model_id) for name, model_id in options if '✅ Vision' in name]

            has_tool_calling_models = any('✅ Advanced Actions' in name for name, _ in options)
            if is_tool_calling and has_tool_calling_models:
                options = [(name, model_id) for name, model_id in options if '✅ Advanced Actions' in name]

            return LLMModelList(options, default_model, allows_manual_model_input=allow_manual_model_input)

        except Exception as e:
            utils.play_error_sound()
            error = f"Failed to retrieve list of models from {service}. A valid API key in 'GPT_SECRET_KEY.txt' is required. The file is in your mod folder of Mantella. Error: {e}"
            return LLMModelList([(error,"error")], "error", allows_manual_model_input=False)