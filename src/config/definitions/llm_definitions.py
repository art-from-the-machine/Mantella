from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_bool import ConfigValueBool


class LLMDefinitions:
    @staticmethod
    def get_llm_api_config_value() -> ConfigValue:
        description = """Selects the LLM service to connect to (either local or via an API).
            If you are connecting to a local service (KoboldCpp, textgenwebui etc), please ensure that the service is running and a model is loaded. You can also enter a custom URL to connect to other LLM services that provide an OpenAI compatible endpoint.
            After selecting a service, select the model using the option below. Press the *Update list* button to load a list of models available from the service.

            **If you are using an API (OpenAI, OpenRouter, etc) ensure you have the correct secret key set in `GPT_SECRET_KEY.txt` for the respective service you are using.**"""
        return ConfigValueSelection("llm_api","LLM Service",description, "OpenRouter", ["OpenRouter", "OpenAI", "KoboldCpp", "textgenwebui"], allows_free_edit=True)

    @staticmethod
    def get_model_config_value() -> ConfigValue:
        model_description = """Select the model to use. Press the *Update list* button to load a list of models available from the service selected above.
                            **If you are using OpenRouter or OpenAI updating the list requires a correct secret key set in `GPT_SECRET_KEY.txt` for the respective service you are using.**
                            The list does not provide all details about the models. For additional information please refer to the corresponsing sites:
                            - OpenRouter: https://openrouter.ai/docs#models
                            - OpenAI: https://platform.openai.com/docs/models https://openai.com/api/pricing/"""
        return ConfigValueSelection("model","Model",model_description,"google/gemma-2-9b-it:free",["Custom Model"], allows_values_not_in_options=True)
    
    @staticmethod
    def get_custom_token_count_config_value() -> ConfigValue:
        description = """If the model chosen is not recognised by Mantella, the token count for the given model will default to this number.
                    If this is not the correct token count for your chosen model, you can change it here.
                    Keep in mind that if this number is greater than the actual token count of the model, then Mantella will crash if a given conversation exceeds the model's token limit."""
        return ConfigValueInt("custom_token_count","Custom Token Count",description, 4096, 4096, 9999999)

    @staticmethod
    def get_max_response_sentences_config_value() -> ConfigValue:
        return ConfigValueInt("max_response_sentences","Max Sentences per Response","The maximum number of sentences returned by the LLM on each response. Lower this value to reduce waffling.\nNote: The setting 'Number Words TTS' in the Text-to-Speech tab takes precedence over this setting.",4,1,999)
    
    # @staticmethod
    # def get_llm_custom_service_url_config_value() -> ConfigValue:
    #     description = """If 'Custom' is selected for 'LLM Service' above, Mantella will connect to the URL below. 
    #                     A custom LLM service is expected to provide an OpenAI API compatible endpoint."""
    #     return ConfigValueString("llm_custom_service_url","LLM Custom Service URL",description, "http://127.0.0.1:5001/v1",tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_wait_time_buffer_config_value() -> ConfigValue:
        description = """Time to wait (in seconds) before generating the next voiceline.
                        Mantella waits for the duration of a given voiceline's .wav file + an extra buffer to account for processing overhead within Skyrim.
                        If you are noticing that some voicelines are not being said in-game, try increasing this buffer."""
        return ConfigValueFloat("wait_time_buffer","Wait Time Buffer",description, -1.0, -999, 999,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_temperature_config_value() -> ConfigValue:
        return ConfigValueFloat("temperature","Temperature","", 1.0, 0, 2,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_top_p_config_value() -> ConfigValue:
        return ConfigValueFloat("top_p","Top P","", 1.0, 0, 1,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_stop_config_value() -> ConfigValue:
        description = """A list of up to FOUR strings, by default only # is used.
                        If you want more than one stopping string use this format: string1,string2,string3,string4"""
        return ConfigValueString("stop","Stop",description, "#",tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_frequency_penalty_config_value() -> ConfigValue:
        return ConfigValueFloat("frequency_penalty","Frequency Penalty","", 0, -2, 2,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_max_tokens_config_value() -> ConfigValue:
        return ConfigValueInt("max_tokens","Max Tokens","Lowering this value can sometimes result in empty responses.", 250, 1, 999999,tags=[ConvigValueTag.advanced])

    # @staticmethod
    # def get_stop_llm_generation_on_assist_keyword() -> ConfigValue:
    #     stop_llm_generation_on_assist_keyword_description = """Should the generation of the LLM be stopped if the word 'assist' is found?
    #                                                             A lot of LLMs are trained to be virtual assistants use the word excessively.
    #                                                             Default: Checked"""
    #     return ConfigValueBool("stop_llm_generation_on_assist_keyword","Stop LLM generation if 'assist' keyword is found",stop_llm_generation_on_assist_keyword_description,True,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_try_filter_narration() -> ConfigValue:
        try_filter_narration_description = """Should Mantella try to filter narrations out of the output of the LLM?
                                            If checked, tries to filter out sentences containing asterisks (*)."""
        return ConfigValueBool("try_filter_narration","Try to filter narrations from LLM output",try_filter_narration_description,True,tags=[ConvigValueTag.advanced])

    