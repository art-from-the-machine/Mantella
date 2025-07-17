from src.llm.client_base import ClientBase
from src.llm.llm_model_list import LLMModelList
import pytest
from src.config.config_loader import ConfigLoader
import logging
from pathlib import Path
from unittest.mock import patch
import pytest

def test_key_found_in_mod_parent(tmp_path, monkeypatch):
    """Test finding API key in mod parent folder"""
    # Setup mock mod_parent_folder structure
    mock_mod_path = tmp_path / "a" / "b" / "c"
    mock_mod_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: mock_mod_path)
    
    key_file = "test_key.txt"
    (tmp_path / key_file).write_text("sk-123")
    
    assert ClientBase._get_api_key([key_file], False) == "sk-123"


def test_key_found_locally(tmp_path, monkeypatch):
    """Test finding API key in local directory"""
    # Setup empty mod_parent_folder
    mock_mod_path = tmp_path / "empty" / "b" / "c"
    mock_mod_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: mock_mod_path)
    
    # Create key in current working directory
    key_file = "local_key.txt"
    (tmp_path / key_file).write_text("sk-456")
    
    assert ClientBase._get_api_key([key_file], False) == "sk-456"


def test_key_not_found(tmp_path, monkeypatch, caplog):
    """Test missing key file handling"""
    mock_mod_path = tmp_path / "a" / "b" / "c"
    mock_mod_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: mock_mod_path)
    
    result = ClientBase._get_api_key(["missing.txt"], False)
    
    assert result is None


def test_string_argument(tmp_path, monkeypatch):
    """Test string instead of list argument (strings should be converted to lists in the function itself)"""
    mock_mod_path = tmp_path / "a" / "b" / "c"
    mock_mod_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: mock_mod_path)
    
    key_file = "single_key.txt"
    (tmp_path / key_file).write_text("sk-789")
    
    assert ClientBase._get_api_key(key_file, False) == "sk-789"


def test_empty_key_file(tmp_path, monkeypatch):
    """Test empty key file skips to next candidate"""
    mock_mod_path = tmp_path / "a" / "b" / "c"
    mock_mod_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: mock_mod_path)
    
    # Create empty key file
    empty_key = "empty.txt"
    (tmp_path / empty_key).write_text("  \n")
    
    # Create valid local key
    valid_key = "valid.txt"
    (tmp_path / valid_key).write_text("sk-abc")
    
    assert ClientBase._get_api_key([empty_key, valid_key], False) == "sk-abc"


def test_key_priority(tmp_path, monkeypatch):
    """Test that the first key in the list is prioritized"""
    mock_mod_path = tmp_path / "a" / "b" / "c"
    mock_mod_path.mkdir(parents=True)
    monkeypatch.setattr('src.utils.resolve_path', lambda: mock_mod_path)
    
    first_key = "first.txt"
    (tmp_path / first_key).write_text("sk-abc")
    
    second_key = "second.txt"
    (tmp_path / second_key).write_text("sk-def")
    
    assert ClientBase._get_api_key([first_key, second_key], False) == "sk-abc"


def test_unknown_service_returns_custom():
    result = ClientBase.get_model_list("Unknown", "key.txt")
    assert result.available_models == [("Custom model", "Custom model")]
    assert result.allows_manual_model_input is True


def test_openai_happy_path():
    """Test OpenAI service with successful model fetch"""
    result = ClientBase.get_model_list("OpenAI", "key.txt")
    assert any("gpt-4" in opt[1] for opt in result.available_models)
    assert result.allows_manual_model_input is True


@patch('src.llm.client_base.ClientBase._get_api_key')
def test_openrouter_missing_key(mock_get_key):
    """Test OpenRouter with missing API key"""
    mock_get_key.return_value = None
    result = ClientBase.get_model_list("OpenRouter", "missing.txt")
    assert "No secret key found" in result.available_models[0][0]


def test_openrouter_success():
    """Test successful OpenRouter model list retrieval"""
    result = ClientBase.get_model_list("OpenRouter", "key.txt")
    assert any("google/gemma-2-9b-it:free" in opt[1] for opt in result.available_models)
    assert result.allows_manual_model_input is False


def test_nanogpt_success():
    """Test successful NanoGPT model list retrieval"""
    result = ClientBase.get_model_list("NanoGPT", "key.txt", "gpt-4o-mini")
    assert result.default_model == "gpt-4o-mini"
    assert result.allows_manual_model_input is True  # NanoGPT allows manual input


def test_is_vision_filtering():
    """Test vision model filtering"""
    result = ClientBase.get_model_list("OpenRouter", "key.txt", is_vision=True)
    assert all("Vision Available" in opt[0] for opt in result.available_models)