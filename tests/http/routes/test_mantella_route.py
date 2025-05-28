from src.http.routes.mantella_route import mantella_route
import pytest
from fastapi.testclient import TestClient
from src.config.definitions.game_definitions import GameEnum
from src.config.definitions.tts_definitions import TTSEnum
from src.config.config_loader import ConfigLoader
from src.http.communication_constants import communication_constants as comm_consts
from src.conversation import conversation as conv_module
import jsonschema
from src.http import models

def setup_mantella_conversation(
        client: TestClient, 
        start_request: models.StartConversationRequest, 
        continue_request: models.ContinueConversationRequest
    ) -> None:
    """Helper function to initialize Player-NPC conversation and get to the player's turn"""
    # Init Mantella
    response = client.post("/mantella", json=models.InitRequest(request_type=comm_consts.KEY_REQUESTTYPE_INIT).model_dump(by_alias=True))
    assert response.status_code == 200
    jsonschema.validate(response.json(), models.InitResponse.model_json_schema())

    # Start conversation
    response = client.post("/mantella", json=start_request.model_dump(by_alias=True, exclude_none=True))
    assert response.status_code == 200
    jsonschema.validate(response.json(), models.StartConversationResponse.model_json_schema())

    # Advance to player's turn
    players_turn = False
    while not players_turn:
        response = client.post("/mantella", json=continue_request.model_dump(by_alias=True, exclude_none=True))
        if response.json()[comm_consts.KEY_REPLYTYPE] == comm_consts.KEY_REPLYTYPE_PLAYERTALK:
            assert response.status_code == 200
            jsonschema.validate(response.json(), models.PlayerTalkResponse.model_json_schema())
            players_turn = True
        else:
            assert response.status_code == 200
            jsonschema.validate(response.json(), models.NpcTalkResponse.model_json_schema())


def test_mantella_player_talk_endpoint(
        production_like_client: TestClient, 
        example_start_conversation_request: models.StartConversationRequest, 
        example_continue_conversation_request: models.ContinueConversationRequest,
        example_player_input_textbox_request: models.PlayerInputRequest
    ):
    # Setup conversation to allow player input endpoint to be called
    setup_mantella_conversation(production_like_client, example_start_conversation_request, example_continue_conversation_request)

    # Send player (textbox) input
    response = production_like_client.post("/mantella", json=example_player_input_textbox_request.model_dump(by_alias=True, exclude_none=True))
    assert response.status_code == 200
    jsonschema.validate(response.json(), models.NpcTalkResponse.model_json_schema())


def test_mantella_end_conversation_endpoint(
        production_like_client: TestClient, 
        example_start_conversation_request: models.StartConversationRequest, 
        example_continue_conversation_request: models.ContinueConversationRequest,
        example_player_input_textbox_goodbye_request: models.PlayerInputRequest
    ):
    # Setup conversation to allow end conversation endpoint to be called
    setup_mantella_conversation(production_like_client, example_start_conversation_request, example_continue_conversation_request)

    # Send player (textbox) goodbye input
    production_like_client.post("/mantella", json=example_player_input_textbox_goodbye_request.model_dump(by_alias=True, exclude_none=True))

    # Respond back to the NPC talk interim step
    response = production_like_client.post("/mantella", json=example_continue_conversation_request.model_dump(by_alias=True, exclude_none=True))
    assert response.json()[comm_consts.KEY_REPLYTYPE_NPCTALK][comm_consts.KEY_ACTOR_LINETOSPEAK] == "Safe travels"
    assert comm_consts.ACTION_ENDCONVERSATION in response.json()[comm_consts.KEY_REPLYTYPE_NPCTALK][comm_consts.KEY_ACTOR_ACTIONS]

    # End comversation
    end_conversation_request = models.EndConversationRequest(request_type=comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION).model_dump(by_alias=True)
    response = production_like_client.post("/mantella", json=end_conversation_request)
    assert response.status_code == 200
    jsonschema.validate(response.json(), models.EndConversationResponse.model_json_schema())


def test_mantella_reload_conversation(
        production_like_client: TestClient, 
        example_start_conversation_request: models.StartConversationRequest, 
        example_continue_conversation_request: models.ContinueConversationRequest,
        example_player_input_textbox_request: models.PlayerInputRequest,
        monkeypatch,
    ):
    # Set up conversation to get to the player's turn
    setup_mantella_conversation(production_like_client, example_start_conversation_request, example_continue_conversation_request)

    # Send player (textbox) input
    response = production_like_client.post("/mantella", json=example_player_input_textbox_request.model_dump(by_alias=True, exclude_none=True))
    assert response.status_code == 200
    jsonschema.validate(response.json(), models.NpcTalkResponse.model_json_schema())

    # Patch TOKEN_LIMIT_PERCENT to 0
    monkeypatch.setattr(conv_module.Conversation, "TOKEN_LIMIT_PERCENT", 0)

    # Continue conversation - should trigger reload
    response = production_like_client.post("/mantella", json=example_continue_conversation_request.model_dump(by_alias=True, exclude_none=True))
    assert response.json()[comm_consts.KEY_REPLYTYPE_NPCTALK][comm_consts.KEY_ACTOR_LINETOSPEAK] == "I need to gather my thoughts for a moment"

    # Patch TOKEN_LIMIT_PERCENT back to 0.9
    monkeypatch.setattr(conv_module.Conversation, "TOKEN_LIMIT_PERCENT", 0.9)

    # Continue again to process the reload (the server first sends a message to let the player know it is reloading, and then actually carries out the reload on the next continue)
    response = production_like_client.post("/mantella", json=example_continue_conversation_request.model_dump(by_alias=True, exclude_none=True))
    # Check that the conversation continues as normal, if unsuccessful the "gather thoughts" message will play on an endless loop
    assert response.json()[comm_consts.KEY_REPLYTYPE_NPCTALK][comm_consts.KEY_ACTOR_LINETOSPEAK] != "I need to gather my thoughts for a moment"


def test_setup_route(default_mantella_route: mantella_route):
    """Test that the setup route method works"""
    default_mantella_route._setup_route()
    assert default_mantella_route._mantella_route__game is not None

@pytest.mark.parametrize(
    "game_enum, tts_service", 
    [
        (GameEnum.FALLOUT4, TTSEnum.XVASYNTH),
        (GameEnum.FALLOUT4, TTSEnum.XTTS),
        (GameEnum.FALLOUT4, TTSEnum.PIPER),
        (GameEnum.SKYRIM, TTSEnum.XVASYNTH),
        (GameEnum.SKYRIM, TTSEnum.XTTS),
        (GameEnum.SKYRIM, TTSEnum.PIPER),
    ]
)
def test_setup_route_combinations(default_config: ConfigLoader, english_language_info: dict, game_enum: GameEnum, tts_service: TTSEnum):
    """Test that the setup route method works with different game and TTS combinations"""
    # Set the game and TTS service on the config
    default_config.game = game_enum
    default_config.tts_service = tts_service

    # Create route instance
    route = mantella_route(
        config=default_config, 
        stt_secret_key_file='STT_SECRET_KEY.txt', 
        image_secret_key_file='IMAGE_SECRET_KEY.txt', 
        secret_key_file='GPT_SECRET_KEY.txt', 
        language_info=english_language_info, 
        show_debug_messages=False
    )
    
    # Call setup_route
    route._setup_route()
    
    # Assert the game was initialized
    assert route._mantella_route__game is not None

def test_setup_route_ends_conversation(default_config: ConfigLoader, english_language_info: dict):
    """Test that calling setup_route creates a new game instance when called multiple times"""
    # Create route instance
    route = mantella_route(
        config=default_config, 
        stt_secret_key_file='STT_SECRET_KEY.txt', 
        image_secret_key_file='IMAGE_SECRET_KEY.txt', 
        secret_key_file='GPT_SECRET_KEY.txt', 
        language_info=english_language_info, 
        show_debug_messages=False
    )
    
    # First setup to create a game
    route._setup_route()
    first_game = route._mantella_route__game
    assert first_game is not None
    
    # Second setup should create a new game instance
    route._setup_route()
    second_game = route._mantella_route__game
    assert second_game is not None
    
    # Assert that a new game instance was created
    assert first_game is not second_game