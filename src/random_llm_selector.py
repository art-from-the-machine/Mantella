import random
from dataclasses import dataclass
from typing import Any
from src.model_profile_manager import ModelProfileManager, get_profile_manager
from src import utils

logger = utils.get_logger()


@dataclass
class LLMSelection:
    """Represents a selected LLM configuration"""
    service: str
    model: str
    parameters: dict[str, Any]


class RandomLLMSelector:
    """Selects a random LLM from a configured pool."""

    def __init__(self, profile_manager: ModelProfileManager | None = None):
        self._profile_manager = profile_manager or get_profile_manager()

    def select(self, random_llm_enabled: bool, random_llm_pool: list[dict[str, str]] | None, fallback: LLMSelection, apply_profile: bool = True) -> LLMSelection | None:
        """Pick a random LLM from the configured pool.

        Returns an LLMSelection if a random model was chosen, or None when
        the feature is disabled / the pool is empty / an error occurs.
        """
        if not random_llm_enabled:
            return None

        pool = random_llm_pool
        if not pool:
            return None

        try:
            return self._select_from_pool(pool, fallback, apply_profile)
        except Exception as e:
            logger.error(f"Error in random LLM selection: {e}")
            return None

    def _select_from_pool(self, pool: list[dict[str, Any]], fallback: LLMSelection, apply_profile: bool) -> LLMSelection | None:
        """Select an LLM from a pool, applying model profile if available."""
        if not isinstance(pool, list) or not pool:
            logger.warning("Invalid or empty random LLM pool")
            return None

        entry = random.choice(pool)

        if not isinstance(entry, dict) or 'service' not in entry or 'model' not in entry:
            logger.error(f"Invalid entry in random LLM pool: {entry}")
            return None

        service = entry['service']
        model = entry['model']

        profile_params = self._profile_manager.resolve_params(
            service=service,
            model=model,
            fallback_params=fallback.parameters,
            apply_profile=apply_profile,
            log_context="random LLM selection",
        )

        has_profile = self._profile_manager.has_profile(service, model)
        profile_status = " (with parameter profile)" if has_profile else ""
        logger.info(f"Randomly selected LLM: {service}/{model}{profile_status}")

        return LLMSelection(
            service=service,
            model=model,
            parameters=profile_params,
        )
