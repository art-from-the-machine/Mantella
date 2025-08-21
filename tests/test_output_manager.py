import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.output_manager import ChatManager
from src.config.config_loader import ConfigLoader
from src.config.definitions.llm_definitions import NarrationHandlingEnum
from src.tts.piper import Piper
from src.llm.sentence_queue import SentenceQueue
from src.llm.message_thread import message_thread
from src.characters_manager import Characters
from src.character_manager import Character
from src.llm.sentence_content import SentenceTypeEnum, SentenceContent
from src.llm.sentence import Sentence
from src.conversation.action import Action
from src.llm.function_client import FunctionClient
import time

class MockAIClient:
    """Mock AIClient for testing that simulates different response patterns"""
    def __init__(self, response_pattern=None, error_on_call=False, delay=0.01):
        self.response_pattern = response_pattern if response_pattern is not None else ["Hello there."]
        self.error_on_call = error_on_call
        self.delay = delay
        
    async def streaming_call(self, messages=None, is_multi_npc=False):
        """Simulates streaming call with configurable response patterns"""
        if self.error_on_call:
            raise Exception("Simulated API error")
            
        for chunk in self.response_pattern:
            yield chunk
            await asyncio.sleep(self.delay)  # Small delay to simulate streaming
    
    def get_count_tokens(self, text):
        """Mock token counting"""
        return len(str(text).split())

    def is_too_long(self, messages, token_limit_percent):
        return False

@pytest.fixture
def mock_ai_client():
    """Fixture providing a default MockAIClient instance"""
    return MockAIClient()

@pytest.fixture
def mock_queue() -> SentenceQueue:
    """Provides an empty sentence queue for collecting results"""
    return SentenceQueue()

@pytest.fixture
def mock_messages(default_config: ConfigLoader) -> message_thread:
    """Provides an empty message thread"""
    return message_thread(default_config, None)

@pytest.fixture
def mock_actions() -> list[Action]:
    """Provides a list of mock actions"""
    basic_action = Action(
        identifier="wave", 
        name="Wave",
        keyword="Wave",
        description="Waves at the player",
        prompt_text="If the player asks you to wave, begin your response with 'Wave:'.",
        is_interrupting=False,
        one_on_one=True,
        multi_npc=False,
        radiant=False,
        info_text="Waving action completed",
    )
    interrupt_action = Action(
        identifier="menu", 
        name="Menu",
        keyword="Menu",
        description="Opens the menu",
        prompt_text="If the player asks you to open the menu, begin your response with 'Menu:'.",
        is_interrupting=True,
        one_on_one=True,
        multi_npc=False,
        radiant=False,
        info_text="Menu action completed",
    )
    return [basic_action, interrupt_action]

@pytest.fixture
def output_manager(default_config: ConfigLoader, piper: Piper, mock_ai_client: MockAIClient, default_function_client: FunctionClient, monkeypatch) -> ChatManager:
    """Creates a ChatManager instance with mocked TTS and AI client"""
    # Mock the TTS synthesize method to avoid actual audio generation and file system interaction
    piper.synthesize = MagicMock(return_value="mock_audio_file.wav")
    # Mock get_audio_duration as well
    monkeypatch.setattr('src.utils.get_audio_duration', lambda *args, **kwargs: 1.0)
    
    manager = ChatManager(default_config, piper, mock_ai_client, default_function_client)
    return manager

def get_sentence_list_from_queue(queue: SentenceQueue) -> list[Sentence]:
    """Helper function to extract sentences from the queue"""
    sentences = []
    while True:
        sentence = queue.get_next_sentence()
        if not sentence:
            break
        sentences.append(sentence)
    return sentences


@pytest.mark.asyncio
async def test_process_response_api_error(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_pc_to_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action], monkeypatch):
    """Test handling of a simulated API error during streaming"""
    output_manager._ChatManager__client.error_on_call = True
    monkeypatch.setattr("src.utils.play_error_sound", lambda *a, **kw: None)
    monkeypatch.setattr(time, "sleep", lambda *a, **kw: None) # Skip sleeping between retries
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions)

    output_sentences = get_sentence_list_from_queue(mock_queue)

    # There should be a number of output sentences based on the number of retries, but just take the first as all should have the same message
    error_sentence = output_sentences[0]
    assert "I can't find the right words at the moment" in error_sentence.content.text
    assert error_sentence.content.is_system_generated_sentence is True
    assert error_sentence.content.speaker == example_skyrim_npc_character


@pytest.mark.asyncio
async def test_process_response_actions(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_pc_to_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action]):
    """Test processing of actions embedded in the response"""
    output_manager._ChatManager__client.response_pattern = ["Wave: ", "See ", "you ", "later."]
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions)
    
    output_sentences = get_sentence_list_from_queue(mock_queue)
    assert len(output_sentences) == 2 # Action+Speech, Empty
    
    sentence = output_sentences[0]
    assert sentence.content.text.strip() == "See you later."
    assert sentence.content.actions # Should have actions
    assert "wave" in sentence.content.actions # Check if the specific action identifier is present


@pytest.mark.asyncio
async def test_process_response_interrupt_action(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_pc_to_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action]):
    """Test processing of actions embedded in the response that should interrupt the response"""
    output_manager._ChatManager__client.response_pattern = ["Menu: ", "Here ", "is ", "what ", "I ", "have.", "Ignore ", "this ", "part."]
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions)
    
    output_sentences = get_sentence_list_from_queue(mock_queue)
    assert len(output_sentences) == 2 # Action+Speech, Empty
    
    sentence = output_sentences[0]
    assert sentence.content.text.strip() == "Here is what I have." # Only the first sentence should remain
    assert sentence.content.actions # Should have actions
    assert "menu" in sentence.content.actions # Check if the specific action identifier is present


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_pattern, narration_handling, max_sentences, min_words, expected_texts, expected_types",
    [
        # Basic speech
        (
            ["Hello ", "world."],
            NarrationHandlingEnum.CUT_NARRATIONS,
            None,
            None,
            ["Hello world.", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Narration kept
        (
            ["(The ", "guard ", "sighs.) ", "Okay, ", "move ", "along."],
            NarrationHandlingEnum.USE_NARRATOR,
            None,
            None,
            ["The guard sighs.", "Okay, move along.", ""],
            [SentenceTypeEnum.NARRATION, SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Cut narration
        (
            ["(The ", "guard ", "sighs.) ", "Okay, ", "move ", "along."],
            NarrationHandlingEnum.CUT_NARRATIONS,
            None,
            None,
            ["Okay, move along.", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Speech mixed with narration
        (
            ["Hello ", "there. ", "(He ", "nods.) ", "Need ", "something?"],
            NarrationHandlingEnum.USE_NARRATOR,
            None,
            None,
            ["Hello there.", "He nods.", "Need something?", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.NARRATION, SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Partial words + limit to 1 sentence
        (
            ["Parti", "al ", "sent", "ence.", " Next."],
            NarrationHandlingEnum.CUT_NARRATIONS,
            1,
            1,
            ["Partial sentence.", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Short sentences merging: two one-word sentences, min_words=2 should merge
        (
            ["Hi.", " Yo."] ,
            NarrationHandlingEnum.CUT_NARRATIONS,
            None,
            2,
            ["Hi. Yo.", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Non-western punctuation
        (
            ["你好！", "再见。"],
            NarrationHandlingEnum.CUT_NARRATIONS,
            None,
            None,
            ["你好！再见。", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Character change parser: change speaker and speak
        (
            ["Guard: ", "Watch ", "out!"] ,
            NarrationHandlingEnum.CUT_NARRATIONS,
            None,
            None,
            ["Watch out!", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Action embedded in response
        (
            ["Wave: ", "See ", "you ", "later."] ,
            NarrationHandlingEnum.CUT_NARRATIONS,
            None,
            None,
            ["See you later.", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Limit sentences: only two allowed
        (
            ["One.", " Two.", " Three."] ,
            NarrationHandlingEnum.CUT_NARRATIONS,
            2,
            1,
            ["One.", "Two.", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Clean parser removes 'As a XYZ,' prefix
        (
            ["As a hunter, I hunt.", " Thanks."] ,
            NarrationHandlingEnum.CUT_NARRATIONS,
            None,
            1,
            ["I hunt.", "Thanks.", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
        # Handle LLMs which output whole sentences as tokens
        (
            [
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. ", 
                "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. ", 
                "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. ", 
                "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
            ] ,
            NarrationHandlingEnum.CUT_NARRATIONS,
            None,
            1,
            [
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.", 
                "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.", 
                "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.", 
                "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.", 
                ""
            ],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
        ),
    ],
)
async def test_process_response_param(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
    mock_actions: list[Action],
    response_pattern,
    narration_handling,
    max_sentences,
    min_words,
    expected_texts,
    expected_types,
):
    client = output_manager._ChatManager__client
    config = output_manager._ChatManager__config

    client.response_pattern = response_pattern
    config.narration_handling = narration_handling
    if max_sentences is not None:
        config.max_response_sentences_single = max_sentences
    if min_words is not None:
        config.number_words_tts = min_words

    await output_manager.process_response(
        example_skyrim_npc_character,
        mock_queue,
        mock_messages,
        example_characters_pc_to_npc,
        mock_actions,
    )

    actual = []
    actual_types = []
    while True:
        sent = mock_queue.get_next_sentence()
        if not sent:
            break
        actual.append(sent.content.text.strip())
        actual_types.append(sent.content.sentence_type)

    assert actual == expected_texts
    assert actual_types == expected_types
