import pytest
from src.tts.tts_factory import parse_tts_service
from src.config.definitions.tts_definitions import TTSEnum


class TestParseTtsService:

    @pytest.mark.parametrize("value, expected", [
        ("piper", TTSEnum.PIPER),
        ("Piper", TTSEnum.PIPER),
        ("PIPER", TTSEnum.PIPER),
        ("xtts", TTSEnum.XTTS),
        ("XTTS", TTSEnum.XTTS),
        ("xvasynth", TTSEnum.XVASYNTH),
        ("xVASynth", TTSEnum.XVASYNTH),
    ])
    def test_valid_service_strings(self, value, expected):
        assert parse_tts_service(value) == expected

    @pytest.mark.parametrize("value", [
        "", None, "nan", "none", "null", "  ",
    ])
    def test_returns_none_for_empty_or_null(self, value):
        assert parse_tts_service(value) is None

    def test_logs_warning_for_unrecognized_service(self):
        assert parse_tts_service("fake_tts") is None
