from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_bool import ConfigValueBool


class FunctionLLMDefinitions:
    @staticmethod

    #def get_function_enable_inference() -> ConfigValue:
    #    description = """ Selecting this will cause Mantella to make separate calls to the LLM to allow the AI to make decisions for the NPCs
#"""
#        return ConfigValueBool("enable_function_inference","Enable function inference",description,False)
 
    def get_function_enable_veto() -> ConfigValue:
        description = """ Selecting this will allow NPC to refuse to perform actions based on function calls if the LLM considers the character itself would not perform them.
"""
        return ConfigValueBool("enable_function_veto","Enable function veto (free will)",description,False)

    @staticmethod
    def get_function_llm_api_config_value() -> ConfigValue:
        description = """Selects the LLM service to connect to (either local or via an API) that will handle your function calls.
            If you are connecting to a local service (KoboldCpp, textgenwebui etc), please ensure that the service is running and a model is loaded. You can also enter a custom URL to connect to other LLM services that provide an OpenAI compatible endpoint.
            After selecting a service, select the model using the option below. Press the *Update list* button to load a list of models available from the service.

            **If you are using an API (OpenAI, OpenRouter, etc) ensure you have the correct secret key set in `GPT_SECRET_KEY.txt` for the respective service you are using."""
        return ConfigValueSelection("function_llm_api","Function LLM service",description, "OpenAI", ["OpenRouter", "OpenAI", "Kobold", "textgenwebui", "Custom"], allows_free_edit=True)
    

    @staticmethod
    def get_function_llm_model_config_value() -> ConfigValue:
        model_description = """THIS OPTION WILL ONLY BE TAKEN INTO ACCOUNT IF FUNCTION INFERENCE IS ACTIVATED
        Select the model to use. Press the *Update list* button to load a list of models available from the service selected above.
                            **If you are using OpenRouter or OpenAI updating the list requires a correct secret key set in `GPT_SECRET_KEY.txt` for the respective service you are using.**
                            The list does not provide all details about the models. For additional information please refer to the corresponding sites:
                            - OpenRouter: https://openrouter.ai/docs#models
                            - OpenAI: https://platform.openai.com/docs/models https://openai.com/api/pricing/"""
        return ConfigValueSelection("function_llm_model","Function LLM Model",model_description,"gpt-4o",["Custom Model"], allows_values_not_in_options=True) #Convert to selector eventually


    @staticmethod
    def get_function_llm_custom_token_count_config_value() -> ConfigValue:
        description = """If the model chosen is not recognized by Mantella, the token count for the given model will default to this number
                    If this is not the correct token count for your chosen model, you can change it here
                    Keep in mind that if this number is greater than the actual token count of the model, then Mantella will crash if a given conversation exceeds the model's token limit"""
        return ConfigValueInt("function_llm_custom_token_count","Custom token count",description, 4096, 4096, 9999999,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_function_llm_temperature_config_value() -> ConfigValue:
        return ConfigValueFloat("function_llm_temperature","Temperature","", 0.5, 0, 2,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_function_llm_top_p_config_value() -> ConfigValue:
        return ConfigValueFloat("function_llm_top_p","Top p","", 1.0, 0, 1,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_function_llm_frequency_penalty_config_value() -> ConfigValue:
        return ConfigValueFloat("function_llm_frequency_penalty","Frequency penalty","", 0, -2, 2,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_function_llm_max_tokens_config_value() -> ConfigValue:
        return ConfigValueInt("function_llm_max_tokens","Max tokens","Lowering this value can sometimes result in empty responses", 2000, 1, 999999,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_function_llm_timeout_value() -> ConfigValue:
        return ConfigValueInt("function_llm_timeout","Function LLM Timeout","Use this value to set a max delay that Mantella will wait before continuing with generating a response. Lower this in case of inconsistent response times.", 15, 1, 999999,tags=[ConvigValueTag.advanced])
    
 

    