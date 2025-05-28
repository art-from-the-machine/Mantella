from src.games.fallout4 import Fallout4
import pytest
from src.config.config_loader import ConfigLoader
from src.llm.sentence import Sentence
from src.llm.sentence_content import SentenceContent
from src.llm.sentence_content import SentenceTypeEnum
from src.games.external_character_info import external_character_info
from src.character_manager import Character
from src.config.definitions.tts_definitions import TTSEnum
import shutil
import os
import json

@pytest.fixture
def fallout4(tmp_path, default_config: ConfigLoader):
    # Change folders where character overrides are searched in
    default_config.mod_path_base = str(tmp_path)
    default_config.save_folder = str(tmp_path)
    
    return Fallout4(default_config)


@pytest.fixture
def fallout4_test_config(tmp_path, default_config: ConfigLoader) -> ConfigLoader:
    """Configures default_config to use tmp_path for override lookups"""
    # Change folders where character overrides are searched in
    default_config.mod_path_base = str(tmp_path)
    default_config.save_folder = str(tmp_path)

    return default_config


def test_fallout4_properties(fallout4: Fallout4):
    """Test the basic properties of the Fallout 4 class"""
    assert fallout4.extender_name == 'F4SE'
    assert fallout4.game_name_in_filepath == 'fallout4'


def test_apply_character_overrides_json_add(tmp_path, fallout4_test_config: ConfigLoader):
    """Test adding a new character via a JSON override file"""
    new_char_data = {
        "name": "Test JSON Character", "base_id": "JSON001", "race": "Nord",
        "bio": "A character added via JSON override.", "voice_model": "TestVoice",
        "fallout4_voice_folder": "TestVoiceFolder", "advanced_voice_model": ""
    }

    override_dir = tmp_path / "data" / "fallout4" / "character_overrides"
    override_dir.mkdir(parents=True, exist_ok=True)
    override_file = override_dir / "test_json_add.json"

    with open(override_file, 'w') as f:
        json.dump(new_char_data, f)

    fallout4 = Fallout4(fallout4_test_config)

    # Check if the new character exists in the dataframe
    df = fallout4.character_df
    match = df[(df['name'] == "Test JSON Character") & (df['base_id'] == "JSON001")]

    assert not match.empty
    assert len(match) == 1
    assert match.iloc[0]['bio'] == "A character added via JSON override."
    assert match.iloc[0]['voice_model'] == "TestVoice"
    assert match.iloc[0]['fallout4_voice_folder'] == "TestVoiceFolder"
    assert match.iloc[0]['advanced_voice_model'] == ""


def test_apply_character_overrides_json_modify(tmp_path, fallout4_test_config: ConfigLoader):
    """Test modifying an existing character via a JSON override file"""
    override_data = {
        "name": "Blake Abernathy", "base_id": "06B4D3", "race": "Human",
        "bio": "This is the overridden bio for Blake.",
        "voice_model": "VoiceOverride"
    }

    override_dir = tmp_path / "data" / "fallout4" / "character_overrides"
    override_dir.mkdir(parents=True, exist_ok=True)
    override_file = override_dir / "test_json_modify.json"

    with open(override_file, 'w') as f:
        json.dump(override_data, f)

    fallout4 = Fallout4(fallout4_test_config)

    # Check if Blake's data was modified
    df = fallout4.character_df
    match = df.loc[df['base_id']=='06B4D3']

    assert not match.empty
    assert len(match) == 1
    assert match.iloc[0]['bio'] == "This is the overridden bio for Blake."
    assert match.iloc[0]['voice_model'] == "VoiceOverride"
    assert match.iloc[0]['fallout4_voice_folder'] == "MaleBoston" # Check unmodified field


def test_apply_character_overrides_csv_add(tmp_path, fallout4_test_config: ConfigLoader):
    """Test adding a new character via a CSV override file"""
    csv_header = "name,base_id,race,bio,voice_model,fallout4_voice_folder,advanced_voice_model"
    csv_data = "Test CSV Character,CSV001,MaleBoston,Added via CSV,TestCSVVoice,TestCSVFolder,"
    csv_content = f"{csv_header}\n{csv_data}"

    override_dir = tmp_path / "F4SE" / "Plugins" / "MantellaSoftware" / "data" / "fallout4" / "character_overrides"
    override_dir.mkdir(parents=True, exist_ok=True)
    override_file = override_dir / "test_csv_add.csv"

    with open(override_file, 'w') as f:
        f.write(csv_content)

    fallout4 = Fallout4(fallout4_test_config)

    # Check if the new character exists
    df = fallout4.character_df
    match = df[(df['name'] == "Test CSV Character") & (df['base_id'] == "CSV001")]

    assert not match.empty
    assert len(match) == 1
    assert match.iloc[0]['bio'] == "Added via CSV"
    assert match.iloc[0]['voice_model'] == "TestCSVVoice"
    assert match.iloc[0]['race'] == "MaleBoston"


def test_apply_character_overrides_csv_modify(tmp_path, fallout4_test_config: ConfigLoader):
    """Test modifying an existing character via a CSV override file"""
    csv_header = "name,base_id,race,bio,voice_model,fallout4_voice_folder,advanced_voice_model,voice_accent"
    csv_data = "Blake Abernathy,06B4D3,Human,Overridden Bio,VoiceOverride,MaleBoston,,en"
    csv_content = f"{csv_header}\n{csv_data}"

    override_dir = tmp_path / "F4SE" / "Plugins" / "MantellaSoftware" / "data" / "fallout4" / "character_overrides"
    override_dir.mkdir(parents=True, exist_ok=True)
    override_file = override_dir / "test_csv_modify.csv"

    with open(override_file, 'w') as f:
        f.write(csv_content)

    fallout4 = Fallout4(fallout4_test_config)

    # Check if character's data was modified
    df = fallout4.character_df
    match = df.loc[df['base_id']=='06B4D3']
    
    assert not match.empty
    assert len(match) == 1
    assert match.iloc[0]['bio'] == "Overridden Bio"
    assert match.iloc[0]['voice_model'] == "VoiceOverride"
    assert match.iloc[0]['fallout4_voice_folder'] == "MaleBoston"


def test_modify_sentence_text_for_game(fallout4: Fallout4):
    """Test text modification for Fallout 4's character limit"""
    # Test with short text (under limit)
    short_text = "This is a short sentence."
    assert fallout4.modify_sentence_text_for_game(short_text) == short_text
    
    # Test with text exactly at the limit
    exact_text = "x" * 148
    expected = "x" * 144 + "..."
    assert fallout4.modify_sentence_text_for_game(exact_text) == expected
    
    # Test with text over the limit
    long_text = "x" * 600
    expected = ("x" * 144) + "..."
    result = fallout4.modify_sentence_text_for_game(long_text)
    assert result == expected
    assert len(result.encode("utf-8")) <= 148

    # Test with multi-byte characters (emoji, each is 4 bytes in UTF-8)
    emoji_exact = "😊" * 37
    result = fallout4.modify_sentence_text_for_game(emoji_exact)
    assert len(result.encode("utf-8")) <= 148 # Ensure result does not exceed 148 bytes
    assert result.encode("utf-8").decode("utf-8") == result # Ensure result still decodes properly
    assert result.endswith("...") # Check that it ends with "..."

    # Test with multi-byte characters that are under the limit
    # 36 emojis produce 144 bytes (36 * 4 = 144) which is below 148, so should remain unchanged
    emoji_short = "😊" * 36
    assert fallout4.modify_sentence_text_for_game(emoji_short) == emoji_short


def test_find_best_voice_model(fallout4: Fallout4, default_config: ConfigLoader):
    """Test voice model selection logic"""
    # Test with a Human male
    voice = fallout4.find_best_voice_model(actor_race='[Race <HumanRace (00013746)>]', actor_sex=0, ingame_voice_model='[VoiceType <MaleEvenToned (00000000)>]')
    assert voice == "maleeventoned"
    
    # Test with a Human female
    voice = fallout4.find_best_voice_model(actor_race='[Race <HumanRace (00013746)>]', actor_sex=1, ingame_voice_model='[VoiceType <FemaleEvenToned (00000000)>]')
    assert voice == "femaleeventoned"
    
    # Test with unknown race (should default to maleboston)
    voice = fallout4.find_best_voice_model(actor_race="Unknown Race", actor_sex=0, ingame_voice_model="Unknown")
    assert voice == "maleboston"

    # Test where voice model ID in FO4_Voice_folder_XVASynth_matches.csv
    voice = fallout4.find_best_voice_model(actor_race='[Race <HumanRace (00013746)>]', actor_sex=1, ingame_voice_model='[VoiceType <Unknown (00077D1D)>]')
    assert voice == "femalebos01"

    # Test xVASynth substitutions
    default_config.tts_service = TTSEnum.XVASYNTH
    xvasynth_fallout4 = Fallout4(default_config)
    voice = xvasynth_fallout4.find_best_voice_model(actor_race='Unknown', actor_sex=0, ingame_voice_model='DLC01RobotCompanionMaleDefault')
    assert voice == "robot_assaultron"
    voice = xvasynth_fallout4.find_best_voice_model(actor_race='Unknown', actor_sex=0, ingame_voice_model='SynthGen1Male02')
    assert voice == "gen1synth01"


def test_dictionary_match(fallout4: Fallout4):
    """Test the dictionary_match method for voice model mapping"""
    # Test with valid race/sex combinations
    assert fallout4.dictionary_match(
        female_voice_model_dictionary=fallout4.FEMALE_VOICE_MODELS_XVASYNTH, 
        male_voice_model_dictionary=fallout4.MALE_VOICE_MODELS_XVASYNTH, 
        actor_race="Ghoul", 
        actor_sex=0
    ) == "maleghoul"
    
    assert fallout4.dictionary_match(
        female_voice_model_dictionary=fallout4.FEMALE_VOICE_MODELS_XVASYNTH, 
        male_voice_model_dictionary=fallout4.MALE_VOICE_MODELS_XVASYNTH, 
        actor_race="SuperMutant", 
        actor_sex=1
    ) == "supermutant"
    
    # Test with invalid race (should default to Boston)
    assert fallout4.dictionary_match(
        female_voice_model_dictionary=fallout4.FEMALE_VOICE_MODELS_XVASYNTH, 
        male_voice_model_dictionary=fallout4.MALE_VOICE_MODELS_XVASYNTH, 
        actor_race="Unknown", 
        actor_sex=1
    ) == "femaleboston"
    
    # Test with None values (should default to Nord)
    assert fallout4.dictionary_match(
        female_voice_model_dictionary=fallout4.FEMALE_VOICE_MODELS_XVASYNTH, 
        male_voice_model_dictionary=fallout4.MALE_VOICE_MODELS_XVASYNTH, 
        actor_race=None, 
        actor_sex=None
    ) == "maleboston"


def test_load_external_character_info(fallout4: Fallout4):
    """Test loading external character info"""
    # Test with a character that should be found in the CSV
    info = fallout4.load_external_character_info(
        base_id='439507', 
        name='Blake Abernathy', 
        race='[Race <HumanRace (00013746)>]', 
        gender=0, 
        ingame_voice_model='[VoiceType <MaleBoston (00023323)>]'
    )
    assert isinstance(info, external_character_info)
    assert info.name == 'Blake Abernathy'
    assert info.is_generic_npc == False
    assert info.ingame_voice_model == 'MaleBoston'
    assert info.tts_voice_model == 'MaleBoston'
    assert info.csv_in_game_voice_model == 'MaleBoston'
    assert 'Blake Abernathy is a man living and farming at Abernathy farm in 2287.' in info.bio
    
    # Test with a character that should not be found in the CSV (generic NPC)
    info = fallout4.load_external_character_info(
        base_id='unknown', 
        name='Unknown Character', 
        race='[Race <HumanRace (00013746)>]', 
        gender=0, 
        ingame_voice_model='[VoiceType <MaleBoston (00023323)>]'
    )
    assert isinstance(info, external_character_info)
    assert info.name == "Unknown Character"
    assert info.is_generic_npc == True
    assert info.ingame_voice_model == 'MaleBoston'
    assert info.tts_voice_model == 'maleboston'
    assert info.csv_in_game_voice_model == 'MaleBoston'
    assert info.bio == "You are a male Human Unknown Character."


def test_prepare_sentence_for_game(tmp_path, fallout4: Fallout4, default_config: ConfigLoader, example_fallout4_npc_character: Character):
    """Test that prepare_sentence_for_game correctly processes audio files based on configuration"""
    default_config.save_audio_data_to_character_folder = False # NOTE: This is not tested as it may be soon deprecated
    default_config.fast_response_mode = False

    # Create sentence content with the test NPC
    example_sentence_content = SentenceContent(
        speaker = example_fallout4_npc_character,
        text = 'Hello there.',
        sentence_type = SentenceTypeEnum.SPEECH,
    )

    # Copy an existing audio file for the sake of testing
    test_audio_path = os.path.join(tmp_path, "test_audio.wav")
    shutil.copyfile('data/mantella_ready.wav', test_audio_path)
    shutil.copyfile('data/Fallout4/placeholder/placeholder.lip', test_audio_path.replace('.wav','.lip'))
    shutil.copyfile('data/Fallout4/placeholder/placeholder.fuz', test_audio_path.replace('.wav','.fuz'))

    # Create sentence
    example_sentence = Sentence(
        content = example_sentence_content,
        voice_file = test_audio_path,
        voice_line_duration = 1.0,
        error_message = None,
    )

    # Configure mod path for testing
    default_config.mod_path = str(os.path.join(tmp_path, f"Sound/Voice/Mantella.esp"))
    mantella_voice_folder = os.path.join(tmp_path, f"Sound/Voice/Mantella.esp/{fallout4.MANTELLA_VOICE_FOLDER}")
    os.makedirs(mantella_voice_folder, exist_ok=True)

    # Test 1: Default behavior with topicID 1    
    fallout4.prepare_sentence_for_game(
        queue_output = example_sentence, 
        context_of_conversation = None, 
        config = default_config, 
        topicID = 1, 
        isFirstLine = False,
    )
    
    # Verify the correct file path and name for topicID 1
    expected_fuz_path = os.path.join(mantella_voice_folder, f"{fallout4.DIALOGUELINE1_FILENAME}.fuz")
    assert os.path.exists(expected_fuz_path)