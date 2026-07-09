import io
import pytest
import requests
import numpy as np
import soundfile as sf
from pathlib import Path
from src.config.config_loader import ConfigLoader
from src.tts.openai_compatible import OpenAICompatibleTTS
from src.tts.synthesization_options import SynthesizationOptions


class FakeResponse:
    def __init__(self, status_code: int = 200, content: bytes = b'', text: str = ''):
        self.status_code = status_code
        self.content = content
        self.text = text


def make_wav_bytes(subtype: str = 'FLOAT') -> bytes:
    """Build a small in-memory WAV file"""
    buffer = io.BytesIO()
    data = np.sin(np.linspace(0, 100, 24000)).astype(np.float32) * 0.5
    sf.write(buffer, data, 24000, format='WAV', subtype=subtype)
    return buffer.getvalue()


@pytest.fixture
def openai_tts(default_config: ConfigLoader, monkeypatch) -> OpenAICompatibleTTS:
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: FakeResponse())
    return OpenAICompatibleTTS(default_config)


@pytest.fixture
def synth_options() -> SynthesizationOptions:
    return SynthesizationOptions(aggro=False, is_first_line_of_response=True)


class TestConstructor:

    def test_survives_unreachable_server(self, default_config: ConfigLoader, monkeypatch):
        def raise_connection_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError('server down')
        monkeypatch.setattr(requests, 'get', raise_connection_error)
        tts = OpenAICompatibleTTS(default_config)
        assert tts is not None

    def test_synthesize_url_from_base_url(self, openai_tts: OpenAICompatibleTTS, default_config: ConfigLoader):
        expected = f'{default_config.openai_tts_url}/v1/audio/speech'
        assert openai_tts._OpenAICompatibleTTS__synthesize_url == expected

    def test_url_ending_in_v1_is_not_doubled(self, default_config: ConfigLoader, monkeypatch):
        monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: FakeResponse())
        default_config.openai_tts_url = 'http://127.0.0.1:8000/v1'
        tts = OpenAICompatibleTTS(default_config)
        assert tts._OpenAICompatibleTTS__synthesize_url == 'http://127.0.0.1:8000/v1/audio/speech'

    def test_local_url_uses_dummy_api_key(self, openai_tts: OpenAICompatibleTTS):
        assert openai_tts._OpenAICompatibleTTS__api_key == 'abc123'


class TestChangeVoice:

    def test_advanced_voice_model_takes_precedence(self, openai_tts: OpenAICompatibleTTS):
        openai_tts.change_voice('Male Nord', 'MaleEvenToned', 'MaleCondescending', 'Custom Voice')
        assert openai_tts._OpenAICompatibleTTS__voice == 'customvoice'

    def test_voice_used_when_advanced_voice_model_empty(self, openai_tts: OpenAICompatibleTTS):
        openai_tts.change_voice('Male Nord', 'MaleEvenToned', 'MaleCondescending', None)
        assert openai_tts._OpenAICompatibleTTS__voice == 'malenord'

    def test_empty_candidates_are_skipped(self, openai_tts: OpenAICompatibleTTS):
        openai_tts.change_voice('', 'MaleEvenToned', None, '  ')
        assert openai_tts._OpenAICompatibleTTS__voice == 'maleeventoned'

    def test_all_empty_candidates_leaves_voice_unchanged(self, openai_tts: OpenAICompatibleTTS):
        openai_tts.change_voice('', None, None, None)
        assert openai_tts._OpenAICompatibleTTS__voice == ''
        assert openai_tts._last_voice == ''

    def test_last_voice_holds_raw_candidate(self, openai_tts: OpenAICompatibleTTS):
        openai_tts.change_voice('Male Even Toned')
        assert openai_tts._last_voice == 'Male Even Toned'
        assert openai_tts._OpenAICompatibleTTS__voice == 'maleeventoned'


class TestTtsSynthesize:

    def test_sends_expected_payload_and_headers(self, openai_tts: OpenAICompatibleTTS, default_config: ConfigLoader, synth_options: SynthesizationOptions, tmp_path: Path, monkeypatch):
        captured = {}
        def fake_post(url, json=None, headers=None, timeout=None):
            captured['url'] = url
            captured['json'] = json
            captured['headers'] = headers
            return FakeResponse(content=make_wav_bytes())
        monkeypatch.setattr(requests, 'post', fake_post)
        openai_tts.change_voice('MaleEvenToned')

        output_file = str(tmp_path / 'out.wav')
        openai_tts.tts_synthesize('Hello there.', output_file, synth_options)

        assert captured['url'] == f'{default_config.openai_tts_url}/v1/audio/speech'
        assert captured['json'] == {
            'model': default_config.openai_tts_model,
            'input': 'Hello there.',
            'voice': 'maleeventoned',
            'response_format': 'wav',
            'speed': default_config.openai_tts_speed,
        }
        assert captured['headers'] == {'Authorization': 'Bearer abc123'}

    def test_writes_pcm16_wav(self, openai_tts: OpenAICompatibleTTS, synth_options: SynthesizationOptions, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: FakeResponse(content=make_wav_bytes(subtype='FLOAT')))
        openai_tts.change_voice('MaleEvenToned')

        output_file = str(tmp_path / 'out.wav')
        openai_tts.tts_synthesize('Hello there.', output_file, synth_options)

        info = sf.info(output_file)
        assert info.subtype == 'PCM_16'
        assert info.frames > 0

    def test_writes_raw_response_when_reencode_fails(self, openai_tts: OpenAICompatibleTTS, synth_options: SynthesizationOptions, tmp_path: Path, monkeypatch):
        wav_bytes = make_wav_bytes(subtype='PCM_16')
        monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: FakeResponse(content=wav_bytes))
        def raise_error(*args, **kwargs):
            raise RuntimeError('unsupported header')
        monkeypatch.setattr(openai_tts, '_convert_to_16bit', raise_error)
        openai_tts.change_voice('MaleEvenToned')

        output_file = str(tmp_path / 'out.wav')
        openai_tts.tts_synthesize('Hello there.', output_file, synth_options)

        assert Path(output_file).read_bytes() == wav_bytes

    def test_non_200_writes_no_file(self, openai_tts: OpenAICompatibleTTS, synth_options: SynthesizationOptions, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: FakeResponse(status_code=400, text='voice not found'))
        openai_tts.change_voice('UnknownVoice')

        output_file = str(tmp_path / 'out.wav')
        openai_tts.tts_synthesize('Hello there.', output_file, synth_options)

        assert not Path(output_file).exists()

    def test_connection_error_writes_no_file(self, openai_tts: OpenAICompatibleTTS, synth_options: SynthesizationOptions, tmp_path: Path, monkeypatch):
        def raise_connection_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError('server down')
        monkeypatch.setattr(requests, 'post', raise_connection_error)
        openai_tts.change_voice('MaleEvenToned')

        output_file = str(tmp_path / 'out.wav')
        openai_tts.tts_synthesize('Hello there.', output_file, synth_options)

        assert not Path(output_file).exists()
