from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_bool import ConfigValueBool


class LLMDefinitions:
    @staticmethod
    def get_model_config_value() -> ConfigValue:
        model_description = """Options:
                            - OpenRouter: see https://openrouter.ai/docs#models. Copy the value displayed under the model heading (eg anthropic/claude-3-sonnet).
                            - OpenAI: gpt-3.5-turbo, gpt-4o
                            Local model users can ignore this setting as you will instead select your model directly in Kobold / Text generation web UI.
                            Remember to change your secret key in GPT_SECRET_KEY.txt when switching between OpenRouter and OpenAI services!"""
        return ConfigValueString("model","Model",model_description,"undi95/toppy-m-7b:free")
    
    @staticmethod
    def get_max_response_sentences_config_value() -> ConfigValue:
        return ConfigValueInt("max_response_sentences","Max Sentences per Pesponse","The maximum number of sentences returned by the LLM on each response. Lower this value to reduce waffling.\nNote: The setting 'Number Words TTS' in the Text-to-Speech tab takes precedence over this setting.",999,1,999)
    
    @staticmethod
    def get_llm_api_config_value() -> ConfigValue:
        description = """Selects the LLM service to connect to.
            By default, the service will be automatically determined based on whether Kobold / Text generation web UI is running, and if neither are running, based on the model selected.
            If you would prefer to explicitly select the service to connect to, you can do so by changing to one of the values below.
            Ensure that you have the correct secret key set in GPT_SECRET_KEY.txt for the service you are using (if using OpenRouter or OpenAI).
            Note that for some services, like Text generation web UI, you must enable the OpenAI extension and have the model you want to use preloaded before running Mantella.
            Choosing 'Custom' will change the URL to the URL set in 'LLM Custom Service URL' below."""
        return ConfigValueSelection("llm_api","LLM Service",description, "auto", ["auto", "OpenRouter", "OpenAI", "Kobold", "textgenwebui", "Custom"],tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_llm_custom_service_url_config_value() -> ConfigValue:
        description = """If 'Custom' is selected for 'LLM Service' above, Mantella will connect to the URL below. 
                        A custom LLM service is expected to provide an OpenAI API compatible endpoint."""
        return ConfigValueString("llm_custom_service_url","LLM Custom Service URL",description, "http://127.0.0.1:5001/v1",tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_custom_token_count_config_value() -> ConfigValue:
        description = """If the model chosen is not recognised by Mantella, the token count for the given model will default to this number.
                    If this is not the correct token count for your chosen model, you can change it here.
                    Keep in mind that if this number is greater than the actual token count of the model, then Mantella will crash if a given conversation exceeds the model's token limit."""
        return ConfigValueInt("custom_token_count","Custom Token Count",description, 4096, 4096, 9999999,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_automatic_greeting_folder_config_value() -> ConfigValue:
        automatic_greeting_description = """Should a conversation be started with an automatic greeting from the LLM / NPC.
                                        If enabled: Conversations are always started by the LLM.
                                        If disabled: The LLM will not respond until the player speaks first."""
        return ConfigValueBool("automatic_greeting","Automatic Greeting",automatic_greeting_description,True,tags=[ConvigValueTag.advanced])
    
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

    