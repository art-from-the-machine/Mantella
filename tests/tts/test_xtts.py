import io
import pytest
import requests
import soundfile as sf
from pathlib import Path
from unittest.mock import MagicMock
from src.config.config_loader import ConfigLoader
from src.tts.xtts import XTTS
from src.tts.synthesization_options import SynthesizationOptions
from tests.tts.conftest import FakeResponse, FakeStreamingResponse, make_wav_bytes, split_into_chunks


class FakeXTTSServerResponse(FakeResponse):
    def __init__(self, speakers: list[str], status_code: int = 200):
        super().__init__(status_code=status_code)
        self.__speakers = speakers

    def json(self):
        return {'en': {'speakers': self.__speakers}}


@pytest.fixture
def streaming_xtts(default_config: ConfigLoader, monkeypatch) -> XTTS:
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: FakeXTTSServerResponse(['maleeventoned']))
    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: FakeResponse())
    tts = XTTS(default_config, None)
    tts.change_voice('Male Even Toned')
    return tts


class TestXTTSStreamedSynthesis:
    def test_streams_from_tts_stream_endpoint(self, streaming_xtts: XTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        wav_bytes = make_wav_bytes(subtype='PCM_16')
        captured = {}
        def fake_post(url, json=None, headers=None, stream=False, timeout=None):
            captured['url'] = url
            captured['json'] = json
            captured['stream'] = stream
            return FakeStreamingResponse(split_into_chunks(wav_bytes, 1000))
        monkeypatch.setattr(requests, 'post', fake_post)

        output_file = str(tmp_path / 'out.wav')
        streaming_xtts.tts_synthesize('Hello there.', output_file, first_line_options)

        assert captured['url'].endswith('/tts_stream')
        assert captured['stream'] is True
        assert captured['json'] == {
            'text': 'Hello there.',
            'speaker_wav': 'maleeventoned',
            'language': 'en',
            'accent': 'en',
        }
        info = sf.info(output_file)
        assert info.subtype == 'PCM_16'
        assert info.frames == sf.info(io.BytesIO(wav_bytes)).frames

    def test_falls_back_to_tts_to_audio_on_streaming_error(self, streaming_xtts: XTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        urls = []
        def fake_post(url, json=None, headers=None, stream=False, timeout=None):
            urls.append(url)
            if stream:
                return FakeStreamingResponse([], status_code=500, text='server error')
            return FakeResponse(content=make_wav_bytes())
        monkeypatch.setattr(requests, 'post', fake_post)
        played = []
        monkeypatch.setattr(streaming_xtts, '_play_wav_async', lambda filename: played.append(filename))

        output_file = str(tmp_path / 'out.wav')
        streaming_xtts.tts_synthesize('Hello there.', output_file, first_line_options)

        assert urls[0].endswith('/tts_stream')
        assert urls[1].endswith('/tts_to_audio/')
        assert Path(output_file).exists()
        assert played == [output_file]

    def test_normal_path_when_streaming_not_requested(self, streaming_xtts: XTTS, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        captured = {}
        def fake_post(url, json=None, headers=None, stream=False, timeout=None):
            captured['url'] = url
            captured['stream'] = stream
            return FakeResponse(content=make_wav_bytes())
        monkeypatch.setattr(requests, 'post', fake_post)
        options = SynthesizationOptions(aggro=False, is_first_line_of_response=True, stream_first_line=False)

        played_externally = streaming_xtts.tts_synthesize('Hello there.', str(tmp_path / 'out.wav'), options)

        assert captured['url'].endswith('/tts_to_audio/')
        assert captured['stream'] is False
        assert played_externally is False

    def test_played_externally_true_after_streaming(self, streaming_xtts: XTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        wav_bytes = make_wav_bytes(subtype='PCM_16')
        monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: FakeStreamingResponse(split_into_chunks(wav_bytes, 1000)))

        played_externally = streaming_xtts.tts_synthesize('Hello there.', str(tmp_path / 'out.wav'), first_line_options)

        assert played_externally is True

    def test_played_externally_true_on_fallback(self, streaming_xtts: XTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        def fake_post(url, json=None, headers=None, stream=False, timeout=None):
            if stream:
                return FakeStreamingResponse([], status_code=500, text='server error')
            return FakeResponse(content=make_wav_bytes())
        monkeypatch.setattr(requests, 'post', fake_post)
        monkeypatch.setattr(streaming_xtts, '_play_wav_async', lambda filename: None)

        played_externally = streaming_xtts.tts_synthesize('Hello there.', str(tmp_path / 'out.wav'), first_line_options)

        assert played_externally is True
