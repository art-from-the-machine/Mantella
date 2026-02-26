import pytest
from src.ptt_controller import PTTController


class TestNormalizeKeyToVk:
    """Tests for the static key-string -> VK-code resolver."""

    def test_single_letter(self):
        assert PTTController._normalize_key_to_vk('V') == ord('V')

    def test_single_letter_lowercase(self):
        assert PTTController._normalize_key_to_vk('v') == ord('V')

    def test_single_digit(self):
        assert PTTController._normalize_key_to_vk('5') == ord('5')

    def test_function_key_f1(self):
        assert PTTController._normalize_key_to_vk('F1') == 0x70

    def test_function_key_f12(self):
        assert PTTController._normalize_key_to_vk('F12') == 0x7B

    def test_function_key_f24(self):
        assert PTTController._normalize_key_to_vk('F24') == 0x87

    def test_function_key_out_of_range(self):
        assert PTTController._normalize_key_to_vk('F25') is None
        assert PTTController._normalize_key_to_vk('F0') is None

    def test_special_keys(self):
        assert PTTController._normalize_key_to_vk('SPACE') == 0x20
        assert PTTController._normalize_key_to_vk('TAB') == 0x09
        assert PTTController._normalize_key_to_vk('ENTER') == 0x0D
        assert PTTController._normalize_key_to_vk('RETURN') == 0x0D
        assert PTTController._normalize_key_to_vk('ESC') == 0x1B
        assert PTTController._normalize_key_to_vk('ESCAPE') == 0x1B
        assert PTTController._normalize_key_to_vk('SHIFT') == 0x10
        assert PTTController._normalize_key_to_vk('CTRL') == 0x11
        assert PTTController._normalize_key_to_vk('CONTROL') == 0x11
        assert PTTController._normalize_key_to_vk('ALT') == 0x12

    def test_case_insensitive(self):
        assert PTTController._normalize_key_to_vk('space') == 0x20
        assert PTTController._normalize_key_to_vk('Space') == 0x20

    def test_whitespace_stripped(self):
        assert PTTController._normalize_key_to_vk('  V  ') == ord('V')

    def test_none_input(self):
        assert PTTController._normalize_key_to_vk(None) is None

    def test_empty_string(self):
        assert PTTController._normalize_key_to_vk('') is None


class TestPTTController:
    """Tests for the controller lifecycle."""

    def test_valid_key_sets_vk(self):
        ptt = PTTController('V')
        assert ptt._vk == ord('V')

    def test_none_key_disables(self):
        ptt = PTTController(None)
        assert ptt._vk is None
        assert ptt.is_pressed() is False

    def test_invalid_key_logs_warning_and_disables(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            ptt = PTTController('F0')
        assert ptt._vk is None
        assert "not recognized" in caplog.text

    def test_update_key_changes_vk(self):
        ptt = PTTController('V')
        assert ptt._vk == ord('V')
        ptt.update_key('SPACE')
        assert ptt._vk == 0x20

    def test_update_key_to_none_disables(self):
        ptt = PTTController('V')
        ptt.update_key(None)
        assert ptt._vk is None

    def test_is_pressed_returns_false_when_no_vk(self):
        ptt = PTTController(None)
        assert ptt.is_pressed() is False
