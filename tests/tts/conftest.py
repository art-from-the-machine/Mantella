import io
import sys
import pytest
import numpy as np
import soundfile as sf
from unittest.mock import MagicMock
from src.tts.synthesization_options import SynthesizationOptions


class FakeResponse:
    def __init__(self, status_code: int = 200, content: bytes = b'', text: str = ''):
        self.status_code = status_code
        self.content = content
        self.text = text


class FakeStreamingResponse:
    def __init__(self, chunks: list[bytes], status_code: int = 200, text: str = ''):
        self.status_code = status_code
        self.text = text
        self.__chunks = chunks

    def iter_content(self, chunk_size: int):
        yield from self.__chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def make_wav_bytes(subtype: str = 'FLOAT') -> bytes:
    """Build a small in-memory WAV file"""
    buffer = io.BytesIO()
    data = np.sin(np.linspace(0, 100, 24000)).astype(np.float32) * 0.5
    sf.write(buffer, data, 24000, format='WAV', subtype=subtype)
    return buffer.getvalue()


def split_into_chunks(payload: bytes, chunk_size: int) -> list[bytes]:
    return [payload[i:i + chunk_size] for i in range(0, len(payload), chunk_size)]


@pytest.fixture
def first_line_options() -> SynthesizationOptions:
    return SynthesizationOptions(aggro=False, is_first_line_of_response=True, stream_first_line=True)


@pytest.fixture
def fake_sounddevice(monkeypatch) -> MagicMock:
    fake_sd = MagicMock()
    monkeypatch.setitem(sys.modules, 'sounddevice', fake_sd)
    return fake_sd
