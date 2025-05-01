from src.llm.image_client import ImageClient
import pytest
import base64
from pathlib import Path
from src.config.config_loader import ConfigLoader

PLACEHOLDER_IMAGE_PATH = Path("img/mantella_logo_github.png")

def load_placeholder_image_base64() -> str | None:
    """Loads the placeholder image and returns it as a base64 encoded string"""
    try:
        if not PLACEHOLDER_IMAGE_PATH.is_file():
             print(f"Warning: Placeholder image not found at {PLACEHOLDER_IMAGE_PATH}")
             return None
        with open(PLACEHOLDER_IMAGE_PATH, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception as e:
        print(f"Warning: Failed to load placeholder image: {e}")
        return None

class FakeImageManager:
    """A simple replacement for ImageManager to provide a fixed image"""
    def __init__(self, base64_image_data: str | None):
        self._image_data = base64_image_data

    def get_image(self) -> str | None:
        """Returns the predefined base64 image string"""
        return self._image_data
    

@pytest.fixture
def image_client_default_llm(default_config: ConfigLoader):
    """Provides an ImageClient instance using the main LLM config for vision"""
    default_config.custom_vision_model = False
    default_config.vision_enabled = True
    return ImageClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")

@pytest.fixture
def image_client_custom_llm(default_config: ConfigLoader):
    """Provides an ImageClient instance using a separate vision LLM config"""
    default_config.custom_vision_model = True
    default_config.vision_enabled = True
    return ImageClient(default_config, "GPT_SECRET_KEY.txt", "IMAGE_SECRET_KEY.txt")

@pytest.fixture
def sample_openai_messages() -> list:
    """Provides a sample list of messages for testing add_image_to_messages"""
    return [
        {"role": "system", "content": "You are an expert at transcribing images."},
        {"role": "user", "content": "What is this image?"},
    ]

@pytest.fixture
def sample_openai_messages_no_user() -> list:
    """Provides a sample list of messages ending with non-user for testing"""
    return [
        {"role": "system", "content": "You are an expert at transcribing images."},
        {"role": "assistant", "content": "Hello."},
    ]


def test_add_image_integrated_mode_structure(image_client_default_llm: ImageClient, sample_openai_messages: list):
    """
    Tests the message structure modification in integrated mode when an image is present
    Replaces ImageManager to provide a controlled image input
    """
    placeholder_b64 = load_placeholder_image_base64()

    # Replace the real ImageManager with a fake one
    image_client_default_llm._ImageClient__image_manager = FakeImageManager(placeholder_b64)

    original_user_content = sample_openai_messages[-1]['content']
    result_messages = image_client_default_llm.add_image_to_messages(list(sample_openai_messages), "vision hint text")

    # Assertions for integrated mode structure:
    assert isinstance(result_messages, list)
    assert len(result_messages) == len(sample_openai_messages) # Length should not change
    last_message = result_messages[-1]
    assert last_message['role'] == 'user'
    assert isinstance(last_message['content'], list)
    assert len(last_message['content']) == 2 # Should have text and image parts
    assert last_message['content'][0] == {"type": "text", "text": original_user_content}
    assert last_message['content'][1]['type'] == "image_url"
    assert last_message['content'][1]['image_url']['url'].startswith("data:image/jpeg;base64,")
    assert last_message['content'][1]['image_url']['url'].endswith(placeholder_b64)
    assert last_message['content'][1]['image_url']['detail'] == image_client_default_llm._ImageClient__detail


def test_add_image_integrated_mode_no_image(image_client_default_llm: ImageClient, sample_openai_messages: list):
    """Tests that messages are unchanged in integrated mode if ImageManager returns None"""
    # Replace ImageManager with one that returns None
    image_client_default_llm._ImageClient__image_manager = FakeImageManager(None)
    original_messages_copy = [msg.copy() for msg in sample_openai_messages] # Deep copy for comparison

    result_messages = image_client_default_llm.add_image_to_messages(list(sample_openai_messages), "hint")

    assert result_messages == original_messages_copy # Messages should be identical


def test_add_image_custom_mode_structure(image_client_custom_llm: ImageClient, sample_openai_messages: list):
    """
    Tests the message structure modification in custom mode, involving a real API call for transcription
    Replaces ImageManager, requires working vision LLM endpoint
    """
    placeholder_b64 = load_placeholder_image_base64()

    # Replace the real ImageManager with a fake one
    image_client_custom_llm._ImageClient__image_manager = FakeImageManager(placeholder_b64)

    original_user_content = sample_openai_messages[-1]['content']
    result_messages = image_client_custom_llm.add_image_to_messages(list(sample_openai_messages), "The image is a logo.")

    # Assertions for integrated mode structure:
    assert isinstance(result_messages, list)
    assert len(result_messages) == len(sample_openai_messages) # Length should not change
    last_message = result_messages[-1]
    assert last_message['role'] == 'user'
    assert isinstance(last_message['content'], list)
    assert len(last_message['content']) == 1 # Should have text and image parts
    assert last_message['content'][0]['type'] == "text"

    modified_content = last_message['content'][0]['text']
    # Check that the original content is present and preceded by the transcription
    assert modified_content.endswith(f"\n{original_user_content}")
    # Check that the transcription part looks like *...*
    assert modified_content.startswith("*")
    # Find the end of the transcription marker
    end_transcription_marker = modified_content.find("*\n")
    assert end_transcription_marker != -1
    # Extract transcription - basic check for non-emptiness
    transcription = modified_content[1:end_transcription_marker]
    assert len(transcription) > 0 # Transcription should not be empty


def test_add_image_custom_mode_no_image(image_client_custom_llm: ImageClient, sample_openai_messages: list):
    """Tests that messages are unchanged in custom mode if ImageManager returns None"""
    # Replace ImageManager with one that returns None
    image_client_custom_llm._ImageClient__image_manager = FakeImageManager(None)
    original_messages_copy = [msg.copy() for msg in sample_openai_messages] # Deep copy

    result_messages = image_client_custom_llm.add_image_to_messages(list(sample_openai_messages), "hint")

    assert result_messages == original_messages_copy # Messages should be identical


def test_add_image_appends_new_message_if_needed(image_client_default_llm: ImageClient, sample_openai_messages_no_user: list):
    """Tests adding an image creates a new user message if the last message isn't 'user'"""
    placeholder_b64 = load_placeholder_image_base64()

    image_client_default_llm._ImageClient__image_manager = FakeImageManager(placeholder_b64)
    original_length = len(sample_openai_messages_no_user)
    vision_hint = 'hint'

    result_messages = image_client_default_llm.add_image_to_messages(list(sample_openai_messages_no_user), vision_hint)

    assert len(result_messages) == original_length + 1
    last_message = result_messages[-1]
    assert last_message['role'] == 'user'
    assert isinstance(last_message['content'], list)
    assert len(last_message['content']) == 2
    # The text part should ONLY contain the hint when a new message is created this way
    assert last_message['content'][0] == {"type": "text", "text": vision_hint}
    assert last_message['content'][1]['type'] == "image_url"
    assert last_message['content'][1]['image_url']['url'].endswith(placeholder_b64)


def test_add_image_appends_new_message_if_needed_custom(image_client_custom_llm: ImageClient, sample_openai_messages_no_user: list):
    """Tests adding an image creates a new user message if the last message isn't 'user' (custom mode)"""
    placeholder_b64 = load_placeholder_image_base64()

    image_client_custom_llm._ImageClient__image_manager = FakeImageManager(placeholder_b64)
    original_length = len(sample_openai_messages_no_user)

    result_messages = image_client_custom_llm.add_image_to_messages(list(sample_openai_messages_no_user), "hint")

    assert len(result_messages) == original_length + 1
    last_message = result_messages[-1]
    assert last_message['role'] == 'user'
    assert isinstance(last_message['content'], list)
    assert len(last_message['content']) == 1
    assert last_message['content'][0]['type'] == "text"
    # Check the content format *transcription*
    assert last_message['content'][0]['text'].startswith("*")
    assert last_message['content'][0]['text'].endswith("*")
    assert len(last_message['content'][0]['text']) > 2 # Should contain more than just "**"