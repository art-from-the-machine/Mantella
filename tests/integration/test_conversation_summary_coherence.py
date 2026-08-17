"""Concrete subsystem compatibility tests for conversation persistence."""

import threading
import time

from src.conversation.conversation import Conversation
from src.remember.summaries import Summaries


def test_concrete_summaries_implements_conversation_persistence_contract(default_rememberer: Summaries):
    """Catch mixed-version Conversation/Summaries trees before packaging."""
    assert callable(default_rememberer.schedule_conversation_state)
    assert callable(default_rememberer.shutdown)


def test_real_participant_transition_schedules_nonblocking_summary_and_tears_down(
    default_conversation: Conversation,
    default_rememberer: Summaries,
    default_chat_manager,
    llm_client,
    example_skyrim_player_character,
    example_skyrim_npc_character,
    another_example_skyrim_npc_character,
    monkeypatch,
):
    """Reproduce Wood Elf -> Sven transition with the concrete Summaries executor."""
    worker_started = threading.Event()
    worker_release = threading.Event()

    def controlled_save(*_args, **_kwargs):
        worker_started.set()
        assert worker_release.wait(2.0)

    monkeypatch.setattr(default_rememberer, "save_conversation_state", controlled_save)
    monkeypatch.setattr("src.conversation.conversation_log.conversation_log.save_conversation_log", lambda *_args, **_kwargs: None)

    # Adding Sven itself is a participant refresh. Removing the original NPC
    # is the production path that detaches and schedules its summary snapshot.
    default_conversation.add_or_update_character([
        example_skyrim_player_character,
        example_skyrim_npc_character,
        another_example_skyrim_npc_character,
    ])
    started = time.monotonic()
    default_conversation.add_or_update_character([
        example_skyrim_player_character,
        another_example_skyrim_npc_character,
    ])
    assert time.monotonic() - started < 0.25
    assert worker_started.wait(1.0)

    worker_release.set()
    default_conversation.end()

    # A new Conversation can immediately reuse the real persistence service;
    # the departed actor and prior lifecycle do not poison its first update.
    next_conversation = Conversation(
        default_conversation.context,
        default_chat_manager,
        default_rememberer,
        llm_client,
        None,
        False,
        False,
    )
    next_conversation.add_or_update_character([
        example_skyrim_player_character,
        example_skyrim_npc_character,
    ])
    assert not next_conversation.has_already_ended
    next_conversation.end()

