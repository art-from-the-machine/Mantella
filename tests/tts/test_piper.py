import os
from src.tts.piper import Piper
from src.tts.synthesization_options import SynthesizationOptions

def test_piper_model_retrieval(piper: Piper):
    '''Test that at least the base Skyrim models are available'''
    assert len(piper._piper__available_models) >= 68


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


def test_voice_models(piper: Piper):
    '''Test that voice models can be loaded and voicelines synthesized'''
    count = 0
    num_models_to_check = 10
    synth_options = SynthesizationOptions(0, 0)

    for voice_model in piper._piper__available_models:
        piper.change_voice(voice_model)
        piper._check_voice_changed()
        assert piper._piper__selected_voice == voice_model

        voiceline_path = f'{piper._voiceline_folder}/out.wav'
        piper.tts_synthesize('Hello.', voiceline_path, synth_options)
        assert os.path.exists(voiceline_path)
        # winsound.PlaySound(voiceline_path, winsound.SND_FILENAME)

        # Voicelines are normally saved to individual files, but in this case just delete the existing file for the next run
        os.remove(voiceline_path)

        if count >= num_models_to_check:
            break
        count += 1