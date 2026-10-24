"""Per-model capabilities for OpenAI chat models and a request parameter adapter.

Newer OpenAI models (GPT-5.x, GPT-6.x) reject several parameters that Mantella sends by default
(``max_tokens``, ``stop``, ``temperature`` with reasoning enabled ...). Instead of failing with
HTTP 400 in the middle of a conversation, :func:`adapt_request_params` rewrites the request for the
target model right before ``chat.completions.create`` is called.

The rules below were measured against the live OpenAI API in October 2026 by sending deliberately invalid
requests (a rejected request is free and the error names the offending parameter). Key findings:

* every reasoning-capable model wants ``max_completion_tokens`` instead of ``max_tokens``
  and rejects ``stop``;
* ``temperature``/``top_p``/penalties are only accepted while ``reasoning_effort`` is ``none``
  (models without ``none`` never accept them);
* GPT-5.4+, GPT-5.5, GPT-5.6 and GPT-6 Sol/Luna accept function tools in Chat Completions only with
  ``reasoning_effort = none``; GPT-6 Astra and GPT-6.1 Sol do not accept function tools at all;
* classic models (gpt-4o, gpt-4.1) reject ``reasoning_effort`` and any ``verbosity`` other than medium.

Models that are not in the table and are not OpenAI models (local models, OpenRouter ids with a
provider prefix, ...) pass through unchanged, so upstream behaviour is preserved.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import src.utils as utils

logger = utils.get_logger()

OPENAI_BASE_URL = 'https://api.openai.com/v1'

# Order from "least thinking" to "most thinking"; used to map an unsupported value to the closest one
EFFORT_ORDER: tuple[str, ...] = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')

# Extra completion tokens granted on top of Mantella's max_tokens when the model is reasoning.
# Reasoning tokens count against max_completion_tokens; without headroom a 250-token budget can be
# consumed entirely by reasoning, leaving an empty reply. Only tokens actually generated are billed.
REASONING_HEADROOM: dict[str, int] = {
    'none': 0, 'minimal': 512, 'low': 2048, 'medium': 4096, 'high': 8192, 'xhigh': 16384, 'max': 32768,
}

SAMPLING_PARAMS: tuple[str, ...] = ('temperature', 'top_p', 'logprobs', 'top_logprobs', 'logit_bias')
PENALTY_PARAMS: tuple[str, ...] = ('frequency_penalty', 'presence_penalty')


@dataclass(frozen=True)
class ModelCapabilities:
    model: str
    context_window: int
    max_output: int
    vision: bool = True
    # 'classic'  : gpt-4o / gpt-4.1 style; max_tokens, all sampling params, no reasoning_effort
    # 'reasoning': reasoning model (gpt-5.x / gpt-6.x / o-series)
    family: str = 'reasoning'
    effort_values: tuple[str, ...] = ()
    default_effort: str | None = None
    # tools in /v1/chat/completions: 'yes' | 'effort_none' (only with reasoning_effort=none) | 'no'
    tools: str = 'yes'
    supports_verbosity: bool = True
    supports_penalties: bool = True
    deprecated: bool = False
    note: str = ''

    @property
    def is_reasoning(self) -> bool:
        return self.family == 'reasoning'

    @property
    def supports_tools(self) -> bool:
        return self.tools != 'no'


def _classic(model, ctx, out, vision=True, deprecated=False, note=''):
    return ModelCapabilities(model, ctx, out, vision=vision, family='classic', tools='yes',
                             supports_verbosity=False, deprecated=deprecated, note=note)


_GPT5_EFFORTS = ('minimal', 'low', 'medium', 'high')
_NONE_TO_HIGH = ('none', 'low', 'medium', 'high')
_NONE_TO_XHIGH = ('none', 'low', 'medium', 'high', 'xhigh')
_LOW_TO_XHIGH = ('low', 'medium', 'high', 'xhigh')

_TABLE: list[ModelCapabilities] = [
    # --- classic (non-reasoning) ---
    _classic('gpt-3.5-turbo', 16_385, 4_096, vision=False),
    _classic('gpt-4', 8_191, 8_192, vision=False),
    _classic('gpt-4-turbo', 128_000, 4_096),
    _classic('gpt-4o', 128_000, 16_384),
    _classic('gpt-4o-mini', 128_000, 16_384),
    _classic('gpt-4.1', 1_047_576, 32_768),
    _classic('gpt-4.1-mini', 1_047_576, 32_768),
    _classic('gpt-4.1-nano', 1_047_576, 32_768, deprecated=True,
             note='API returns "deprecated" (404) as of 2026-10-24'),
    # --- GPT-5 (Aug 2025): minimal..high, default medium, no sampling params at all ---
    ModelCapabilities('gpt-5', 400_000, 128_000, effort_values=_GPT5_EFFORTS, default_effort='medium'),
    ModelCapabilities('gpt-5-mini', 400_000, 128_000, effort_values=_GPT5_EFFORTS, default_effort='medium'),
    ModelCapabilities('gpt-5-nano', 400_000, 128_000, effort_values=_GPT5_EFFORTS, default_effort='medium'),
    # --- GPT-5.1 / 5.2: none..high(/xhigh), default none, tools with any effort ---
    ModelCapabilities('gpt-5.1', 400_000, 128_000, effort_values=_NONE_TO_HIGH, default_effort='none'),
    ModelCapabilities('gpt-5.2', 400_000, 128_000, effort_values=_NONE_TO_XHIGH, default_effort='none'),
    # --- GPT-5.4+: tools only with effort none in Chat Completions ---
    ModelCapabilities('gpt-5.4', 1_050_000, 128_000, effort_values=_NONE_TO_XHIGH, default_effort='none',
                      tools='effort_none'),
    ModelCapabilities('gpt-5.4-mini', 400_000, 128_000, effort_values=_NONE_TO_XHIGH, default_effort='none',
                      tools='effort_none'),
    ModelCapabilities('gpt-5.4-nano', 400_000, 128_000, effort_values=_NONE_TO_XHIGH, default_effort='none',
                      tools='effort_none',
                      note='marked deprecated on its model page but still served'),
    ModelCapabilities('gpt-5.5', 1_050_000, 128_000, effort_values=_NONE_TO_XHIGH, default_effort='medium',
                      tools='effort_none'),
    ModelCapabilities('gpt-5.6-sol', 1_050_000, 128_000, effort_values=_NONE_TO_XHIGH, default_effort='medium',
                      tools='effort_none'),
    ModelCapabilities('gpt-5.6-terra', 1_050_000, 128_000, effort_values=_NONE_TO_XHIGH, default_effort='medium',
                      tools='effort_none'),
    ModelCapabilities('gpt-5.6-luna', 1_050_000, 128_000, effort_values=_NONE_TO_XHIGH, default_effort='medium',
                      tools='effort_none'),
    # --- GPT-6 ---
    ModelCapabilities('gpt-6-sol', 1_050_000, 128_000, effort_values=_NONE_TO_XHIGH, default_effort='medium',
                      tools='effort_none'),
    ModelCapabilities('gpt-6-luna', 1_050_000, 128_000, effort_values=_NONE_TO_XHIGH, default_effort='medium',
                      tools='effort_none', supports_penalties=False,
                      note='frequency/presence_penalty cause HTTP 500 (measured), so they are dropped'),
    ModelCapabilities('gpt-6.1-sol', 1_050_000, 128_000, effort_values=_LOW_TO_XHIGH, default_effort='medium',
                      tools='no',
                      note='no function tools in Chat Completions: NPC actions are disabled'),
    ModelCapabilities('gpt-6-astra', 1_050_000, 128_000, effort_values=_LOW_TO_XHIGH, default_effort='medium',
                      tools='no',
                      note='no function tools in Chat Completions: NPC actions are disabled'),
]

_BY_ID: dict[str, ModelCapabilities] = {c.model: c for c in _TABLE}

_SNAPSHOT_RE = re.compile(r'-(\d{4}-\d{2}-\d{2}|\d{4})$')
_NON_CHAT_RE = re.compile(r'(audio|realtime|transcribe|tts|image|search|codex|embedding|whisper|dall-e|live|moderation|-pro$|deep-research)')


def normalize_model_id(model: str) -> str:
    """'openai/gpt-5-mini-2025-08-07' -> 'gpt-5-mini'"""
    model = (model or '').strip().lower()
    if model.startswith('openai/'):
        model = model[len('openai/'):]
    return _SNAPSHOT_RE.sub('', model)


def get_capabilities(model: str) -> ModelCapabilities | None:
    """Capabilities for a known model id (snapshot suffixes and an 'openai/' prefix are ignored).
    Unknown OpenAI-looking ids get a conservative family guess; everything else returns None."""
    norm = normalize_model_id(model)
    if norm in _BY_ID:
        return _BY_ID[norm]
    if '/' in norm or _NON_CHAT_RE.search(norm):
        return None
    # Future / unlisted models: assume the newest observed behaviour of their family
    if re.match(r'^o\d', norm):
        return ModelCapabilities(norm, 200_000, 100_000, effort_values=('low', 'medium', 'high'),
                                 default_effort='medium', supports_verbosity=False, note='guessed (o-series)')
    m = re.match(r'^gpt-(\d+)(?:\.(\d+))?', norm)
    if m:
        major, minor = int(m.group(1)), int(m.group(2) or 0)
        if major >= 6 or (major == 5 and minor >= 4):
            return ModelCapabilities(norm, 400_000, 128_000, effort_values=(), default_effort='medium',
                                     tools='effort_none', note='guessed (gpt-5.4+ family)')
        if major == 5:
            return ModelCapabilities(norm, 400_000, 128_000, effort_values=(), default_effort=None,
                                     note='guessed (gpt-5 family)')
    return None


def is_reasoning(model: str) -> bool:
    caps = get_capabilities(model)
    return bool(caps and caps.is_reasoning)


def supports_vision(model: str) -> bool:
    caps = get_capabilities(model)
    return bool(caps and caps.vision)


def supports_tools(model: str) -> bool:
    caps = get_capabilities(model)
    return True if caps is None else caps.supports_tools


def token_limit(model: str) -> int | None:
    """Context window of a known model, or None."""
    caps = get_capabilities(model)
    return caps.context_window if caps else None


def openai_token_limits() -> dict[str, int]:
    """Token limits of all models in the table, keyed by model id (for utils.get_model_token_limits)."""
    return {c.model: c.context_window for c in _TABLE}


def summary_token_threshold(model_token_limit: int, limit_pct: float, configured_max: int = 0) -> int:
    """Token count above which an NPC's conversation summaries are condensed (resummarised).

    Upstream uses ``model_token_limit * limit_pct`` (30%). With 1M-token models that is ~315k tokens,
    so summaries are never condensed and every summary is injected into every prompt forever.
    ``configured_max`` (config ``summary_condense_token_limit``) caps the threshold; 0 keeps upstream behaviour.
    """
    threshold = int(model_token_limit * limit_pct)
    if configured_max and configured_max > 0:
        threshold = min(threshold, int(configured_max))
    return threshold


def _closest_effort(requested: str, supported: tuple[str, ...]) -> str:
    """Map an effort value to a supported one, preferring the next *higher* level (never silently less thinking
    than 'none' allows, e.g. 'none' on gpt-5-mini -> 'minimal')."""
    if not supported or requested in supported:
        return requested
    if requested not in EFFORT_ORDER:
        return supported[0]
    idx = EFFORT_ORDER.index(requested)
    for candidate in EFFORT_ORDER[idx:]:
        if candidate in supported:
            return candidate
    return supported[-1]


_warned: set[tuple[str, str]] = set()


def _log_once(model: str, key: str, message: str, level: int = logging.INFO) -> None:
    if (model, key) in _warned:
        return
    _warned.add((model, key))
    logger.log(level, message)


def adapt_request_params(model: str, params: dict[str, Any] | None, base_url: str | None = None) -> dict[str, Any]:
    """Return a copy of ``params`` that the given OpenAI model accepts.

    Args:
        model: model id as sent to the API
        params: request kwargs other than model/messages/stream (max_tokens, temperature, tools, ...)
        base_url: endpoint the request goes to. When given and not api.openai.com, params pass through
            unchanged (OpenRouter / local servers translate parameters themselves).
    """
    adapted: dict[str, Any] = dict(params or {})
    if base_url is not None and base_url.rstrip('/') != OPENAI_BASE_URL:
        return adapted
    if base_url is None and '/' in (model or '') and not model.lower().startswith('openai/'):
        return adapted
    caps = get_capabilities(model)
    if caps is None:
        return adapted

    dropped: list[str] = []

    if not caps.is_reasoning:
        for key in ('reasoning_effort', 'reasoning'):
            if key in adapted:
                adapted.pop(key); dropped.append(key)
        if 'verbosity' in adapted and adapted['verbosity'] != 'medium':
            adapted.pop('verbosity'); dropped.append('verbosity')
        if dropped:
            _log_once(caps.model, 'classic:' + ','.join(dropped),
                      f"{model} is not a reasoning model; ignoring parameters: {', '.join(dropped)}")
        return adapted

    # --- reasoning models ---
    has_tools = bool(adapted.get('tools'))
    if has_tools and caps.tools == 'no':
        adapted.pop('tools', None)
        adapted.pop('tool_choice', None)
        adapted.pop('parallel_tool_calls', None)
        has_tools = False
        _log_once(caps.model, 'no-tools',
                  f"{model} does not support function tools in Chat Completions; NPC actions are disabled for this model. "
                  f"Choose another model (e.g. gpt-5.4-mini, gpt-6-luna) to use actions.", logging.WARNING)

    effort = adapted.get('reasoning_effort')
    if effort is not None:
        effort = str(effort).strip().lower()
        mapped = _closest_effort(effort, caps.effort_values)
        if mapped != effort:
            _log_once(caps.model, f'effort:{effort}', f"{model} does not support reasoning_effort '{effort}', using '{mapped}'")
        effort = mapped
    if has_tools and caps.tools == 'effort_none' and (effort or caps.default_effort) not in (None, 'none'):
        _log_once(caps.model, 'tools-effort-none',
                  f"{model} only accepts function tools with reasoning_effort 'none' in Chat Completions; "
                  f"using 'none' instead of '{effort or caps.default_effort}' for calls with actions")
        effort = 'none'
    if effort is not None:
        adapted['reasoning_effort'] = effort
    effective_effort = effort if effort is not None else caps.default_effort

    # Token budget: max_tokens -> max_completion_tokens (+ headroom for reasoning tokens)
    if 'max_tokens' in adapted:
        max_tokens = adapted.pop('max_tokens')
        if 'max_completion_tokens' not in adapted and max_tokens is not None:
            headroom = REASONING_HEADROOM.get(effective_effort or 'medium', REASONING_HEADROOM['medium'])
            adapted['max_completion_tokens'] = int(max_tokens) + headroom

    if 'stop' in adapted:
        adapted.pop('stop'); dropped.append('stop')

    sampling_ok = effective_effort == 'none'
    for key in SAMPLING_PARAMS:
        if key in adapted and not sampling_ok:
            adapted.pop(key); dropped.append(key)
    for key in PENALTY_PARAMS:
        if key in adapted and (not sampling_ok or not caps.supports_penalties):
            adapted.pop(key); dropped.append(key)

    if 'verbosity' in adapted and not caps.supports_verbosity:
        adapted.pop('verbosity'); dropped.append('verbosity')

    if dropped:
        _log_once(caps.model, f'drop:{effective_effort}:' + ','.join(dropped),
                  f"{model} (reasoning_effort={effective_effort}) does not accept: {', '.join(dropped)}; dropped from the request")
    return adapted


def merge_config_params(params: dict[str, Any] | None, reasoning_effort: str | None, verbosity: str | None) -> dict[str, Any] | None:
    """Merge the UI settings `reasoning_effort` / `verbosity` into the request params.

    'Model default' (or empty) leaves params untouched, which is upstream behaviour. Values already present in
    the JSON params win, so power users keep full control. The adapter later drops them for models that do not
    support them.
    """
    extra: dict[str, Any] = {}
    for key, value in (('reasoning_effort', reasoning_effort), ('verbosity', verbosity)):
        if value and str(value).strip().lower() not in ('model default', 'default', ''):
            extra[key] = str(value).strip().lower()
    if not extra:
        return params
    merged = dict(extra)
    merged.update(params or {})
    return merged


def openai_model_catalog() -> list[dict[str, Any]]:
    """OpenAI chat models in the OpenRouter-like format used by ClientBase.get_model_list.
    Deprecated models are omitted. Prices are not stored to avoid sharing outdated information (-1 = unknown)."""
    catalog = []
    for c in _TABLE:
        if c.deprecated:
            continue
        supported = ['max_tokens']
        if c.supports_tools:
            supported.append('tools')
        if c.is_reasoning:
            supported.append('reasoning')
        catalog.append({
            "id": c.model,
            "model_extra": {
                "context_length": c.context_window,
                "pricing": {"prompt": -1, "completion": -1},
                "architecture": {"modality": "text+image->text" if c.vision else "text->text"},
                "supported_parameters": supported,
            },
        })
    return catalog
