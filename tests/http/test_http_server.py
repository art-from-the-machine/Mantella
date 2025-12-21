from src.http.http_server import http_server
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from fastapi import Response
from fastapi import FastAPI

@pytest.fixture
def mock_routes():
    """Create mock routes"""
    class MockRoute(MagicMock):
        def add_route_to_server(self, app):
            @app.get("/test")
            def test_endpoint():
                return {"message": "Test successful"}
    
    return [MockRoute(), MockRoute()]

@pytest.fixture
def mock_client(server: http_server, mock_routes) -> TestClient:
    """Create a TestClient with mock routes configured"""
    server._setup_routes(mock_routes)
    return TestClient(server.app)


def test_app_property(server: http_server):
    """Test that app property returns the FastAPI instance"""
    assert isinstance(server.app, FastAPI)


def test_mock_endpoint(mock_client: TestClient):
    """Test that routes work correctly"""
    response: Response = mock_client.get("/test")
    assert response.status_code == 200
    assert response.json() == {"message": "Test successful"}


def test_ui_endpoint(production_like_client: TestClient):
    """Test the UI endpoint works"""
    response = production_like_client.get("/ui")
    assert response.status_code == 200


@patch('uvicorn.run')
@patch('src.utils.play_mantella_ready_sound')
def test_start(mock_sound, mock_uvicorn, server: http_server, mock_routes):
    """Test the start method without actually starting the server"""
    server.start(port=4999, routes=mock_routes, play_startup_sound=True, show_debug=False)
    
    # Verify sound played
    mock_sound.assert_called_once()
    
    # Verify uvicorn was called with the right parameters
    mock_uvicorn.assert_called_once()
    args, kwargs = mock_uvicorn.call_args
    assert args[0] == server.app
    assert kwargs['port'] == 4999