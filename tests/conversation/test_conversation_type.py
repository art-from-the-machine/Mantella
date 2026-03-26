from src.conversation.conversation_type import radiant
from src.conversation.context import Context
from src.config.config_loader import ConfigLoader
from src.llm.message_thread import message_thread
from src.llm.messages import UserMessage, AssistantMessage

def _simulate_turns(conv: radiant, context: Context, thread: message_thread, num_turns: int):
    """Simulate a number of LLM turns by alternating get_user_message and adding an assistant response."""
    for _ in range(num_turns):
        user_msg = conv.get_user_message(context, thread)
        if user_msg is None:
            break
        thread.add_message(user_msg)
        thread.add_message(AssistantMessage(context.config))

def test_radiant_max_turns_2_produces_exactly_2_responses(default_config: ConfigLoader, default_context: Context):
    """With radiant_max_turns=2, the LLM should respond exactly 2 times before the conversation ends."""
    default_config.radiant_max_turns = 2
    conv = radiant(default_config)
    thread = message_thread(default_config, "system prompt")

    _simulate_turns(conv, default_context, thread, num_turns=10)

    llm_responses = sum(1 for i in range(len(thread)) if isinstance(thread[i], AssistantMessage))
    assert llm_responses == 2

def test_radiant_max_turns_1_produces_exactly_1_response(default_config: ConfigLoader, default_context: Context):
    """With radiant_max_turns=1, the LLM should respond exactly 1 time."""
    default_config.radiant_max_turns = 1
    conv = radiant(default_config)
    thread = message_thread(default_config, "system prompt")

    _simulate_turns(conv, default_context, thread, num_turns=10)

    llm_responses = sum(1 for i in range(len(thread)) if isinstance(thread[i], AssistantMessage))
    assert llm_responses == 1

def test_radiant_max_turns_5_produces_exactly_5_responses(default_config: ConfigLoader, default_context: Context):
    """With radiant_max_turns=5, the LLM should respond exactly 5 times."""
    default_config.radiant_max_turns = 5
    conv = radiant(default_config)
    thread = message_thread(default_config, "system prompt")

    _simulate_turns(conv, default_context, thread, num_turns=10)

    llm_responses = sum(1 for i in range(len(thread)) if isinstance(thread[i], AssistantMessage))
    assert llm_responses == 5

def test_radiant_should_end_matches_max_turns(default_config: ConfigLoader, default_context: Context):
    """should_end should return False before max_turns responses and True once reached."""
    default_config.radiant_max_turns = 3
    conv = radiant(default_config)
    thread = message_thread(default_config, "system prompt")

    for turn in range(3):
        assert not conv.should_end(default_context, thread)
        user_msg = conv.get_user_message(default_context, thread)
        thread.add_message(user_msg)
        thread.add_message(AssistantMessage(default_config))

    assert conv.should_end(default_context, thread)
