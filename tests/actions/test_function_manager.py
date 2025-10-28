import pytest
import json
from pathlib import Path
from src.actions.function_manager import FunctionManager
from src.conversation.context import Context
from src.characters_manager import Characters
from src.conversation.action import Action

def test_load_all_actions():
    """Test loading all actions from data/actions/ folder"""
    # Clear any previously loaded actions
    FunctionManager._actions.clear()
    
    # Load actions
    FunctionManager.load_all_actions()
    
    # Verify actions were loaded
    assert len(FunctionManager._actions) > 0
    
    # Verify all loaded actions have the mantella_ prefix
    for identifier in FunctionManager._actions.keys():
        assert identifier.startswith('mantella_')


def test_load_all_actions_structure():
    """Test that loaded actions have required fields"""
    FunctionManager.load_all_actions()
    
    for _, action in FunctionManager._actions.items():
        assert 'identifier' in action
        assert 'name' in action
        assert 'description' in action
        assert 'key' in action
        assert 'prompt' in action
        assert 'is-interrupting' in action or 'is_interrupting' in action
        assert 'one-on-one' in action or 'one_on_one' in action
        assert 'multi-npc' in action or 'multi_npc' in action
        assert 'radiant' in action


def test_load_all_actions_respects_enabled_flag(tmp_path):
    """Test that actions with enabled: false are not loaded"""
    FunctionManager._actions.clear()
    
    actions_dir = tmp_path / "actions"
    actions_dir.mkdir()
    
    enabled_action = {
        "identifier": "test_enabled",
        "name": "EnabledAction",
        "description": "Test",
        "key": "Enabled",
        "prompt": "Test",
        "enabled": True,
        "is-interrupting": False,
        "one-on-one": True,
        "multi-npc": False,
        "radiant": False
    }
    
    disabled_action = {
        "identifier": "test_disabled",
        "name": "DisabledAction",
        "description": "Test",
        "key": "Disabled",
        "prompt": "Test",
        "enabled": False,
        "is-interrupting": False,
        "one-on-one": True,
        "multi-npc": False,
        "radiant": False
    }
    
    default_action = {
        "identifier": "test_default",
        "name": "DefaultAction",
        "description": "Test",
        "key": "Default",
        "prompt": "Test",
        "is-interrupting": False,
        "one-on-one": True,
        "multi-npc": False,
        "radiant": False
    }
    
    with open(actions_dir / "enabled.json", 'w') as f:
        json.dump(enabled_action, f)
    with open(actions_dir / "disabled.json", 'w') as f:
        json.dump(disabled_action, f)
    with open(actions_dir / "default.json", 'w') as f:
        json.dump(default_action, f)
    
    # Load test actions
    for file_path in actions_dir.glob("*.json"):
        FunctionManager._load_action_file(file_path)
    
    # Only enabled and default actions should be loaded
    assert 'mantella_test_enabled' in FunctionManager._actions
    assert 'mantella_test_default' in FunctionManager._actions
    assert 'mantella_test_disabled' not in FunctionManager._actions
    assert len(FunctionManager._actions) == 2
    
    # Cleanup: Restore original actions
    FunctionManager.load_all_actions()


def test_get_legacy_actions():
    """Test that get_legacy_actions returns Action objects"""
    FunctionManager.load_all_actions()
    
    legacy_actions = FunctionManager.get_legacy_actions()
    
    assert isinstance(legacy_actions, list)
    assert all(isinstance(action, Action) for action in legacy_actions)
    
    for action in legacy_actions:
        assert hasattr(action, 'identifier')
        assert hasattr(action, 'name')
        assert hasattr(action, 'keyword')
        assert hasattr(action, 'description')
        assert hasattr(action, 'prompt_text')
        assert hasattr(action, 'is_interrupting')
        assert hasattr(action, 'use_in_on_on_one')
        assert hasattr(action, 'use_in_multi_npc')
        assert hasattr(action, 'use_in_radiant')


def test_get_legacy_actions_matches_loaded_count():
    """Test that get_legacy_actions returns same number as loaded actions"""
    FunctionManager.load_all_actions()
    
    loaded_count = len(FunctionManager._actions)
    legacy_actions = FunctionManager.get_legacy_actions()
    
    # Should have same number of actions
    assert len(legacy_actions) == loaded_count


def test_parse_function_calls_empty_list():
    """Test parsing empty function calls list"""
    result = FunctionManager.parse_function_calls([])
    assert result == []


def test_parse_function_calls_none():
    """Test parsing None function calls"""
    result = FunctionManager.parse_function_calls(None)
    assert result == []


def test_parse_function_calls_valid():
    """Test parsing valid function calls"""
    # Load actions first to have action mappings
    FunctionManager.load_all_actions()
    
    # Create a mock tool call
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'source': ['Guard']})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls)
    
    assert len(result) == 1
    assert 'identifier' in result[0]
    assert 'arguments' in result[0]
    assert result[0]['arguments'] == {'source': ['Guard']}


def test_parse_function_calls_malformed_json():
    """Test parsing function calls with malformed JSON arguments"""
    # Load actions first to have action mappings
    FunctionManager.load_all_actions()

    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': 'not valid json {'
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls)
    
    assert len(result) == 1
    # When arguments are empty, the key should not be present
    assert 'arguments' not in result[0]


def test_parse_function_calls_unknown_function():
    """Test parsing function calls with unknown function name"""
    FunctionManager.load_all_actions()
    
    tool_calls = [
        {
            'function': {
                'name': 'unknown_function_name',
                'arguments': json.dumps({})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls)
    
    # Unknown functions should not be parsed
    assert len(result) == 0


def test_parse_function_calls_multiple_calls():
    """Test parsing multiple function calls"""
    FunctionManager.load_all_actions()
    
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'source': ['Guard']})
            }
        },
        {
            'function': {
                'name': 'StandDown',
                'arguments': json.dumps({'source': ['Guard']})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls)
    
    assert len(result) == 2
    assert result[0]['arguments'] == {'source': ['Guard']}
    assert result[1]['arguments'] == {'source': ['Guard']}


def test_generate_context_aware_tools(default_context: Context):
    """Test generating context-aware tools from loaded actions"""
    FunctionManager.load_all_actions()
    
    tools = FunctionManager.generate_context_aware_tools(default_context)
    
    # Verify tools were generated
    assert isinstance(tools, list)
    
    # Verify tool structure
    for tool in tools:
        assert 'type' in tool
        assert tool['type'] == 'function'
        assert 'function' in tool
        assert 'name' in tool['function']
        assert 'description' in tool['function']


def test_generate_context_aware_tools_adds_npc_context(default_context: Context):
    """Test that NPC context is added to tool parameters"""
    FunctionManager.load_all_actions()
    
    tools = FunctionManager.generate_context_aware_tools(default_context)
    
    # Find a tool with parameters
    tool_with_params = None
    for tool in tools:
        if 'parameters' in tool['function']:
            tool_with_params = tool
            break
    
    if tool_with_params:
        # Check if any parameter descriptions were enhanced with NPC context
        properties = tool_with_params['function']['parameters'].get('properties', {})
        for param_name, param_def in properties.items():
            if 'source' in param_name.lower() or 'target' in param_name.lower() or 'npc_name' in param_name.lower():
                # These parameters should have "Available" text added
                assert 'Available' in param_def.get('description', ''), \
                    f"Parameter {param_name} should have NPC context added to description"


def test_parse_function_calls_exception_handling():
    """Test that exceptions during parsing are handled gracefully"""
    FunctionManager.load_all_actions()

    # Create a tool call that might cause issues
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'key': 'value'})
            }
        },
        # This one is malformed (missing 'function' key)
        {
            'invalid': 'structure'
        }
    ]
    
    # Should not raise an exception, should log error and continue
    result = FunctionManager.parse_function_calls(tool_calls)
    
    # Should still parse the valid call
    assert len(result) == 1


def test_generate_context_aware_tools_with_parameters(default_context: Context):
    """Test that tools with parameters are properly formatted"""
    FunctionManager.load_all_actions()
    
    tools = FunctionManager.generate_context_aware_tools(default_context)
    
    # Find a tool with parameters and required fields
    for tool in tools:
        if 'parameters' in tool['function']:
            params = tool['function']['parameters']
            
            # Verify parameter structure
            assert params['type'] == 'object'
            assert 'properties' in params
            
            # If the tool has required fields in the action definition,
            # they should be present in the parameters
            if 'required' in params:
                assert isinstance(params['required'], list)
            
            # Only need to check one tool with parameters
            break


def test_validate_npc_names_valid_names(example_characters_pc_to_npc: Characters):
    """Test validation with all valid NPC names"""
    npc_names = ['Guard', 'Dragonborn']
    
    result = FunctionManager._validate_npc_names(npc_names, example_characters_pc_to_npc, exclude_player=False)
    
    assert len(result) == 2
    assert 'Guard' in result
    assert 'Dragonborn' in result


def test_validate_npc_names_case_insensitive(example_characters_pc_to_npc: Characters):
    """Test that NPC name matching is case-insensitive"""
    npc_names = ['guard', 'GUARD', 'Guard']

    result = FunctionManager._validate_npc_names(npc_names, example_characters_pc_to_npc, exclude_player=False)

    # All variations refer to same NPC, should deduplicate and preserve first occurrence's casing
    assert len(result) == 1
    assert 'guard' in result  # First occurrence preserved


def test_validate_npc_names_invalid_names(example_characters_pc_to_npc: Characters):
    """Test that invalid NPC names are filtered out"""
    npc_names = ['Guard', 'NonExistentNPC', 'AnotherFakeNPC']

    result = FunctionManager._validate_npc_names(npc_names, example_characters_pc_to_npc, exclude_player=False)

    # Only valid names should be returned
    assert len(result) == 1
    assert 'Guard' in result
    assert 'NonExistentNPC' not in result
    assert 'AnotherFakeNPC' not in result


def test_validate_npc_names_exclude_player(example_characters_pc_to_npc: Characters):
    """Test that player is excluded by default"""
    npc_names = ['Guard', 'Dragonborn']
    
    # With exclude_player=True (default)
    result = FunctionManager._validate_npc_names(npc_names, example_characters_pc_to_npc)
    
    assert len(result) == 1
    assert 'Guard' in result
    assert 'Dragonborn' not in result


def test_validate_npc_names_include_player(example_characters_pc_to_npc: Characters):
    """Test that player can be included when specified"""
    npc_names = ['Guard', 'Dragonborn']
    
    # With exclude_player=False
    result = FunctionManager._validate_npc_names(npc_names, example_characters_pc_to_npc, exclude_player=False)
    
    assert len(result) == 2
    assert 'Guard' in result
    assert 'Dragonborn' in result


def test_validate_npc_names_empty_list(example_characters_pc_to_npc: Characters):
    """Test validation with empty list"""
    npc_names = []
    
    result = FunctionManager._validate_npc_names(npc_names, example_characters_pc_to_npc, exclude_player=False)
    
    assert result == []


def test_validate_npc_names_all_invalid(example_characters_pc_to_npc: Characters):
    """Test when all names are invalid"""
    npc_names = ['FakeNPC1', 'FakeNPC2', 'FakeNPC3']

    result = FunctionManager._validate_npc_names(npc_names, example_characters_pc_to_npc, exclude_player=False)

    assert result == []


def test_validate_npc_names_mixed_valid_invalid(example_characters_pc_to_npc: Characters):
    """Test with mix of valid and invalid names"""
    npc_names = ['Guard', 'FakeNPC', 'Dragonborn', 'AnotherFake']

    result = FunctionManager._validate_npc_names(npc_names, example_characters_pc_to_npc, exclude_player=False)

    assert len(result) == 2
    assert 'Guard' in result
    assert 'Dragonborn' in result
    assert 'FakeNPC' not in result
    assert 'AnotherFake' not in result


def test_validate_npc_names_preserves_llm_casing(example_characters_pc_to_npc: Characters):
    """Test that original LLM casing is preserved"""
    npc_names = ['gUaRd', 'DRAGONBORN']

    result = FunctionManager._validate_npc_names(npc_names, example_characters_pc_to_npc, exclude_player=False)

    # Original casing should be preserved
    assert 'gUaRd' in result
    assert 'DRAGONBORN' in result


def test_validate_npc_names_duplicate_names(example_characters_pc_to_npc: Characters):
    """Test handling of duplicate names in input"""
    npc_names = ['Guard', 'Guard', 'Dragonborn']

    result = FunctionManager._validate_npc_names(npc_names, example_characters_pc_to_npc, exclude_player=False)

    # Should remove duplicates - only unique names returned
    assert len(result) == 2
    assert 'Guard' in result
    assert 'Dragonborn' in result
    assert result.count('Guard') == 1
    assert result.count('Dragonborn') == 1


def test_parse_function_calls_with_validation_valid_source(example_characters_pc_to_npc: Characters):
    """Test parsing with valid source parameter"""
    FunctionManager.load_all_actions()
    
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'source': ['Guard']})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls, example_characters_pc_to_npc)
    
    assert len(result) == 1
    assert result[0]['arguments']['source'] == ['Guard']


def test_parse_function_calls_with_validation_invalid_source(example_characters_pc_to_npc: Characters):
    """Test parsing with invalid source parameter - action should be skipped"""
    FunctionManager.load_all_actions()
    
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'source': ['NonExistentNPC']})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls, example_characters_pc_to_npc)
    
    # Action should be skipped due to no valid NPCs
    assert len(result) == 0


def test_parse_function_calls_with_validation_mixed_valid_invalid_source(example_characters_pc_to_npc: Characters):
    """Test parsing with mix of valid and invalid source names"""
    FunctionManager.load_all_actions()
    
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'source': ['Guard', 'FakeNPC', 'AnotherFakeNPC']})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls, example_characters_pc_to_npc)
    
    assert len(result) == 1
    # Only valid NPC should remain
    assert result[0]['arguments']['source'] == ['Guard']


def test_parse_function_calls_with_validation_valid_target(example_characters_pc_to_npc: Characters):
    """Test parsing with valid target parameter"""
    FunctionManager.load_all_actions()
    
    # Manually add a test action with source and target parameters
    FunctionManager._actions['test_action'] = {
        'identifier': 'test_action',
        'name': 'TestAction',
        'parameters': {
            'source': {'type': 'array'},
            'target': {'type': 'array'}
        }
    }
    
    tool_calls = [
        {
            'function': {
                'name': 'TestAction',
                'arguments': json.dumps({'source': ['Guard'], 'target': ['Dragonborn']})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls, example_characters_pc_to_npc)
    
    assert len(result) == 1
    assert result[0]['arguments']['source'] == ['Guard']
    assert result[0]['arguments']['target'] == ['Dragonborn']


def test_parse_function_calls_with_validation_target_includes_player(example_characters_pc_to_npc: Characters):
    """Test that target can include player (exclude_player=False for target)"""
    FunctionManager.load_all_actions()
    
    # Manually add a test action with source and target parameters
    FunctionManager._actions['test_action'] = {
        'identifier': 'test_action',
        'name': 'TestAction',
        'parameters': {
            'source': {'type': 'array'},
            'target': {'type': 'array'}
        }
    }
    
    tool_calls = [
        {
            'function': {
                'name': 'TestAction',
                'arguments': json.dumps({'source': ['Guard'], 'target': ['Dragonborn']})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls, example_characters_pc_to_npc)
    
    assert len(result) == 1
    assert 'Dragonborn' in result[0]['arguments']['target']


def test_parse_function_calls_with_validation_source_excludes_player(example_characters_pc_to_npc: Characters):
    """Test that source excludes player (exclude_player=True for source)"""
    FunctionManager.load_all_actions()
    
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'source': ['Guard', 'Dragonborn']})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls, example_characters_pc_to_npc)
    
    assert len(result) == 1
    # Player (Dragonborn) should be filtered out from source
    assert result[0]['arguments']['source'] == ['Guard']
    assert 'Dragonborn' not in result[0]['arguments']['source']


def test_parse_function_calls_with_validation_other_params_unchanged(example_characters_pc_to_npc: Characters):
    """Test that non-NPC parameters are passed through unchanged"""
    FunctionManager.load_all_actions()
    
    # Add a test action with multiple parameter types
    FunctionManager._actions['test_action'] = {
        'identifier': 'test_action',
        'name': 'TestAction',
        'parameters': {
            'source': {'type': 'array'},
            'mode': {'type': 'string'},
            'duration': {'type': 'number'},
            'custom_flag': {'type': 'boolean'}
        }
    }
    
    tool_calls = [
        {
            'function': {
                'name': 'TestAction',
                'arguments': json.dumps({
                    'source': ['Guard'],
                    'mode': 'aggressive',
                    'duration': 60,
                    'custom_flag': True
                })
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls, example_characters_pc_to_npc)
    
    assert len(result) == 1
    assert result[0]['arguments']['source'] == ['Guard']
    assert result[0]['arguments']['mode'] == 'aggressive'
    assert result[0]['arguments']['duration'] == 60
    assert result[0]['arguments']['custom_flag'] is True


def test_parse_function_calls_case_insensitive_validation(example_characters_pc_to_npc: Characters):
    """Test that NPC validation is case-insensitive and preserves LLM casing"""
    FunctionManager.load_all_actions()
    
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'source': ['guard', 'GUARD', 'Guard']})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls, example_characters_pc_to_npc)
    
    assert len(result) == 1
    # Should deduplicate and preserve first occurrence's casing
    assert len(result[0]['arguments']['source']) == 1
    assert 'guard' in result[0]['arguments']['source']


def test_parse_function_calls_skip_action_when_all_sources_invalid(example_characters_pc_to_npc: Characters):
    """Test that action is skipped when all source NPCs are invalid"""
    FunctionManager.load_all_actions()
    
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'source': ['FakeNPC1', 'FakeNPC2']})
            }
        },
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'source': ['Guard']})  # Valid action
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls, example_characters_pc_to_npc)
    
    # First action should be skipped, second should be processed
    assert len(result) == 1
    assert result[0]['arguments']['source'] == ['Guard']


def test_validate_arguments_against_schema_valid_args():
    """Test that valid arguments pass through unchanged"""
    FunctionManager.load_all_actions()
    
    # Follow action has 'source' parameter
    defined_params = {'source': {'type': 'array'}}
    llm_arguments = {'source': ['Guard']}
    
    result = FunctionManager._validate_arguments_against_schema(
        llm_arguments, defined_params, 'mantella_npc_follow'
    )
    
    assert result == {'source': ['Guard']}


def test_validate_arguments_against_schema_hallucinated_args():
    """Test that hallucinated / unknown arguments are filtered out"""
    FunctionManager.load_all_actions()
    
    # Follow action has 'source' parameter
    defined_params = {'source': {'type': 'array'}}
    
    # LLM hallucinates 'speed' and 'distance' parameters
    llm_arguments = {
        'source': ['Guard'],
        'speed': 'fast',
        'distance': 100
    }
    
    result = FunctionManager._validate_arguments_against_schema(
        llm_arguments, defined_params, 'mantella_npc_follow'
    )
    
    # Only valid parameter should remain
    assert result == {'source': ['Guard']}
    assert 'speed' not in result
    assert 'distance' not in result


def test_validate_arguments_against_schema_all_invalid():
    """Test when all arguments are invalid/hallucinated"""
    FunctionManager.load_all_actions()
    
    defined_params = {'source': {'type': 'array'}}
    
    # All arguments are hallucinated
    llm_arguments = {
        'fake_param': 'value',
        'another_fake': 123
    }
    
    result = FunctionManager._validate_arguments_against_schema(
        llm_arguments, defined_params, 'mantella_npc_follow'
    )
    
    # Should return empty dict
    assert result == {}


def test_validate_arguments_against_schema_mixed_valid_invalid():
    """Test with mix of valid and invalid parameters"""
    FunctionManager.load_all_actions()
    
    # Action with multiple parameters
    defined_params = {
        'source': {'type': 'array'},
        'target': {'type': 'array'},
        'mode': {'type': 'string'}
    }
    
    llm_arguments = {
        'source': ['Guard'],
        'fake_param': 'value',
        'target': ['Dragonborn'],
        'another_fake': 123,
        'mode': 'aggressive'
    }
    
    result = FunctionManager._validate_arguments_against_schema(
        llm_arguments, defined_params, 'test_action'
    )
    
    # Only valid parameters should remain
    assert result == {
        'source': ['Guard'],
        'target': ['Dragonborn'],
        'mode': 'aggressive'
    }
    assert 'fake_param' not in result
    assert 'another_fake' not in result


def test_validate_arguments_against_schema_empty_params():
    """Test validation when action has no parameters defined"""
    FunctionManager.load_all_actions()
    
    defined_params = {}
    llm_arguments = {'some_arg': 'value'}
    
    result = FunctionManager._validate_arguments_against_schema(
        llm_arguments, defined_params, 'test_action'
    )
    
    # All arguments should be filtered out
    assert result == {}


def test_parse_function_calls_with_hallucinated_args(example_characters_pc_to_npc: Characters):
    """Test that hallucinated arguments are filtered during parsing"""
    FunctionManager.load_all_actions()
    
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({
                    'source': ['Guard'],
                    'speed': 'fast',  # Hallucinated
                    'duration': 60    # Hallucinated
                })
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls, example_characters_pc_to_npc)
    
    assert len(result) == 1
    # Only valid 'source' parameter should remain
    assert result[0]['arguments'] == {'source': ['Guard']}
    assert 'speed' not in result[0]['arguments']
    assert 'duration' not in result[0]['arguments']


def test_parse_function_calls_validation_order():
    """Test that schema validation happens before NPC name validation"""
    FunctionManager.load_all_actions()
    
    # No characters manager provided, so only schema validation should occur
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({
                    'source': ['AnyNPC'],
                    'fake_param': 'value'  # Should be filtered by schema validation
                })
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls)
    
    assert len(result) == 1
    # Schema validation should have filtered out fake_param
    # NPC validation skipped because no characters manager provided
    assert result[0]['arguments'] == {'source': ['AnyNPC']}
    assert 'fake_param' not in result[0]['arguments']


def test_parse_function_calls_empty_arguments_not_included():
    """Test that when all arguments are filtered out, 'arguments' key is not present"""
    FunctionManager.load_all_actions()
    
    # Offended action has no parameters defined in JSON
    tool_calls = [
        {
            'function': {
                'name': 'Attack',
                'arguments': json.dumps({})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls)
    
    assert len(result) == 1
    assert result[0]['identifier'] == 'mantella_npc_offended'
    # When there are no arguments, the key should not be present at all
    assert 'arguments' not in result[0]


def test_parse_function_calls_hallucinated_args_removed_completely():
    """Test that when all LLM arguments are hallucinated and filtered, 'arguments' key is not present"""
    FunctionManager.load_all_actions()
    
    # Offended action has no parameters, LLM hallucinates some
    tool_calls = [
        {
            'function': {
                'name': 'Attack',
                'arguments': json.dumps({
                    'intensity': 'high',
                    'reason': 'insult',
                    'duration': 60
                })
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls)
    
    assert len(result) == 1
    assert result[0]['identifier'] == 'mantella_npc_offended'
    # All arguments were hallucinated and filtered out, so key should not be present
    assert 'arguments' not in result[0]


class TestNearbyNPCValidation:
    """Tests for NPC name validation with nearby NPCs"""

    def test_validate_npc_names_conversation_scope(self, example_characters_with_nearby: Characters):
        """Should validate against conversation participants only"""
        
        # LLM provides names - some in conversation, some nearby
        llm_names = ["Guard", "Bandit", "Unknown"]
        
        result = FunctionManager._validate_npc_names(
            llm_names, 
            example_characters_with_nearby,
            exclude_player=True,
            include_nearby=False
        )
        
        # Only "Guard" should be valid (in conversation)
        assert len(result) == 1
        assert "Guard" in result
        assert "Bandit" not in result  # Nearby, not in conversation
        assert "Unknown" not in result  # Doesn't exist

    def test_validate_npc_names_all_npcs_scope(self, example_characters_with_nearby: Characters):
        """Should validate against conversation + nearby NPCs"""
        
        llm_names = ["Guard", "Bandit", "Merchant", "Unknown"]
        
        result = FunctionManager._validate_npc_names(
            llm_names,
            example_characters_with_nearby,
            exclude_player=True,
            include_nearby=True
        )
        
        # Guard (conversation) + Bandit + Merchant (nearby) should be valid
        assert len(result) == 3
        assert "Guard" in result
        assert "Bandit" in result
        assert "Merchant" in result
        assert "Unknown" not in result

    def test_validate_npc_names_player_alias_resolution(self, example_characters_pc_to_npc):
        """Should resolve 'player' to actual player name"""
        llm_names = ["player", "Guard"]
        
        result = FunctionManager._validate_npc_names(
            llm_names,
            example_characters_pc_to_npc,
            exclude_player=False,  # Allow player
            include_nearby=False
        )
        
        assert len(result) == 2
        assert "Dragonborn" in result  # Actual player name
        assert "Guard" in result
        assert "player" not in result  # Alias replaced

    def test_validate_npc_names_player_excluded(self, example_characters_pc_to_npc):
        """Should exclude player when exclude_player=True"""
        llm_names = ["player", "Dragonborn", "Guard"]
        
        result = FunctionManager._validate_npc_names(
            llm_names,
            example_characters_pc_to_npc,
            exclude_player=True,
            include_nearby=False
        )
        
        assert len(result) == 1
        assert "Guard" in result
        assert "Dragonborn" not in result
        assert "player" not in result

    def test_validate_npc_names_case_insensitive_matching(self, example_characters_with_nearby: Characters):
        """Should match names case-insensitively but preserve LLM casing"""
        
        llm_names = ["GUARD", "bandit", "GuArD"]  # Various casings
        
        result = FunctionManager._validate_npc_names(
            llm_names,
            example_characters_with_nearby,
            exclude_player=True,
            include_nearby=True
        )
        
        # Should match but preserve LLM casing, no duplicates
        assert len(result) == 2
        assert "GUARD" in result  # First occurrence preserved
        assert "bandit" in result

    def test_validate_npc_names_removes_duplicates(self, example_characters_pc_to_npc):
        """Should remove duplicate NPC names"""
        llm_names = ["Guard", "guard", "GUARD"]
        
        result = FunctionManager._validate_npc_names(
            llm_names,
            example_characters_pc_to_npc,
            exclude_player=True,
            include_nearby=False
        )
        
        assert len(result) == 1
        assert "Guard" in result  # First occurrence kept

    def test_validate_npc_names_empty_list(self, example_characters_pc_to_npc):
        """Should handle empty input gracefully"""
        result = FunctionManager._validate_npc_names(
            [],
            example_characters_pc_to_npc,
            exclude_player=True,
            include_nearby=False
        )
        
        assert result == []


class TestParseWithNearbyNPCs:
    """Tests for parse_function_calls with nearby NPCs"""

    def test_parse_with_nearby_target_validation(self, example_characters_with_nearby: Characters):
        """Should validate target parameter against nearby NPCs"""
        FunctionManager.load_all_actions()
        
        # Attack action: source=conversation, target=all_npcs_w_player
        tool_calls = [
            {
                'function': {
                    'name': 'Attack',
                    'arguments': json.dumps({
                        'source': ['Guard'],
                        'target': 'Bandit'  # Nearby NPC
                    })
                }
            }
        ]
        
        result = FunctionManager.parse_function_calls(tool_calls, example_characters_with_nearby)
        
        assert len(result) == 1
        assert result[0]['identifier'] == 'mantella_npc_offended'
        assert result[0]['arguments']['source'] == ['Guard']
        assert result[0]['arguments']['target'] == 'Bandit'  # Validated against nearby

    def test_parse_with_invalid_nearby_target(self, example_characters_with_nearby: Characters):
        """Should skip action when required parameter is invalid"""
        FunctionManager.load_all_actions()
        
        tool_calls = [
            {
                'function': {
                    'name': 'Attack',
                    'arguments': json.dumps({
                        'source': ['Guard'],
                        'target': 'NonExistentNPC'  # Not in conversation or nearby
                    })
                }
            }
        ]
        
        result = FunctionManager.parse_function_calls(tool_calls, example_characters_with_nearby)
        
        # Action should be skipped if target is invalid
        assert len(result) == 0

    def test_parse_follow_with_multiple_conversation_npcs(self, example_characters_multi_npc: Characters):
        """Should validate multiple source NPCs from conversation"""
        FunctionManager.load_all_actions()
        
        tool_calls = [
            {
                'function': {
                    'name': 'Follow',
                    'arguments': json.dumps({
                        'source': ['Guard', 'Lydia']
                    })
                }
            }
        ]
        
        result = FunctionManager.parse_function_calls(tool_calls, example_characters_multi_npc)
        
        assert len(result) == 1
        assert result[0]['identifier'] == 'mantella_npc_follow'
        assert result[0]['arguments']['source'] == ['Guard', 'Lydia']

    def test_parse_mixed_valid_invalid_sources(self, example_characters_pc_to_npc):
        """Should filter out invalid NPCs but keep valid ones"""
        FunctionManager.load_all_actions()
        
        tool_calls = [
            {
                'function': {
                    'name': 'Follow',
                    'arguments': json.dumps({
                        'source': ['Guard', 'NonExistent', 'AnotherFake']
                    })
                }
            }
        ]
        
        result = FunctionManager.parse_function_calls(tool_calls, characters=example_characters_pc_to_npc)
        
        # Should keep only valid NPC
        assert len(result) == 1
        assert result[0]['arguments']['source'] == ['Guard']


class TestToolGenerationWithNearby:
    """Tests for generate_context_aware_tools with nearby NPCs"""

    def test_adds_nearby_npcs_to_target_parameter(self, example_context_with_nearby: Context):
        """Should add nearby NPCs to target parameter description"""
        FunctionManager.load_all_actions()
        
        tools = FunctionManager.generate_context_aware_tools(example_context_with_nearby)
        
        # Find Attack action tool
        attack_tool = None
        for tool in tools:
            if tool['function']['name'] == 'Attack':
                attack_tool = tool
                break
        
        assert attack_tool is not None
        
        # Target parameter should include nearby NPCs
        target_desc = attack_tool['function']['parameters']['properties']['target']['description']
        assert 'Bandit' in target_desc
        assert 'Merchant' in target_desc

    def test_conversation_scope_excludes_nearby(self, example_context_with_nearby: Context):
        """Should not include nearby NPCs in conversation-scoped parameters"""
        FunctionManager.load_all_actions()
        
        tools = FunctionManager.generate_context_aware_tools(example_context_with_nearby)
        
        # Find Follow action tool (source has "conversation" scope)
        follow_tool = None
        for tool in tools:
            if tool['function']['name'] == 'Follow':
                follow_tool = tool
                break
        
        assert follow_tool is not None
        
        # Source parameter should NOT include nearby NPCs
        source_desc = follow_tool['function']['parameters']['properties']['source']['description']
        assert 'Guard' in source_desc  # Conversation NPC
        assert 'Bandit' not in source_desc  # Nearby NPC

    def test_no_nearby_npcs_graceful_handling(self, default_context):
        """Should work normally when no nearby NPCs are set"""
        FunctionManager.load_all_actions()
        
        # Don't set nearby NPCs (default empty)
        tools = FunctionManager.generate_context_aware_tools(default_context)
        
        # Should still generate tools
        assert len(tools) > 0
        
        # Find Attack action
        attack_tool = None
        for tool in tools:
            if tool['function']['name'] == 'Attack':
                attack_tool = tool
                break
        
        assert attack_tool is not None
        # Should only have conversation NPCs in description
        target_desc = attack_tool['function']['parameters']['properties']['target']['description']
        assert 'Guard' in target_desc


class TestScopeEntityRetrieval:
    """Tests for _get_entities_for_scope helper method"""

    def test_conversation_scope_returns_npcs_only(self, default_context):
        """Scope 'conversation' should return NPCs without player"""
        result = FunctionManager._get_entities_for_scope('conversation', default_context)
        
        assert 'Guard' in result
        assert 'Dragonborn' not in result  # Player excluded

    def test_conversation_w_player_scope(self, default_context):
        """Scope 'conversation_w_player' should include player"""
        result = FunctionManager._get_entities_for_scope('conversation_w_player', default_context)
        
        assert 'Guard' in result
        assert 'Dragonborn' in result

    def test_nearby_scope(self, example_context_with_nearby: Context):
        """Scope 'nearby' should return only nearby NPCs"""
        
        result = FunctionManager._get_entities_for_scope('nearby', example_context_with_nearby)
        
        assert 'Bandit' in result
        assert 'Guard' not in result  # Conversation NPC excluded

    def test_all_npcs_scope(self, example_context_with_nearby: Context):
        """Scope 'all_npcs' should return conversation + nearby"""
        
        result = FunctionManager._get_entities_for_scope('all_npcs', example_context_with_nearby)
        
        assert 'Guard' in result  # Conversation
        assert 'Bandit' in result  # Nearby
        assert 'Dragonborn' not in result  # Player excluded

    def test_all_npcs_w_player_scope(self, example_context_with_nearby: Context):
        """Scope 'all_npcs_w_player' should return everyone"""
        
        result = FunctionManager._get_entities_for_scope('all_npcs_w_player', example_context_with_nearby)
        
        assert 'Guard' in result  # Conversation
        assert 'Bandit' in result  # Nearby
        assert 'Dragonborn' in result  # Player included

    def test_unknown_scope_returns_empty(self, default_context):
        """Unknown scope should return empty string and log warning"""
        result = FunctionManager._get_entities_for_scope('invalid_scope', default_context)
        
        assert result == ""