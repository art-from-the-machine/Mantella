import pytest
import json
from pathlib import Path
from src.actions.function_manager import FunctionManager
from src.conversation.context import Context
from src.characters_manager import Characters

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


def test_parse_function_calls_with_validation_source_string_converted_to_list(example_characters_pc_to_npc: Characters):
    """Test that single source string is converted to list"""
    FunctionManager.load_all_actions()
    
    tool_calls = [
        {
            'function': {
                'name': 'Follow',
                'arguments': json.dumps({'source': 'Guard'})
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