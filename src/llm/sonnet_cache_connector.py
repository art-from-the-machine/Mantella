from __future__ import annotations

from typing import Any, Dict, List
import json
import logging


class SonnetCacheConnector:
    """Adds Anthropic prompt-caching for Claude Sonnet models via OpenRouter.

    - Only active when enabled and when using OpenRouter with a Sonnet model.
    - Injects the required header and converts messages into Claude-compatible content blocks.
    - Applies a single cache breakpoint to the previous user message (before the latest user turn)
      so the entire conversation history (including assistant responses) can be cached while keeping 
      only the newest user input uncached.
    
    Caching strategy:
    - Turn 1: system [cached] + user_new
    - Turn 2+: system + ... + user_previous [cached] + assistant + user_new
    
    This maximizes cache reuse as the conversation grows.
    """

    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    @staticmethod
    def _is_openrouter(base_url: str) -> bool:
        return base_url.strip().lower().startswith("https://openrouter.ai/")

    @staticmethod
    def _is_sonnet_model(model_name: str) -> bool:
        name = (model_name or "").strip().lower()
        return "sonnet" in name  # covers claude-3.5/3.7 sonnet variants

    def is_applicable(self, base_url: str, model_name: str) -> bool:
        if not self._enabled:
            return False
        return self._is_openrouter(base_url) and self._is_sonnet_model(model_name)

    def augment_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        augmented = dict(headers or {})
        # Anthropic prompt caching header (proxied by OpenRouter)
        augmented["anthropic-beta"] = "prompt-caching-2024-07-31"
        return augmented

    def transform_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not messages:
            return messages

        # Shallow-copy messages without altering their content format
        transformed: List[Dict[str, Any]] = [dict(message) for message in messages]

        cache_index = self._get_cache_target_index(transformed)
        if cache_index is not None:
            target_message = transformed[cache_index]
            target_message["content"] = self._normalize_content(target_message.get("content"))
            self._apply_cache_control(target_message)
            logging.debug(
                f"Sonnet cache: breakpoint at message {cache_index+1}/{len(transformed)} (role={target_message.get('role')}), "
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

    def _get_cache_target_index(self, messages: List[Dict[str, Any]]) -> int | None:
        """Find the index of the message to apply cache_control to.
        
        We want to cache everything UP TO the latest user message (before the current/new one).
        This means we put cache_control on the second-to-last user message or the system message.
        """
        if not messages:
            return None

        last_idx = len(messages) - 1
        
        # If the last message is user (the new input), search backwards for the previous user message
        if messages[last_idx].get("role") == "user":
            # Search backwards from second-to-last message
            for idx in range(last_idx - 1, -1, -1):
                role = messages[idx].get("role")
                # Put breakpoint on the last user message before the current one
                # (this caches all history including that user's message and the assistant's response)
                if role == "user":
                    return idx
                # Fallback: if we only have system + new user, cache the system message
                if idx == 0 and role == "system":
                    return idx
        
        logging.debug("Sonnet cache: no suitable message found to cache (need at least system or previous user)")
        return None

    def _apply_cache_control(self, message: Dict[str, Any]) -> None:
        contents = message.get("content", [])
        for idx in range(len(contents) - 1, -1, -1):
            part = contents[idx]
            if isinstance(part, dict) and part.get("type") == "text":
                updated_part = dict(part)
                updated_part["cache_control"] = {"type": "ephemeral"}
                contents[idx] = updated_part
                message["content"] = contents
                logging.debug(f"Sonnet cache: added cache_control to existing text block at index {idx}")
                return

        contents.append({"type": "text", "text": "", "cache_control": {"type": "ephemeral"}})
        message["content"] = contents
        logging.debug("Sonnet cache: appended empty text block with cache_control")


