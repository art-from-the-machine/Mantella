import pytest
import json
from pathlib import Path
from src.actions.function_manager import FunctionManager
from src.conversation.context import Context

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
                'name': 'follow',
                'arguments': json.dumps({'source_npc_name': 'Guard'})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls)
    
    assert len(result) == 1
    assert 'identifier' in result[0]
    assert 'arguments' in result[0]
    assert result[0]['arguments'] == {'source_npc_name': 'Guard'}


def test_parse_function_calls_malformed_json():
    """Test parsing function calls with malformed JSON arguments"""
    tool_calls = [
        {
            'function': {
                'name': 'follow',
                'arguments': 'not valid json {'
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls)
    
    assert len(result) == 1
    assert result[0]['arguments'] == {}


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
                'arguments': json.dumps({'source': 'Guard'})
            }
        },
        {
            'function': {
                'name': 'Offended',
                'arguments': json.dumps({'source': 'Guard'})
            }
        }
    ]
    
    result = FunctionManager.parse_function_calls(tool_calls)
    
    assert len(result) == 2
    assert result[0]['arguments'] == {'source': 'Guard'}
    assert result[1]['arguments'] == {'source': 'Guard'}


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