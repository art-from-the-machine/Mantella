import io
import sys
import time
import pytest
import requests
import soundfile as sf
from pathlib import Path
from unittest.mock import MagicMock
from src.config.config_loader import ConfigLoader
from src.tts.openai_compatible import OpenAICompatibleTTS
from src.tts.synthesization_options import SynthesizationOptions
from tests.tts.conftest import FakeResponse, FakeStreamingResponse, make_wav_bytes, split_into_chunks


@pytest.fixture
def openai_tts(default_config: ConfigLoader, monkeypatch) -> OpenAICompatibleTTS:
    monkeypatch.setattr(requests.Session, 'get', lambda self, *args, **kwargs: FakeResponse())
    return OpenAICompatibleTTS(default_config)


@pytest.fixture
def synth_options() -> SynthesizationOptions:
    return SynthesizationOptions(aggro=False, is_first_line_of_response=True)


class TestConstructor:

    def test_survives_unreachable_server(self, default_config: ConfigLoader, monkeypatch):
        def raise_connection_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError('server down')
        monkeypatch.setattr(requests.Session, 'get', raise_connection_error)
        tts = OpenAICompatibleTTS(default_config)
        assert tts is not None

    def test_synthesize_url_from_base_url(self, openai_tts: OpenAICompatibleTTS, default_config: ConfigLoader):
        expected = f'{default_config.openai_tts_url}/v1/audio/speech'
        assert openai_tts._OpenAICompatibleTTS__synthesize_url == expected

    def test_url_ending_in_v1_is_not_doubled(self, default_config: ConfigLoader, monkeypatch):
        monkeypatch.setattr(requests.Session, 'get', lambda self, *args, **kwargs: FakeResponse())
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
        def fake_post(self, url, json=None, headers=None, timeout=None):
            captured['url'] = url
            captured['json'] = json
            captured['headers'] = headers
            return FakeResponse(content=make_wav_bytes())
        monkeypatch.setattr(requests.Session, 'post', fake_post)
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
        monkeypatch.setattr(requests.Session, 'post', lambda self, *args, **kwargs: FakeResponse(content=make_wav_bytes(subtype='FLOAT')))
        openai_tts.change_voice('MaleEvenToned')

        output_file = str(tmp_path / 'out.wav')
        openai_tts.tts_synthesize('Hello there.', output_file, synth_options)

        info = sf.info(output_file)
        assert info.subtype == 'PCM_16'
        assert info.frames > 0

    def test_writes_raw_response_when_reencode_fails(self, openai_tts: OpenAICompatibleTTS, synth_options: SynthesizationOptions, tmp_path: Path, monkeypatch):
        wav_bytes = make_wav_bytes(subtype='PCM_16')
        monkeypatch.setattr(requests.Session, 'post', lambda self, *args, **kwargs: FakeResponse(content=wav_bytes))
        def raise_error(*args, **kwargs):
            raise RuntimeError('unsupported header')
        monkeypatch.setattr(openai_tts, '_convert_to_16bit', raise_error)
        openai_tts.change_voice('MaleEvenToned')

        output_file = str(tmp_path / 'out.wav')
        openai_tts.tts_synthesize('Hello there.', output_file, synth_options)

        assert Path(output_file).read_bytes() == wav_bytes

    def test_non_200_writes_no_file(self, openai_tts: OpenAICompatibleTTS, synth_options: SynthesizationOptions, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(requests.Session, 'post', lambda self, *args, **kwargs: FakeResponse(status_code=400, text='voice not found'))
        openai_tts.change_voice('UnknownVoice')

        output_file = str(tmp_path / 'out.wav')
        openai_tts.tts_synthesize('Hello there.', output_file, synth_options)

        assert not Path(output_file).exists()

    def test_connection_error_writes_no_file(self, openai_tts: OpenAICompatibleTTS, synth_options: SynthesizationOptions, tmp_path: Path, monkeypatch):
        def raise_connection_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError('server down')
        monkeypatch.setattr(requests.Session, 'post', raise_connection_error)
        openai_tts.change_voice('MaleEvenToned')

        output_file = str(tmp_path / 'out.wav')
        openai_tts.tts_synthesize('Hello there.', output_file, synth_options)

        assert not Path(output_file).exists()


@pytest.fixture
def streaming_tts(default_config: ConfigLoader, monkeypatch) -> OpenAICompatibleTTS:
    monkeypatch.setattr(requests.Session, 'get', lambda self, *args, **kwargs: FakeResponse())
    tts = OpenAICompatibleTTS(default_config)
    tts.change_voice('MaleEvenToned')
    return tts


class TestStreamedSynthesis:
    def test_streams_and_writes_pcm16_wav(self, streaming_tts: OpenAICompatibleTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        wav_bytes = make_wav_bytes(subtype='PCM_16')
        captured = {}
        def fake_post(self, url, json=None, headers=None, stream=False, timeout=None):
            captured['stream'] = stream
            captured['json'] = json
            return FakeStreamingResponse(split_into_chunks(wav_bytes, 1000))
        monkeypatch.setattr(requests.Session, 'post', fake_post)

        output_file = str(tmp_path / 'out.wav')
        streaming_tts.tts_synthesize('Hello there.', output_file, first_line_options)

        assert captured['stream'] is True
        assert captured['json']['response_format'] == 'wav'
        info = sf.info(output_file)
        assert info.subtype == 'PCM_16'
        assert info.samplerate == 24000
        assert info.frames == sf.info(io.BytesIO(wav_bytes)).frames
        for _ in range(100):
            if fake_sounddevice.OutputStream.called:
                break
            time.sleep(0.01)
        fake_sounddevice.OutputStream.assert_called_once_with(samplerate=24000, channels=1, dtype='float32')

    def test_header_split_across_chunks(self, streaming_tts: OpenAICompatibleTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        wav_bytes = make_wav_bytes(subtype='PCM_16')
        monkeypatch.setattr(requests.Session, 'post', lambda self, *args, **kwargs: FakeStreamingResponse(split_into_chunks(wav_bytes, 7)))

        output_file = str(tmp_path / 'out.wav')
        streaming_tts.tts_synthesize('Hello there.', output_file, first_line_options)

        assert sf.info(output_file).frames == sf.info(io.BytesIO(wav_bytes)).frames

    def test_streaming_skipped_when_not_requested(self, streaming_tts: OpenAICompatibleTTS, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        captured = {}
        def fake_post(self, url, json=None, headers=None, stream=False, timeout=None):
            captured['stream'] = stream
            return FakeResponse(content=make_wav_bytes())
        monkeypatch.setattr(requests.Session, 'post', fake_post)
        options = SynthesizationOptions(aggro=False, is_first_line_of_response=True, stream_first_line=False)

        streaming_tts.tts_synthesize('Hello there.', str(tmp_path / 'out.wav'), options)

        assert captured['stream'] is False

    def test_streaming_request_ignored_when_service_does_not_support_it(self, streaming_tts: OpenAICompatibleTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(OpenAICompatibleTTS, 'supports_streaming', False)
        captured = {}
        def fake_post(self, url, json=None, headers=None, stream=False, timeout=None):
            captured['stream'] = stream
            return FakeResponse(content=make_wav_bytes())
        monkeypatch.setattr(requests.Session, 'post', fake_post)

        played_externally = streaming_tts.tts_synthesize('Hello there.', str(tmp_path / 'out.wav'), first_line_options)

        assert captured['stream'] is False
        assert played_externally is False

    def test_falls_back_and_plays_externally_when_sounddevice_missing(self, streaming_tts: OpenAICompatibleTTS, first_line_options: SynthesizationOptions, tmp_path: Path, monkeypatch):
        monkeypatch.setitem(sys.modules, 'sounddevice', None)
        monkeypatch.setattr(requests.Session, 'post', lambda self, *args, **kwargs: FakeResponse(content=make_wav_bytes()))
        played = []
        monkeypatch.setattr(streaming_tts, '_play_wav_async', lambda filename: played.append(filename))

        output_file = str(tmp_path / 'out.wav')
        streaming_tts.tts_synthesize('Hello there.', output_file, first_line_options)

        assert Path(output_file).exists()
        assert played == [output_file]

    def test_falls_back_on_streaming_server_error(self, streaming_tts: OpenAICompatibleTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        calls = []
        def fake_post(self, url, json=None, headers=None, stream=False, timeout=None):
            calls.append(stream)
            if stream:
                return FakeStreamingResponse([], status_code=500, text='server error')
            return FakeResponse(content=make_wav_bytes())
        monkeypatch.setattr(requests.Session, 'post', fake_post)
        played = []
        monkeypatch.setattr(streaming_tts, '_play_wav_async', lambda filename: played.append(filename))

        output_file = str(tmp_path / 'out.wav')
        streaming_tts.tts_synthesize('Hello there.', output_file, first_line_options)

        assert calls == [True, False]
        assert Path(output_file).exists()
        assert played == [output_file]

    def test_interrupted_stream_writes_partial_file(self, streaming_tts: OpenAICompatibleTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        wav_bytes = make_wav_bytes(subtype='PCM_16')
        chunks = split_into_chunks(wav_bytes, 1000)
        def interrupted_chunks():
            yield chunks[0]
            yield chunks[1]
            raise requests.exceptions.ChunkedEncodingError('connection lost')
        fake_response = FakeStreamingResponse([])
        fake_response.iter_content = lambda chunk_size: interrupted_chunks()
        monkeypatch.setattr(requests.Session, 'post', lambda self, *args, **kwargs: fake_response)

        output_file = str(tmp_path / 'out.wav')
        streaming_tts.tts_synthesize('Hello there.', output_file, first_line_options)

        info = sf.info(output_file)
        assert info.subtype == 'PCM_16'
        assert 0 < info.frames < sf.info(io.BytesIO(wav_bytes)).frames

    def test_played_externally_true_after_streaming(self, streaming_tts: OpenAICompatibleTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        wav_bytes = make_wav_bytes(subtype='PCM_16')
        monkeypatch.setattr(requests.Session, 'post', lambda self, *args, **kwargs: FakeStreamingResponse(split_into_chunks(wav_bytes, 1000)))

        played_externally = streaming_tts.tts_synthesize('Hello there.', str(tmp_path / 'out.wav'), first_line_options)

        assert played_externally is True

    def test_played_externally_true_on_fallback(self, streaming_tts: OpenAICompatibleTTS, first_line_options: SynthesizationOptions, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        def fake_post(self, url, json=None, headers=None, stream=False, timeout=None):
            if stream:
                return FakeStreamingResponse([], status_code=500, text='server error')
            return FakeResponse(content=make_wav_bytes())
        monkeypatch.setattr(requests.Session, 'post', fake_post)
        monkeypatch.setattr(streaming_tts, '_play_wav_async', lambda filename: None)

        played_externally = streaming_tts.tts_synthesize('Hello there.', str(tmp_path / 'out.wav'), first_line_options)

        assert played_externally is True

    def test_played_externally_false_when_not_streamed(self, streaming_tts: OpenAICompatibleTTS, fake_sounddevice: MagicMock, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(requests.Session, 'post', lambda self, *args, **kwargs: FakeResponse(content=make_wav_bytes()))
        options = SynthesizationOptions(aggro=False, is_first_line_of_response=True, stream_first_line=False)

        played_externally = streaming_tts.tts_synthesize('Hello there.', str(tmp_path / 'out.wav'), options)

        assert played_externally is False

    def test_stop_external_playback_exits_worker_early(self, streaming_tts: OpenAICompatibleTTS, first_line_options: SynthesizationOptions, tmp_path: Path, monkeypatch):
        wav_bytes = make_wav_bytes(subtype='PCM_16')
        writes = []

        class FakeStream:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def write(self, samples):
                writes.append(len(samples))
                # Simulate the player interrupting right after the first chunk is written
                streaming_tts.stop_external_playback()

        fake_sd = MagicMock()
        fake_sd.OutputStream.return_value = FakeStream()
        monkeypatch.setitem(sys.modules, 'sounddevice', fake_sd)
        # Split into many small chunks so more than one write would happen if playback was not stopped
        monkeypatch.setattr(requests.Session, 'post', lambda self, *args, **kwargs: FakeStreamingResponse(split_into_chunks(wav_bytes, 500)))

        output_file = str(tmp_path / 'out.wav')
        streaming_tts.tts_synthesize('Hello there.', output_file, first_line_options)

        for _ in range(100):
            if writes:
                break
            time.sleep(0.01)
        time.sleep(0.05)
        assert len(writes) == 1
        # The downloader keeps saving the complete wav regardless of playback being stopped
        assert Path(output_file).exists()
