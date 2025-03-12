import pytest
from src import utils
import time
import logging


@utils.time_it
def decorated_dummy_function(delay=0.01):
    time.sleep(delay)
    return "done"

def test_time_it_decorator(caplog):
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