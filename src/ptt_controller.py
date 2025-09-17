import sys
import logging


class PTTController:
    """Lightweight push-to-talk key state checker (Windows-focused).

    - Accepts a human-friendly key string (e.g., 'V', 'SPACE', 'F1').
    - Polls key state using GetAsyncKeyState; no global hooks required.
    - On non-Windows platforms, always returns False.
    """

    def __init__(self, key: str | None) -> None:
        self._vk: int | None = None
        self._is_windows: bool = sys.platform.startswith('win')
        self.update_key(key)

    @staticmethod
    def _normalize_key_to_vk(key: str | None) -> int | None:
        if not key:
            return None

        k = key.strip().upper()
        if not k:
            return None

        # Letters A-Z and digits 0-9 map directly to VK codes
        if len(k) == 1:
            c = k[0]
            if 'A' <= c <= 'Z':
                return ord(c)
            if '0' <= c <= '9':
                return ord(c)

        # Function keys F1-F24
        if k.startswith('F') and k[1:].isdigit():
            try:
                n = int(k[1:])
                if 1 <= n <= 24:
                    return 0x70 + (n - 1)  # VK_F1 = 0x70
            except Exception:
                return None

        specials = {
            'SPACE': 0x20,
            'TAB': 0x09,
            'ESC': 0x1B,
            'ESCAPE': 0x1B,
            'ENTER': 0x0D,
            'RETURN': 0x0D,
            'SHIFT': 0x10,
            'CTRL': 0x11,
            'CONTROL': 0x11,
            'ALT': 0x12,
            'CAPSLOCK': 0x14,
            'LEFT': 0x25,
            'UP': 0x26,
            'RIGHT': 0x27,
            'DOWN': 0x28,
        }
        return specials.get(k)

    def update_key(self, key: str | None) -> None:
        try:
            self._vk = self._normalize_key_to_vk(key)
            if self._vk is None and key:
                logging.warning(f"PTT hotkey '{key}' not recognized. PTT will be disabled until a valid key is set.")
        except Exception as e:
            logging.warning(f"Failed to set PTT key '{key}': {e}")
            self._vk = None

    def is_pressed(self) -> bool:
        if not self._is_windows:
            return False
        if self._vk is None:
            return False
        try:
            import ctypes
            return (ctypes.windll.user32.GetAsyncKeyState(self._vk) & 0x8000) != 0
        except Exception:
            return False


