from typing import Any, Dict, List
import json
import logging


class ClaudeCacheConnector:
    """Adds Anthropic prompt-caching for Claude models via OpenRouter.

    - Automatically active when using OpenRouter with a Claude model.
    - Converts messages into Claude-compatible content blocks and applies
      a single cache breakpoint to the previous user message (before the
      latest user turn) so the entire conversation history (including
      assistant responses) can be cached while keeping only the newest user
      input uncached.

    Caching strategy:
    - Turn 1: system [cached] + user_new
    - Turn 2+: system + ... + user_previous [cached] + assistant + user_new

    This maximizes cache reuse as the conversation grows.
    """

    def is_applicable(self, base_url: str, model_name: str) -> bool:
        is_openrouter = base_url.strip().lower().startswith("https://openrouter.ai/")

        name = (model_name or "").strip().lower()
        is_claude_model = "claude" in name

        return is_openrouter and is_claude_model

    def transform_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not messages:
            return messages

        transformed: List[Dict[str, Any]] = [dict(message) for message in messages]

        cache_index = self._get_cache_target_index(transformed)
        if cache_index is not None:
            target_message = transformed[cache_index]
            target_message["content"] = self._normalize_content(target_message.get("content"))
            self._apply_cache_control(target_message)
            logging.debug(
                f"Claude cache: breakpoint at message {cache_index+1}/{len(transformed)} "
                f"(role={target_message.get('role')}), caching all messages up to this point"
            )

        return transformed

    def _normalize_content(self, content: Any) -> List[Dict[str, Any]]:
        """Convert any content format into a list of content blocks (dicts).
        
        Claude's caching API requires content to be a list of typed blocks.
        Plain string content or unexpected formats are wrapped accordingly.
        """
        if isinstance(content, list):
            normalized: List[Dict[str, Any]] = []
            for part in content:
                if isinstance(part, dict):
                    normalized_part = dict(part)
                    normalized_part.pop("cache_control", None) # clear stale markers
                    normalized.append(normalized_part)
                else:
                    normalized.append({"type": "text", "text": str(part)})
            return normalized

        if isinstance(content, str) or content is None:
            text_value = content if isinstance(content, str) else ""
            return [{"type": "text", "text": text_value}]

        return [{"type": "text", "text": json.dumps(content, ensure_ascii=False)}]

    def _get_cache_target_index(self, messages: List[Dict[str, Any]]) -> int | None:
        """Find the index of the message to apply cache_control to.

        Cache everything up to the latest user message. 
        This means either the second-to-last user message, 
        or the system message if there's only one user turn.
        """
        if not messages:
            return None

        last_idx = len(messages) - 1

        if messages[last_idx].get("role") == "user":
            for idx in range(last_idx - 1, -1, -1):
                role = messages[idx].get("role")
                if role == "user":
                    return idx
                if idx == 0 and role == "system":
                    return idx

        logging.debug("Claude cache: no suitable message found to cache "
        "(need at least system or previous user message)")
        return None

    def _apply_cache_control(self, message: Dict[str, Any]) -> None:
        """Attach cache_control to the last text block in the message."""
        contents = message.get("content", [])
        for idx in range(len(contents) - 1, -1, -1):
            part = contents[idx]
            if isinstance(part, dict) and part.get("type") == "text":
                updated_part = dict(part)
                updated_part["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
                contents[idx] = updated_part
                message["content"] = contents
                logging.debug(f"Claude cache: added cache_control to text block at index {idx}")
                return

        # Fallback: append an empty text block with cache_control
        contents.append({"type": "text", "text": "", "cache_control": {"type": "ephemeral", "ttl": "1h"}})
        message["content"] = contents
        logging.debug("Claude cache: appended empty text block with cache_control")
