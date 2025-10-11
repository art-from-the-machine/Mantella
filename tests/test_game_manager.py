from src.game_manager import GameStateManager
import pytest
import jsonschema
from src.http import models
from src.http.communication_constants import communication_constants as comm_consts
from src.conversation import conversation as conv_module
from src.character_manager import Character
from src.llm.sentence import Sentence
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum

def setup_conversation(game_manager: GameStateManager, start_request: dict, continue_request: dict):
    # Start conversation
    response = game_manager.start_conversation(start_request)
    jsonschema.validate(response, models.StartConversationResponse.model_json_schema())

    # Advance to player's turn
    advance_to_player_turn(game_manager, continue_request)

def advance_to_player_turn(game_manager: GameStateManager, continue_request: dict):
    players_turn = False
    while not players_turn:
        response = game_manager.continue_conversation(continue_request)
        if response[comm_consts.KEY_REPLYTYPE] == comm_consts.KEY_REPLYTYPE_PLAYERTALK:
            jsonschema.validate(response, models.PlayerTalkResponse.model_json_schema())
            players_turn = True
        else:
            jsonschema.validate(response, models.NpcTalkResponse.model_json_schema())


def test_reload_conversation(
        default_game_manager: GameStateManager, 
        example_start_conversation_request: models.StartConversationRequest, 
        example_continue_conversation_request: models.ContinueConversationRequest, 
        example_player_input_textbox_request: models.PlayerInputRequest,
        monkeypatch
    ):
    # Set up conversation
    setup_conversation(default_game_manager, example_start_conversation_request.model_dump(by_alias=True, exclude_none=True), example_continue_conversation_request.model_dump(by_alias=True, exclude_none=True))

    # Send player (textbox) input
    response = default_game_manager.player_input(example_player_input_textbox_request.model_dump(by_alias=True, exclude_none=True))
    jsonschema.validate(response, models.NpcTalkResponse.model_json_schema())

    advance_to_player_turn(default_game_manager, example_continue_conversation_request.model_dump(by_alias=True, exclude_none=True))
    # Send player (textbox) input once more (summaries do not trigger if a conversation is too short)
    response = default_game_manager.player_input(example_player_input_textbox_request.model_dump(by_alias=True, exclude_none=True))
    jsonschema.validate(response, models.NpcTalkResponse.model_json_schema())

    # Note the current system message
    orig_system_message = default_game_manager._GameStateManager__talk._Conversation__messages._message_thread__messages[0].text

    # Set TOKEN_LIMIT_PERCENT to 0 to simulate a reload
    monkeypatch.setattr(conv_module.Conversation, "TOKEN_LIMIT_PERCENT", 0)
    response = default_game_manager.continue_conversation(example_continue_conversation_request.model_dump(by_alias=True, exclude_none=True))
    # Assert that the response indicates to the player that a reload will occur
    assert response[comm_consts.KEY_REPLYTYPE_NPCTALK][comm_consts.KEY_ACTOR_LINETOSPEAK] == "I need to gather my thoughts for a moment"
    
    # Reset TOKEN_LIMIT_PERCENT
    monkeypatch.setattr(conv_module.Conversation, "TOKEN_LIMIT_PERCENT", 0.9)
    # The next continue should trigger the reload
    response = default_game_manager.continue_conversation(example_continue_conversation_request.model_dump(by_alias=True, exclude_none=True))
    # Once reloaded, the message list should be reset and contain only the system prompt and automatic player greeting
    new_system_message = default_game_manager._GameStateManager__talk._Conversation__messages._message_thread__messages[0].text
    assert new_system_message != orig_system_message


def test_player_action_command(
        default_game_manager: GameStateManager, 
        example_start_conversation_request: models.StartConversationRequest, 
        example_continue_conversation_request: models.ContinueConversationRequest, 
        example_player_input_textbox_action_command_request: models.PlayerInputRequest,
    ):
    ''' Test that a player action command (eg "Follow.") results in the action being returned in the response'''

    # Set up conversation
    setup_conversation(default_game_manager, example_start_conversation_request.model_dump(by_alias=True, exclude_none=True), example_continue_conversation_request.model_dump(by_alias=True, exclude_none=True))

    # Send player (textbox) input
    response = default_game_manager.player_input(example_player_input_textbox_action_command_request.model_dump(by_alias=True, exclude_none=True))
    
    # Assert that the response contains the action
    assert response[comm_consts.KEY_REPLYTYPE_NPCACTION][comm_consts.KEY_ACTOR_ACTIONS][0] == 'mantella_npc_follow'


def test_sentence_to_json_with_dict_actions(default_game_manager: GameStateManager, example_skyrim_npc_character: Character):
    """Test sentence_to_json extracts full action dicts"""    
    # Create a sentence with full action dicts
    actions = [
        {
            "identifier": "mantella_npc_follow",
            "arguments": {"source": ["Lydia", "Serana"]}
        }
    ]
    
    sentence_content = SentenceContent(
        speaker=example_skyrim_npc_character,
        text="Of course, we'll follow.",
        sentence_type=SentenceTypeEnum.SPEECH,
        is_system_generated_sentence=False,
        actions=actions
    )
    
    sentence = Sentence(sentence_content, "test.wav", 2.5)
    
    # Convert to JSON
    result = default_game_manager.sentence_to_json(sentence, topicID=1)
    
    assert comm_consts.KEY_ACTOR_ACTIONS in result
    assert len(result[comm_consts.KEY_ACTOR_ACTIONS]) == 1
    assert result[comm_consts.KEY_ACTOR_ACTIONS][0]["identifier"] == "mantella_npc_follow"
    assert result[comm_consts.KEY_ACTOR_ACTIONS][0]["arguments"] == {"source": ["Lydia", "Serana"]}


def test_sentence_to_json_with_multiple_dict_actions(default_game_manager: GameStateManager, example_skyrim_npc_character: Character):
    """Test sentence_to_json handles multiple action dicts correctly"""
    
    # Create a sentence with multiple full action dicts
    actions = [
        {
            "identifier": "mantella_npc_follow",
            "arguments": {"source": ["Erik"]}
        },
        {
            "identifier": "mantella_npc_inventory",
            "arguments": {"source": ["Erik"]}
        }
    ]
    
    sentence_content = SentenceContent(
        speaker=example_skyrim_npc_character,
        text="Ready for battle.",
        sentence_type=SentenceTypeEnum.SPEECH,
        is_system_generated_sentence=False,
        actions=actions
    )
    
    sentence = Sentence(sentence_content, "test.wav", 1.5)
    
    # Convert to JSON
    result = default_game_manager.sentence_to_json(sentence, topicID=1)
    
    assert comm_consts.KEY_ACTOR_ACTIONS in result
    assert len(result[comm_consts.KEY_ACTOR_ACTIONS]) == 2
    assert result[comm_consts.KEY_ACTOR_ACTIONS][0]["identifier"] == "mantella_npc_follow"
    assert result[comm_consts.KEY_ACTOR_ACTIONS][1]["identifier"] == "mantella_npc_inventory"
    assert result[comm_consts.KEY_ACTOR_ACTIONS][0]["arguments"] == {"source": ["Erik"]}
    assert result[comm_consts.KEY_ACTOR_ACTIONS][1]["arguments"] == {"source": ["Erik"]}


def test_sentence_to_json_with_empty_actions(default_game_manager: GameStateManager,example_skyrim_npc_character: Character):
    """Test sentence_to_json handles sentences with no actions correctly"""
    
    # Create a sentence with no actions
    sentence_content = SentenceContent(
        speaker=example_skyrim_npc_character,
        text="Hello there.",
        sentence_type=SentenceTypeEnum.SPEECH,
        is_system_generated_sentence=False,
        actions=[]
    )
    
    sentence = Sentence(sentence_content, "test.wav", 1.0)
    
    # Convert to JSON
    result = default_game_manager.sentence_to_json(sentence, topicID=1)
    
    assert comm_consts.KEY_ACTOR_ACTIONS in result
    assert result[comm_consts.KEY_ACTOR_ACTIONS] == []