import pytest
from src.config.config_loader import ConfigLoader
from src.http.http_server import http_server
from src.http.routes.mantella_route import mantella_route
from src.ui.start_ui import StartUI
from src.http.routes.routeable import routeable
from fastapi.testclient import TestClient
from pathlib import Path
from src import utils

@pytest.fixture
def default_config(tmp_path: Path) -> ConfigLoader:
    # Set up default config by passing path without a config.ini file already present
    default_config = ConfigLoader(mygame_folder_path=str(tmp_path))

    # Load the actual config file
    # NOTE: This does not work with user-defined save folder paths
    my_games_folder = utils.get_my_games_directory(custom_user_folder='')
    actual_config = ConfigLoader(mygame_folder_path=my_games_folder)

    # Not all default values workout of the box
    # Override default config values with known paths from actual config
    default_config.piper_path = actual_config.piper_path

    return default_config

@pytest.fixture
def english_language_info() -> dict:
    return {'alpha2': 'en', 'language': 'English', 'hello': 'Hello'}

@pytest.fixture
def server() -> http_server:
    """Create a test instance of http_server"""
    return http_server()

@pytest.fixture
def default_mantella_route(default_config: ConfigLoader, english_language_info: dict) -> mantella_route:
    return mantella_route(
        config=default_config, 
        stt_secret_key_file='STT_SECRET_KEY.txt', 
        image_secret_key_file='IMAGE_SECRET_KEY.txt', 
        secret_key_file='GPT_SECRET_KEY.txt', 
        language_info=english_language_info, 
        show_debug_messages=False
    )

@pytest.fixture
def real_routes(default_config: ConfigLoader, default_mantella_route: mantella_route) -> list[routeable]:
    """Create the actual routes that would be used in production"""
    default_config.auto_launch_ui=False
    ui = StartUI(default_config)

    return [default_mantella_route, ui]

@pytest.fixture
def production_like_client(server: http_server, real_routes: list[routeable]) -> TestClient:
    """Create a TestClient configured like production"""
    server._setup_routes(real_routes)
    return TestClient(server.app)