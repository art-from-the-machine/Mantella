from src.setup import MantellaSetup
import pytest
import os
import sys
import logging
import configparser
from pathlib import Path
from unittest.mock import patch
from pytest import MonkeyPatch
from pytest import LogCaptureFixture
import pandas as pd

@pytest.fixture
def mantella_setup() -> MantellaSetup:
    return MantellaSetup()

@pytest.fixture
def languages_csv_file(tmp_path: Path) -> str:
    data = {
        'alpha2': ['en', 'fr'],
        'name': ['English', 'French']
    }
    df = pd.DataFrame(data)
    file_path = tmp_path / "languages.csv"
    df.to_csv(file_path, index=False)
    return str(file_path)


def test_init(mantella_setup: MantellaSetup):
    assert mantella_setup.save_folder == ""
    assert mantella_setup.config is None
    assert mantella_setup.language_info == {}


@patch('os.chdir')
def test_set_cwd_to_exe_dir(mock_chdir, mantella_setup: MantellaSetup, monkeypatch: MonkeyPatch):
    # Test when not frozen (regular Python script)
    mantella_setup._set_cwd_to_exe_dir()
    mock_chdir.assert_not_called()
    
    # Test when frozen (executable)
    original_getattr = getattr
    def mock_getattr(obj, name, default=None):
        if obj is sys and name == 'frozen':
            return True
        return original_getattr(obj, name, default)
    
    # Mock the executable path
    mock_executable = '/mock/path/executable'
    monkeypatch.setattr(sys, 'executable', mock_executable)
    
    # Replace the built-in getattr with mock version
    monkeypatch.setattr('builtins.getattr', mock_getattr)
    
    mantella_setup._set_cwd_to_exe_dir()
    mock_chdir.assert_called_once_with(os.path.dirname(sys.executable))


def test_get_custom_user_folder_no_file(mantella_setup: MantellaSetup, tmp_path: Path, monkeypatch: MonkeyPatch):
    # Change to a temporary directory to avoid actual file
    monkeypatch.chdir(tmp_path)
    
    # Test when file doesn't exist
    result = mantella_setup._get_custom_user_folder()
    assert result == ""

def test_get_custom_user_folder_with_file(mantella_setup: MantellaSetup, tmp_path: Path, monkeypatch: MonkeyPatch):
    # Change to a temporary directory
    monkeypatch.chdir(tmp_path)
    
    # Create a test config file
    config = configparser.ConfigParser()
    config['UserFolder'] = {'custom_user_folder': str(tmp_path / 'test_folder')}
    
    with open('custom_user_folder.ini', 'w', encoding='utf-8') as f:
        config.write(f)
    
    # Test when file exists with valid data
    result = mantella_setup._get_custom_user_folder()
    assert result == str(tmp_path / 'test_folder')

def test_get_custom_user_folder_invalid_file(mantella_setup: MantellaSetup, tmp_path: Path, monkeypatch: MonkeyPatch, caplog):
    # Change to a temporary directory
    monkeypatch.chdir(tmp_path)
    
    # Create an invalid test config file
    with open('custom_user_folder.ini', 'w', encoding='utf-8') as f:
        f.write('This is not a valid config file')
    
    # Test with invalid file
    result = mantella_setup._get_custom_user_folder()
    assert result == ""
    assert "Unable to read / open 'custom_user_folder.ini'" in caplog.text

def test_get_custom_user_folder_missing_section(mantella_setup: MantellaSetup, tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture):
    # Change to a temporary directory
    monkeypatch.chdir(tmp_path)
    
    # Create a test config file with missing section
    config = configparser.ConfigParser()
    config['WrongSection'] = {'custom_user_folder': str(tmp_path / 'test_folder')}
    
    with open('custom_user_folder.ini', 'w', encoding='utf-8') as f:
        config.write(f)
    
    # Test when file exists but section is missing
    result = mantella_setup._get_custom_user_folder()
    assert result == ""
    assert "Could not find option 'custom_user_folder'" in caplog.text


def test_setup_logging(mantella_setup: MantellaSetup, tmp_path: Path):
    log_file = tmp_path / "test_log.log"
    
    # Reset root logger to avoid interference from pytest
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)  # Reset to default
    root_logger.handlers = []  # Clear any existing handlers
    
    # Test with advanced_logs=False
    mantella_setup._setup_logging(str(log_file), advanced_logs=False)
    
    # Verify logger configuration
    assert root_logger.level == logging.INFO
    assert len(root_logger.handlers) == 2  # Console and file handler
    
    # Test with advanced_logs=True
    root_logger.handlers = []  # Clear handlers
    mantella_setup._setup_logging(str(log_file), advanced_logs=True)
    
    # Verify logger configuration
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 2


def test_get_language_info_valid(mantella_setup: MantellaSetup, languages_csv_file: str):
    result = mantella_setup._get_language_info(languages_csv_file, 'en')
    expected = {'alpha2': 'en', 'name': 'English'}
    assert result == expected

def test_get_language_info_invalid(mantella_setup: MantellaSetup, languages_csv_file: str, caplog: LogCaptureFixture):
    with caplog.at_level(logging.ERROR):
        result = mantella_setup._get_language_info(languages_csv_file, 'de')  # 'de' is not present in the test CSV
    assert result == {}
    assert any("Could not load language 'de'" in message for message in caplog.text.splitlines())