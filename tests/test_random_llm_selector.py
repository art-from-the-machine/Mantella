import pytest
from pathlib import Path
from src.random_llm_selector import RandomLLMSelector, LLMSelection
from src.model_profile_manager import ModelProfileManager


def _make_selector(tmp_path: Path) -> RandomLLMSelector:
    """Create a RandomLLMSelector backed by a temp profile store."""
    mgr = ModelProfileManager(storage_path=tmp_path / "model_profiles.json")
    return RandomLLMSelector(profile_manager=mgr)


def _default_fallback() -> LLMSelection:
    return LLMSelection(service="OpenRouter", model="default-model", parameters={"temperature": 0.8, "max_tokens": 250})


class TestDisabledOrEmpty:
    def test_disabled_returns_none(self, tmp_path: Path):
        selector = _make_selector(tmp_path)
        result = selector.select(
            random_llm_enabled=False,
            random_llm_pool=[{"service": "OpenAI", "model": "gpt-4o-mini"}],
            fallback=_default_fallback(),
        )
        assert result is None

    def test_empty_pool_returns_none(self, tmp_path: Path):
        selector = _make_selector(tmp_path)
        result = selector.select(
            random_llm_enabled=True,
            random_llm_pool=[],
            fallback=_default_fallback(),
        )
        assert result is None

    def test_none_pool_returns_none(self, tmp_path: Path):
        selector = _make_selector(tmp_path)
        result = selector.select(
            random_llm_enabled=True,
            random_llm_pool=None,
            fallback=_default_fallback(),
        )
        assert result is None


class TestSingleEntry:
    def test_single_entry_always_selected(self, tmp_path: Path):
        selector = _make_selector(tmp_path)
        pool = [{"service": "OpenAI", "model": "gpt-4o-mini"}]
        result = selector.select(random_llm_enabled=True, random_llm_pool=pool, fallback=_default_fallback())
        assert result is not None
        assert result.service == "OpenAI"
        assert result.model == "gpt-4o-mini"

    def test_single_entry_uses_fallback_params_when_no_profile(self, tmp_path: Path):
        selector = _make_selector(tmp_path)
        fallback = LLMSelection(service="OpenRouter", model="default", parameters={"temperature": 0.5})
        pool = [{"service": "OpenAI", "model": "gpt-4o-mini"}]

        result = selector.select(random_llm_enabled=True, random_llm_pool=pool, fallback=fallback)
        assert result.parameters == {"temperature": 0.5}


class TestProfileResolution:
    def test_profile_params_override_fallback(self, tmp_path: Path):
        mgr = ModelProfileManager(storage_path=tmp_path / "model_profiles.json")
        mgr.create_or_update_profile("openrouter", "mistral-small", {"temperature": 0.2, "max_tokens": 100})
        selector = RandomLLMSelector(profile_manager=mgr)

        fallback = LLMSelection(service="OpenAI", model="default", parameters={"temperature": 0.9, "max_tokens": 500})
        pool = [{"service": "OpenRouter", "model": "mistral-small"}]

        result = selector.select(random_llm_enabled=True, random_llm_pool=pool, fallback=fallback)
        assert result is not None
        assert result.parameters == {"temperature": 0.2, "max_tokens": 100}

    def test_no_profile_falls_back_to_main_params(self, tmp_path: Path):
        mgr = ModelProfileManager(storage_path=tmp_path / "model_profiles.json")
        selector = RandomLLMSelector(profile_manager=mgr)

        fallback = LLMSelection(service="OpenAI", model="default", parameters={"temperature": 0.9})
        pool = [{"service": "OpenRouter", "model": "no-profile-model"}]

        result = selector.select(random_llm_enabled=True, random_llm_pool=pool, fallback=fallback)
        assert result is not None
        assert result.parameters == {"temperature": 0.9}

    def test_service_alias_resolves_profile(self, tmp_path: Path):
        """Profile saved under 'openrouter' should be found when pool entry says 'OpenRouter'."""
        mgr = ModelProfileManager(storage_path=tmp_path / "model_profiles.json")
        mgr.create_or_update_profile("openrouter", "model-x", {"max_tokens": 42})
        selector = RandomLLMSelector(profile_manager=mgr)

        pool = [{"service": "OpenRouter", "model": "model-x"}]
        result = selector.select(random_llm_enabled=True, random_llm_pool=pool, fallback=_default_fallback())
        assert result.parameters == {"max_tokens": 42}

    def test_apply_profile_false_ignores_profile(self, tmp_path: Path):
        """When apply_profile=False, stored profiles should be ignored and fallback params used."""
        mgr = ModelProfileManager(storage_path=tmp_path / "model_profiles.json")
        mgr.create_or_update_profile("openrouter", "mistral-small", {"temperature": 0.2, "max_tokens": 100})
        selector = RandomLLMSelector(profile_manager=mgr)

        fallback = LLMSelection(service="OpenAI", model="default", parameters={"temperature": 0.9, "max_tokens": 500})
        pool = [{"service": "OpenRouter", "model": "mistral-small"}]

        result = selector.select(random_llm_enabled=True, random_llm_pool=pool, fallback=fallback, apply_profile=False)
        assert result is not None
        assert result.parameters == {"temperature": 0.9, "max_tokens": 500}


class TestInvalidPoolEntries:
    def test_entry_missing_service_returns_none(self, tmp_path: Path):
        selector = _make_selector(tmp_path)
        pool = [{"model": "gpt-4o-mini"}]
        result = selector.select(random_llm_enabled=True, random_llm_pool=pool, fallback=_default_fallback())
        assert result is None

    def test_entry_missing_model_returns_none(self, tmp_path: Path):
        selector = _make_selector(tmp_path)
        pool = [{"service": "OpenAI"}]
        result = selector.select(random_llm_enabled=True, random_llm_pool=pool, fallback=_default_fallback())
        assert result is None

    def test_non_dict_entry_returns_none(self, tmp_path: Path):
        selector = _make_selector(tmp_path)
        pool = ["not-a-dict"]
        result = selector.select(random_llm_enabled=True, random_llm_pool=pool, fallback=_default_fallback())
        assert result is None

    def test_non_list_pool_returns_none(self, tmp_path: Path):
        selector = _make_selector(tmp_path)
        pool = "not-a-list"
        result = selector.select(random_llm_enabled=True, random_llm_pool=pool, fallback=_default_fallback())
        assert result is None
