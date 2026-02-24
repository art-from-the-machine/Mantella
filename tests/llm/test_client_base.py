from src.llm.client_base import ClientBase
from unittest.mock import patch
import json
import os


def test_service_key_found_in_mod_secret_json(tmp_path, monkeypatch):
    """Service key should be read from mod-folder secret_keys.json first"""
    mod_root = tmp_path / "mod"
    runtime_path = mod_root / "a" / "b" / "c"
    runtime_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: runtime_path)

    (mod_root / "secret_keys.json").write_text(json.dumps({"OpenRouter": "sk-mod"}), encoding="utf-8")

    assert ClientBase._get_api_key("OpenRouter", False) == "sk-mod"


def test_service_key_found_in_local_secret_json(tmp_path, monkeypatch):
    """Falls back to local secret_keys.json when mod one is missing"""
    runtime_path = tmp_path / "x" / "y" / "z"
    runtime_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: runtime_path)

    local_secret = tmp_path / "secret_keys.json"
    local_secret.write_text(json.dumps({"OpenRouter": "sk-local"}), encoding="utf-8")

    previous_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        assert ClientBase._get_api_key("OpenRouter", False) == "sk-local"
    finally:
        os.chdir(previous_cwd)


def test_service_url_alias_resolution(tmp_path, monkeypatch):
    """Service alias should resolve to canonical URL key in secret_keys.json"""
    mod_root = tmp_path / "mod"
    runtime_path = mod_root / "a" / "b" / "c"
    runtime_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: runtime_path)

    (mod_root / "secret_keys.json").write_text(
        json.dumps({"https://openrouter.ai/api/v1": "sk-url"}),
        encoding="utf-8"
    )

    assert ClientBase._get_api_key("or", False) == "sk-url"


def test_service_key_fallback_to_gpt_secret_txt(tmp_path, monkeypatch):
    """Falls back to GPT_SECRET_KEY.txt when secret_keys.json has no matching key"""
    mod_root = tmp_path / "mod"
    runtime_path = mod_root / "a" / "b" / "c"
    runtime_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: runtime_path)

    (mod_root / "GPT_SECRET_KEY.txt").write_text("sk-gpt-fallback\n", encoding="utf-8")

    isolated_cwd = tmp_path / "isolated"
    isolated_cwd.mkdir(parents=True)
    previous_cwd = os.getcwd()
    try:
        os.chdir(isolated_cwd)
        assert ClientBase._get_api_key("OpenRouter", False) == "sk-gpt-fallback"
    finally:
        os.chdir(previous_cwd)


def test_service_key_not_found_returns_none(tmp_path, monkeypatch):
    """Returns None when neither secret_keys.json nor GPT_SECRET_KEY.txt provides a key"""
    runtime_path = tmp_path / "a" / "b" / "c"
    runtime_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: runtime_path)
    isolated_cwd = tmp_path / "isolated"
    isolated_cwd.mkdir(parents=True)
    previous_cwd = os.getcwd()
    try:
        os.chdir(isolated_cwd)
        assert ClientBase._get_api_key("OpenRouter", False) is None
    finally:
        os.chdir(previous_cwd)


def test_unknown_service_returns_custom():
    result = ClientBase.get_model_list("Unknown")
    assert result.available_models == [("Custom model", "Custom model")]
    assert result.allows_manual_model_input is True


def test_openai_happy_path():
    """Test OpenAI service with successful model fetch"""
    result = ClientBase.get_model_list("OpenAI")
    assert any("gpt-4" in opt[1] for opt in result.available_models)
    assert result.allows_manual_model_input is True


@patch('src.llm.client_base.ClientBase._get_api_key')
def test_openrouter_missing_key(mock_get_key):
    """Test OpenRouter with missing API key"""
    mock_get_key.return_value = None
    result = ClientBase.get_model_list("OpenRouter")
    assert "No secret key found" in result.available_models[0][0]


def test_openrouter_success():
    """Test successful OpenRouter model list retrieval"""
    result = ClientBase.get_model_list("OpenRouter")
    assert any("mistralai/mistral-small-3.1-24b-instruct:free" in opt[1] for opt in result.available_models)
    assert result.allows_manual_model_input is False


def test_is_vision_filtering():
    """Test vision model filtering"""
    result = ClientBase.get_model_list("OpenRouter", is_vision=True)
    assert all("✅ Vision" in opt[0] for opt in result.available_models)


@patch('src.llm.client_base.ClientBase._get_api_key')
def test_nanogpt_missing_key(mock_get_key):
    """Test NanoGPT with missing API key"""
    mock_get_key.return_value = None
    result = ClientBase.get_model_list("NanoGPT")
    assert "No secret key found" in result.available_models[0][0]


def test_nanogpt_success():
    """Test successful NanoGPT model list retrieval"""
    result = ClientBase.get_model_list("NanoGPT")
    assert result.default_model == "mistral-small-31-24b-instruct"
    assert result.allows_manual_model_input is False