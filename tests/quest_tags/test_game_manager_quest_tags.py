"""Tests for how GameStateManager passes quest tag answers on: announcements on player input, and the check list request."""
from unittest.mock import MagicMock
import pytest
from src.game_manager import GameStateManager
from src.games.skyrim import Skyrim
from src.http.communication_constants import communication_constants as comm_consts
from src.quest_tags.conditions import CheckList

CHECK_LIST = CheckList({"battle": {2: "getstagedone CWObj 100=1"}})


@pytest.fixture
def game_manager(skyrim, default_chat_manager, default_config, english_language_info, llm_client, monkeypatch):
    manager = GameStateManager(skyrim, default_chat_manager, default_config, english_language_info, llm_client, None, "STT_SECRET_KEY.txt", "GPT_SECRET_KEY.txt")
    monkeypatch.setattr(Skyrim, "quest_check_list", property(lambda self: CHECK_LIST))
    monkeypatch.setattr(Skyrim, "get_quest_outcome_text", lambda self, tag, slot: "{player_name} won the battle.")
    talk = MagicMock()
    talk.context.world_id = "Player1"
    talk.context.npcs_in_conversation.get_player_character.return_value.name = "Dovahkiin"
    manager._GameStateManager__talk = talk
    return manager


def _player_input(results: list[float], events: list[str]) -> dict:
    return {comm_consts.KEY_CONTEXT: {
        comm_consts.KEY_CONTEXT_INGAMEEVENTS: events,
        comm_consts.KEY_QUESTCHECKS_VERSION: CHECK_LIST.version,
        comm_consts.KEY_QUESTCHECKS_RESULTS: results,
    }}


def test_announcement_is_added_after_the_game_events(game_manager: GameStateManager):
    add_announcements = game_manager._GameStateManager__add_quest_tag_announcements
    add_announcements(_player_input([0.0], []))  # The first check: background, nothing announced
    request = _player_input([1.0], ["The location is now Whiterun."])
    add_announcements(request)
    assert request[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_INGAMEEVENTS] == ["The location is now Whiterun.", "Dovahkiin won the battle."]


def test_first_check_announces_nothing(game_manager: GameStateManager):
    request = _player_input([1.0], [])
    game_manager._GameStateManager__add_quest_tag_announcements(request)
    assert request[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_INGAMEEVENTS] == []


def test_check_list_reply(game_manager: GameStateManager):
    reply = game_manager.quest_check_list()
    assert reply[comm_consts.KEY_REPLYTYPE] == comm_consts.KEY_REPLYTYPE_QUESTCHECKLIST
    assert reply[comm_consts.KEY_QUESTCHECKS_LIST][comm_consts.KEY_QUESTCHECKS_FUNCTIONS] == ["getstagedone"]
