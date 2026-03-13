import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from src import utils

logger = utils.get_logger()


@dataclass
class ModelProfile:
    """Represents a model profile with LLM parameters."""
    service: str # Canonical endpoint URL (eg 'https://openrouter.ai/api/v1')
    model: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for JSON serialization."""
        return {
            "service": self.service,
            "model": self.model,
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelProfile":
        """Create profile from dictionary (JSON deserialization)."""
        return cls(
            service=data["service"],
            model=data["model"],
            parameters=data.get("parameters", {}),
        )


class ModelProfileManager:
    """Manages model parameter profiles with JSON-based storage.

    Profiles are keyed by ``{endpoint_url}:{model}`` where *endpoint_url* is
    resolved from a service name via ``utils.resolve_service_endpoint``.
    """

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        if storage_path is None:
            data_dir = Path(utils.resolve_path()) / "data"
            self.storage_path = data_dir / "model_profiles.json"
        else:
            self.storage_path = storage_path

        self._profiles: dict[str, ModelProfile] = {}
        self._load_profiles()

    @staticmethod
    def _resolve_endpoint(service: str) -> str:
        """Resolve a service name to a canonical endpoint URL."""
        return utils.resolve_service_endpoint(service)

    def get_profile_id(self, service: str, model: str) -> str:
        """Return the canonical ``{endpoint_url}:{model}`` key."""
        endpoint = self._resolve_endpoint(service)
        return f"{endpoint}:{model}"

    def create_or_update_profile(self, service: str, model: str, parameters: dict[str, Any]) -> bool:
        """Create or update a model profile.

        Returns True on success, False on error.
        """
        try:
            endpoint = self._resolve_endpoint(service)
            profile = ModelProfile(service=endpoint, model=model, parameters=parameters)
            profile_id = self.get_profile_id(service, model)
            action = "Updated" if profile_id in self._profiles else "Created"
            self._profiles[profile_id] = profile
            self._save_profiles()
            logger.info(f"{action} model profile: {profile_id}")
            return True
        except Exception as e:
            logger.error(f"Error creating/updating model profile: {e}")
            return False

    def get_profile(self, service: str, model: str) -> Optional[ModelProfile]:
        """Retrieve a profile by service + model, or *None*."""
        profile_id = self.get_profile_id(service, model)
        return self._profiles.get(profile_id)

    def has_profile(self, service: str, model: str) -> bool:
        """Check whether a profile exists for the given service + model."""
        return self.get_profile(service, model) is not None

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile by its full profile-id string.

        Returns True if deleted, False if not found or on error.
        """
        try:
            if profile_id not in self._profiles:
                logger.warning(f"Profile with ID {profile_id} not found")
                return False
            del self._profiles[profile_id]
            self._save_profiles()
            logger.info(f"Deleted model profile: {profile_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting model profile: {e}")
            return False

    def resolve_params(
        self,
        service: str,
        model: str,
        fallback_params: dict[str, Any] | None,
        apply_profile: bool,
        log_context: str = "",
    ) -> dict[str, Any]:
        """Return final LLM parameters.

        If *apply_profile* is True and a matching profile exists, its
        parameters are returned.  Otherwise *fallback_params* is returned.
        """
        base = (fallback_params or {}).copy()

        if not apply_profile:
            logger.debug(f"{log_context} parameters (manual): {base}")
            return base

        profile = self.get_profile(service, model)
        if profile and profile.parameters:
            logger.info(f"Applied profile for {log_context}: {service}/{model}")
            logger.debug(f"{log_context} profile parameters: {profile.parameters}")
            return profile.parameters.copy()

        logger.debug(f"No profile found for {log_context} {service}/{model}, using manual parameters: {base}")
        return base

    def _load_profiles(self) -> None:
        """Load profiles from the JSON file on disk."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                profiles_data = data.get("profiles", {})
                loaded = {}
                for pid, pdata in profiles_data.items():
                    try:
                        loaded[pid] = ModelProfile.from_dict(pdata)
                    except (KeyError, TypeError) as e:
                        logger.warning(f"Skipping malformed profile '{pid}': {e}")
                self._profiles = loaded
                logger.debug(f"Loaded {len(self._profiles)} model profiles from {self.storage_path}")
            else:
                logger.debug(f"No existing model profiles found at {self.storage_path}, starting with empty profiles")
        except Exception as e:
            logger.error(f"Error loading model profiles from {self.storage_path}: {e}")
            self._profiles = {}

    def _save_profiles(self) -> None:
        """Persist all profiles to the JSON file on disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "profiles": {pid: p.to_dict() for pid, p in self._profiles.items()},
            }

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(self._profiles)} model profiles to {self.storage_path}")
        except Exception as e:
            logger.error(f"Error saving model profiles: {e}")


_instance: Optional[ModelProfileManager] = None


def get_profile_manager() -> ModelProfileManager:
    """Return the shared :class:`ModelProfileManager` singleton."""
    global _instance
    if _instance is None:
        _instance = ModelProfileManager()
    return _instance
