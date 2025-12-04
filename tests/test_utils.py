from src import utils
import pytest
import time
import logging
import sys
import os
import platform
import playsound
from pathlib import Path
from pytest import LogCaptureFixture
from pytest import MonkeyPatch

if platform.system() == "Windows":
    import winsound

@utils.time_it
def decorated_dummy_function(delay=0.01):
    time.sleep(delay)
    return "done"

def test_time_it_decorator(caplog: LogCaptureFixture):
    caplog.set_level(logging.DEBUG)
    result = decorated_dummy_function(0.01)
    assert result == "done"
    # Check that a debug log about timing is generated
    assert any("took" in record.message for record in caplog.records)


@pytest.mark.parametrize(
    'raw_text, cleaned_text',
    [
        ('abc', 'abc'),
        ('Hello, World!', 'hello world'),
        pytest.param('','',id='empty_string'),
        ('   ', ''),
        ('!@#$%^', ''),
        ('  Text  with    extra  spaces  ', 'text with extra spaces'),
        ('é è à ü ñ ç 龙', 'é è à ü ñ ç 龙'),
    ]
)
def test_clean_text(raw_text, cleaned_text):
    assert utils.clean_text(raw_text) == cleaned_text

def test_clean_text_non_string():
    with pytest.raises(AttributeError):
        utils.clean_text(123)


@pytest.mark.parametrize(
    "raw_text, cleaned_text",
    [
        ("Test123", "Test"),
        ("NoNumbers", "NoNumbers"),
        ("Trailing 123", "Trailing"),
        ("   123", ""),
        (123, 123),
    ]
)
def test_remove_trailing_number(raw_text, cleaned_text):
    assert utils.remove_trailing_number(raw_text) == cleaned_text


def test_resolve_path_not_frozen():
    resolved = utils.resolve_path()

    assert isinstance(resolved, str)
    assert os.path.isdir(resolved)

def test_resolve_path_frozen(monkeypatch: MonkeyPatch):
    # Create a mock for getattr that returns True when checking for 'frozen'
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
    
    resolved = utils.resolve_path()
    assert resolved == os.path.dirname(mock_executable)


@pytest.fixture
def fake_play_sound(monkeypatch: MonkeyPatch):
    calls = []

    def fake_play_winsound(filename, flags):
        calls.append((filename, flags))

    def fake_play_playsound(filename):
        calls.append((filename))

    if platform.system() == "Windows":
        monkeypatch.setattr(winsound, "PlaySound", fake_play_winsound)
    monkeypatch.setattr(playsound, "playsound", fake_play_playsound)
    return calls

def test_play_mantella_ready_sound(fake_play_sound, monkeypatch: MonkeyPatch):
    monkeypatch.setattr(utils, "resolve_path", lambda: "/fake/path")
    utils.play_mantella_ready_sound()
    expected = os.path.join("/fake/path", "data", "mantella_ready.wav")
    assert any(expected in call[0] for call in fake_play_sound)

def test_play_no_mic_input_detected_sound(fake_play_sound, monkeypatch: MonkeyPatch):
    monkeypatch.setattr(utils, "resolve_path", lambda: "/fake/path")
    utils.play_no_mic_input_detected_sound()
    expected = os.path.join("/fake/path", "data", "no_mic_input_detected.wav")
    assert any(expected in call[0] for call in fake_play_sound)

def test_play_error_sound(fake_play_sound):
    utils.play_error_sound()
    # For error sound, the expected sound is "SystemHand"
    assert any("SystemHand" in call[0] for call in fake_play_sound)


@pytest.mark.parametrize(
    "raw_text, expected_encoding",
    [
        ('Hello, World!', 'ascii'),
        ('é è à ü ñ ç 龙', 'utf-8'),
    ]
)
def test_get_file_encoding(raw_text, expected_encoding, tmp_path: Path):
    # Create a temporary text file with known content
    file: Path = tmp_path / "test.txt"
    file.write_text(raw_text, encoding="utf-8")
    encoding = utils.get_file_encoding(str(file))
    assert encoding is not None
    assert encoding.lower() == expected_encoding


def test_cleanup_tmp(tmp_path: Path):
    # Create a temporary directory with a file and a subdirectory
    tmp_folder: Path = tmp_path / "tmp_folder"
    tmp_folder.mkdir()
    file_path = tmp_folder / "temp.txt"
    file_path.write_text("data")
    sub_folder = tmp_folder / "subdir"
    sub_folder.mkdir()
    (sub_folder / "subfile.txt").write_text("more data")
    # Call cleanup_tmp to remove files in tmp_folder
    utils.cleanup_tmp(str(tmp_folder))
    # Check that the file and subdirectory have been removed
    # Note: The folder itself should remain
    assert os.listdir(str(tmp_folder)) == []

def test_cleanup_tmp_already_empty(tmp_path: Path):
    # Create a temporary directory with a file and a subdirectory
    tmp_folder: Path = tmp_path / "tmp_folder"
    tmp_folder.mkdir()
    # Call cleanup_tmp to remove files in tmp_folder
    utils.cleanup_tmp(str(tmp_folder))
    # Check that the file and subdirectory have been removed
    # Note: The folder itself should remain
    assert os.listdir(str(tmp_folder)) == []


def test_cleanup_mei_no_mei(caplog: LogCaptureFixture):
    utils.cleanup_mei(remove_mei_folders=True)
    # We expect no log message regarding cleanup if _MEIPASS is not set
    assert not any("runtime folder" in record.message for record in caplog.records)

def test_cleanup_mei_with_fake_mei(monkeypatch: MonkeyPatch, tmp_path: Path, caplog: LogCaptureFixture):
    caplog.set_level(logging.DEBUG)
    
    # Create the current MEI directory (where the exe files currently sit) in tmp_path
    current_mei_dir = tmp_path / "_MEI1234"
    current_mei_dir.mkdir()
    
    # Create another MEI directory in the same parent directory (tmp_path)
    other_mei_dir = tmp_path / "_MEI5678"
    other_mei_dir.mkdir()

    original_getattr = getattr
    def mock_getattr(obj, name, default=None):
        if obj is sys and name == '_MEIPASS':
            return str(current_mei_dir)
        return original_getattr(obj, name, default)
    
    # Force _MEIPASS attribute
    monkeypatch.setattr('builtins.getattr', mock_getattr)

    # Check if cleanup_mei finds the other MEI directory
    utils.cleanup_mei(remove_mei_folders=False)
    assert any("runtime folder(s) found" in record.message for record in caplog.records)

    # Check if cleanup_mei removes the other MEI directory
    utils.cleanup_mei(remove_mei_folders=True)
    assert any("runtime folder(s) cleaned up" in record.message for record in caplog.records)


def test_get_my_games_directory(tmp_path: Path):
    result = utils.get_my_games_directory(custom_user_folder='')
    assert os.path.exists(result)
    assert result != str(tmp_path) + '\\'

    result = utils.get_my_games_directory(custom_user_folder=str(tmp_path))
    assert os.path.exists(result)
    assert result == str(tmp_path) + '\\'


@pytest.mark.parametrize(
    "identifier, expected_hex",
    [
        ("1", "00000001"),
        ("255", "000000FF"),
        ("-1", "FFFFFFFF"),
        ("4294967295", "FFFFFFFF"),
    ]
)
def test_convert_to_skyrim_hex_format(identifier, expected_hex):
    assert utils.convert_to_skyrim_hex_format(identifier) == expected_hex


@pytest.mark.parametrize(
    "in_game_time, expected_group",
    [
        (0, 'at night'),
        (1, 'at night'),
        (2, 'at night'),
        (3, 'at night'),
        (4, 'at night'),
        (5, 'in the early morning'),
        (7, 'in the early morning'),
        (8, 'in the morning'),
        (9, 'in the morning'),
        (10, 'in the morning'),
        (11, 'in the morning'),
        (12, 'in the afternoon'),
        (13, 'in the afternoon'),
        (14, 'in the afternoon'),
        (15, 'in the early evening'),
        (16, 'in the early evening'),
        (17, 'in the early evening'),
        (18, 'in the early evening'),
        (19, 'in the early evening'),
        (20, 'in the late evening'),
        (21, 'in the late evening'),
        (22, 'at night'),
        (23, 'at night'),
        (24, 'at night'),
    ]
)
def test_get_time_group(in_game_time, expected_group):
    assert utils.get_time_group(in_game_time) == expected_group


@pytest.mark.parametrize(
    "keyword_string, expected",
    [
        ("hello", ["hello"]),
        ("Hello, World!", ["hello", "world!"]),
        (" one , two , three ", ["one", "two", "three"]),
        (" one , two , THREE ", ["one", "two", "three"]),
        ("singleKeyword", ["singlekeyword"]),
    ]
)
def test_parse_keywords(keyword_string, expected):
    assert utils.parse_keywords(keyword_string) == expected



@pytest.mark.parametrize(
    "num, expected",
    [
        (99_999, "99,999"),
        (100_000, "100k"),
        (500_000, "500k"),
        (1_000_000, "1m"),
        (50_000_000, "50m"),
        (1_000_000_000, "1b"),
        (5_000_000_000, "5b"),
        (999_999_999_999_999_999_999, "999999999999b"),
    ]
)
def test_format_context_size(num, expected):
    assert utils.format_context_size(num) == expected


@pytest.mark.parametrize(
    "price, expected",
    [
        (-10, "unknown"),
        (0, "free"),
        (10.0, "$10"),
        (10.50, "$10.50"),
        (9.99, "$9.99"),
    ]
)
def test_format_price(price, expected):
    assert utils.format_price(price) == expected


def test_get_openai_model_list():
    result = utils.get_openai_model_list()
    # Check that result has a 'data' attribute which is a list with expected items
    assert hasattr(result, "data")
    assert isinstance(result.data, list)
    # Check that at least one model has the expected structure
    model = result.data[0]
    assert hasattr(model, "id")
    assert hasattr(model, "model_extra")


def test_get_model_token_limits():
    token_limits = utils.get_model_token_limits()
    assert isinstance(token_limits, dict)
    # Check for some known keys and values
    assert token_limits.get("gpt-3.5-turbo") == 16385
    assert token_limits.get("gpt-4") == 8191
