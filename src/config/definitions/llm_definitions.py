from enum import Enum, auto
from src.config.types.config_value_multi_selection import ConfigValueMultiSelection
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_bool import ConfigValueBool

class NarrationHandlingEnum(Enum):
    CUT_NARRATIONS = auto()
    RESPECTIVE_CHARACTER_SPEAKS_NARRATION = auto()
    USE_NARRATOR = auto()
    DEACTIVATE_HANDLING_OF_NARRATIONS = auto()

    @property
    def display_name(self) -> str:
        return {
            self.CUT_NARRATIONS: "Cut narrations",
            self.RESPECTIVE_CHARACTER_SPEAKS_NARRATION: "Respective character speaks its narrations",
            self.USE_NARRATOR: "Use narrator",
            self.DEACTIVATE_HANDLING_OF_NARRATIONS: "Deactivate handling of narrations",
        }[self]

class NarrationIndicatorsEnum(Enum):
    PARANTHESES = auto()
    ASTERISKS = auto()
    BRACKETS = auto()

    @property
    def display_name(self) -> str:
        return {
            self.PARANTHESES: "()",
            self.ASTERISKS: "**",
            self.BRACKETS: "[]",
        }[self]

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
    
    @staticmethod
    def get_wait_time_buffer_config_value() -> ConfigValue:
        description = """Time to wait (in seconds) before generating the next voiceline.
                        Mantella waits for the duration of a given voiceline's .wav file + an extra buffer to account for processing overhead.
                        If you are noticing that some voicelines are not being said in-game, try increasing this buffer."""
        return ConfigValueFloat("wait_time_buffer","Wait Time Buffer",description, 0, -999, 999,tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
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

    #LLM output parsing options

    @staticmethod
    def get_narration_handling() -> ConfigValue:
        description = """How to handle narrations in the output of the LLM.
                                            - Cut narrations: Removes narrations from the output.
                                            - Respective character speaks its narrations: The currently active character will speak it's actions out aloud.
                                            - Use narrator: Narrations will be spoken by a special narrator. The voice model can be set by the config value 'Narrator voice' below.
                                            - Deactivate handling of narrations: Any narration or speech indicators will be ignored during parsing.
                                            
                                            Note: The seperation of narration and speech is experimental and may not work if the LLM output is not formatted well."""
        options = [e.display_name for e in NarrationHandlingEnum]
        return ConfigValueSelection("narration_handling", "Narration Handling", description, NarrationHandlingEnum.CUT_NARRATIONS.display_name, options, corresponding_enums=list(NarrationHandlingEnum), tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_narrator_voice() -> ConfigValue:
        description = """Which voice model to use if 'Narration Handling' is set to 'Use narrator'.
                        Must be a valid voice model from the current TTS. Same rules apply as for choosing a voice for the player."""
        return ConfigValueString("narrator_voice","Narrator voice",description,"", tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_narration_start_indicators() -> ConfigValue:
        description = """List of characters used to identify the start of narrations in the LLM output."""
        possible_characters = ["*","(","["]
        return ConfigValueMultiSelection("narration_start_indicators","Narration start indicators",description,possible_characters, possible_characters, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_narration_end_indicators() -> ConfigValue:
        description = """List of characters used to identify the start of narrations in the LLM output."""
        possible_characters = ["*",")","]"]
        return ConfigValueMultiSelection("narration_end_indicators","Narration end indicators",description,possible_characters, possible_characters, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_speech_start_indicators() -> ConfigValue:
        description = """List of characters used to identify the end of narrations in the LLM output."""
        possible_characters = ["\""]
        return ConfigValueMultiSelection("speech_start_indicators","Speech start indicators",description,possible_characters, possible_characters, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_speech_end_indicators() -> ConfigValue:
        description = """List of characters used to identify the start of speech in the LLM output."""
        possible_characters = ["\""]
        return ConfigValueMultiSelection("speech_end_indicators","Speech end indicators",description,possible_characters, possible_characters, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_narration_indicators() -> ConfigValue:
        description = """Which narration indicators to use for sentences identified as narrations.
                        If sentences get marked as narrations and are not cut, they will be surrounded by these narration indicators the next time they are fed back to the LLM.
                        This helps to keep the LLM consistent in its use of narration indicators."""
        options = [e.display_name for e in NarrationIndicatorsEnum]
        return ConfigValueSelection("narration_indicators", "Narration indicators to use", description, NarrationIndicatorsEnum.PARANTHESES.display_name, options, corresponding_enums=list(NarrationIndicatorsEnum), tags=[ConfigValueTag.advanced])

