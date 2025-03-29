from src.games.skyrim import skyrim as Skyrim
import pytest
from src.config.config_loader import ConfigLoader
from src.llm.sentence import sentence as Sentence
from src.llm.sentence_content import sentence_content as SentenceContent
from src.llm.sentence_content import SentenceTypeEnum
from src.games.external_character_info import external_character_info
from src.character_manager import Character
import shutil
import os

# TODO: Test __apply_character_overrides

@pytest.fixture
def skyrim(tmp_path, default_config: ConfigLoader):
    # Change folders where character overrides are searched in
    default_config.mod_path_base = str(tmp_path)
    default_config.save_folder = str(tmp_path)
    
    return Skyrim(default_config)


def test_skyrim_properties(skyrim: Skyrim):
    """Test the basic properties of the skyrim class"""
    assert skyrim.extender_name == 'SKSE'
    assert skyrim.game_name_in_filepath == 'skyrim'


def test_modify_sentence_text_for_game(skyrim: Skyrim):
    """Test text modification for Skyrim's character limit"""
    # Test with short text (under limit)
    short_text = "This is a short sentence."
    assert skyrim.modify_sentence_text_for_game(short_text) == short_text
    
    # Test with text exactly at the limit
    exact_text = "x" * 500
    assert skyrim.modify_sentence_text_for_game(exact_text) == exact_text
    
    # Test with text over the limit
    long_text = "x" * 600
    expected = ("x" * 497) + "..."
    assert skyrim.modify_sentence_text_for_game(long_text) == expected
    assert len(skyrim.modify_sentence_text_for_game(long_text)) == 500


def test_is_sentence_allowed(skyrim: Skyrim):
    """Test sentence filtering logic"""
    # 'assist' keyword should be filtered out if not first sentence
    assert skyrim.is_sentence_allowed("I will assist you with that.", 1) == False
    assert skyrim.is_sentence_allowed("I will assist you with that.", 0) == True
    
    # Normal sentences should be allowed
    assert skyrim.is_sentence_allowed("Hello there!", 0) == True
    assert skyrim.is_sentence_allowed("How are you today?", 1) == True


def test_find_best_voice_model(skyrim: Skyrim):
    """Test voice model selection logic"""
    # Test with a Nord male
    nord_voice = skyrim.find_best_voice_model(actor_race='[Race <NordRace (00013746)>]', actor_sex=0, ingame_voice_model='MaleNord')
    assert nord_voice == "MaleNord"
    
    # Test with a High Elf female
    high_elf_voice = skyrim.find_best_voice_model(actor_race="[Race <HighElfRace (12345678)>]", actor_sex=1, ingame_voice_model="FemaleElfHaughty")
    assert high_elf_voice == "FemaleElfHaughty"
    
    # Test with unknown race (should default to Nord)
    unknown_voice = skyrim.find_best_voice_model(actor_race="Unknown Race", actor_sex=0, ingame_voice_model="Unknown")
    assert unknown_voice == "Male Nord" # Default model names have spaces for readability, but are parsed without spaces


def test_dictionary_match(skyrim: Skyrim):
    """Test the dictionary_match method for voice model mapping"""
    # Test with valid race/sex combinations
    assert skyrim.dictionary_match(
        female_voice_model_dictionary=skyrim.FEMALE_VOICE_MODELS_XVASYNTH, 
        male_voice_model_dictionary=skyrim.MALE_VOICE_MODELS_XVASYNTH, 
        actor_race="Imperial", 
        actor_sex=0
    ) == "Male Even Toned"
    
    assert skyrim.dictionary_match(
        female_voice_model_dictionary=skyrim.FEMALE_VOICE_MODELS_XVASYNTH, 
        male_voice_model_dictionary=skyrim.MALE_VOICE_MODELS_XVASYNTH, 
        actor_race="Khajiit", 
        actor_sex=1
    ) == "Female Khajiit"
    
    # Test with invalid race (should default to Nord)
    assert skyrim.dictionary_match(
        female_voice_model_dictionary=skyrim.FEMALE_VOICE_MODELS_XVASYNTH, 
        male_voice_model_dictionary=skyrim.MALE_VOICE_MODELS_XVASYNTH, 
        actor_race="Unknown", 
        actor_sex=1
    ) == "Female Nord"
    
    # Test with None values (should default to Nord)
    assert skyrim.dictionary_match(
        female_voice_model_dictionary=skyrim.FEMALE_VOICE_MODELS_XVASYNTH, 
        male_voice_model_dictionary=skyrim.MALE_VOICE_MODELS_XVASYNTH, 
        actor_race=None, 
        actor_sex=None
    ) == "Male Nord"


def test_get_weather_description(skyrim: Skyrim):
    """Test weather description retrieval"""
    # Test with valid weather ID
    weather_attrs = {skyrim.KEY_CONTEXT_WEATHER_ID: "1113848"}
    assert skyrim.get_weather_description(weather_attrs) == "In Sovngarde, the sky is choked with ominous clouds, swirling as if the heavens themselves are brooding, casting the land in a perpetual twilight."
    
    # Test with valid weather classification
    weather_attrs = {skyrim.KEY_CONTEXT_WEATHER_CLASSIFICATION: 0}
    assert skyrim.get_weather_description(weather_attrs) == skyrim.WEATHER_CLASSIFICATIONS[0]
    
    # Test with empty attributes
    weather_attrs = {}
    assert skyrim.get_weather_description(weather_attrs) == ""


def test_load_external_character_info(skyrim: Skyrim):
    """Test loading external character info"""
    # Test with a character that should be found in the CSV
    info = skyrim.load_external_character_info(
        base_id='0A2C8E', 
        name='Lydia', 
        race='[Race <NordRace (00013746)>]', 
        gender=1, 
        ingame_voice_model='[VoiceType <FemaleEvenToned (00013ADD)>]'
    )
    assert isinstance(info, external_character_info)
    assert info.name == "Lydia"
    assert info.is_generic_npc == False
    assert info.ingame_voice_model == "FemaleEvenToned"
    assert info.tts_voice_model == "FemaleEvenToned"
    assert info.csv_in_game_voice_model == "FemaleEvenToned"
    assert info.advanced_voice_model == "LydiaUniqueReworked"
    assert info.voice_accent == "en"
    assert "I am sworn to carry your burdens" in info.bio
    
    # Test with a character that should not be found in the CSV (generic NPC)
    info = skyrim.load_external_character_info(
        base_id='unknown', 
        name='Unknown Character', 
        race='[Race <NordRace (00013746)>]', 
        gender=0, 
        ingame_voice_model='[VoiceType <MaleNord (12345678)>]'
    )
    assert isinstance(info, external_character_info)
    assert info.name == "Unknown Character"
    assert info.is_generic_npc == True
    assert info.ingame_voice_model == "MaleNord"
    assert info.tts_voice_model == "MaleNord"
    assert info.csv_in_game_voice_model == "MaleNord"
    assert info.advanced_voice_model == ""
    assert info.voice_accent == "en"
    assert info.bio == "You are a male Nord Unknown Character."


def test_prepare_sentence_for_game(tmp_path, skyrim: Skyrim, default_config: ConfigLoader, example_skyrim_npc_character: Character):
    """Test that prepare_sentence_for_game correctly processes audio files based on configuration"""
    default_config.save_audio_data_to_character_folder = False
    default_config.fast_response_mode = False

    # Create sentence content with the test NPC
    example_sentence_content = SentenceContent(
        speaker = example_skyrim_npc_character,
        text = 'Hello there.',
        sentence_type = SentenceTypeEnum.SPEECH,
    )

    # Copy an existing audio file for the sake of testing
    # Ignore the .lip file as it is can be skipped
    test_audio_path = os.path.join(tmp_path, "test_audio.wav")
    shutil.copyfile('data/mantella_ready.wav', test_audio_path)

    # Create sentence
    example_sentence = Sentence(
        content = example_sentence_content,
        voice_file = test_audio_path,
        voice_line_duration = 1.0,
        error_message = None,
    )

    # Configure mod path for testing
    default_config.mod_path = str(os.path.join(tmp_path, f"Sound/Voice/Mantella.esp"))
    mantella_voice_folder = os.path.join(tmp_path, f"Sound/Voice/Mantella.esp/{skyrim.MANTELLA_VOICE_FOLDER}")
    os.makedirs(mantella_voice_folder, exist_ok=True)

    # Test 1: Default behavior with topicID 1    
    skyrim.prepare_sentence_for_game(
        queue_output = example_sentence, 
        context_of_conversation = None, 
        config = default_config, 
        topicID = 1, 
        isFirstLine = False,
    )
    
    # Verify the correct file path and name for topicID 1
    expected_wav_path = os.path.join(mantella_voice_folder, f"{skyrim.DIALOGUELINE1_FILENAME}.wav")
    assert os.path.exists(expected_wav_path)
    
    # Clean up for next test
    os.remove(expected_wav_path)
    
    # Test 2: Different topicID
    skyrim.prepare_sentence_for_game(
        queue_output = example_sentence, 
        context_of_conversation = None, 
        config = default_config,
        topicID = 2,
        isFirstLine = False,
    )
    
    # Verify different filename for topicID 2
    expected_wav_path_topic2 = os.path.join(mantella_voice_folder, f"{skyrim.DIALOGUELINE2_FILENAME}.wav")
    assert os.path.exists(expected_wav_path_topic2)
    
    # Clean up
    os.remove(expected_wav_path_topic2)

    # Test 3: Fast response mode
    default_config.fast_response_mode = True
    default_config.fast_response_mode_volume = 0

    skyrim.prepare_sentence_for_game(
        queue_output = example_sentence, 
        context_of_conversation = None, 
        config = default_config,
        topicID = 1,
        isFirstLine = True, # isFirstLine determines whether a fast response should play
    )
    
    # Verify the correct file path and name
    expected_wav_path = os.path.join(mantella_voice_folder, f"{skyrim.DIALOGUELINE1_FILENAME}.wav")
    assert os.path.exists(expected_wav_path)
    
    # Clean up
    os.remove(expected_wav_path)
    
    # Note: save_audio_data_to_character_folder is not tested as it may be deprecated
