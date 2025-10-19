from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString

class ActionDefinitions:
    @staticmethod
    def get_advanced_actions_enabled_config_value() -> ConfigValue:
        description = """If enabled, LLMs with tool calling capabilities can trigger advanced in-game actions.
                        If disabled, only basic actions can be triggered by the LLM using an '[action_name]: [NPC response]' format (eg 'Follow: Lead the way')."""
        return ConfigValueBool("advanced_actions_enabled", "Advanced Actions", description, False)

    @staticmethod
    def get_custom_function_model_config_value() -> ConfigValue:
        description = """Whether to call a separate tool-calling-capable LLM for advanced action handling (NPC verbal responses will still use the model chosen in the `Large Language Model` tab).
                        If enabled, please configure the tool-calling-capable LLM to connect to below.
                        If disabled, the model chosen in the `Large Language Model` tab will be used for both verbal responses and advanced action handling (if advanced actions are enabled)."""
        return ConfigValueBool("custom_function_model", "Custom Tool Calling Model", description, False, tags=[ConfigValueTag.advanced])

    @staticmethod
    def get_function_llm_api_config_value() -> ConfigValue:
        description = """Selects the LLM service to connect to (either local or via an API) that will handle NPC actions.
            Please ensure the selected model supports tool calling.
            If you are connecting to a local service (KoboldCpp, textgenwebui etc), please ensure that the service is running and a model is loaded. You can also enter a custom URL to connect to other LLM services that provide an OpenAI compatible endpoint.
            After selecting a service, select the model using the option below. Press the *Update list* button to load a list of models available from the service.

            **If you are using an API (OpenAI, OpenRouter, etc) ensure you have the correct secret key set in `GPT_SECRET_KEY.txt` for the respective service you are using."""
        options = ["OpenRouter", "OpenAI", "KoboldCpp", "textgenwebui"]
        return ConfigValueSelection("function_llm_api", "Custom Tool Calling LLM service", description, "OpenRouter", options, allows_free_edit=True, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_function_llm_model_config_value() -> ConfigValue:
        model_description = """Select the tool calling model to handle NPC actions. Press the *Update* button to load a list of models available from the service selected above.
                            The list does not provide all details about the models. For additional information please refer to the corresponding sites:
                            - OpenRouter: https://openrouter.ai/models?fmt=cards&supported_parameters=tools
                            - OpenAI: https://platform.openai.com/docs/models https://openai.com/api/pricing/"""
        return ConfigValueSelection("function_llm","Custom Tool Calling Model", model_description, "mistralai/mistral-small-3.2-24b-instruct", ["Custom Model"], allows_values_not_in_options=True, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_function_llm_custom_token_count_config_value() -> ConfigValue:
        description = """If the model chosen is not recognized by Mantella, the token count for the given model will default to this number.
                    If this is not the correct token count for your chosen model, you can change it here.
                    Keep in mind that if this number is greater than the actual token count of the model, then Mantella will crash if a given conversation exceeds the model's token limit."""
        return ConfigValueInt("function_llm_custom_token_count","Custom Tool Calling Model Token Count", description, 4096, 4096, 9999999, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_function_llm_params_config_value() -> ConfigValue:
        value = """{
                        "max_tokens": 500,
                        "stop": ["#"]
                    }"""
        description = """Parameters passed as part of the request to the tool calling model.
                        The "tools" parameter is automatically added by Mantella and should not be included here.
                        A list of the most common parameters can be found here: https://openrouter.ai/docs/parameters.
                        Note that available parameters can vary per LLM provider."""
        return ConfigValueString("function_llm_params", "Custom Tool Calling Model Parameters", description, value, tags=[ConfigValueTag.advanced])