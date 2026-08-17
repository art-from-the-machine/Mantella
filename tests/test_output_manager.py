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
from src.actions.action_authorization import ActionAuthorizationContext
from src.llm.function_client import FunctionClient
from src.llm.messages import AssistantMessage
from tests.conftest import MockAIClient
import time

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
        requires_response=False,
        is_interrupting=False,
        one_on_one=True,
        multi_npc=False,
        radiant=False
    )
    interrupt_action = Action(
        identifier="menu", 
        name="Menu",
        keyword="Menu",
        description="Opens the menu",
        prompt_text="If the player asks you to open the menu, begin your response with 'Menu:'.",
        requires_response=False,
        is_interrupting=True,
        one_on_one=True,
        multi_npc=False,
        radiant=False
    )
    return [basic_action, interrupt_action]

@pytest.fixture
def output_manager(default_config: ConfigLoader, piper: Piper, mock_ai_client: MockAIClient, default_function_client: FunctionClient, monkeypatch) -> ChatManager:
    """Creates a ChatManager instance with mocked TTS and AI client"""
    # Mock the TTS synthesize method to avoid actual audio generation and file system interaction
    piper.synthesize = MagicMock(return_value=("mock_audio_file.wav", False))
    # Mock get_audio_duration as well
    monkeypatch.setattr('src.utils.get_audio_duration', lambda *args, **kwargs: 1.0)
    
    manager = ChatManager(default_config, piper, mock_ai_client)
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
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions, tools=None)

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
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions, tools=None)
    
    output_sentences = get_sentence_list_from_queue(mock_queue)
    assert len(output_sentences) == 2 # Action+Speech, Empty
    
    sentence = output_sentences[0]
    assert sentence.content.text.strip() == "See you later."
    assert sentence.content.actions # Should have actions

    action_identifiers = []
    for action in sentence.content.actions:
        action_identifiers.append(action['identifier'])
    assert "wave" in action_identifiers # Check if the specific action identifier is present


def test_short_action_sentence_preserves_actions(output_manager: ChatManager, example_skyrim_npc_character: Character):
    """Skipping TTS for an empty action-only line must not drop its action payload."""
    action = {"identifier": "mantella_npc_inventory"}
    sentence = output_manager.generate_sentence(
        SentenceContent(example_skyrim_npc_character, "", SentenceTypeEnum.SPEECH, False, [action])
    )
    assert sentence.text.strip() == ""
    assert sentence.voice_file == ""
    assert sentence.actions == [action]


@pytest.mark.asyncio
async def test_action_only_legacy_response_reaches_action_queue(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    """An exact ``Inventory:`` response still emits an action-only sentence."""
    inventory = Action(
        identifier="mantella_npc_inventory", name="Inventory", keyword="Inventory",
        description="Opens inventory", prompt_text="", requires_response=False,
        is_interrupting=False, one_on_one=True, multi_npc=False, radiant=False,
    )
    output_manager._ChatManager__client.response_pattern = ["Inventory:"]
    auth = ActionAuthorizationContext.for_player_turn(1, "Can you open your inventory?", ["0"])
    output_manager.set_action_authorization_context(auth)

    await output_manager.process_response(
        example_skyrim_npc_character,
        mock_queue,
        mock_messages,
        example_characters_pc_to_npc,
        [inventory],
        tools=None,
        action_context=auth,
    )

    sentences = get_sentence_list_from_queue(mock_queue)
    assert sentences[0].text.strip() == ""
    assert sentences[0].actions == [{"identifier": "mantella_npc_inventory"}]


@pytest.mark.asyncio
async def test_follow_obligation_does_not_speak_compliance_without_follow_action(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    follow = Action(
        identifier="mantella_npc_follow", name="Follow", keyword="Follow",
        description="Follow the player", prompt_text="", requires_response=False,
        is_interrupting=False, one_on_one=True, multi_npc=True, radiant=False,
    )
    output_manager._ChatManager__client.response_pattern = ["Lead on."]
    auth = ActionAuthorizationContext.for_player_turn(
        21, "Come with me.",
        [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)],
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character, mock_queue, mock_messages,
        example_characters_pc_to_npc, [follow], tools=None, action_context=auth,
    )
    sentences = get_sentence_list_from_queue(mock_queue)
    assert all("Lead on" not in sentence.text for sentence in sentences)


@pytest.mark.asyncio
async def test_follow_action_remains_dispatchable_with_current_turn_authority(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    follow = Action(
        identifier="mantella_npc_follow", name="Follow", keyword="Follow",
        description="Follow the player", prompt_text="", requires_response=False,
        is_interrupting=False, one_on_one=True, multi_npc=True, radiant=False,
    )
    output_manager._ChatManager__client.response_pattern = ["Follow: Lead on."]
    auth = ActionAuthorizationContext.for_player_turn(
        22, "Come with me.",
        [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)],
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character, mock_queue, mock_messages,
        example_characters_pc_to_npc, [follow], tools=None, action_context=auth,
    )
    sentences = get_sentence_list_from_queue(mock_queue)
    action_sentences = [sentence for sentence in sentences if sentence.actions]
    assert action_sentences
    assert action_sentences[0].actions == [{"identifier": "mantella_npc_follow"}]


@pytest.mark.asyncio
async def test_rejected_look_prefix_fences_attached_state_claim(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    """Unauthorized action prose cannot be downgraded into ordinary TTS dialogue."""
    look = Action(
        identifier="mantella_npc_vision", name="Look", keyword="Look",
        description="Inspect view", prompt_text="", requires_response=False,
        is_interrupting=False, one_on_one=True, multi_npc=True, radiant=False,
    )
    output_manager._ChatManager__client.response_pattern = [
        "Look: I can see that I am already wearing the Stormcloak Cuirass."
    ]
    auth = ActionAuthorizationContext.for_player_turn(
        23,
        "Put your clothes back on.",
        [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)],
        owned_equip_items_by_actor={example_skyrim_npc_character.ref_id: ("Roughspun Tunic",)},
        authoritative_inventory_actor_refs={example_skyrim_npc_character.ref_id},
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character, mock_queue, mock_messages,
        example_characters_pc_to_npc, [look], tools=None, action_context=auth,
    )

    sentences = get_sentence_list_from_queue(mock_queue)
    assert not any(sentence.text.strip() for sentence in sentences)
    assert not any(sentence.actions for sentence in sentences)


@pytest.mark.asyncio
async def test_requires_response_action_does_not_speak_unverified_trailing_dialogue(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    """Inventory result verification must happen before any claimed success is spoken."""
    inventory = Action(
        identifier="mantella_npc_inventory", name="Inventory", keyword="Inventory",
        description="Opens inventory", prompt_text="", requires_response=True,
        is_interrupting=False, one_on_one=True, multi_npc=False, radiant=False,
    )
    output_manager._ChatManager__client.response_pattern = ["Inventory: Skooma x6."]
    auth = ActionAuthorizationContext.for_player_turn(1, "Open your inventory.", ["0"])
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character, mock_queue, mock_messages,
        example_characters_pc_to_npc, [inventory], tools=None, action_context=auth,
    )
    sentences = get_sentence_list_from_queue(mock_queue)
    assert sentences[0].text.strip() == ""
    assert sentences[0].actions == [{"identifier": "mantella_npc_inventory"}]


@pytest.mark.asyncio
async def test_successful_action_only_dispatch_is_generated_authorized_and_queued(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    inventory = Action(
        identifier="mantella_npc_inventory", name="Inventory", keyword="Inventory",
        description="Opens inventory", prompt_text="", requires_response=True,
        is_interrupting=True, one_on_one=True, multi_npc=False, radiant=False,
    )
    output_manager._ChatManager__client.response_pattern = ["Inventory:"]
    auth = ActionAuthorizationContext.for_player_turn(
        1, "Open your inventory.", [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)]
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character, mock_queue, mock_messages,
        example_characters_pc_to_npc, [inventory], None, action_context=auth,
    )
    lifecycle = output_manager.active_action_lifecycle
    key = ("mantella_npc_inventory", example_skyrim_npc_character.ref_id)
    assert lifecycle.generated == {key}
    assert lifecycle.authorized == {key}
    assert lifecycle.queued == {key}
    assert lifecycle.missing_generated(example_skyrim_npc_character.ref_id) == frozenset()
    assert output_manager.consume_missing_requested_actions() == frozenset()
    output_manager.mark_actions_protocol_dispatched(
        [{"identifier": "mantella_npc_inventory"}], example_skyrim_npc_character.ref_id
    )
    assert lifecycle.protocol_dispatched == {key}
    output_manager.mark_action_result_received()
    assert lifecycle.game_result_received == {key}


@pytest.mark.asyncio
async def test_missing_inventory_action_gets_exactly_one_bounded_correction(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    inventory = Action(
        identifier="mantella_npc_inventory", name="Inventory", keyword="Inventory",
        description="Opens inventory", prompt_text="", requires_response=True,
        is_interrupting=True, one_on_one=True, multi_npc=False, radiant=False,
    )
    calls = 0
    async def streaming_call(messages=None, is_multi_npc=False, tools=None):
        nonlocal calls
        calls += 1
        yield ("content", "I have opened my inventory." if calls == 1 else "Inventory:")
    output_manager._ChatManager__client.streaming_call = streaming_call
    auth = ActionAuthorizationContext.for_player_turn(
        5, "Open your inventory.", [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)]
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character, mock_queue, mock_messages,
        example_characters_pc_to_npc, [inventory], None, action_context=auth,
    )
    sentences = get_sentence_list_from_queue(mock_queue)
    assert calls == 2
    assert sentences[0].actions == [{"identifier": "mantella_npc_inventory"}]
    assert all("I have opened" not in sentence.text for sentence in sentences)
    assert output_manager.active_action_lifecycle.correction_attempted is True
    assert output_manager.consume_missing_requested_actions() == frozenset()


@pytest.mark.asyncio
async def test_equip_correction_preserves_target_and_dispatches_without_nameerror(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    inventory = Action(
        identifier="mantella_npc_inventory", name="Inventory", keyword="Inventory",
        description="Opens inventory", prompt_text="", requires_response=True,
        is_interrupting=True, one_on_one=True, multi_npc=False, radiant=False,
    )
    equip = Action(
        identifier="mantella_npc_equip", name="Equip", keyword="Equip",
        description="Equips item", prompt_text="", requires_response=True,
        is_interrupting=True, one_on_one=True, multi_npc=False, radiant=False,
    )
    calls = 0

    async def streaming_call(messages=None, is_multi_npc=False, tools=None):
        nonlocal calls
        calls += 1
        yield ("content", "Inventory:" if calls == 1 else "Equip: Golden Saint Shield | I will equip it.")

    output_manager._ChatManager__client.streaming_call = streaming_call
    auth = ActionAuthorizationContext.for_player_turn(
        8,
        "Equip the shield.",
        [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)],
        recent_equip_items=("Golden Saint Shield",),
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character,
        mock_queue,
        mock_messages,
        example_characters_pc_to_npc,
        [inventory, equip],
        None,
        action_context=auth,
    )
    sentences = get_sentence_list_from_queue(mock_queue)
    assert calls == 2
    assert any(sentence.actions == [{"identifier": "mantella_npc_equip", "arguments": {"item": "Golden Saint Shield"}}] for sentence in sentences)
    assert output_manager.active_action_lifecycle.correction_attempted is True


@pytest.mark.asyncio
async def test_failed_correction_retries_once_and_reports_final_missing(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    inventory = Action(
        identifier="mantella_npc_inventory", name="Inventory", keyword="Inventory",
        description="Opens inventory", prompt_text="", requires_response=True,
        is_interrupting=True, one_on_one=True, multi_npc=False, radiant=False,
    )
    calls = 0
    async def streaming_call(messages=None, is_multi_npc=False, tools=None):
        nonlocal calls
        calls += 1
        yield ("content", "I have opened my inventory.")
    output_manager._ChatManager__client.streaming_call = streaming_call
    auth = ActionAuthorizationContext.for_player_turn(
        6, "Open your inventory.", [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)]
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character, mock_queue, mock_messages,
        example_characters_pc_to_npc, [inventory], None, action_context=auth,
    )
    assert calls == 2
    assert output_manager.consume_missing_requested_actions() == frozenset({"mantella_npc_inventory"})


@pytest.mark.asyncio
async def test_new_turn_cancels_action_correction_without_leaking_missing_state(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    inventory = Action(
        identifier="mantella_npc_inventory", name="Inventory", keyword="Inventory",
        description="Opens inventory", prompt_text="", requires_response=True,
        is_interrupting=True, one_on_one=True, multi_npc=False, radiant=False,
    )
    calls = 0
    async def streaming_call(messages=None, is_multi_npc=False, tools=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            yield ("content", "I have opened my inventory.")
        else:
            replacement = ActionAuthorizationContext.for_player_turn(
                11, "Are you sure?", [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)]
            )
            output_manager.set_action_authorization_context(replacement)
            yield ("content", "Inventory:")
    output_manager._ChatManager__client.streaming_call = streaming_call
    auth = ActionAuthorizationContext.for_player_turn(
        10, "Open your inventory.", [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)]
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character, mock_queue, mock_messages,
        example_characters_pc_to_npc, [inventory], None, action_context=auth,
    )
    assert calls == 2
    assert output_manager.consume_missing_requested_actions() == frozenset()


@pytest.mark.asyncio
async def test_rejected_exact_equip_discards_action_bearing_success_dialogue(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    equip = Action(
        identifier="mantella_npc_equip", name="Equip", keyword="Equip",
        description="Equips item", prompt_text="", requires_response=True,
        is_interrupting=True, one_on_one=True, multi_npc=False, radiant=False,
    )
    output_manager._ChatManager__client.response_pattern = [
        "Equip: Roughspun Tunic | I have equipped the Golden Saint Shield."
    ]
    auth = ActionAuthorizationContext.for_player_turn(
        7,
        "Equip the Golden Saint Shield.",
        [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)],
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character, mock_queue, mock_messages,
        example_characters_pc_to_npc, [equip], None, action_context=auth,
    )
    sentences = get_sentence_list_from_queue(mock_queue)
    assert all("equipped" not in sentence.text for sentence in sentences)
    lifecycle = output_manager.active_action_lifecycle
    key = ("mantella_npc_equip", example_skyrim_npc_character.ref_id)
    assert lifecycle.generated == {key}
    # The streamed parser now preserves the generated exact item, so this
    # deliberately wrong item is rejected as a target mismatch.
    assert lifecycle.rejected[key] == "equip_target_not_authorized"
    assert lifecycle.missing_generated(example_skyrim_npc_character.ref_id) == frozenset()


@pytest.mark.asyncio
async def test_rejected_inventory_continuation_discards_inventory_prose(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    """A stale Inventory prefix must not leave its item dump available to TTS."""
    inventory = Action(
        identifier="mantella_npc_inventory", name="Inventory", keyword="Inventory",
        description="Opens inventory", prompt_text="", requires_response=True,
        is_interrupting=True, one_on_one=True, multi_npc=False, radiant=False,
    )
    output_manager._ChatManager__client.response_pattern = [
        "Inventory: Here is what I have on me, Emilia. Some Skooma, Moon Sugar, Sleeping Tree Sap, and a little gold. I also have my armor: Roughspun Tunic."
    ]
    auth = ActionAuthorizationContext.for_player_turn(
        12, "Are you sure?", [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)]
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character, mock_queue, mock_messages,
        example_characters_pc_to_npc, [inventory], None, action_context=auth,
    )
    sentences = get_sentence_list_from_queue(mock_queue)
    assert all("Skooma" not in sentence.text for sentence in sentences)
    assert all("Roughspun Tunic" not in sentence.text for sentence in sentences)
    assert output_manager.active_action_lifecycle.rejected
    assert output_manager.active_action_lifecycle.missing_generated(
        example_skyrim_npc_character.ref_id
    ) == frozenset()


@pytest.mark.asyncio
async def test_omitted_equip_is_not_synthetically_injected_from_plain_dialogue(
    output_manager: ChatManager,
    example_skyrim_npc_character: Character,
    example_characters_pc_to_npc: Characters,
    mock_queue: SentenceQueue,
    mock_messages: message_thread,
):
    equip = Action(
        "mantella_npc_equip", "Equip", "Equip", "", "", True, False,
        True, True, False, "item_name", "npc_items", ["equip", "wear", "put on"],
    )
    output_manager._ChatManager__client.response_pattern = [
        "I ", "only ", "have ", "my ", "tunic."
    ]

    auth = ActionAuthorizationContext.for_player_turn(
        24,
        "Please equip your armor",
        [(example_skyrim_npc_character.name, example_skyrim_npc_character.ref_id)],
        owned_equip_items_by_actor={example_skyrim_npc_character.ref_id: ("Roughspun Tunic",)},
    )
    output_manager.set_action_authorization_context(auth)
    await output_manager.process_response(
        example_skyrim_npc_character,
        mock_queue,
        mock_messages,
        example_characters_pc_to_npc,
        [equip],
        tools=None,
        action_context=auth,
    )

    sentences = get_sentence_list_from_queue(mock_queue)
    actions = [action for sentence in sentences for action in sentence.actions]
    assert actions == []
    assert output_manager.active_action_lifecycle.correction_attempted is True


@pytest.mark.asyncio
async def test_process_response_interrupt_action(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_pc_to_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action]):
    """Test processing of actions embedded in the response that should interrupt the response"""
    output_manager._ChatManager__client.response_pattern = ["Menu: ", "Here ", "is ", "what ", "I ", "have.", "Ignore ", "this ", "part."]
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions, tools=None)
    
    output_sentences = get_sentence_list_from_queue(mock_queue)
    assert len(output_sentences) == 2 # Action-only, Empty

    sentence = output_sentences[0]
    # Interrupting legacy prefixes stop parsing at the prefix.  This test
    # predates the action-only dispatch contract and must not expect its
    # trailing prose to be retained.
    assert sentence.content.text.strip() == ""
    assert sentence.content.actions # Should have actions

    action_identifiers = []
    for action in sentence.content.actions:
        action_identifiers.append(action['identifier'])
    assert "menu" in action_identifiers # Check if the specific action identifier is present


@pytest.mark.asyncio
async def test_process_response_with_tool_calls(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_pc_to_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action], monkeypatch):
    """Test the two-call pattern: first call returns tool_calls, second call returns text"""
    # Mock tools list
    mock_tools = [{"type": "function", "function": {"name": "follow_npc"}}]
    
    # Configure client to return tool calls on first call
    client = output_manager._ChatManager__client
    client.tool_calls = [
        {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "Follow"
            }
        }
    ]
    client.response_pattern = ["I'll ", "follow ", "you."]
    
    # Mock FunctionManager.parse_function_calls
    def mock_parse(tool_calls, characters=None, game=None, **kwargs):
        return [{"identifier": "mantella_npc_follow"}]
    monkeypatch.setattr("src.actions.function_manager.FunctionManager.parse_function_calls", mock_parse)
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions, mock_tools)
    
    output_sentences = get_sentence_list_from_queue(mock_queue)
    
    # Should have sentences: action-only sentence + text response + empty terminator
    assert len(output_sentences) == 3
    
    # First sentence should be action-only (empty text, but has actions)
    action_sentence = output_sentences[0]
    assert action_sentence.content.text == ""
    action_identifiers = []
    for action in action_sentence.content.actions:
        action_identifiers.append(action['identifier'])
    assert "mantella_npc_follow" in action_identifiers
    
    # Second sentence should have the text response
    text_sentence = output_sentences[1]
    assert "follow" in text_sentence.content.text.lower()


@pytest.mark.asyncio
async def test_process_response_with_multiple_tool_calls(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_pc_to_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action], monkeypatch):
    """Test handling of multiple tool calls in a single response"""
    mock_tools = [
        {"type": "function", "function": {"name": "follow_npc"}},
        {"type": "function", "function": {"name": "draw_weapon"}}
    ]
    
    client = output_manager._ChatManager__client
    client.tool_calls = [
        {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "Follow"
            }
        },
        {
            "id": "call_456",
            "type": "function",
            "function": {
                "name": "DrawWeapon"
            }
        }
    ]
    client.response_pattern = ["Okay, ", "let's ", "go."]
    
    def mock_parse(tool_calls, characters=None, game=None, **kwargs):
        return [
            {"identifier": "mantella_npc_follow"},
            {"identifier": "mantella_draw_weapon"}
        ]
    monkeypatch.setattr("src.actions.function_manager.FunctionManager.parse_function_calls", mock_parse)
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions, mock_tools)
    
    output_sentences = get_sentence_list_from_queue(mock_queue)
    
    # Should have sentences: action-only sentence + text response + empty terminator
    assert len(output_sentences) == 3
    
    # First sentence should be action-only with both actions attached
    action_sentence = output_sentences[0]
    action_identifiers = []
    for action in action_sentence.content.actions:
        action_identifiers.append(action['identifier'])
    assert "mantella_npc_follow" in action_identifiers
    assert "mantella_draw_weapon" in action_identifiers


@pytest.mark.asyncio
async def test_process_response_tool_calls_added_to_message_thread(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_pc_to_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action], monkeypatch):
    """Test that tool calls are properly added to the message thread"""
    mock_tools = [{"type": "function", "function": {"name": "attack_npc"}}]
    
    client = output_manager._ChatManager__client
    client.tool_calls = [
        {
            "id": "call_789",
            "type": "function",
            "function": {
                "name": "Attack",
                "arguments": '{"target": "bandit"}'
            }
        }
    ]
    client.response_pattern = ["Never ", "should ", "have ", "come ", "here."]
    
    def mock_parse(tool_calls, characters=None, game=None, **kwargs):
        return [{"identifier": "mantella_attack", "arguments": {"target": "bandit"}}]
    monkeypatch.setattr("src.actions.function_manager.FunctionManager.parse_function_calls", mock_parse)
    
    # Get initial message count
    initial_message_count = len(mock_messages)
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions, mock_tools)
    
    # Message thread should have new messages added (tool call message + final text message)
    assert len(mock_messages) > initial_message_count
    
    # Check that an AssistantMessage with tool_calls was added
    assistant_messages = [msg for msg in mock_messages._message_thread__messages if isinstance(msg, AssistantMessage)]
    
    # Should have at least one assistant message with tool_calls
    tool_call_messages = [msg for msg in assistant_messages if msg.tool_calls is not None]
    assert len(tool_call_messages) >= 1
    
    # Verify the tool call content
    tool_call_msg = tool_call_messages[0]
    assert len(tool_call_msg.tool_calls) == 1
    assert tool_call_msg.tool_calls[0]["function"]["name"] == "Attack"


@pytest.mark.asyncio
async def test_process_response_stores_full_action_dicts(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_pc_to_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action], monkeypatch):
    """Test that full action dictionaries (not just identifiers) are stored in sentences"""
    mock_tools = [{"type": "function", "function": {"name": "Follow"}}]
    
    client = output_manager._ChatManager__client
    client.tool_calls = [
        {
            "id": "call_follow_123",
            "type": "function",
            "function": {
                "name": "Follow",
                "arguments": '{"source": ["Lydia", "Serana"]}'
            }
        }
    ]
    client.response_pattern = ["Of ", "course, ", "we'll ", "follow."]
    
    # Mock parse_function_calls to return full action dicts with validated arguments
    def mock_parse(tool_calls, characters=None, game=None, **kwargs):
        return [{
            "identifier": "mantella_npc_follow",
            "arguments": {"source": ["Lydia", "Serana"]}
        }]
    monkeypatch.setattr("src.actions.function_manager.FunctionManager.parse_function_calls", mock_parse)
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions, mock_tools)
    
    output_sentences = get_sentence_list_from_queue(mock_queue)
    
    # Should have sentences: action-only sentence + text response + empty terminator
    assert len(output_sentences) == 3
    
    # First sentence should be action-only with the full action dict stored
    action_sentence = output_sentences[0]
    assert len(action_sentence.content.actions) == 1
    
    action = action_sentence.content.actions[0]
    assert isinstance(action, dict)
    assert action["identifier"] == "mantella_npc_follow"
    assert "arguments" in action
    assert action["arguments"] == {"source": ["Lydia", "Serana"]}


@pytest.mark.asyncio
async def test_process_response_stores_multiple_full_action_dicts(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_pc_to_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action], monkeypatch):
    """Test that multiple full action dictionaries are correctly stored in sentences"""
    mock_tools = [
        {"type": "function", "function": {"name": "Follow"}},
        {"type": "function", "function": {"name": "DrawWeapon"}}
    ]
    
    client = output_manager._ChatManager__client
    client.tool_calls = [
        {
            "id": "call_follow_456",
            "type": "function",
            "function": {
                "name": "Follow",
                "arguments": '{"source": ["Erik"]}'
            }
        },
        {
            "id": "call_weapon_789",
            "type": "function",
            "function": {
                "name": "DrawWeapon",
                "arguments": '{"weapon_type": "sword"}'
            }
        }
    ]
    client.response_pattern = ["Ready ", "for ", "battle."]
    
    # Mock parse_function_calls to return multiple full action dicts
    def mock_parse(tool_calls, characters=None, game=None, **kwargs):
        return [
            {
                "identifier": "mantella_npc_follow",
                "arguments": {"source": ["Erik"]}
            },
            {
                "identifier": "mantella_draw_weapon",
                "arguments": {"weapon_type": "sword"}
            }
        ]
    monkeypatch.setattr("src.actions.function_manager.FunctionManager.parse_function_calls", mock_parse)
    
    await output_manager.process_response(example_skyrim_npc_character, mock_queue, mock_messages, example_characters_pc_to_npc, mock_actions, mock_tools)
    
    output_sentences = get_sentence_list_from_queue(mock_queue)
    
    # Should have sentences: action-only sentence + text response + empty terminator
    assert len(output_sentences) == 3
    
    # First sentence should be action-only with both full action dicts stored
    action_sentence = output_sentences[0]
    assert len(action_sentence.content.actions) == 2
    
    # Verify first action
    action1 = action_sentence.content.actions[0]
    assert isinstance(action1, dict)
    assert action1["identifier"] == "mantella_npc_follow"
    assert action1["arguments"] == {"source": ["Erik"]}
    
    # Verify second action
    action2 = action_sentence.content.actions[1]
    assert isinstance(action2, dict)
    assert action2["identifier"] == "mantella_draw_weapon"
    assert action2["arguments"] == {"weapon_type": "sword"}


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
        # Cut narrations should not count toward max_sentences budget
        (
            ["(this is a narration) (even more narration) (it does not end) (some extra narration) Fine, I apologize."],
            NarrationHandlingEnum.CUT_NARRATIONS,
            4,
            3,
            ["Fine, I apologize.", ""],
            [SentenceTypeEnum.SPEECH, SentenceTypeEnum.SPEECH],
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
        tools=None,
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


@pytest.mark.asyncio
async def test_process_response_stores_discarded_character_name(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_multi_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action]):
    """When the LLM addresses an unrecognized character, process_response should store
    the discarded name on the output manager so conversation can add corrective feedback."""
    async def wrong_character_call(messages=None, is_multi_npc=False, tools=None):
        for chunk in ["Hulda: Here's your mead!"]:
            yield ("content", chunk)

    output_manager._ChatManager__client.streaming_call = wrong_character_call

    assert output_manager.discarded_character_name is None

    await output_manager.process_response(
        example_skyrim_npc_character,
        mock_queue,
        mock_messages,
        example_characters_multi_npc,
        mock_actions,
        tools=None,
    )

    assert output_manager.discarded_character_name == "Hulda"


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True,
    reason="Bug #9: an unknown speaker label after a streamed newline can leak prose before the parser stops generation",
)
async def test_process_response_stores_discarded_character_on_partial_response(output_manager: ChatManager, example_skyrim_npc_character: Character, example_characters_multi_npc: Characters, mock_queue: SentenceQueue, mock_messages: message_thread, mock_actions: list[Action]):
    """When the LLM produces valid sentences but then addresses an unrecognized character,
    the discarded name should still be stored for corrective feedback on the next turn."""
    async def partial_then_wrong_call(messages=None, is_multi_npc=False, tools=None):
        for chunk in ["Guard: Thank you for your service. ", "\nHulda: Here's your mead!"]:
            yield ("content", chunk)

    output_manager._ChatManager__client.streaming_call = partial_then_wrong_call

    await output_manager.process_response(
        example_skyrim_npc_character,
        mock_queue,
        mock_messages,
        example_characters_multi_npc,
        mock_actions,
        tools=None,
    )

    output_sentences = get_sentence_list_from_queue(mock_queue)
    real_sentences = [s for s in output_sentences if s.content.text.strip()]

    assert len(real_sentences) == 1
    assert "Thank you for your service" in real_sentences[0].content.text
    assert output_manager.discarded_character_name == "Hulda"
