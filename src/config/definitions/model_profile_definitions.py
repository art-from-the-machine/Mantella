from src.config.types.config_value import ConfigValue
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString


class ModelProfileDefinitions:
    @staticmethod
    def get_apply_model_profiles_config_value() -> ConfigValue:
        description = """When enabled, Mantella will use saved model profiles to override manual LLM parameters.
                        Model profiles store per-model parameters (temperature, max_tokens, etc) and are applied automatically when a matching profile exists."""
        return ConfigValueBool("apply_model_profiles", "Apply Model Param Profiles", description, False)

    @staticmethod
    def get_selected_service_config_value() -> ConfigValue:
        description = """Select the LLM service for the profile you want to create or edit.
                        After selecting a service, choose a model from the available models list below."""
        options = ["OpenRouter", "OpenAI", "NanoGPT", "KoboldCpp", "textgenwebui"]
        return ConfigValueSelection("profile_selected_service", "Service", description, "OpenRouter", options, allows_free_edit=True)

    @staticmethod
    def get_selected_model_config_value() -> ConfigValue:
        description = """Select or type the model name for the profile.
                        Press the *Update* button to load a list of available models from the service selected above."""
        return ConfigValueSelection("profile_selected_model", "Model", description, "mistralai/mistral-small-3.1-24b-instruct:free", ["Custom Model"], allows_values_not_in_options=True)

    @staticmethod
    def get_profile_parameters_config_value() -> ConfigValue:
        value = """{
                        "max_tokens": 250,
                        "stop": ["#"]
                    }"""
        description = """Parameters passed as part of the request to the model selected above.
                        A list of the most common parameters can be found here: https://openrouter.ai/docs/parameters.
                        Note that available parameters can vary per LLM provider."""
        return ConfigValueString("profile_parameters", "Model Parameters", description, value)
