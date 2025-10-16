from src.conversation.context import Context
from src.config.config_loader import ConfigLoader

def test_context_generates_prompt_without_actions_when_advanced_enabled(default_config: ConfigLoader, default_context: Context):
    """
    Tests that Context.generate_system_message returns empty actions placeholder when advanced actions are enabled
    """
    default_config.advanced_actions_enabled = True
    default_context._Context__config = default_config
    
    # Generate prompt with actions list
    prompt = default_context.generate_system_message(
        default_config.prompt,
        [a for a in default_config.actions if a.use_in_on_on_one]
    )
    
    # The prompt should not contain legacy action text when advanced actions are enabled
    # Check that none of the action prompts appear in the full prompt
    for action in default_config.actions:
        if action.use_in_on_on_one:
            # The keyword might still appear in character names/bios, but the full prompt text shouldn't
            assert action.prompt_text.format(key=action.keyword) not in prompt


def test_context_generates_prompt_with_actions_when_advanced_disabled(default_config: ConfigLoader, default_context: Context):
    """
    Tests that Context.generate_system_message includes actions placeholder when advanced actions are disabled
    """
    default_config.advanced_actions_enabled = False
    default_context._Context__config = default_config
    
    # Generate prompt with actions list
    prompt = default_context.generate_system_message(
        default_config.prompt,
        [a for a in default_config.actions if a.use_in_on_on_one]
    )
    
    # At least one action's prompt text should appear
    action_text_found = False
    for action in default_config.actions:
        if action.prompt_text.format(key=action.keyword) in prompt:
            action_text_found = True
            break
    
    assert action_text_found