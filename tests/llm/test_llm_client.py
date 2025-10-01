from src.llm.llm_client import LLMClient
import pytest
from src.config.config_loader import ConfigLoader
import src.llm.client_base
from src.llm.messages import SystemMessage
from src.character_manager import Character
from src.llm.messages import AssistantMessage
from src.llm.sentence import Sentence
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum

@pytest.fixture
def example_system_message(default_config: ConfigLoader):
    return SystemMessage('Test.', default_config)


def test_missing_api_key_raises_error(default_config: ConfigLoader, tmp_path, monkeypatch):
    mock_mod_path = tmp_path / "a" / "b" / "c"
    mock_mod_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: mock_mod_path)

    def fake_sleep(*args, **kwargs):
        raise ValueError("API key is missing")
    monkeypatch.setattr(src.llm.client_base.time, 'sleep', fake_sleep) # Skip sleeping on error

    monkeypatch.setattr("src.utils.play_error_sound", lambda *a, **kw: None)
    
    with pytest.raises(ValueError, match="API key is missing"):
        LLMClient(default_config, "", "IMAGE_SECRET_KEY.txt")


def test_apis_load_correctly(default_config: ConfigLoader):
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
    async for item in llm_client.streaming_call(messages=example_system_message, is_multi_npc=False):
        if item is not None:
            if isinstance(item, tuple) and len(item) == 2:
                item_type, item_data = item
                if item_type == "content":
                    response += item_data
            else:
                # Backward compatibility: plain string
                response += item
    assert response is not None
    assert isinstance(response, str)

    response = ''
    # Multi NPC
    async for item in llm_client.streaming_call(messages=example_system_message, is_multi_npc=True):
        if item is not None:
            if isinstance(item, tuple) and len(item) == 2:
                item_type, item_data = item
                if item_type == "content":
                    response += item_data
            else:
                # Backward compatibility: plain string
                response += item
    assert response is not None
    assert isinstance(response, str)


def test_assistant_message_tool_calls_serialization(default_config: ConfigLoader):
    """Test that AssistantMessage properly stores and serializes tool_calls"""
    from src.llm.messages import AssistantMessage
    
    # Create an assistant message
    assistant_msg = AssistantMessage(default_config)
    
    # Set tool calls
    tool_calls = [
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "attack_npc",
                "arguments": '{"target": "bandit"}'
            }
        }
    ]
    assistant_msg.tool_calls = tool_calls
    
    # Get OpenAI message format
    openai_msg = assistant_msg.get_openai_message()
    
    # Verify the structure
    assert openai_msg["role"] == "assistant"
    assert "tool_calls" in openai_msg
    assert openai_msg["tool_calls"] == tool_calls
    assert openai_msg["content"] is None or openai_msg["content"] == ""


def test_assistant_message_without_tool_calls(default_config: ConfigLoader, example_skyrim_npc_character: Character):
    """Test that AssistantMessage without tool_calls serializes normally"""
    
    # Create an assistant message with text content
    assistant_msg = AssistantMessage(default_config)
    sentence_content = SentenceContent(
        speaker=example_skyrim_npc_character,
        text="Hello there.",
        sentence_type=SentenceTypeEnum.SPEECH,
        is_system_generated_sentence=False
    )
    sentence = Sentence(sentence_content, "mock_audio.wav", 1.0)
    assistant_msg.add_sentence(sentence)
    
    # Get OpenAI message format
    openai_msg = assistant_msg.get_openai_message()
    
    # Verify the structure
    assert openai_msg["role"] == "assistant"
    assert "tool_calls" not in openai_msg
    assert openai_msg["content"] == "Hello there."


def test_assistant_message_with_both_tool_calls_and_content(default_config: ConfigLoader, example_skyrim_npc_character: Character):
    """Test AssistantMessage with both tool_calls and text content"""    
    # Create an assistant message
    assistant_msg = AssistantMessage(default_config)
    
    # Add tool calls
    tool_calls = [
        {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "follow_npc",
                "arguments": '{}'
            }
        }
    ]
    assistant_msg.tool_calls = tool_calls
    
    # Add text content
    sentence_content = SentenceContent(
        speaker=example_skyrim_npc_character,
        text="I'll follow you.",
        sentence_type=SentenceTypeEnum.SPEECH,
        is_system_generated_sentence=False
    )
    sentence = Sentence(sentence_content, "mock_audio.wav", 1.0)
    assistant_msg.add_sentence(sentence)
    
    # Get OpenAI message format
    openai_msg = assistant_msg.get_openai_message()
    
    # Verify the structure
    assert openai_msg["role"] == "assistant"
    assert "tool_calls" in openai_msg
    assert openai_msg["tool_calls"] == tool_calls
    assert openai_msg["content"] == "I'll follow you."
