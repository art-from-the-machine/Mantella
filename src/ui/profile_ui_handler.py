import json
from typing import Any, Callable
import gradio as gr
from src.config.types.config_value import ConfigValue
from src import utils

logger = utils.get_logger()


class ProfileUIHandler:
    """Handles Save / Delete / auto-load logic for the Model Profiles UI section.

    Receives references to the shared identifier->ConfigValue and
    ConfigValue->UI-element dictionaries from SettingsUIConstructor.
    """

    PARAMS_ID = "profile_parameters"
    SERVICE_ID = "profile_selected_service"
    MODEL_ID = "profile_selected_model"

    def __init__(self, identifier_to_cv: dict[str, ConfigValue], cv_to_ui: dict[ConfigValue, Any]) -> None:
        self._id_to_cv = identifier_to_cv
        self._cv_to_ui = cv_to_ui

    @staticmethod
    def _get_profile_manager():
        """Lazily import and return the shared ModelProfileManager singleton."""
        from src.model_profile_manager import get_profile_manager
        return get_profile_manager()

    def get_additional_buttons(self) -> list[tuple[str, Callable[[], Any]]]:
        """Return the (label, callback) pairs for the profile_parameters field."""
        return [
            ("Save", self.on_save),
            ("Delete", self.on_delete),
        ]

    def on_save(self) -> str:
        """Save the current service/model/params as a model profile."""
        try:
            service_cv = self._id_to_cv.get(self.SERVICE_ID)
            model_cv = self._id_to_cv.get(self.MODEL_ID)
            params_cv = self._id_to_cv.get(self.PARAMS_ID)
            if not all([service_cv, model_cv, params_cv]):
                logger.error("Missing profile configuration fields")
                return params_cv.value if params_cv else ""

            model = (model_cv.value or "").strip()
            if not model or model == "Custom Model":
                logger.warning("Cannot save profile: no model selected")
                return params_cv.value

            params_text = (params_cv.value or "").strip()
            if not params_text:
                params_text = "{}"
            try:
                parameters = json.loads(params_text)
                if not isinstance(parameters, dict):
                    logger.error("Profile parameters must be a JSON object")
                    return params_cv.value
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in profile parameters: {e}")
                return params_cv.value

            mgr = self._get_profile_manager()
            success = mgr.create_or_update_profile(service_cv.value, model, parameters)
            if success:
                formatted = json.dumps(parameters, indent=2)
                params_cv.value = formatted
                logger.info(f"Profile saved for {service_cv.value}/{model}")
                return formatted
            else:
                logger.error(f"Failed to save profile for {service_cv.value}/{model}")
                return params_cv.value
        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            return ""

    def on_delete(self) -> str:
        """Delete the profile for the currently selected service/model."""
        try:
            service_cv = self._id_to_cv.get(self.SERVICE_ID)
            model_cv = self._id_to_cv.get(self.MODEL_ID)
            params_cv = self._id_to_cv.get(self.PARAMS_ID)
            if not all([service_cv, model_cv]):
                logger.warning("Cannot delete profile: missing service or model")
                return params_cv.default_value if params_cv else ""

            model = (model_cv.value or "").strip()
            if not model:
                return params_cv.default_value if params_cv else ""

            mgr = self._get_profile_manager()
            profile_id = mgr.get_profile_id(service_cv.value, model)
            success = mgr.delete_profile(profile_id)
            if success:
                logger.info(f"Profile deleted for {service_cv.value}/{model}")
            else:
                logger.warning(f"No profile found for {service_cv.value}/{model}")

            if params_cv:
                params_cv.value = params_cv.default_value
                return params_cv.default_value
            return ""
        except Exception as e:
            logger.error(f"Error deleting profile: {e}")
            return ""

    def setup_auto_load(self, params_config_value: ConfigValue) -> None:
        """Wire the profile model dropdown to auto-load existing profile parameters."""
        model_cv = self._id_to_cv.get(self.MODEL_ID)
        params_ui = self._cv_to_ui.get(params_config_value)
        if not model_cv or not params_ui:
            return
        model_ui = self._cv_to_ui.get(model_cv)
        if not model_ui or not callable(getattr(model_ui, "change", None)):
            return

        def on_model_change(new_model_value):
            service_cv = self._id_to_cv.get(self.SERVICE_ID)
            params_cv = self._id_to_cv.get(self.PARAMS_ID)
            if not service_cv or not params_cv or not new_model_value:
                return gr.update()
            try:
                profile = self._get_profile_manager().get_profile(service_cv.value, new_model_value)
                if profile and profile.parameters:
                    params_json = json.dumps(profile.parameters, indent=2)
                    params_cv.value = params_json
                    return gr.update(value=params_json)
                else:
                    params_cv.value = params_cv.default_value
                    return gr.update(value=params_cv.default_value)
            except Exception as e:
                logger.error(f"Error auto-loading profile: {e}")
                return gr.update()

        model_ui.change(on_model_change, model_ui, params_ui)
