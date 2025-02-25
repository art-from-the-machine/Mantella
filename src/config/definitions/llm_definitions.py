from src.config.types.config_value import ConfigValue, ConfigValueTag
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
            After selecting a service, select the model using the option below. Press the *Update* button to load a list of models available from the service.

            If you are using an API (OpenAI, OpenRouter, etc) ensure you have the correct secret key set in `GPT_SECRET_KEY.txt` for the respective service you are using."""
        return ConfigValueSelection("llm_api","LLM Service",description, "OpenRouter", ["OpenRouter", "OpenAI", "KoboldCpp", "textgenwebui"], allows_free_edit=True)

    @staticmethod
    def get_model_config_value() -> ConfigValue:
        model_description = """Select the model to use. Press the *Update* button to load a list of models available from the service selected above.
                            The list does not provide all details about the models. For additional information please refer to the corresponding sites:
                            - OpenRouter: https://openrouter.ai/docs#models
                            - OpenAI: https://platform.openai.com/docs/models https://openai.com/api/pricing/"""
        return ConfigValueSelection("model","Model",model_description,"google/gemma-2-9b-it:free",["Custom Model"], allows_values_not_in_options=True)
    
    @staticmethod
    def get_summary_model_config_value() -> ConfigValue:
        summary_model_description = """Select the model to use for creating the summaries of your conversations. Press the *Update* button to load a list of models available from the service selected above.
                            The list does not provide all details about the models. For additional information please refer to the corresponding sites:
                            - OpenRouter: https://openrouter.ai/docs#models
                            - OpenAI: https://platform.openai.com/docs/models https://openai.com/api/pricing/"""
        return ConfigValueSelection("model_summaries","Model for summaries",summary_model_description,"google/gemma-2-9b-it:free",["Custom Model"], allows_values_not_in_options=True, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_use_different_model_for_summaries() -> ConfigValue:
        description = """Enable this to use 'Model for summaries' for creating the summaries of your conversations instead of your primary selected model"""
        return ConfigValueBool("enable_summaries_model","Use a different model for summarization", description, False, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_llm_priority_config_value() -> ConfigValue:
        description = """(OpenRouter only) Select the priority of choosing an LLM service provider:
                        - Balanced (default): Prioritize the provider with the lowest price which has not experienced recent outages.
                        - Price: Prioritize the provider with the lowest price, regardless of recent outages.
                        - Speed: Prioritize the provider with the fastest response times.
                        For more information: see here: https://openrouter.ai/docs/features/provider-routing"""
        return ConfigValueSelection("llm_priority", "Priority", description, "Balanced", ["Balanced", "Price", "Speed"], allows_free_edit=False)
    
    @staticmethod
    def get_custom_token_count_config_value() -> ConfigValue:
        description = """If the model chosen is not recognised by Mantella, the token count for the given model will default to this number.
                    If this is not the correct token count for your chosen model, you can change it here.
                    Keep in mind that if this number is greater than the actual token count of the model, then Mantella will crash if a given conversation exceeds the model's token limit."""
        return ConfigValueInt("custom_token_count","Custom Token Count",description, 4096, 4096, 9999999, tags=[ConfigValueTag.share_row])

    @staticmethod
    def get_max_response_sentences_config_value() -> ConfigValue:
        description = "The maximum number of sentences returned by the LLM on each response. Lower this value to reduce waffling.\nNote: The setting 'Number Words TTS' in the Text-to-Speech tab takes precedence over this setting."
        return ConfigValueInt("max_response_sentences","Max Sentences per Response", description, 4, 1, 999, tags=[ConfigValueTag.share_row])
    
    # @staticmethod
    # def get_llm_custom_service_url_config_value() -> ConfigValue:
    #     description = """If 'Custom' is selected for 'LLM Service' above, Mantella will connect to the URL below. 
    #                     A custom LLM service is expected to provide an OpenAI API compatible endpoint."""
    #     return ConfigValueString("llm_custom_service_url","LLM Custom Service URL",description, "http://127.0.0.1:5001/v1",tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_wait_time_buffer_config_value() -> ConfigValue:
        description = """Time to wait (in seconds) before generating the next voiceline.
                        Mantella waits for the duration of a given voiceline's .wav file + an extra buffer to account for processing overhead.
                        If you are noticing that some voicelines are not being said in-game, try increasing this buffer."""
        return ConfigValueFloat("wait_time_buffer","Wait Time Buffer",description, 0, -999, 999,tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    # @staticmethod
    # def get_try_filter_narration() -> ConfigValue:
    #     try_filter_narration_description = """If checked, sentences containing asterisks (*) will not be spoken aloud."""
    #     return ConfigValueBool("try_filter_narration","Filter Narration",try_filter_narration_description,True,tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_narration_handling() -> ConfigValue:
        narration_handling_description = """How to handle narrations in the output of the LLM.
                                            - Cut narrations: Removes narrations from the output.
                                            - Respective character speaks its narrations: The currently active character will speak it's actions out aloud.
                                            - Use narrator: Narrations will be spoken by a special narrator. The voice model can be set by the config value *Narrator voice* below.
                                            
                                            Note: The seperation of narration and speech is experimental and may not work if the LLM output is not formatted well."""
        options = ["Cut narrations", "Respective character speaks its narrations", "Use narrator"]
        return ConfigValueSelection("narration_handling","Narration Handling",narration_handling_description,options[0], options, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_narrator_voice() -> ConfigValue:
        description = """Which voice model to use if *Narration Handling* is set to 'Use narrator'.
                        Must be a valid voice model from the current TTS. Same rules apply as for choosing a voice for the player."""
        return ConfigValueString("narrator_voice","Narrator voice",description,"", tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_llm_params_config_value() -> ConfigValue:
        value = """{
                        "max_tokens": 250,
                        "stop": ["#"]
                    }"""
        description = """Parameters passed as part of the request to the LLM.
                        A list of the most common parameters can be found here: https://openrouter.ai/docs/parameters.
                        Note that available parameters can vary per LLM provider."""
        return ConfigValueString("llm_params", "Parameters", description, value, tags=[ConfigValueTag.advanced])

    # @staticmethod
    # def get_stop_llm_generation_on_assist_keyword() -> ConfigValue:
    #     stop_llm_generation_on_assist_keyword_description = """Should the generation of the LLM be stopped if the word 'assist' is found?
    #                                                             A lot of LLMs are trained to be virtual assistants use the word excessively.
    #                                                             Default: Checked"""
    #     return ConfigValueBool("stop_llm_generation_on_assist_keyword","Stop LLM generation if 'assist' keyword is found",stop_llm_generation_on_assist_keyword_description,True,tags=[ConfigValueTag.advanced])    