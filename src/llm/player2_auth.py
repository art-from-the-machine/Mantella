# =============================================================================
# player2_auth.py
# =============================================================================
# Authentication helpers for the Player2 LLM service integration.
# https://player2.game
#
# Player2 is an AI platform designed for game NPCs. It exposes an
# OpenAI-compatible /chat/completions endpoint and optionally a local
# desktop app that can serve API keys without manual configuration.
#
# NOTE FOR MAINTAINER:
#   PLAYER2_GAME_CLIENT_ID is currently a development/test ID.
#   Register Mantella at https://developer.player2.game and replace it
#   with the official client ID before merging this PR.
# =============================================================================

import requests
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Player2 API base URL (remote)
PLAYER2_API_BASE_URL = "https://api.player2.game/v1"

# Player2 desktop app local endpoint
PLAYER2_LOCAL_BASE_URL = "http://localhost:4315/v1"

# Player2 developer dashboard
PLAYER2_DASHBOARD_URL = "https://developer.player2.game"

# Development/test client ID — replace with official Mantella client ID
PLAYER2_GAME_CLIENT_ID = "019caf24-0f44-793e-86c1-c14a30f3b7e3"

# Path to the API keys file (relative to Mantella root)
_SECRET_KEYS_PATH = Path("secret_keys.json")


def is_player2_service(base_url: str) -> bool:
    """Returns True if the given base URL belongs to the Player2 service."""
    return base_url is not None and "player2.game" in base_url


def check_player2_app_running() -> bool:
    """Checks if the Player2 desktop app is running by querying its health endpoint.

    Returns:
        True if the app is running and healthy, False otherwise.
    """
    try:
        response = requests.get(f"{PLAYER2_LOCAL_BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def get_existing_key() -> str | None:
    """Reads the Player2 API key from secret_keys.json if it exists.

    Returns:
        The API key string, or None if not found.
    """
    try:
        if _SECRET_KEYS_PATH.exists():
            with open(_SECRET_KEYS_PATH, "r") as f:
                keys = json.load(f)
            return keys.get(PLAYER2_API_BASE_URL) or None
    except Exception as e:
        logger.debug(f"Player2: Could not read secret_keys.json: {e}")
    return None


def get_key_from_local_app() -> str | None:
    """Attempts to obtain a Player2 API key from the local desktop app.

    Calls POST http://localhost:4315/v1/login/web/{game_client_id} and
    returns the p2Key from the response, or None if the app is not running
    or the request fails.
    """
    try:
        response = requests.post(
            f"{PLAYER2_LOCAL_BASE_URL}/login/web/{PLAYER2_GAME_CLIENT_ID}",
            timeout=3
        )
        if response.status_code == 200:
            key = response.json().get("p2Key")
            if key:
                logger.info("Player2: API key obtained from local app.")
                return key
    except Exception as e:
        logger.info(f"Player2: Local app not available. Looking for manual API key in secret_keys.json...")
    return None


def save_key_to_file(key: str) -> bool:
    """Saves the Player2 API key to secret_keys.json.

    Merges with existing keys rather than overwriting the entire file.

    Returns:
        True if saved successfully, False otherwise.
    """
    try:
        existing = {}
        if _SECRET_KEYS_PATH.exists():
            with open(_SECRET_KEYS_PATH, "r") as f:
                existing = json.load(f)
        existing[PLAYER2_API_BASE_URL] = key.strip()
        with open(_SECRET_KEYS_PATH, "w") as f:
            json.dump(existing, f, indent=4)
        logger.info(f"Player2: API key saved to {_SECRET_KEYS_PATH.resolve()}")
        return True
    except Exception as e:
        logger.error(f"Player2: Could not save key to secret_keys.json: {e}")
        return False