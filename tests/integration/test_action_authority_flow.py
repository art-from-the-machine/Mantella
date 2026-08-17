"""Production-path Bug #8 regression tests.

These intentionally drive Conversation rather than calling the authorization
factory directly.  The event-result continuation is included because that is
where the live transfer referent enters the real conversation state.
"""

import asyncio
import threading
import time

import pytest
from unittest.mock import MagicMock

from src.actions.action_authorization import ActionAuthorizationContext
from src.conversation.conversation import Conversation
from src.games.equipment import Equipment, EquipmentItem
from src.llm.messages import UserMessage


@pytest.fixture
def piper():
    """Keep this headless integration module process-free.

    The shared fixture starts a real Piper process when the executable happens
    to be available, but does not own/close that process. Repeating these
    production-flow cases then exhausts process resources and makes a later
    fixture setup appear to hang. TTS is an external boundary here, so a
    recording stub is the correct isolated dependency.
    """
    tts = MagicMock()
    tts.synthesize.return_value = ("unused.wav", False)
    return tts


@pytest.fixture
def llm_client():
    """Avoid real secret-key lookup in this deterministic integration module."""
    client = MagicMock()
    client.is_too_long.return_value = False
    client.get_count_tokens.side_effect = lambda text: len(str(text).split())
    return client


class _ScriptedStreamingClient:
    """External LLM boundary only; all Mantella parsing remains real."""

    def __init__(self, responses: list[str | list[str]]) -> None:
        self._responses = iter(responses)
        self.calls: list[dict] = []

    async def streaming_call(self, **kwargs):
        self.calls.append(kwargs)
        response = next(self._responses)
        chunks = response if isinstance(response, list) else [response]
        for chunk in chunks:
            yield "content", chunk

    def get_count_tokens(self, text: str) -> int:
        return len(text.split())


class _BlockingCorrectionClient:
    """Hold a real corrective stream while the production context is replaced."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    async def streaming_call(self, **kwargs):
        self.calls += 1
        self.started.set()
        released = await asyncio.to_thread(self.release.wait, 2.0)
        if not released:
            raise TimeoutError("blocked correction was not released")
        yield "content", self.response

    def get_count_tokens(self, text: str) -> int:
        return len(text.split())


def _run_conversation_generation_synchronously(conversation: Conversation, manager, monkeypatch) -> None:
    """Replace only the background-thread boundary with deterministic execution."""
    def start(allow_tool_use: bool = True, allow_explicit_actions: bool = False) -> None:
        context = conversation._Conversation__action_authorization_context
        if not allow_explicit_actions:
            context = context.for_continuation()
        manager.set_action_authorization_context(context)
        npc = conversation.context.npcs_in_conversation.get_non_player_characters()[0]
        asyncio.run(manager.process_response(
            npc,
            conversation._Conversation__sentences,
            conversation._Conversation__messages,
            conversation.context.npcs_in_conversation,
            conversation.context.config.actions,
            None,
            action_context=context,
        ))

    monkeypatch.setattr(conversation, "_Conversation__start_generating_npc_sentences", start)


def _prime_result_continuation(conversation: Conversation, events: list[str], monkeypatch) -> None:
    """Deliver an action-result event exactly as Conversation consumes it."""
    # Avoid starting a background LLM thread; all state transitions before that
    # boundary remain production code.
    monkeypatch.setattr(
        conversation,
        "_Conversation__start_generating_npc_sentences",
        lambda *args, **kwargs: None,
    )
    conversation.context.update_context(
        conversation.context.location,
        12,
        events,
        None,
        None,
        {},
        None,
    )
    # The initial participant refresh is complete before a real player turn;
    # leave that deferred-refresh flag in the settled state used by gameplay.
    conversation.context.have_actors_changed = False
    conversation._Conversation__awaiting_action_result = True
    assert conversation.resume_after_interrupting_action() is True


@pytest.mark.parametrize(
    "player_text,expected",
    [
        ("Can you equip the shield?", "Golden Saint Shield"),
        ("Equip the shield.", "Golden Saint Shield"),
        ("Please equip it.", "Golden Saint Shield"),
    ],
)
def test_real_conversation_turn_builds_shield_authority_after_result_consumption(
    default_conversation: Conversation,
    monkeypatch,
    player_text: str,
    expected: str,
):
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    _prime_result_continuation(
        default_conversation,
        [
            f"{npc.name} picked up/took Golden Saint Shield from Dragonborn",
        ],
        monkeypatch,
    )
    # Prove the first half of the live trace: persistence is present after
    # transient event consumption, before the next player turn is built.
    assert default_conversation.context.get_recent_equip_items(npc.ref_id) == (
        "Golden Saint Shield",
    )

    # This is the real player-turn entry point.  It creates the immutable
    # authorization snapshot and consumes/clears transient events.
    default_conversation.process_player_input(player_text)
    context = default_conversation._Conversation__action_authorization_context

    assert context.turn_id == 1
    assert context.equip_target == expected
    assert context.authorize(
        "mantella_npc_equip", npc.ref_id, {"item": expected}
    ) == (True, "authorized")
    assert default_conversation.context.get_recent_equip_items(npc.ref_id) == (expected,)


def test_real_conversation_turn_builds_cuirass_authority_after_result_consumption(
    default_conversation: Conversation,
    monkeypatch,
):
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    _prime_result_continuation(
        default_conversation,
        [f"{npc.name} picked up/took Stormcloak Cuirass from Dragonborn"],
        monkeypatch,
    )
    assert default_conversation.context.get_recent_equip_items(npc.ref_id) == (
        "Stormcloak Cuirass",
    )
    default_conversation.process_player_input("Can you equip the armor?")
    context = default_conversation._Conversation__action_authorization_context
    assert context.equip_target == "Stormcloak Cuirass"
    assert context.authorize(
        "mantella_npc_equip", npc.ref_id, {"item": "Stormcloak Cuirass"}
    )[0]


@pytest.mark.parametrize(
    "player_text,transfer,item",
    [
        ("Equip the Golden Saint Shield.", "Golden Saint Shield", "Golden Saint Shield"),
        ("Equip the armor.", "Stormcloak Cuirass", "Stormcloak Cuirass"),
    ],
)
def test_streamed_single_npc_equip_preserves_item_payload(
    default_conversation: Conversation,
    default_chat_manager,
    monkeypatch,
    player_text: str,
    transfer: str,
    item: str,
):
    """A normal streamed ``Equip: item | dialogue`` reaches the action gate."""
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    scripted_llm = _ScriptedStreamingClient([f"Equip: {item} | It shall be my shield."])
    recording_tts = MagicMock()
    recording_tts.synthesize.return_value = ("unused.wav", False)
    default_chat_manager._ChatManager__client = scripted_llm
    default_chat_manager._ChatManager__tts = recording_tts
    monkeypatch.setattr("src.output_manager.utils.get_audio_duration", lambda _path: 0.0)
    default_conversation.context.have_actors_changed = False
    _prime_result_continuation(
        default_conversation,
        [f"{npc.name} picked up/took {transfer} from Dragonborn"],
        monkeypatch,
    )
    _run_conversation_generation_synchronously(default_conversation, default_chat_manager, monkeypatch)

    default_conversation.process_player_input(player_text)
    queue = default_conversation._Conversation__sentences
    queue.is_more_to_come = False
    sentences = []
    while sentence := queue.get_next_sentence():
        sentences.append(sentence)
    actions = [action for sentence in sentences for action in sentence.actions]
    assert actions == [{
        "identifier": "mantella_npc_equip",
        "arguments": {"item": item},
    }]
    assert not recording_tts.synthesize.call_args_list


def test_current_turn_event_is_persisted_before_authorization_snapshot(
    default_conversation: Conversation,
    monkeypatch,
):
    """The regression case: events arrive with the player-input request."""
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    default_conversation.context.have_actors_changed = False
    # This test asserts turn-state construction only.  Do not start the
    # production background LLM thread, which would outlive the fixture when
    # no scripted client is installed.
    monkeypatch.setattr(
        default_conversation,
        "_Conversation__start_generating_npc_sentences",
        lambda *args, **kwargs: None,
    )
    # This is the transient buffer consumed by Conversation.update_game_events;
    # no persistent referent exists when process_player_input starts.
    default_conversation.context._Context__ingame_events.append(
        f"{npc.name} picked up/took Golden Saint Shield from Dragonborn"
    )
    assert default_conversation.context.get_recent_equip_items(npc.ref_id) == ()

    default_conversation.process_player_input("Can you equip the shield?")
    authorization = default_conversation._Conversation__action_authorization_context
    assert authorization.equip_target == "Golden Saint Shield"
    assert authorization.authorize(
        "mantella_npc_equip", npc.ref_id, {"item": "Golden Saint Shield"}
    )[0]


def test_real_conversation_exact_and_generic_targets_do_not_depend_on_transfer(
    default_conversation: Conversation,
    monkeypatch,
):
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    # This test inspects immutable authorization snapshots; generation is not
    # part of its contract and must remain inside the test boundary.
    monkeypatch.setattr(
        default_conversation,
        "_Conversation__start_generating_npc_sentences",
        lambda *args, **kwargs: None,
    )
    default_conversation.process_player_input("Equip the Golden Saint Shield.")
    exact = default_conversation._Conversation__action_authorization_context
    assert exact.equip_target.casefold() == "golden saint shield"
    assert exact.authorize(
        "mantella_npc_equip", npc.ref_id, {"item": "Golden Saint Shield"}
    )[0]

    # Build a fresh conversation turn through the same entry point.
    default_conversation.process_player_input("Equip your best armor.")
    generic = default_conversation._Conversation__action_authorization_context
    assert generic.equip_target == "best armor"
    assert generic.authorize(
        "mantella_npc_equip", npc.ref_id, {"item": "best armor"}
    )[0]


def test_real_conversation_ambiguous_transfers_fail_closed(
    default_conversation: Conversation,
    monkeypatch,
):
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    _prime_result_continuation(
        default_conversation,
        [
            f"{npc.name} picked up/took Golden Saint Shield from Dragonborn",
            f"{npc.name} picked up/took Steel Shield from Dragonborn",
        ],
        monkeypatch,
    )
    default_conversation.process_player_input("Can you equip the shield?")
    context = default_conversation._Conversation__action_authorization_context
    assert context.equip_target == "recent transferred shield"
    assert context.authorize(
        "mantella_npc_equip", npc.ref_id, {"item": "Golden Saint Shield"}
    ) == (False, "equip_target_missing")


def test_failed_equip_attempt_does_not_clear_real_transfer_referent(
    default_conversation: Conversation,
    monkeypatch,
):
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    _prime_result_continuation(
        default_conversation,
        [f"{npc.name} picked up/took Golden Saint Shield from Dragonborn"],
        monkeypatch,
    )
    default_conversation.process_player_input("Equip the shield.")
    assert default_conversation.context.get_recent_equip_items(npc.ref_id)
    default_conversation.process_player_input("Can you equip the shield?")
    assert default_conversation._Conversation__action_authorization_context.equip_target == "Golden Saint Shield"


def test_rejected_inventory_action_result_continuation_never_reaches_tts(
    default_conversation: Conversation,
    default_chat_manager,
    monkeypatch,
):
    """Reproduce the live stale Inventory continuation through Conversation."""
    scripted_llm = _ScriptedStreamingClient([
        "Inventory:",
        "Inventory: Here is what I have on me, Emilia. Some Skooma, Moon Sugar, Sleeping Tree Sap, and a little gold. I also have my armor: Roughspun Tunic.",
    ])
    recording_tts = MagicMock()
    recording_tts.synthesize.return_value = ("unused.wav", False)
    default_chat_manager._ChatManager__client = scripted_llm
    default_chat_manager._ChatManager__tts = recording_tts
    # The TTS boundary is intentionally null/recording; audio duration is not
    # part of action authorization or continuation behavior.
    monkeypatch.setattr("src.output_manager.utils.get_audio_duration", lambda _path: 0.0)
    default_conversation.context.have_actors_changed = False
    _run_conversation_generation_synchronously(default_conversation, default_chat_manager, monkeypatch)

    default_conversation.process_player_input("Open your inventory.")
    reply_type, sentence = default_conversation.continue_conversation()
    assert sentence is not None
    assert sentence.actions == [{"identifier": "mantella_npc_inventory"}]

    default_conversation.update_context(
        default_conversation.context.location,
        12,
        [
            "Authoritative Skyrim inventory for Guard at action time: Skooma x6, Moon Sugar x3, Sleeping Tree Sap x2, gold x38.",
            "Guard's inventory opened.",
        ],
        None,
        None,
        {},
        None,
    )
    assert default_conversation.resume_after_interrupting_action() is True

    # The continuation action is rejected by its immutable continuation
    # context and its attached prose must not make either queue or TTS.
    queued = default_conversation._Conversation__sentences
    queued.is_more_to_come = False
    leaked = []
    while sentence := queued.get_next_sentence():
        leaked.append(sentence)
    spoken = [call.args[1] for call in recording_tts.synthesize.call_args_list]
    # The queue always receives one blank completion sentinel; only nonblank
    # content is relevant to the rejected-action speech invariant.
    leaked_text = [sentence.text for sentence in leaked if sentence.text.strip()]
    assert not leaked_text and not any(
        "Skooma" in text or "Moon Sugar" in text for text in spoken
    ), {"queued": leaked_text, "tts": spoken}
    assert reply_type == "mantella_npc_action"


def test_rejected_inventory_action_split_across_stream_chunks_never_reaches_tts(
    default_conversation: Conversation,
    default_chat_manager,
    monkeypatch,
):
    """The fence applies after the action prefix even when prose is streamed in chunks."""
    scripted_llm = _ScriptedStreamingClient([
        "Inventory:",
        [
            "Inventory: Here is what I have on me.",
            " Some Skooma and Moon Sugar.",
            " I also have my armor: Roughspun Tunic.",
        ],
    ])
    recording_tts = MagicMock()
    recording_tts.synthesize.return_value = ("unused.wav", False)
    default_chat_manager._ChatManager__client = scripted_llm
    default_chat_manager._ChatManager__tts = recording_tts
    monkeypatch.setattr("src.output_manager.utils.get_audio_duration", lambda _path: 0.0)
    default_conversation.context.have_actors_changed = False
    _run_conversation_generation_synchronously(default_conversation, default_chat_manager, monkeypatch)

    default_conversation.process_player_input("Open your inventory.")
    reply_type, sentence = default_conversation.continue_conversation()
    assert sentence is not None and sentence.actions == [{"identifier": "mantella_npc_inventory"}]
    default_conversation.update_context(
        default_conversation.context.location,
        12,
        ["Guard's inventory opened."],
        None,
        None,
        {},
        None,
    )
    assert default_conversation.resume_after_interrupting_action() is True
    spoken = [call.args[1] for call in recording_tts.synthesize.call_args_list]
    assert not any("Skooma" in text or "Moon Sugar" in text or "Roughspun" in text for text in spoken)
    assert reply_type == "mantella_npc_action"


def test_live_inventory_removal_then_put_clothes_back_on_uses_remaining_owned_tunic(
    default_conversation: Conversation,
    default_chat_manager,
    monkeypatch,
):
    """Literal live state ordering: remove worn gear, then equip owned clothing."""
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    npc.equipment = Equipment({
        "body": EquipmentItem("Stormcloak Cuirass"),
        "feet": EquipmentItem("Iron Plate Boots"),
        "righthand": EquipmentItem("Ancient Nord Sword"),
    })
    default_conversation.context.update_context(
        default_conversation.context.location,
        12,
        [
            f"Authoritative Skyrim inventory for {npc.name} at action time: Ancient Nord Sword, Stormcloak Cuirass, Golden Saint Shield, Roughspun Tunic, Iron Plate Boots.",
            f"Prisoner picked up/took Ancient Nord Sword from {npc.name}",
            f"Prisoner picked up/took Golden Saint Shield from {npc.name}",
            f"Prisoner picked up/took Stormcloak Cuirass from {npc.name}",
        ],
        None,
        None,
        {},
        None,
    )
    state = default_conversation.context.get_authoritative_current_state_event()
    assert "Stormcloak Cuirass" not in state
    assert "Ancient Nord Sword" not in state
    assert "Iron Plate Boots" in state

    scripted_llm = _ScriptedStreamingClient([
        "Equip: Roughspun Tunic | I will put my clothes back on."
    ])
    recording_tts = MagicMock()
    recording_tts.synthesize.return_value = ("unused.wav", False)
    default_chat_manager._ChatManager__client = scripted_llm
    default_chat_manager._ChatManager__tts = recording_tts
    monkeypatch.setattr("src.output_manager.utils.get_audio_duration", lambda _path: 0.0)
    default_conversation.context.have_actors_changed = False
    _run_conversation_generation_synchronously(default_conversation, default_chat_manager, monkeypatch)

    default_conversation.process_player_input("Put your clothes back on")
    authorization = default_conversation._Conversation__action_authorization_context
    assert authorization.equip_target == "Roughspun Tunic"
    queue = default_conversation._Conversation__sentences
    queue.is_more_to_come = False
    sentences = []
    while sentence := queue.get_next_sentence():
        sentences.append(sentence)
    actions = [action for sentence in sentences for action in sentence.actions]
    assert actions == [{
        "identifier": "mantella_npc_equip",
        "arguments": {"item": "Roughspun Tunic"},
    }]
    assert not any(
        "Stormcloak Cuirass" in call.args[1] or "Ancient Nord Sword" in call.args[1]
        for call in recording_tts.synthesize.call_args_list
    )


def test_unauthorized_look_with_dependent_live_dialogue_never_reaches_tts(
    default_conversation: Conversation,
    default_chat_manager,
    monkeypatch,
):
    scripted_llm = _ScriptedStreamingClient([
        ["Look:", " I am already wearing my Stormcloak Cuirass and Iron Plate Boots."],
        "I cannot do that.",
    ])
    recording_tts = MagicMock()
    recording_tts.synthesize.return_value = ("unused.wav", False)
    default_chat_manager._ChatManager__client = scripted_llm
    default_chat_manager._ChatManager__tts = recording_tts
    monkeypatch.setattr("src.output_manager.utils.get_audio_duration", lambda _path: 0.0)
    default_conversation.context.have_actors_changed = False
    _run_conversation_generation_synchronously(default_conversation, default_chat_manager, monkeypatch)

    default_conversation.process_player_input("Put your clothes back on")
    queue = default_conversation._Conversation__sentences
    queue.is_more_to_come = False
    leaked = []
    while sentence := queue.get_next_sentence():
        leaked.append(sentence)
    assert not any("Stormcloak Cuirass" in sentence.text for sentence in leaked)
    assert not any(
        "Stormcloak Cuirass" in call.args[1]
        for call in recording_tts.synthesize.call_args_list
    )


@pytest.mark.parametrize("iteration", range(50))
def test_real_missing_equip_prefix_starts_corrective_llm_and_queues_exact_action(
    default_conversation: Conversation,
    default_chat_manager,
    monkeypatch,
    iteration: int,
):
    """Exact live transcript: ordinary prose, then one corrective Equip call."""
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    scripted_llm = _ScriptedStreamingClient([
        (
            "I do not have the Golden Saint Shield equipped yet. "
            "I am wearing my usual roughspun tunic and gauntlets. "
            "To equip the shield, I would need to access my inventory and select it. "
            "Would you like me to do that now?"
        ),
        "Equip: Golden Saint Shield | I will equip it now.",
    ])
    recording_tts = MagicMock()
    recording_tts.synthesize.return_value = ("unused.wav", False)
    default_chat_manager._ChatManager__client = scripted_llm
    default_chat_manager._ChatManager__tts = recording_tts
    monkeypatch.setattr("src.output_manager.utils.get_audio_duration", lambda _path: 0.0)
    default_conversation.context.have_actors_changed = False
    # The literal live completion crossed the configured sentence cap. That
    # local fence previously retained ClientBase's streaming lock.
    default_conversation.context.config.max_response_sentences_single = 3
    _run_conversation_generation_synchronously(default_conversation, default_chat_manager, monkeypatch)

    _prime_result_continuation(
        default_conversation,
        [f"{npc.name} picked up/took Golden Saint Shield from Dragonborn"],
        monkeypatch,
    )
    _run_conversation_generation_synchronously(default_conversation, default_chat_manager, monkeypatch)

    started = time.monotonic()
    default_conversation.process_player_input("Can you equip the shield?")
    assert time.monotonic() - started < 2.0, "missing-action correction stalled"

    # The main response and its corrective retry must be separate real client
    # calls. The ordinary pre-result prose is held rather than spoken.
    assert len(scripted_llm.calls) == 2
    queued = default_conversation._Conversation__sentences
    queued.is_more_to_come = False
    sentences = []
    while sentence := queued.get_next_sentence():
        sentences.append(sentence)
    actions = [action for sentence in sentences for action in sentence.actions]
    lifecycle = default_chat_manager.active_action_lifecycle
    assert actions == [{
        "identifier": "mantella_npc_equip",
        "arguments": {"item": "Golden Saint Shield"},
    }], {
        "calls": len(scripted_llm.calls),
        "generated": lifecycle.generated if lifecycle else None,
        "rejected": lifecycle.rejected if lifecycle else None,
        "correction_attempted": lifecycle.correction_attempted if lifecycle else None,
        "stop_generation": default_chat_manager._ChatManager__stop_generation.is_set(),
    }
    spoken = [call.args[1] for call in recording_tts.synthesize.call_args_list]
    assert not spoken


@pytest.mark.parametrize("iteration", range(25))
def test_pending_correction_is_cancelled_by_real_new_turn_context(
    default_conversation: Conversation,
    default_chat_manager,
    iteration: int,
    monkeypatch,
):
    """A replacement player-turn snapshot rejects an in-flight old correction."""
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    monkeypatch.setattr("src.output_manager.utils.get_audio_duration", lambda _path: 0.0)
    old_context = ActionAuthorizationContext.for_player_turn(
        1,
        "Can you equip the shield?",
        [(npc.name, npc.ref_id)],
        recent_equip_items_by_actor={npc.ref_id: ("Golden Saint Shield",)},
    )
    default_chat_manager.set_action_authorization_context(old_context)
    lifecycle = default_chat_manager.active_action_lifecycle
    assert lifecycle is not None
    client = _BlockingCorrectionClient(
        "Equip: Golden Saint Shield | I will equip it now."
    )
    queue = default_conversation._Conversation__sentences
    queue.is_more_to_come = True
    messages = default_conversation._Conversation__messages
    actions = default_conversation.context.config.actions

    async def exercise() -> None:
        correction = asyncio.create_task(
            default_chat_manager._attempt_action_correction(
                client,
                npc,
                default_conversation.context.npcs_in_conversation,
                messages,
                actions,
                lifecycle,
                queue,
                False,
            )
        )
        assert await asyncio.to_thread(client.started.wait, 1.0)

        # This is the production context replacement used for a new player
        # turn; no test-only stale flag is toggled on the old snapshot.
        new_context = ActionAuthorizationContext.for_player_turn(
            2, "Are you ready?", [(npc.name, npc.ref_id)]
        )
        default_chat_manager.set_action_authorization_context(new_context)
        client.release.set()
        await asyncio.wait_for(correction, 1.0)

        # The same manager/client path must be usable immediately by the new
        # turn; this catches a generation lock retained by the stale stream.
        next_client = _ScriptedStreamingClient(["I am ready."])
        default_chat_manager._ChatManager__client = next_client
        await asyncio.wait_for(
            default_chat_manager.process_response(
                npc,
                queue,
                messages,
                default_conversation.context.npcs_in_conversation,
                actions,
                None,
                action_context=new_context,
            ),
            1.0,
        )
        assert len(next_client.calls) == 1

    asyncio.run(exercise())
    queue.is_more_to_come = False
    queued = []
    while sentence := queue.get_next_sentence():
        queued.append(sentence)
    assert client.calls == 1
    assert lifecycle.correction_attempted is True
    assert not [action for sentence in queued for action in sentence.actions]
    assert default_chat_manager.active_action_lifecycle.context is not old_context
    assert default_chat_manager.active_action_lifecycle.context.turn_id == 2


@pytest.mark.parametrize("iteration", range(25))
def test_correction_without_action_terminates_once_and_next_turn_works(
    default_conversation: Conversation,
    default_chat_manager,
    monkeypatch,
    caplog,
    iteration: int,
):
    """A second action-less completion ends the retry cleanly without looping."""
    npc = default_conversation.context.npcs_in_conversation.get_non_player_characters()[0]
    scripted_llm = _ScriptedStreamingClient([
        "I would need to equip it first.",
        "I understand. I will take care of it.",
        "I am ready.",
    ])
    recording_tts = MagicMock()
    recording_tts.synthesize.return_value = ("unused.wav", False)
    default_chat_manager._ChatManager__client = scripted_llm
    default_chat_manager._ChatManager__tts = recording_tts
    monkeypatch.setattr("src.output_manager.utils.get_audio_duration", lambda _path: 0.0)
    default_conversation.context.have_actors_changed = False
    _run_conversation_generation_synchronously(default_conversation, default_chat_manager, monkeypatch)
    _prime_result_continuation(
        default_conversation,
        [f"{npc.name} picked up/took Golden Saint Shield from Dragonborn"],
        monkeypatch,
    )
    _run_conversation_generation_synchronously(default_conversation, default_chat_manager, monkeypatch)

    started = time.monotonic()
    default_conversation.process_player_input("Can you equip the shield?")
    assert time.monotonic() - started < 2.0
    lifecycle = default_chat_manager.active_action_lifecycle
    assert lifecycle is not None and lifecycle.correction_attempted is True
    assert len(scripted_llm.calls) == 2
    assert sum("Retrying missing requested action once" in record.message for record in caplog.records) == 1
    assert sum("Requested action not emitted: mantella_npc_equip" in record.message for record in caplog.records) == 1
    queue = default_conversation._Conversation__sentences
    queue.is_more_to_come = False
    queued = []
    while sentence := queue.get_next_sentence():
        queued.append(sentence)
    assert not [action for sentence in queued for action in sentence.actions]

    # A later player turn gets a fresh generation and cannot be trapped in the
    # terminal no-action correction state.
    default_conversation.process_player_input("Are you ready?")
    assert len(scripted_llm.calls) == 3
