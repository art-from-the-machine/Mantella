from src.llm.llm_client import LLMClient
import pytest
from src.config.config_loader import ConfigLoader
from src.llm.messages import SystemMessage

@pytest.fixture
def llm_client(default_config: ConfigLoader):
    return LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")

@pytest.fixture
def example_system_message(default_config: ConfigLoader):
    return SystemMessage('Test.', default_config)


def test_missing_api_key_raises_error(default_config: ConfigLoader):
    with pytest.raises(ValueError, match="API key is missing"):
        LLMClient(default_config, "", "IMAGE_SECRET_KEY.txt")


def test_apis_load_correctly(default_config: ConfigLoader):
    #["OpenRouter", "OpenAI", "KoboldCpp", "textgenwebui"]
    default_config.llm_api = 'OpenRouter'
    llm_client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")
    assert llm_client._base_url == 'https://openrouter.ai/api/v1'
    assert llm_client.is_local is False

    default_config.llm_api = 'OpenAI'
    llm_client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")
    assert llm_client._base_url == 'https://api.openai.com/v1'
    assert llm_client.is_local is False

    default_config.llm_api = 'KoboldCpp'
    llm_client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")
    assert llm_client._base_url == 'http://127.0.0.1:5001/v1'
    assert llm_client.is_local is True

    default_config.llm_api = 'textgenwebui'
    llm_client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")
    assert llm_client._base_url == 'http://127.0.0.1:5000/v1'
    assert llm_client.is_local is True

    # Custom external URL
    default_config.llm_api = 'https://custom-url.com'
    llm_client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")
    assert llm_client._base_url == 'https://custom-url.com'
    assert llm_client.is_local is False

    # Custom local URL
    default_config.llm_api = 'http://custom-url.com'
    llm_client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")
    assert llm_client._base_url == 'http://custom-url.com'
    assert llm_client.is_local is True
    assert llm_client.api_key == 'abc123'


def test_startup_async_client_initialized(llm_client: LLMClient):
    """Tests that the initial async client is generated"""
    assert llm_client._startup_async_client is not None


def test_default_vision_model_loads_correctly(default_config: ConfigLoader):
    default_config.vision_enabled = True
    llm_client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")
    assert llm_client._image_client is not None


def test_vision_model_disabled(default_config: ConfigLoader):
    llm_client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")
    assert llm_client._image_client is None


def test_sync_call(llm_client: LLMClient, example_system_message: SystemMessage):
    response = llm_client.request_call(example_system_message)
    assert response is not None
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_async_call(llm_client: LLMClient, example_system_message: SystemMessage):
    response = ''
    # Single NPC
    async for content in llm_client.streaming_call(messages=example_system_message, is_multi_npc=False):
        if content is not None:
            response += content
    assert response is not None
    assert isinstance(response, str)

    response = ''
    # Multi NPC
    async for content in llm_client.streaming_call(messages=example_system_message, is_multi_npc=True):
        if content is not None:
            response += content
    assert response is not None
    assert isinstance(response, str)