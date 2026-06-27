from __future__ import annotations

from typing import Any, Dict, List
import json
import logging


class SonnetCacheConnector:
    """Adds Anthropic prompt-caching for Claude models via OpenRouter.

    - Only active when enabled and when using OpenRouter with a Claude model.
    - Injects the required header and converts messages into Claude-compatible content blocks.
    - Applies cache breakpoints to the stable system prompt and recent previous user messages
      so each request can reuse an existing prefix while extending the cache for the next turn.
    
    Caching strategy:
    - Turn 1: system [cached] + user_new
    - Turn 2+: system [cached] + ... + recent previous users [cached] + assistant + user_new
    
    This maximizes cache reuse as the conversation grows.
    """

    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    @staticmethod
    def _is_openrouter(base_url: str) -> bool:
        return base_url.strip().lower().startswith("https://openrouter.ai/")

    @staticmethod
    def _is_cacheable_model(model_name: str) -> bool:
        name = (model_name or "").strip().lower()
        return ("claude" in name) or ("gemini" in name)

    def is_applicable(self, base_url: str, model_name: str) -> bool:
        if not self._enabled:
            return False
        return self._is_openrouter(base_url) and self._is_cacheable_model(model_name)

    def augment_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        augmented = dict(headers or {})
        # Anthropic prompt caching header (proxied by OpenRouter)
        augmented["anthropic-beta"] = "prompt-caching-2024-07-31"
        return augmented

    def transform_messages(self, messages: List[Dict[str, Any]], model_name: str = "") -> List[Dict[str, Any]]:
        if not messages:
            return messages

        # Shallow-copy messages without altering their content format
        transformed: List[Dict[str, Any]] = [dict(message) for message in messages]

        for message in transformed:
            message["content"] = self._normalize_content(message.get("content"))

        cache_indices = self._get_cache_target_indices(transformed, model_name=model_name)
        for cache_index in cache_indices:
            target_message = transformed[cache_index]
            self._apply_cache_control(target_message)
            logging.debug(
                f"Claude cache: breakpoint at message {cache_index+1}/{len(transformed)} (role={target_message.get('role')}), "
                "caching all messages up to this point"
            )

        return transformed

    def _normalize_content(self, content: Any) -> List[Dict[str, Any]]:
        if isinstance(content, list):
            normalized: List[Dict[str, Any]] = []
            for part in content:
                if isinstance(part, dict):
                    normalized_part = dict(part)
                    normalized_part.pop("cache_control", None)
                    normalized.append(normalized_part)
                else:
                    normalized.append({"type": "text", "text": str(part)})
            return normalized

        if isinstance(content, str) or content is None:
            text_value = content if isinstance(content, str) else ""
            return [{"type": "text", "text": text_value}]

        return [{"type": "text", "text": json.dumps(content, ensure_ascii=False)}]

    def _get_cache_target_indices(self, messages: List[Dict[str, Any]], model_name: str = "") -> List[int]:
        """Find message indices to apply cache_control to.
        
        We cache reusable prefixes before the newest user input. Keeping the system breakpoint
        and recent previous user breakpoints allows request N+1 to hit a breakpoint created
        by request N, while also creating a newer breakpoint for the following request.
        """
        if not messages:
            return []

        last_idx = len(messages) - 1

        if messages[last_idx].get("role") != "user":
            logging.debug("Claude cache: no suitable message found to cache (latest message is not user)")
            return []

        normalized_model_name = (model_name or "").strip().lower()
        is_gemini_model = "gemini" in normalized_model_name

        cache_indices: List[int] = []
        max_breakpoints = 4

        has_system_message = messages[0].get("role") == "system"
        if has_system_message and not is_gemini_model:
            cache_indices.append(0)

        previous_user_indices = [
            idx
            for idx in range(last_idx)
            if messages[idx].get("role") == "user"
        ]
        remaining_breakpoints = max_breakpoints - len(cache_indices)
        cache_indices.extend(previous_user_indices[-remaining_breakpoints:])

        # Gemini on OpenRouter uses only the final breakpoint for normal message content.
        # Keep the system breakpoint as the final marker so cache target is stable.
        if is_gemini_model and has_system_message:
            cache_indices = [idx for idx in cache_indices if idx != 0]
            remaining_breakpoints = max_breakpoints - 1
            cache_indices = cache_indices[-remaining_breakpoints:]
            cache_indices.append(0)

        if cache_indices:
            return cache_indices

        logging.debug("Claude cache: no suitable message found to cache (need at least system or previous user)")
        return []

    def _apply_cache_control(self, message: Dict[str, Any]) -> None:
        contents = message.get("content", [])
        for idx in range(len(contents) - 1, -1, -1):
            part = contents[idx]
            if isinstance(part, dict) and part.get("type") == "text":
                updated_part = dict(part)
                updated_part["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
                contents[idx] = updated_part
                message["content"] = contents
                logging.debug(f"Claude cache: added cache_control to existing text block at index {idx}")
                return

        contents.append({"type": "text", "text": "", "cache_control": {"type": "ephemeral", "ttl": "1h"}})
        message["content"] = contents
        logging.debug("Claude cache: appended empty text block with cache_control")


