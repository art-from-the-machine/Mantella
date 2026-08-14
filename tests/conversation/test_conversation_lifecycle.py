from unittest.mock import MagicMock

from src.conversation.conversation import Conversation


def _ended_conversation_stub() -> Conversation:
    conversation = Conversation.__new__(Conversation)
    conversation._Conversation__has_already_ended = False
    conversation._Conversation__stop_generation = MagicMock()
    conversation._Conversation__sentences = MagicMock()
    conversation._Conversation__save_conversation = MagicMock()
    return conversation


def test_end_detaches_once_and_starts_background_persistence():
    conversation = _ended_conversation_stub()

    conversation.end()
    conversation.end()

    assert conversation._Conversation__save_conversation.call_count == 1
    conversation._Conversation__save_conversation.assert_called_once_with(
        is_reload=False,
        end_timestamp=None,
    )
    assert conversation._Conversation__stop_generation.call_count == 1


class _SnapshotCharacters:
    def __init__(self):
        self.pending_shares = [("A", "B", "ref-b")]

    def get_pending_shares(self):
        return list(self.pending_shares)

    def clear_pending_shares(self):
        self.pending_shares.clear()

    def get_non_player_characters(self):
        return []

    def get_all_characters_since_start(self):
        return []


def test_summary_schedule_uses_rememberer_executor():
    conversation = Conversation.__new__(Conversation)
    conversation._Conversation__context = MagicMock()
    conversation._Conversation__context.npcs_in_conversation = _SnapshotCharacters()
    conversation._Conversation__context.world_id = "conversation-a"
    conversation._Conversation__messages = MagicMock()
    conversation._Conversation__conversation_type = MagicMock()
    conversation._Conversation__rememberer = MagicMock()

    conversation._Conversation__save_conversation(is_reload=False, end_timestamp=None)

    conversation._Conversation__rememberer.schedule_conversation_state.assert_called_once()


def test_participant_removal_uses_detached_persistence(monkeypatch):
    conversation = Conversation.__new__(Conversation)
    conversation._Conversation__messages = MagicMock()
    conversation._Conversation__messages.__len__.return_value = 4
    removed = object()
    context = MagicMock()
    context.add_or_update_characters.return_value = [removed]
    conversation._Conversation__context = context
    conversation._Conversation__save_conversation = MagicMock()

    conversation.add_or_update_character([])

    conversation._Conversation__save_conversation.assert_called_once_with(
        is_reload=True,
        departed_npcs=[removed],
    )
