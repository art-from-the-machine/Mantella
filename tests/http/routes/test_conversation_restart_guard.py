from unittest.mock import MagicMock
import asyncio

from fastapi import FastAPI

from src.game_manager import GameStateManager
from src.http.communication_constants import communication_constants as comm_consts
from src.http.routes.mantella_route import mantella_route


def test_game_manager_reports_only_live_conversations():
    manager = GameStateManager.__new__(GameStateManager)
    manager._GameStateManager__talk = MagicMock(has_already_ended=False)
    assert manager.has_active_conversation is True

    manager._GameStateManager__talk.has_already_ended = True
    assert manager.has_active_conversation is False


def test_stale_terminal_request_is_rejected_for_newer_session():
    manager = GameStateManager.__new__(GameStateManager)
    manager._GameStateManager__session_id = 2
    manager._GameStateManager__last_session_id = 2

    assert not manager.request_session_matches({comm_consts.KEY_CONVERSATION_SESSION: 1})
    reply = manager.stale_request_reply(
        comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION,
        1,
    )

    assert reply == {
        comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_STALE_REQUEST,
        comm_consts.KEY_CONVERSATION_SESSION: 2,
    }


def test_route_does_not_dispatch_stale_end_while_current_input_can_continue():
    """The route-level guard, rather than timing, protects the newer lifecycle."""
    route = mantella_route.__new__(mantella_route)
    manager = MagicMock()
    manager.diagnostic_state = "session=2 active=True"
    manager.protocol_session_id = 2
    manager.request_session_matches.return_value = False
    manager.stale_request_reply.return_value = {
        comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_STALE_REQUEST,
        comm_consts.KEY_CONVERSATION_SESSION: 2,
    }
    route._mantella_route__game = manager
    route._mantella_route__request_sequence = 0
    route._config = MagicMock(show_http_debug_messages=False)
    route._can_route_be_used = lambda: True

    app = FastAPI()
    route.add_route_to_server(app)
    endpoint = next(item.endpoint for item in app.routes if getattr(item, "path", None) == "/mantella")

    class Request:
        async def json(self):
            return {
                comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION,
                comm_consts.KEY_CONVERSATION_SESSION: 1,
            }

    reply = asyncio.run(endpoint(Request()))

    assert reply[comm_consts.KEY_REPLYTYPE] == comm_consts.KEY_REPLYTYPE_STALE_REQUEST
    manager.end_conversation.assert_not_called()


def test_legacy_request_without_session_remains_compatible():
    manager = GameStateManager.__new__(GameStateManager)
    manager._GameStateManager__session_id = 2
    assert manager.request_session_matches({})


def test_duplicate_end_after_closed_session_is_harmless():
    manager = GameStateManager.__new__(GameStateManager)
    manager._GameStateManager__diagnostic_generation = 1
    manager._GameStateManager__talk = None
    manager._GameStateManager__session_id = 2
    manager._GameStateManager__last_session_id = 2
    manager._GameStateManager__game = MagicMock()

    reply = manager.end_conversation({comm_consts.KEY_CONVERSATION_SESSION: 2})

    assert manager._GameStateManager__talk is None
    assert reply[comm_consts.KEY_REPLYTYPE] == comm_consts.KEY_REPLYTYPE_ENDCONVERSATION
    assert reply[comm_consts.KEY_CONVERSATION_SESSION] == 2


def test_route_reinitialization_does_not_end_active_conversation():
    route = mantella_route.__new__(mantella_route)
    active_manager = MagicMock(has_active_conversation=True)
    route._mantella_route__game = active_manager
    route._mantella_route__route_reinitialization_pending = False

    route._setup_route()

    active_manager.end_conversation.assert_not_called()
    assert route._mantella_route__route_reinitialization_pending is True
