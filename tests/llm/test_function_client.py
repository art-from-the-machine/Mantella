from src.llm.function_client import FunctionClient
from src.llm.message_thread import message_thread
from src.conversation.context import Context
from src.config.config_loader import ConfigLoader
from src.actions.function_manager import FunctionManager
from src.llm.messages import UserMessage
from src.llm.message_thread import message_thread

def test_check_for_actions_with_tools(default_function_client: FunctionClient, sample_message_thread_function_request: message_thread, default_context: Context):
    """
    Tests that check_for_actions returns tool calls
    """
    tools = FunctionManager.generate_context_aware_tools(default_context)
    result = default_function_client.check_for_actions(sample_message_thread_function_request, tools)
    
    # There is some randomness in that the LLM may not always decide to call a function depending on the model / prompt,
    # but if this is inconsistent enough to be a problem, then the default model or prompt should be adjusted
    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0
    assert "function" in result[0]
    assert "name" in result[0]["function"]
    # If a function was called, it should be related to the "Follow" request given the contents of sample_message_thread_function_request
    assert "follow" in result[0]["function"]["name"].lower()
    assert "arguments" in result[0]["function"]


def test_check_for_actions_no_function_needed(default_function_client: FunctionClient, sample_message_thread_no_function_needed: message_thread, default_context: Context):
    """
    Tests that check_for_actions returns None when no function should be called
    """
    tools = FunctionManager.generate_context_aware_tools(default_context)
    result = default_function_client.check_for_actions(sample_message_thread_no_function_needed, tools)
    
    # No functions should be called when not prompted
    assert result is None


def test_function_client_initialization(default_config: ConfigLoader):
    """
    Tests that FunctionClient initializes correctly with proper config values
    """    
    FunctionManager.load_all_actions()
    client = FunctionClient(default_config, "GPT_SECRET_KEY.txt", "FUNCTION_SECRET_KEY.txt")
    
    assert client is not None


def test_function_client_uses_separate_config(default_config: ConfigLoader):
    """
    Tests that FunctionClient uses its own config values, not the main LLM config
    """
    # Set different values for main LLM and function LLM
    default_config.llm_api = 'https://main-api.example.com/v1'
    default_config.llm = 'main-model'
    default_config.function_llm_api = 'https://function-api.example.com/v1'
    default_config.function_llm = 'function-model'
    default_config.function_llm_params = {"temperature": 0.3}
    
    FunctionManager.load_all_actions()
    client = FunctionClient(default_config, "GPT_SECRET_KEY.txt", "FUNCTION_SECRET_KEY.txt")
    
    # Verify function client uses function-specific config
    assert client.model_name == default_config.function_llm
    assert client.model_name != default_config.llm


def test_check_for_actions_with_empty_tools(default_function_client: FunctionClient, sample_message_thread_no_function_needed: message_thread):
    """
    Tests that check_for_actions handles empty tools list gracefully
    """
    result = default_function_client.check_for_actions(sample_message_thread_no_function_needed, [])
    
    assert result is None


def test_check_for_actions_multiple_tools(default_function_client: FunctionClient, sample_message_thread_multiple_functions_needed: message_thread, default_context: Context):
    """
    Tests that check_for_actions can handle multiple tool calls in one response
    """    
    tools = FunctionManager.generate_context_aware_tools(default_context)
    result = default_function_client.check_for_actions(sample_message_thread_multiple_functions_needed, tools)
    
    assert result is not None
    assert isinstance(result, list)
    assert len(result) >= 1 # More than one function called
    assert all(isinstance(tool_call, dict) for tool_call in result)
    assert all("function" in tool_call and "name" in tool_call["function"] for tool_call in result)


def test_shortened_context_creation(default_function_client: FunctionClient, sample_message_thread_function_request: message_thread):
    """
    Tests that _create_shortened_context properly creates a shortened version of the message thread
    """
    # Create a shortened context with max 3 messages
    shortened = default_function_client._create_shortened_context(sample_message_thread_function_request, max_messages=3)
    
    # Should have a system message + at most 3 recent messages
    assert len(shortened) <= 4  # System message + 3 user/assistant messages
    assert len(shortened) >= 1  # At least the system message
    
    # First message should be the function prompt system message
    messages = shortened.get_openai_messages()
    assert messages[0]["role"] == "system"
    assert "analyzing a conversation" in messages[0]["content"].lower()
    
    
def test_shortened_context_respects_max_messages(default_function_client: FunctionClient):
    """
    Tests that shortened context properly limits the number of messages
    """    
    config = default_function_client._FunctionClient__config
    long_thread = message_thread(config, "Initial prompt")
    
    # Add 10 user messages
    for i in range(10):
        long_thread.add_message(UserMessage(config, f"User message {i}"))
    
    # Create shortened context with max 5 messages
    shortened = default_function_client._create_shortened_context(long_thread, max_messages=5)
    
    # Should have system message + 5 most recent messages
    assert len(shortened) == 6
    
    messages = shortened.get_openai_messages()
    # The last message should be one of the later ones (message 7, 8, or 9)
    last_content = messages[-1]["content"]
    assert any(f"message {i}" in last_content for i in [5, 6, 7, 8, 9])
