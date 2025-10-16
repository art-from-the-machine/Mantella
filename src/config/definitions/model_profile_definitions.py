from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString


class ModelProfileDefinitions:
    @staticmethod
    def get_selected_service_config_value() -> ConfigValue:
        description = """Select the LLM service to create a profile for.
                        After selecting a service, choose a model from the available models list."""
        return ConfigValueSelection(
            "profile_selected_service", 
            "Service", 
            description, 
            "OpenRouter", 
            ["OpenRouter", "OpenAI", "NanoGPT"], 
            allows_free_edit=False
        )
    
    @staticmethod
    def get_selected_model_config_value() -> ConfigValue:
        description = """Select the model to create a profile for.
                        Press the *Update Models* button to refresh the list of available models."""
        return ConfigValueSelection(
            "profile_selected_model",
            "Model",
            description,
            "google/gemma-2-9b-it:free",
            ["Select a service first"],
            allows_values_not_in_options=True
        )
    

    
    @staticmethod
    def get_profile_parameters_config_value() -> ConfigValue:
        default_json = ""
        description = """JSON parameters for the model. You can specify any parameters supported by the LLM service.
                        
Common parameters:
- max_tokens: Maximum number of tokens to generate
- temperature: Controls randomness (0.0-2.0)
- top_p: Nucleus sampling parameter (0.0-1.0)
- frequency_penalty: Reduces repetition (-2.0 to 2.0)
- presence_penalty: Encourages new topics (-2.0 to 2.0)
- stop: Array of stop sequences
- extra_body: Additional service-specific parameters

Example with OpenRouter reasoning exclusion:
```
{
    "max_tokens": 250,
    "temperature": 1,
    "top_p": 0.9,
    "stop": [
        "#"
    ],
    "extra_body": {
        "reasoning": {
            "exclude": true,
            "enabled": false,
            "max_tokens": 400
        },
        "provider": {
            "only": [
                "z-ai"
            ]
        }
    }
}
```"""
        return ConfigValueString(
            "profile_parameters",
            "Parameters (JSON)",
            description,
            default_json
        )
    
    @staticmethod
    def get_example_profile_json_config_value() -> ConfigValue:
        example_json = """{
    "max_tokens": 250,
    "temperature": 1,
    "top_p": 0.9,
    "stop": [
        "#"
    ],
    "extra_body": {
        "reasoning": {
            "exclude": true,
            "enabled": false,
            "max_tokens": 400
        },
        "provider": {
            "only": [
                "z-ai"
            ]
        }
    }
}"""
        description = """Example JSON profile showing advanced parameters including OpenRouter reasoning exclusion and provider filtering."""
        return ConfigValueString(
            "example_profile_json",
            "Example Profile JSON",
            description,
            example_json
        )