from src.llm.function_client import FunctionClient
from src.llm.message_thread import message_thread

def test_check_for_actions_with_tools(default_function_client: FunctionClient, sample_message_thread_function_request: message_thread):
    """
    Tests that check_for_actions uses tools when provided (and requested in the prompt)
    """
    result = default_function_client.check_for_actions(sample_message_thread_function_request, 'Okay, lead the way.')
    
    # Assertions for basic structure
    assert result is not None
    assert isinstance(result, list)
    assert "id" in result[0]
    assert "name" in result[0]
    assert "arguments" in result[0]
    
    # Check that the requested tool was called
    assert result[0]["name"] == "follow"


def test_check_for_actions_no_function_needed(default_function_client: FunctionClient, sample_message_thread_no_function_needed: message_thread):
    """
    Tests that check_for_actions still returns a response even when no function should be called
    """
    result = default_function_client.check_for_actions(sample_message_thread_no_function_needed, 'Fine.')
    
    # No functions should be called when not prompted
    assert result is None
