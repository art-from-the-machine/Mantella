"""
LLM Debug Logger - Writes full LLM prompts/responses to a plain text file.

Enable via environment variable: MANTELLA_LLM_DEBUG=1

This exists because the regular Python logger was truncating/dropping characters
from large prompts. This writes raw ASCII to a file with no processing.
"""
import os
from pathlib import Path
from datetime import datetime

_log_path: Path | None = None
_enabled: bool = os.environ.get('MANTELLA_LLM_DEBUG', '').lower() in ('1', 'true', 'yes')


def set_log_folder(folder_path: str | Path):
    """Set the folder where llm_debug.log will be written."""
    global _log_path
    folder = Path(folder_path)
    folder.mkdir(parents=True, exist_ok=True)
    new_path = folder / 'llm_debug.log'
    
    # Only write header if this is a NEW path (different conversation)
    if _log_path != new_path:
        _log_path = new_path
        with open(_log_path, 'w', encoding='ascii', errors='replace') as f:
            f.write(f"=== LLM Debug Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")


def log(text: str):
    """Write a line to the debug log. No-op if not enabled or path not set."""
    if not _enabled or not _log_path:
        return
    
    try:
        timestamp = datetime.now().strftime('%H:%M:%S')
        with open(_log_path, 'a', encoding='ascii', errors='replace') as f:
            f.write(f"{timestamp} {text}\n")
    except:
        pass  # Never crash on debug logging


def log_section(title: str):
    """Log a section header."""
    log("")
    log("=" * 80)
    log(title)
    log("=" * 80)


def is_enabled() -> bool:
    """Check if debug logging is enabled."""
    return _enabled


def log_llm_request(openai_messages: list, vision_mode: str = None):
    """Log full LLM request with all messages."""
    if not _enabled:
        return
    
    log_section(f"LLM REQUEST - {len(openai_messages)} messages")
    if vision_mode:
        log(f"Vision mode: {vision_mode}")
    
    for i, msg in enumerate(openai_messages):
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        tool_calls = msg.get('tool_calls')
        
        log(f"--- Message {i} ({role}) ---")
        
        # Handle tool calls (actions)
        if tool_calls:
            action_names = [tc.get('function', {}).get('name', 'unknown') for tc in tool_calls]
            log(f"[TOOL CALLS: {', '.join(action_names)}]")
        
        # Handle content
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'text':
                        log(str(item.get('text', '')))
                    elif item.get('type') == 'image_url':
                        log("[IMAGE ATTACHED]")
                else:
                    log(str(item))
        elif content:  # Skip empty or None content
            log(str(content))
    log("")


def log_llm_response(response: str, token_count: int = None):
    """Log LLM response."""
    if not _enabled:
        return
    
    header = f"LLM RESPONSE ({token_count} tokens)" if token_count else "LLM RESPONSE"
    log_section(header)
    log(response.strip() if response else "")


def log_player_transcript(text: str, whisper_prompt: str = None):
    """Log player transcript with optional Whisper prompt."""
    if not _enabled:
        return
    
    log_section("PLAYER TRANSCRIPT")
    log(f"Text: {text}")
    if whisper_prompt:
        log(f"Whisper prompt: {whisper_prompt}")


def log_dynamic_vocab(prompt: str, response: str = None):
    """Log dynamic vocabulary extraction."""
    if not _enabled:
        return
    
    log_section("DYNAMIC VOCAB EXTRACTION")
    log(f"Prompt: {prompt}")
    if response:
        log(f"Response: {response}")

