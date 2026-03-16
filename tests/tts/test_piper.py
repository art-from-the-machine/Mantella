import pytest
import os
from unittest.mock import MagicMock, patch
from queue import Queue
from src.tts.piper import Piper, TTSServiceFailure
from src.tts.synthesization_options import SynthesizationOptions


def _fast_time():
    """Yield ever-increasing timestamps so time-based polling loops exit immediately."""
    t = 0.0
    while True:
        yield t
        t += 100.0


def _make_mock_piper():
    """Create a minimal mock Piper instance without calling __init__"""
    piper = object.__new__(Piper)
    piper._Piper__selected_voice = 'testvoice'
    piper._Piper__waiting_for_voice_load = False
    piper._Piper__models_path = MagicMock()
    piper._loglevel = 20
    piper._last_voice = None
    piper.process = MagicMock()
    piper.process.poll.return_value = None
    piper.process.stdin = MagicMock()
    piper.q = Queue()
    piper.t = MagicMock()
    piper.stop_thread = False
    return piper


def test_check_voice_changed_returns_true_on_model_loaded():
    """_check_voice_changed returns True when queue contains 'Model loaded'"""
    piper = _make_mock_piper()
    piper._Piper__waiting_for_voice_load = True
    piper.q.put("Model loaded successfully")

    result = piper._check_voice_changed(max_retries=0)
    assert result is True
    assert piper._Piper__waiting_for_voice_load is False


def test_check_voice_changed_returns_false_after_retries():
    """_check_voice_changed returns False when model never loads"""
    piper = _make_mock_piper()
    piper._Piper__waiting_for_voice_load = True

    with patch.object(piper, '_restart_piper'), \
         patch('src.tts.piper.time.sleep'), \
         patch('src.tts.piper.time.time', side_effect=_fast_time()):
        result = piper._check_voice_changed(max_retries=0)

    assert result is False
    assert piper._Piper__waiting_for_voice_load is False


def test_synthesize_raises_after_all_attempts(tmp_path):
    """tts_synthesize raises TTSServiceFailure when synthesis never produces a file"""
    piper = _make_mock_piper()
    synth_options = SynthesizationOptions(aggro=False, is_first_line_of_response=False)
    output_file = str(tmp_path / 'out.wav')

    with patch.object(piper, '_restart_piper'), \
         patch.object(piper, 'change_voice'), \
         patch.object(piper, '_check_voice_changed', return_value=True), \
         patch('src.tts.piper.time.sleep'), \
         patch('src.tts.piper.time.time', side_effect=_fast_time()):
        with pytest.raises(TTSServiceFailure, match="failed after"):
            piper.tts_synthesize('Hello.', output_file, synth_options)


def test_synthesize_strips_newlines(tmp_path):
    """Newlines and carriage returns are stripped before being sent to Piper stdin"""
    piper = _make_mock_piper()
    synth_options = SynthesizationOptions(aggro=False, is_first_line_of_response=False)
    output_file = str(tmp_path / 'out.wav')

    written_lines = []
    piper.process.stdin.write = lambda text: written_lines.append(text)

    with patch.object(piper, '_restart_piper'), \
         patch.object(piper, 'change_voice'), \
         patch.object(piper, '_check_voice_changed', return_value=True), \
         patch('src.tts.piper.time.sleep'), \
         patch('src.tts.piper.time.time', side_effect=_fast_time()):
        with pytest.raises(TTSServiceFailure):
            piper.tts_synthesize("Hello\nworld\r!", output_file, synth_options)

    # Every write call should have exactly one newline (the command terminator), no embedded newlines
    for line in written_lines:
        payload = line.rstrip('\n')
        assert '\n' not in payload
        assert '\r' not in payload


@pytest.mark.requires_external_exe
def test_piper_model_retrieval(piper: Piper):
    '''Test that at least the base Skyrim models are available'''
    assert len(piper._Piper__available_models) >= 68


@pytest.mark.requires_external_exe
def test_select_voice_type(piper: Piper):
    basic_voice_search = piper._select_voice_type(
        voice = 'maleeventoned',
        in_game_voice = None,
        csv_in_game_voice = None,
        advanced_voice_model = None,
        voice_gender = None,
        voice_race = None
    )
    assert basic_voice_search == 'maleeventoned'

    heirarchy_voice_search = piper._select_voice_type(
        voice = 'ignore',
        in_game_voice = 'ignore',
        csv_in_game_voice = 'ignore',
        advanced_voice_model = 'maleeventoned',
        voice_gender = None,
        voice_race = None
    )
    assert heirarchy_voice_search == 'maleeventoned'

    unknown_voice_search = piper._select_voice_type(
        voice = '',
        in_game_voice = '',
        csv_in_game_voice = None,
        advanced_voice_model = None,
        voice_gender = 1,
        voice_race = 'Argonian'
    )
    assert unknown_voice_search == 'femaleargonian'

    unknown_voice_race_gender_search = piper._select_voice_type(
        voice = '',
        in_game_voice = '',
        csv_in_game_voice = None,
        advanced_voice_model = None,
        voice_gender = None,
        voice_race = None
    )
    assert unknown_voice_race_gender_search == 'malenord'


@pytest.mark.requires_external_exe
def test_voice_models(piper: Piper):
    '''Test that voice models can be loaded and voicelines synthesized'''
    count = 0
    num_models_to_check = 10 # Limit the number of models to load or we'll be here all day
    synth_options = SynthesizationOptions(0, 0)

    assert len(piper._Piper__available_models) >= 1, "No available voice models found for testing."

    for voice_model in piper._Piper__available_models:
        piper.change_voice(voice_model)
        piper._check_voice_changed()
        assert piper._Piper__selected_voice == voice_model

        voiceline_path = f'{piper._voiceline_folder}/out.wav'
        piper.tts_synthesize('Hello.', voiceline_path, synth_options)
        assert os.path.exists(voiceline_path)
        # Optionally, play the synthesized voiceline:
        # winsound.PlaySound(voiceline_path, winsound.SND_FILENAME)

        # Voicelines are normally saved to individual files, but in this case just delete the existing file for the next run
        os.remove(voiceline_path)

        if count >= num_models_to_check:
            break
        count += 1