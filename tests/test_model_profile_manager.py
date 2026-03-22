import json
import pytest
from pathlib import Path
from src.model_profile_manager import ModelProfile, ModelProfileManager, get_profile_manager
import src.model_profile_manager as mpm_module


def _make_manager(tmp_path: Path) -> ModelProfileManager:
    """Create a ModelProfileManager using a temp file."""
    return ModelProfileManager(storage_path=tmp_path / "model_profiles.json")


class TestModelProfile:
    def test_to_dict_roundtrip(self):
        profile = ModelProfile(
            service="https://openrouter.ai/api/v1",
            model="google/gemma-2-9b-it:free",
            parameters={"max_tokens": 250, "temperature": 1},
        )
        d = profile.to_dict()
        restored = ModelProfile.from_dict(d)

        assert restored.service == profile.service
        assert restored.model == profile.model
        assert restored.parameters == profile.parameters

    def test_from_dict_missing_parameters_defaults_to_empty(self):
        d = {"service": "http://localhost", "model": "m"}
        profile = ModelProfile.from_dict(d)
        assert profile.parameters == {}


class TestCRUD:
    def test_create_profile(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        result = mgr.create_or_update_profile("openrouter", "google/gemma-2-9b-it:free", {"max_tokens": 250})
        assert result is True
        assert mgr.has_profile("openrouter", "google/gemma-2-9b-it:free")

    def test_update_profile(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        mgr.create_or_update_profile("openrouter", "model-a", {"temperature": 0.5})
        mgr.create_or_update_profile("openrouter", "model-a", {"temperature": 0.9})

        profile = mgr.get_profile("openrouter", "model-a")
        assert profile is not None
        assert profile.parameters["temperature"] == 0.9

    def test_get_profile_returns_none_when_missing(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        assert mgr.get_profile("openrouter", "nonexistent") is None

    def test_has_profile_false_when_missing(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        assert mgr.has_profile("openai", "gpt-4") is False

    def test_delete_profile(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        mgr.create_or_update_profile("openai", "gpt-4", {"max_tokens": 500})
        profile_id = mgr.get_profile_id("openai", "gpt-4")
        assert mgr.delete_profile(profile_id) is True
        assert mgr.has_profile("openai", "gpt-4") is False

    def test_delete_nonexistent_profile_returns_false(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        assert mgr.delete_profile("fake:id") is False


class TestEndpointKeying:
    """Different service aliases / names should resolve to the same endpoint URL and therefore the same profile."""

    @pytest.mark.parametrize(
        "service_input",
        ["openrouter", "OpenRouter", "or", "OR", " openrouter ", "https://openrouter.ai/api/v1"],
    )
    def test_openrouter_aliases_resolve_to_same_profile(self, tmp_path: Path, service_input: str):
        mgr = _make_manager(tmp_path)
        mgr.create_or_update_profile("openrouter", "model-x", {"temperature": 0.7})
        profile = mgr.get_profile(service_input, "model-x")
        assert profile is not None
        assert profile.parameters["temperature"] == 0.7

    @pytest.mark.parametrize(
        "service_input",
        ["nanogpt", "nano", "NanoGPT", "https://nano-gpt.com/api/v1"],
    )
    def test_nanogpt_aliases_resolve_to_same_profile(self, tmp_path: Path, service_input: str):
        mgr = _make_manager(tmp_path)
        mgr.create_or_update_profile("nano", "mistral-small", {"max_tokens": 100})
        profile = mgr.get_profile(service_input, "mistral-small")
        assert profile is not None
        assert profile.parameters["max_tokens"] == 100

    @pytest.mark.parametrize(
        "service_input",
        ["kobold", "koboldcpp", "KoboldCpp"],
    )
    def test_kobold_aliases_resolve_to_same_profile(self, tmp_path: Path, service_input: str):
        mgr = _make_manager(tmp_path)
        mgr.create_or_update_profile("kobold", "local-model", {"temperature": 1.0})
        profile = mgr.get_profile(service_input, "local-model")
        assert profile is not None

    def test_different_services_produce_different_keys(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        mgr.create_or_update_profile("openrouter", "model-a", {"temperature": 0.5})
        mgr.create_or_update_profile("openai", "model-a", {"temperature": 0.9})

        or_profile = mgr.get_profile("openrouter", "model-a")
        oai_profile = mgr.get_profile("openai", "model-a")
        assert or_profile.parameters["temperature"] == 0.5
        assert oai_profile.parameters["temperature"] == 0.9

    def test_get_profile_id_format(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        pid = mgr.get_profile_id("openrouter", "google/gemma-2-9b-it:free")
        assert pid == "https://openrouter.ai/api/v1:google/gemma-2-9b-it:free"

    def test_custom_url_used_as_is(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        custom_url = "http://my-server:8080/v1"
        mgr.create_or_update_profile(custom_url, "custom-model", {"max_tokens": 42})
        profile = mgr.get_profile(custom_url, "custom-model")
        assert profile is not None
        assert profile.parameters["max_tokens"] == 42
        pid = mgr.get_profile_id(custom_url, "custom-model")
        assert pid == f"{custom_url}:custom-model"


class TestResolveParams:
    def test_apply_false_returns_fallback(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        mgr.create_or_update_profile("openrouter", "model-a", {"temperature": 0.1})
        fallback = {"temperature": 0.9, "max_tokens": 200}

        result = mgr.resolve_params("openrouter", "model-a", fallback, apply_profile=False)
        assert result == fallback

    def test_apply_true_with_profile(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        saved_params = {"temperature": 0.3, "max_tokens": 300}
        mgr.create_or_update_profile("openrouter", "model-a", saved_params)
        fallback = {"temperature": 0.9, "max_tokens": 200}

        result = mgr.resolve_params("openrouter", "model-a", fallback, apply_profile=True, log_context="test")
        assert result == saved_params

    def test_apply_true_without_profile_returns_fallback(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        fallback = {"temperature": 0.9, "max_tokens": 200}

        result = mgr.resolve_params("openrouter", "model-z", fallback, apply_profile=True, log_context="test")
        assert result == fallback

    def test_apply_true_with_none_fallback(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        result = mgr.resolve_params("openrouter", "model-z", None, apply_profile=True)
        assert result == {}

    def test_apply_false_with_none_fallback(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        result = mgr.resolve_params("openrouter", "model-z", None, apply_profile=False)
        assert result == {}

    def test_resolve_returns_copy_not_reference(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        saved_params = {"temperature": 0.3}
        mgr.create_or_update_profile("openrouter", "model-a", saved_params)

        result = mgr.resolve_params("openrouter", "model-a", None, apply_profile=True)
        result["temperature"] = 999 # mutate the returned dict
        # original profile should be unaffected
        profile = mgr.get_profile("openrouter", "model-a")
        assert profile.parameters["temperature"] == 0.3

    def test_resolve_fallback_returns_copy_not_reference(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        fallback = {"temperature": 0.5}
        result = mgr.resolve_params("openrouter", "model-z", fallback, apply_profile=False)
        result["temperature"] = 999
        assert fallback["temperature"] == 0.5


class TestPersistence:
    def test_save_and_reload(self, tmp_path: Path):
        mgr1 = _make_manager(tmp_path)
        mgr1.create_or_update_profile("openrouter", "google/gemma-2-9b-it:free", {"max_tokens": 250, "temperature": 1})

        # Create a new manager that reads the same file
        mgr2 = ModelProfileManager(storage_path=mgr1.storage_path)
        profile = mgr2.get_profile("openrouter", "google/gemma-2-9b-it:free")
        assert profile is not None
        assert profile.parameters == {"max_tokens": 250, "temperature": 1}
        assert profile.model == "google/gemma-2-9b-it:free"
        assert profile.service == "https://openrouter.ai/api/v1"

    def test_json_file_format(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        mgr.create_or_update_profile("openrouter", "google/gemma-2-9b-it:free", {"max_tokens": 250, "temperature": 1})

        with open(mgr.storage_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "profiles" in data

        profile_key = "https://openrouter.ai/api/v1:google/gemma-2-9b-it:free"
        assert profile_key in data["profiles"]
        p = data["profiles"][profile_key]
        assert p["service"] == "https://openrouter.ai/api/v1"
        assert p["model"] == "google/gemma-2-9b-it:free"
        assert p["parameters"] == {"max_tokens": 250, "temperature": 1}

    def test_corrupted_file_handled_gracefully(self, tmp_path: Path):
        storage = tmp_path / "model_profiles.json"
        storage.write_text("THIS IS NOT JSON", encoding="utf-8")

        mgr = _make_manager(tmp_path)
        # Should start with empty profiles, not crash
        assert mgr.has_profile("openrouter", "any-model") is False

    def test_empty_json_object_handled(self, tmp_path: Path):
        storage = tmp_path / "model_profiles.json"
        storage.write_text("{}", encoding="utf-8")

        mgr = _make_manager(tmp_path)
        assert mgr.has_profile("openrouter", "any-model") is False

    def test_missing_file_creates_empty_manager(self, tmp_path: Path):
        mgr = ModelProfileManager(storage_path=tmp_path / "nonexistent" / "profiles.json")
        assert mgr.has_profile("openrouter", "any-model") is False

    def test_delete_persists(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        mgr.create_or_update_profile("openai", "gpt-4", {"max_tokens": 500})
        profile_id = mgr.get_profile_id("openai", "gpt-4")
        mgr.delete_profile(profile_id)

        mgr2 = ModelProfileManager(storage_path=mgr.storage_path)
        assert mgr2.has_profile("openai", "gpt-4") is False

    def test_multiple_profiles_persist(self, tmp_path: Path):
        mgr = _make_manager(tmp_path)
        mgr.create_or_update_profile("openrouter", "model-a", {"temperature": 0.5})
        mgr.create_or_update_profile("openai", "model-b", {"temperature": 0.9})

        mgr2 = ModelProfileManager(storage_path=mgr.storage_path)
        assert mgr2.has_profile("openrouter", "model-a")
        assert mgr2.has_profile("openai", "model-b")
        assert mgr2.get_profile("openrouter", "model-a").parameters["temperature"] == 0.5
        assert mgr2.get_profile("openai", "model-b").parameters["temperature"] == 0.9


class TestSingleton:
    def test_get_profile_manager_returns_same_instance(self):
        # Reset the singleton state so our test starts clean
        old = mpm_module._instance
        mpm_module._instance = None
        try:
            a = get_profile_manager()
            b = get_profile_manager()
            assert a is b
        finally:
            # Restore original singleton to avoid polluting other tests
            mpm_module._instance = old

    def test_get_profile_manager_creates_instance_when_none(self):
        old = mpm_module._instance
        mpm_module._instance = None
        try:
            mgr = get_profile_manager()
            assert isinstance(mgr, ModelProfileManager)
        finally:
            mpm_module._instance = old
