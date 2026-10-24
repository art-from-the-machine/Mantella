"""Tests for src/llm/model_capabilities.py and its hooks in ClientBase / Summaries.
The OpenAI client is mocked; no network calls are made."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.llm import model_capabilities as mc
from src.llm.client_base import ClientBase
from src.llm.message_thread import message_thread
from src.llm.messages import SystemMessage, UserMessage

OPENAI = 'https://api.openai.com/v1'
MANTELLA_DEFAULT = {"max_tokens": 250, "stop": ["#"]}
TOOLS = [{"type": "function", "function": {"name": "Follow", "description": "Follow", "parameters": {"type": "object", "properties": {}}}}]


# ---------------------------------------------------------------- lookup helpers

def test_normalize_strips_prefix_and_snapshot():
    assert mc.normalize_model_id('openai/gpt-5-mini-2025-08-07') == 'gpt-5-mini'
    assert mc.normalize_model_id('gpt-4o-mini-2024-07-18') == 'gpt-4o-mini'
    assert mc.normalize_model_id('GPT-6-Luna') == 'gpt-6-luna'


def test_helpers():
    assert mc.is_reasoning('gpt-5.4-mini') and not mc.is_reasoning('gpt-4.1-mini')
    assert mc.supports_vision('gpt-6-luna') and not mc.supports_vision('gpt-3.5-turbo')
    assert mc.token_limit('gpt-4.1-mini') == 1_047_576
    assert mc.token_limit('gpt-5.4-mini-2026-03-17') == 400_000
    assert mc.token_limit('llama-3-8b') is None
    assert not mc.supports_tools('gpt-6-astra') and mc.supports_tools('gpt-6-luna')
    assert mc.supports_tools('some-local-model')  # unknown -> don't block


def test_unknown_and_non_chat_models_have_no_caps():
    assert mc.get_capabilities('mistral-small') is None
    assert mc.get_capabilities('gpt-realtime-2') is None
    assert mc.get_capabilities('google/gemma-4-26b-a4b-it:free') is None


def test_future_models_get_conservative_guess():
    caps = mc.get_capabilities('gpt-7-nova')
    assert caps and caps.is_reasoning and caps.tools == 'effort_none'


# ---------------------------------------------------------------- adapter

def test_classic_model_keeps_mantella_defaults():
    out = mc.adapt_request_params('gpt-4.1-mini', {**MANTELLA_DEFAULT, "temperature": 0.8, "reasoning_effort": "low", "verbosity": "low"}, OPENAI)
    assert out == {"max_tokens": 250, "stop": ["#"], "temperature": 0.8}


def test_classic_model_keeps_medium_verbosity():
    assert mc.adapt_request_params('gpt-4o-mini', {"verbosity": "medium"}, OPENAI) == {"verbosity": "medium"}


def test_gpt5_mini_renames_max_tokens_and_drops_unsupported():
    params = {**MANTELLA_DEFAULT, "temperature": 0.7, "top_p": 0.9, "frequency_penalty": 0.1, "presence_penalty": 0.1}
    out = mc.adapt_request_params('gpt-5-mini', params, OPENAI)
    # default effort medium -> reasoning headroom added
    assert out == {"max_completion_tokens": 250 + mc.REASONING_HEADROOM['medium']}
    assert params["max_tokens"] == 250  # input not mutated


def test_gpt5_none_maps_to_minimal():
    out = mc.adapt_request_params('gpt-5-nano', {"max_tokens": 100, "reasoning_effort": "none"}, OPENAI)
    assert out["reasoning_effort"] == "minimal"
    assert out["max_completion_tokens"] == 100 + mc.REASONING_HEADROOM['minimal']


def test_effort_none_keeps_sampling_params():
    params = {**MANTELLA_DEFAULT, "temperature": 0.7, "top_p": 0.9, "frequency_penalty": 0.1, "reasoning_effort": "none", "verbosity": "low"}
    out = mc.adapt_request_params('gpt-5.4-mini', params, OPENAI)
    assert out == {"max_completion_tokens": 250, "temperature": 0.7, "top_p": 0.9, "frequency_penalty": 0.1,
                   "reasoning_effort": "none", "verbosity": "low"}


def test_default_effort_none_model_keeps_temperature():
    # gpt-5.1/5.2/5.4 default to none (measured: temperature accepted without reasoning_effort)
    out = mc.adapt_request_params('gpt-5.2', {"temperature": 0.5, "max_tokens": 250}, OPENAI)
    assert out == {"temperature": 0.5, "max_completion_tokens": 250}


def test_effort_low_drops_sampling_params():
    out = mc.adapt_request_params('gpt-5.4-mini', {"temperature": 0.7, "presence_penalty": 0.2, "reasoning_effort": "low"}, OPENAI)
    assert out == {"reasoning_effort": "low"}


def test_tools_force_effort_none_on_new_models():
    out = mc.adapt_request_params('gpt-6-luna', {"max_tokens": 250, "reasoning_effort": "low", "tools": TOOLS, "temperature": 0.7}, OPENAI)
    assert out["reasoning_effort"] == "none"
    assert out["tools"] == TOOLS
    assert out["max_completion_tokens"] == 250
    assert out["temperature"] == 0.7


def test_tools_with_default_medium_effort_set_none_explicitly():
    out = mc.adapt_request_params('gpt-6-luna', {"tools": TOOLS}, OPENAI)
    assert out["reasoning_effort"] == "none"


def test_tools_allowed_with_effort_on_gpt51():
    out = mc.adapt_request_params('gpt-5.1', {"tools": TOOLS, "reasoning_effort": "low"}, OPENAI)
    assert out == {"tools": TOOLS, "reasoning_effort": "low"}


def test_no_tool_models_drop_tools():
    out = mc.adapt_request_params('gpt-6-astra', {"tools": TOOLS, "tool_choice": "auto", "reasoning_effort": "none", "max_tokens": 250}, OPENAI)
    assert "tools" not in out and "tool_choice" not in out
    assert out["reasoning_effort"] == "low"  # astra has no none/minimal
    assert out["max_completion_tokens"] == 250 + mc.REASONING_HEADROOM['low']


def test_gpt6_luna_drops_penalties_even_with_effort_none():
    out = mc.adapt_request_params('gpt-6-luna', {"reasoning_effort": "none", "frequency_penalty": 0.1, "presence_penalty": 0.1, "temperature": 0.7}, OPENAI)
    assert out == {"reasoning_effort": "none", "temperature": 0.7}


def test_explicit_max_completion_tokens_wins():
    out = mc.adapt_request_params('gpt-5-mini', {"max_tokens": 250, "max_completion_tokens": 999}, OPENAI)
    assert out == {"max_completion_tokens": 999}


def test_non_openai_endpoint_passthrough():
    params = {**MANTELLA_DEFAULT, "temperature": 0.7}
    assert mc.adapt_request_params('gpt-5-mini', params, 'https://openrouter.ai/api/v1') == params
    assert mc.adapt_request_params('openai/gpt-5-mini', params) == mc.adapt_request_params('gpt-5-mini', params, OPENAI)
    assert mc.adapt_request_params('meta/llama-3', params) == params


def test_unknown_model_passthrough():
    params = {**MANTELLA_DEFAULT, "temperature": 0.7}
    assert mc.adapt_request_params('my-local-model', params, OPENAI) == params


def test_none_params():
    assert mc.adapt_request_params('gpt-5-mini', None, OPENAI) == {}


@pytest.mark.parametrize("requested,supported,expected", [
    ("none", ('minimal', 'low', 'medium', 'high'), "minimal"),
    ("minimal", ('none', 'low', 'medium'), "low"),
    ("max", ('none', 'low', 'medium', 'high', 'xhigh'), "xhigh"),
    ("bogus", ('low', 'medium'), "low"),
    ("low", ('low',), "low"),
])
def test_closest_effort(requested, supported, expected):
    assert mc._closest_effort(requested, supported) == expected


# ---------------------------------------------------------------- config merge / summary threshold / catalog

def test_merge_config_params():
    assert mc.merge_config_params({"max_tokens": 250}, "Model default", "Model default") == {"max_tokens": 250}
    assert mc.merge_config_params({"max_tokens": 250}, "none", "low") == {"reasoning_effort": "none", "verbosity": "low", "max_tokens": 250}
    # JSON params win
    assert mc.merge_config_params({"reasoning_effort": "low"}, "none", None) == {"reasoning_effort": "low"}
    assert mc.merge_config_params(None, "minimal", "") == {"reasoning_effort": "minimal"}


def test_summary_threshold():
    assert mc.summary_token_threshold(1_047_576, 0.3, 0) == 314_272  # upstream
    assert mc.summary_token_threshold(1_047_576, 0.3, 6000) == 6000
    assert mc.summary_token_threshold(4096, 0.3, 6000) == 1228  # never above upstream


def test_catalog_shape_and_flags():
    catalog = {m["id"]: m["model_extra"] for m in mc.openai_model_catalog()}
    assert "gpt-4.1-nano" not in catalog  # deprecated
    assert "tools" in catalog["gpt-6-luna"]["supported_parameters"]
    assert "tools" not in catalog["gpt-6-astra"]["supported_parameters"]
    assert "reasoning" in catalog["gpt-5-mini"]["supported_parameters"]
    assert catalog["gpt-4.1-mini"]["context_length"] == 1_047_576


def test_openai_model_list_in_ui():
    result = ClientBase.get_model_list("OpenAI")
    ids = [model_id for _, model_id in result.available_models]
    for model in ("gpt-4.1-mini", "gpt-5-mini", "gpt-5.4-mini", "gpt-6-luna", "gpt-6.1-sol"):
        assert model in ids
    names = dict((model_id, name) for name, model_id in result.available_models)
    assert "✅ Advanced Actions" in names["gpt-6-luna"] and "⚠️ Reasoning" in names["gpt-6-luna"]
    assert "✅ Advanced Actions" not in names["gpt-6-astra"]
    assert "Prompt: unknown" in names["gpt-6-luna"]  # prices are not stored
    assert result.allows_manual_model_input
    tool_ids = [m for _, m in ClientBase.get_model_list("OpenAI", is_tool_calling=True).available_models]
    assert "gpt-6-astra" not in tool_ids and "gpt-6-luna" in tool_ids


def test_token_limit_dict_contains_new_models():
    import src.utils as utils
    limits = utils.get_model_token_limits()
    assert limits["gpt-6-luna"] == 1_050_000
    assert limits["gpt-5-mini"] == 400_000


# ---------------------------------------------------------------- ClientBase hooks (mocked OpenAI client)

def _make_client(model: str, params: dict) -> ClientBase:
    with patch.object(ClientBase, '_get_api_key', return_value='sk-test'):
        return ClientBase('OpenAI', model, params, 4096)


def test_client_base_token_limit_for_snapshot():
    client = _make_client('gpt-5.4-mini-2026-03-17', {})
    assert client.token_limit == 400_000


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        self._it = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


def _chunk(content):
    delta = MagicMock(content=content, tool_calls=None)
    return MagicMock(choices=[MagicMock(delta=delta)])


def test_streaming_call_sends_adapted_params():
    client = _make_client('gpt-6-luna', {"max_tokens": 250, "stop": ["#"], "reasoning_effort": "low", "frequency_penalty": 0.1})
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeStream([_chunk("Hail, "), _chunk("traveler.")])

    async_client = MagicMock()
    async_client.chat.completions.create = fake_create

    async def close():
        return None
    async_client.close = close
    client._startup_async_client = async_client

    thread = message_thread(None, SystemMessage("You are a guard.", None))
    thread.add_message(UserMessage(None, "Hello", "Player"))

    async def run():
        return [item async for item in client.streaming_call(thread, False, tools=TOOLS)]

    items = asyncio.run(run())
    assert [i for i in items if i[0] == "content"] == [("content", "Hail, "), ("content", "traveler.")]
    assert captured["model"] == 'gpt-6-luna'
    assert captured["stream"] is True
    assert captured["reasoning_effort"] == "none"  # forced because tools are present
    assert captured["max_completion_tokens"] == 250
    assert "max_tokens" not in captured and "stop" not in captured and "frequency_penalty" not in captured
    assert captured["tools"] == TOOLS
    # the configured params are untouched for the next call
    assert client._request_params == {"max_tokens": 250, "stop": ["#"], "reasoning_effort": "low", "frequency_penalty": 0.1}


def test_request_call_sends_adapted_params():
    client = _make_client('gpt-5-mini', {"max_tokens": 250, "stop": ["#"], "reasoning_effort": "minimal"})
    sync_client = MagicMock()
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content="A summary."))]
    sync_client.chat.completions.create.return_value = completion
    with patch.object(ClientBase, 'generate_sync_client', return_value=sync_client):
        reply = client.request_call(UserMessage(None, "Summarise", "Player"))
    assert reply == "A summary."
    kwargs = sync_client.chat.completions.create.call_args.kwargs
    assert kwargs["max_completion_tokens"] == 250 + mc.REASONING_HEADROOM['minimal']
    assert kwargs["reasoning_effort"] == "minimal"
    assert "stop" not in kwargs and "max_tokens" not in kwargs


def test_request_call_classic_model_unchanged():
    client = _make_client('gpt-4.1-mini', {"max_tokens": 250, "stop": ["#"]})
    sync_client = MagicMock()
    sync_client.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))])
    with patch.object(ClientBase, 'generate_sync_client', return_value=sync_client):
        client.request_call(UserMessage(None, "hi", "Player"))
    kwargs = sync_client.chat.completions.create.call_args.kwargs
    assert kwargs["max_tokens"] == 250 and kwargs["stop"] == ["#"]
