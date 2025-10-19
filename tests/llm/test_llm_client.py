from src.llm.llm_client import LLMClient
import pytest
from src.config.config_loader import ConfigLoader
import src.llm.client_base
from src.llm.messages import SystemMessage
from src.character_manager import Character
from src.llm.messages import AssistantMessage
from src.llm.sentence import Sentence
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum
from src.actions.function_manager import FunctionManager
from src.llm.function_client import FunctionClient
from src.conversation.context import Context
from src.llm.message_thread import message_thread

@pytest.fixture
def example_system_message(default_config: ConfigLoader):
    return SystemMessage('Test.', default_config)

@pytest.fixture
def llm_client_w_function_client(default_config: ConfigLoader):
    default_config.advanced_actions_enabled = True
    default_config.custom_function_model = True
    client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt", "FUNCTION_SECRET_KEY.txt")
    return client


def test_missing_api_key_uses_fallback(default_config: ConfigLoader, tmp_path, monkeypatch):
    """Test that when no API key is found, the client falls back to 'abc123'"""
    mock_mod_path = tmp_path / "a" / "b" / "c"
    mock_mod_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: mock_mod_path)

    monkeypatch.setattr('time.sleep', lambda *args, **kwargs: None)
    monkeypatch.setattr("src.utils.play_error_sound", lambda *a, **kw: None)
    
    # When API key file is empty/missing, client should still be created with fallback
    # For cloud APIs, the fallback is 'abc123'
    default_config.llm_api = 'OpenRouter' # Cloud API
    client = LLMClient(default_config, "", "IMAGE_SECRET_KEY.txt")
    assert client.api_key == 'abc123'


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


def test_function_client_created_when_enabled(default_config: ConfigLoader):
    """
    Tests that LLMClient creates a FunctionClient when both flags are enabled
    """
    FunctionManager.load_all_actions()
    default_config.advanced_actions_enabled = True
    default_config.custom_function_model = True
    client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt", "FUNCTION_SECRET_KEY.txt")
    
    # Check that the function client exists
    assert hasattr(client, '_function_client')
    assert client._function_client is not None
    assert isinstance(client._function_client, FunctionClient)


def test_no_function_client_by_default(default_config: ConfigLoader):
    """
    Tests that LLMClient does not create a FunctionClient when flags are disabled
    """
    client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt", "FUNCTION_SECRET_KEY.txt")

    assert hasattr(client, '_function_client')
    assert client._function_client is None


def test_no_function_client_when_only_advanced_enabled(default_config: ConfigLoader):
    """
    Tests that FunctionClient is not created when only advanced_actions_enabled is True
    """
    default_config.advanced_actions_enabled = True
    default_config.custom_function_model = False
    
    client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")
    
    assert client._function_client is None


def test_llm_client_no_function_client_when_only_custom_model_enabled(default_config: ConfigLoader):
    """
    Tests that FunctionClient is not created when only custom_function_model is True
    """
    default_config.advanced_actions_enabled = False
    default_config.custom_function_model = True
    
    client = LLMClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt", "FUNCTION_SECRET_KEY.txt")
    
    assert client._function_client is None


@pytest.mark.asyncio
async def test_streaming_call_with_function_client(llm_client_w_function_client: LLMClient, default_context: Context, sample_message_thread_function_request: message_thread):
    """
    Tests that streaming_call uses function client when tools are provided and function client exists
    NOTE: This is an integration test that requires an actual LLM connection
    """
    tools = FunctionManager.generate_context_aware_tools(default_context)
    
    # Call streaming_call with tools - should use function client
    tool_calls_received = []
    content_received = []
    
    async for stream_type, item in llm_client_w_function_client.streaming_call(sample_message_thread_function_request, False, tools):
        if stream_type == "tool_calls":
            tool_calls_received.append(item)
        elif stream_type == "content":
            content_received.append(item)
    
    # Verify the call completed without errors
    assert isinstance(tool_calls_received, list)
    assert isinstance(content_received, list)


@pytest.mark.asyncio  
async def test_streaming_call_without_function_client(llm_client: LLMClient, default_context: Context, sample_message_thread_function_request: message_thread):
    """
    Tests that streaming_call uses main LLM for tools when function client doesn't exist
    NOTE: This is an integration test that requires an actual LLM connection
    """
    FunctionManager.load_all_actions()

    # Verify no function client (default)
    assert llm_client._function_client is None
    
    # Generate tools
    tools = FunctionManager.generate_context_aware_tools(default_context)
    
    # Call streaming_call with tools - should use main LLM
    tool_calls_received = []
    content_received = []
    
    async for stream_type, item in llm_client.streaming_call(sample_message_thread_function_request, False, tools):
        if stream_type == "tool_calls":
            tool_calls_received.append(item)
        elif stream_type == "content":
            content_received.append(item)
    
    # Verify the call completed without errors
    assert isinstance(tool_calls_received, list)
    assert isinstance(content_received, list)


@pytest.mark.asyncio
async def test_streaming_call_without_tools(llm_client_w_function_client: LLMClient, default_config: ConfigLoader, sample_message_thread_function_request: message_thread):
    """
    Tests that streaming_call uses main LLM when no tools are provided (even with function client)
    NOTE: This is an integration test that requires an actual LLM connection
    """
    default_config.advanced_actions_enabled = True
    default_config.custom_function_model = True
    
    # Call streaming_call WITHOUT tools - should use main LLM
    content_received = []
    tool_calls_received = []
    
    async for stream_type, item in llm_client_w_function_client.streaming_call(sample_message_thread_function_request, False, None):
        if stream_type == "content":
            content_received.append(item)
        elif stream_type == "tool_calls":
            tool_calls_received.append(item)
    
    # Should receive content
    assert len(content_received) > 0
    # Verify the call completed without errors
    assert isinstance(tool_calls_received, list)
    assert len(tool_calls_received) == 0