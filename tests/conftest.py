import pytest
from src.characters_manager import Characters
from src.config.config_loader import ConfigLoader
from src.http.http_server import http_server
from src.http.routes.mantella_route import mantella_route
from src.ui.start_ui import StartUI
from src.http.routes.routeable import routeable
from fastapi.testclient import TestClient
from pathlib import Path
from src import utils
from src.config.definitions.game_definitions import GameEnum
from src.http.communication_constants import communication_constants as comm_consts
from src.http import models
from src.character_manager import Character
from src.games.skyrim import Skyrim
from src.tts.piper import Piper
from src.games.equipment import Equipment, EquipmentItem

@pytest.fixture
def default_config(tmp_path: Path) -> ConfigLoader:
    # Set up default config by passing path without a config.ini file already present
    default_config = ConfigLoader(mygame_folder_path=str(tmp_path), game_override=GameEnum.SKYRIM)

    # Load the actual config file
    # NOTE: This does not work with user-defined save folder paths
    my_games_folder = utils.get_my_games_directory(custom_user_folder='')
    actual_config = ConfigLoader(mygame_folder_path=my_games_folder)

    # Not all default values workout of the box
    # Override default config values with known paths from actual config
    default_ish_config = override_default_config_values(default_config, actual_config)

    return default_ish_config

def override_default_config_values(default_config: ConfigLoader, actual_config: ConfigLoader) -> ConfigLoader:
    """Override default config values with values from actual config for user-dependent values (eg folder paths)"""
    default_config.game = GameEnum.SKYRIM # default to Skyrim for testing
    default_config.piper_path = actual_config.piper_path # must be set to the Skyrim Piper folder
    default_config.xtts_server_path = actual_config.xtts_server_path
    default_config.xvasynth_path = actual_config.xvasynth_path

    return default_config

@pytest.fixture
def english_language_info() -> dict:
    return {'alpha2': 'en', 'language': 'English', 'hello': 'Hello'}

@pytest.fixture
def piper(default_config: ConfigLoader, skyrim: Skyrim):
    return Piper(default_config, skyrim)

@pytest.fixture
def server() -> http_server:
    """Create a test instance of http_server"""
    return http_server()

@pytest.fixture
def default_mantella_route(default_config: ConfigLoader, english_language_info: dict) -> mantella_route:
    return mantella_route(
        config=default_config, 
        stt_secret_key_file='STT_SECRET_KEY.txt', 
        image_secret_key_file='IMAGE_SECRET_KEY.txt', 
        secret_key_file='GPT_SECRET_KEY.txt', 
        language_info=english_language_info, 
        show_debug_messages=False
    )

@pytest.fixture
def real_routes(default_config: ConfigLoader, default_mantella_route: mantella_route) -> list[routeable]:
    """Create the actual routes that would be used in production"""
    default_config.auto_launch_ui=False
    ui = StartUI(default_config)

    return [default_mantella_route, ui]

@pytest.fixture
def production_like_client(server: http_server, real_routes: list[routeable]) -> TestClient:
    """Create a TestClient configured like production"""
    server._setup_routes(real_routes)
    return TestClient(server.app)


@pytest.fixture
def example_player_actor() -> models.Actor:
    return models.Actor(
        **{
            comm_consts.KEY_ACTOR_BASEID: 0,
            comm_consts.KEY_ACTOR_CUSTOMVALUES: {
                comm_consts.KEY_ACTOR_PC_DESCRIPTION: "",
                comm_consts.KEY_ACTOR_PC_VOICEPLAYERINPUT: False,
            },
            comm_consts.KEY_ACTOR_GENDER: 0,
            comm_consts.KEY_ACTOR_ISENEMY: False,
            comm_consts.KEY_ACTOR_ISINCOMBAT: False,
            comm_consts.KEY_ACTOR_ISPLAYER: True,
            comm_consts.KEY_ACTOR_NAME: "Prisoner",
            comm_consts.KEY_ACTOR_RACE: "[Race <NordRace (00013746)>]",
            comm_consts.KEY_ACTOR_REFID: 0,
            comm_consts.KEY_ACTOR_RELATIONSHIPRANK: 0,
            comm_consts.KEY_ACTOR_VOICETYPE: "[VoiceType <MaleEvenToned (00013AD2)>]",
            comm_consts.KEY_ACTOR_EQUIPMENT: {
                "body": "Iron Armor",
                "feet": "Iron Boots",
                "hands": "Iron Gauntlets",
                "head": "Iron Helmet",
                "righthand": "Iron War Axe",
            }
        }
    )

@pytest.fixture
def example_npc_actor() -> models.Actor:
    return models.Actor(
        **{
            comm_consts.KEY_ACTOR_BASEID: 0,
            comm_consts.KEY_ACTOR_CUSTOMVALUES: None,
            comm_consts.KEY_ACTOR_GENDER: 0,
            comm_consts.KEY_ACTOR_ISENEMY: False,
            comm_consts.KEY_ACTOR_ISINCOMBAT: False,
            comm_consts.KEY_ACTOR_ISPLAYER: False,
            comm_consts.KEY_ACTOR_NAME: "Guard",
            comm_consts.KEY_ACTOR_RACE: "[Race <ImperialRace (00013744)>]",
            comm_consts.KEY_ACTOR_REFID: 0,
            comm_consts.KEY_ACTOR_RELATIONSHIPRANK: 0,
            comm_consts.KEY_ACTOR_VOICETYPE: "[VoiceType <MaleEvenToned (00013AD2)>]",
            comm_consts.KEY_ACTOR_EQUIPMENT: {
                "body": "Iron Armor",
                "feet": "Iron Boots",
                "hands": "Iron Gauntlets",
                "head": "Iron Helmet",
                "righthand": "Iron War Axe",
            }
        }
    )

@pytest.fixture
def example_skyrim_player_character() -> Character:
    return Character(
        base_id = '000007',
        ref_id = '000014',
        name = 'Dragonborn',
        gender = 0,
        race = '[Race <NordRace (00013746)>]',
        is_player_character = True,
        bio = '',
        is_in_combat = False,
        is_enemy = False,
        relationship_rank = 0,
        is_generic_npc = False,
        ingame_voice_model = 'MaleEvenToned',
        tts_voice_model = 'MaleEvenToned',
        csv_in_game_voice_model = 'MaleEvenToned',
        advanced_voice_model = 'MaleEvenToned',
        voice_accent = 'en',
        equipment = Equipment({
            'body': EquipmentItem('Iron Armor'),
            'feet': EquipmentItem('Iron Boots'),
            'hands': EquipmentItem('Iron Gauntlets'),
            'head': EquipmentItem('Iron Helmet'),
            'righthand': EquipmentItem('Iron Sword'),
        }),
        custom_character_values = {'mantella_pc_description': '', 'mantella_pc_voiceplayerinput': False},
    )

@pytest.fixture
def example_skyrim_npc_character() -> Character:
    return Character(
        base_id = '0',
        ref_id = '0',
        name = 'Guard',
        gender = 0,
        race = '[Race <ImperialRace (00013744)>]',
        is_player_character = False,
        bio = 'You are a male Imperial Guard.',
        is_in_combat = False,
        is_enemy = False,
        relationship_rank = 0,
        is_generic_npc = True,
        ingame_voice_model = 'MaleEvenToned',
        tts_voice_model = 'MaleEvenToned',
        csv_in_game_voice_model = 'MaleEvenToned',
        advanced_voice_model = 'MaleEvenToned',
        voice_accent = 'en',
        equipment = None,
        custom_character_values = None,
    )

@pytest.fixture
def example_characters_pc_to_npc(example_skyrim_player_character: Character, example_skyrim_npc_character: Character) -> Characters:
    """Provides a Characters manager with the test character"""
    chars = Characters()
    chars.add_or_update_character(example_skyrim_player_character)
    chars.add_or_update_character(example_skyrim_npc_character)
    return chars

@pytest.fixture
def example_fallout4_npc_character() -> Character:
    return Character(
        base_id = '0',
        ref_id = '0',
        name = 'Guard',
        gender = 0,
        race = '[Race <HumanRace (00013746)>]',
        is_player_character = False,
        bio = 'You are a male Human Guard.',
        is_in_combat = False,
        is_enemy = False,
        relationship_rank = 0,
        is_generic_npc = True,
        ingame_voice_model = 'MaleBoston',
        tts_voice_model = 'MaleBoston',
        csv_in_game_voice_model = 'MaleBoston',
        advanced_voice_model = None,
        voice_accent = None,
        equipment = None,
        custom_character_values = None,
    )

@pytest.fixture
def example_start_conversation_request(example_player_actor: models.Actor, example_npc_actor: models.Actor) -> models.StartConversationRequest:
    return  models.StartConversationRequest(
        **{
            comm_consts.KEY_ACTORS: [
                example_player_actor,
                example_npc_actor,
            ],
            comm_consts.KEY_CONTEXT: {
                comm_consts.KEY_CONTEXT_INGAMEEVENTS: [],
                comm_consts.KEY_CONTEXT_LOCATION: "Skyrim",
                comm_consts.KEY_CONTEXT_TIME: 12
            },
            comm_consts.KEY_INPUTTYPE: comm_consts.KEY_INPUTTYPE_TEXT,
            comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_STARTCONVERSATION,
            comm_consts.KEY_STARTCONVERSATION_WORLDID: "Test1"
        }
    )

@pytest.fixture
def example_continue_conversation_request() -> models.ContinueConversationRequest:
    return models.ContinueConversationRequest(
        **{
            comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_CONTINUECONVERSATION,
            comm_consts.KEY_CONTINUECONVERSATION_TOPICINFOFILE: 1
        }
    )

@pytest.fixture
def example_player_input_textbox_request() -> models.PlayerInputRequest:
    return models.PlayerInputRequest(
        **{
            comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_PLAYERINPUT,
            comm_consts.KEY_REQUESTTYPE_PLAYERINPUT: 'Oi oi.'
        }
    )

@pytest.fixture
def example_player_input_textbox_goodbye_request() -> models.PlayerInputRequest:
    return models.PlayerInputRequest(
        **{
            comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_PLAYERINPUT,
            comm_consts.KEY_REQUESTTYPE_PLAYERINPUT: 'Goodbye.'
        }
    )

@pytest.fixture
def skyrim(tmp_path, default_config: ConfigLoader) -> Skyrim:
    # Change folders where character overrides are searched in
    default_config.mod_path_base = str(tmp_path)
    default_config.save_folder = str(tmp_path)
    
    return Skyrim(default_config)