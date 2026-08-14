from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.game_manager import GameStateManager
from src.http.communication_constants import communication_constants as comm_consts
from src.http.routes.mantella_route import mantella_route


def test_game_manager_reports_only_live_conversations():
    manager = GameStateManager.__new__(GameStateManager)
    manager._GameStateManager__talk = MagicMock(has_already_ended=False)
    assert manager.has_active_conversation is True

    manager._GameStateManager__talk.has_already_ended = True
    assert manager.has_active_conversation is False


def test_game_manager_diagnostic_state_identifies_conversation():
    manager = GameStateManager.__new__(GameStateManager)
    manager._GameStateManager__diagnostic_generation = 7
    manager._GameStateManager__talk = None
    assert "manager=7/" in manager.diagnostic_state
    assert "conversation=None" in manager.diagnostic_state

    manager._GameStateManager__talk = MagicMock(has_already_ended=False)
    assert "conversation=" in manager.diagnostic_state
    assert "active=True" in manager.diagnostic_state


def test_stale_session_terminal_request_is_rejected_without_clearing_active_state():
    manager = GameStateManager.__new__(GameStateManager)
    manager._GameStateManager__session_id = 2
    manager._GameStateManager__last_session_id = 2
    assert manager.request_session_matches({"mantella_conversation_session": 2})
    assert not manager.request_session_matches({"mantella_conversation_session": 1})
    reply = manager.stale_request_reply("mantella_end_conversation", 1)
    assert reply["mantella_reply_type"] == "mantella_stale_request"
    assert reply["mantella_conversation_session"] == 2


def test_legacy_request_without_session_remains_compatible():
    manager = GameStateManager.__new__(GameStateManager)
    manager._GameStateManager__session_id = 2
    assert manager.request_session_matches({})


def test_new_session_is_returned_by_start_response():
    manager = GameStateManager.__new__(GameStateManager)
    manager._GameStateManager__session_id = "B"
    manager._GameStateManager__last_session_id = "B"
    assert manager.protocol_session_id == "B"


def test_route_reinitialization_does_not_end_active_conversation():
    route = mantella_route.__new__(mantella_route)
    active_manager = MagicMock(has_active_conversation=True)
    route._mantella_route__game = active_manager
    route._mantella_route__route_reinitialization_pending = False

    route._setup_route()

    active_manager.end_conversation.assert_not_called()
    assert route._mantella_route__route_reinitialization_pending is True


def test_first_player_input_survives_deferred_route_reinitialization():
    """A config reload observed on B's first request must not end B first."""
    route = mantella_route.__new__(mantella_route)

    class Config:
        has_any_config_value_changed = True
        have_all_config_values_loaded_correctly = True
        show_http_debug_messages = False

        def update_config_loader_with_changed_config_values(self):
            self.has_any_config_value_changed = False

    manager = MagicMock(has_active_conversation=True)
    manager.player_input.return_value = {"mantella_reply_type": "mantella_npc_talk"}
    route._config = Config()
    route._has_route_been_initialized = True
    route._mantella_route__game = manager
    route._mantella_route__route_reinitialization_pending = False
    route._mantella_route__request_sequence = 0

    app = FastAPI()
    route.add_route_to_server(app)
    response = TestClient(app).post(
        "/mantella",
        json={
            comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_PLAYERINPUT,
            comm_consts.KEY_REQUESTTYPE_PLAYERINPUT: "Hey, Lydia, how's it going?",
        },
    )

    assert response.status_code == 200
    manager.player_input.assert_called_once()
    manager.end_conversation.assert_not_called()
    assert route._mantella_route__route_reinitialization_pending is True
