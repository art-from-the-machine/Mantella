from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_bool import ConfigValueBool


class ImageLLMDefinitions:
    @staticmethod
    def get_image_analysis_skyrim_filepath_config_value() -> ConfigValue:
        description = """ Settings for for the filepath of Skyrim (desktop) directory where the executable is located. 
        If you are not using Skyrim (desktop), you may retain the default setting.
        Copy the complete filepath from your OS file explorer. """
        return ConfigValueString("image_analysis_skyrim_filepath","Set the filepath to Skyrim (desktop) directory",description,"C:\Games\Steam\steamapps\common\Skyrim Special Edition")

    def get_image_analysis_skyrim_vr_filepath_config_value() -> ConfigValue:
        description = """ Settings for for the filepath of Steam directory where the steam screenshots are stored. 
        They should located inside your steam directory -> userdata -> Your personal user number -> 760 -> remote -> 611670 -> screenshots
        If you are not using Skyrim (VR), you may retain the default setting.
        Copy the complete filepath from your OS file explorer. """
        return ConfigValueString("image_analysis_skyrim_vr_filepath","Set the filepath to Steam Screenshot directory for Skyrim VR",description,"C:\\Games\\Steam\\userdata\\YOUR_USER_NUMBER_HERE\\760\\remote\\611670\\screenshots")
    
    def get_image_analysis_fallout4_filepath_config_value() -> ConfigValue:
        description = """ Settings for for the filepath of Fallout 4 (desktop) directory where the executable is located. 
        If you are not using Fallout 4 (desktop), you may retain the default setting.
        Copy the complete filepath from your OS file explorer. """
        return ConfigValueString("image_analysis_fallout4_filepath","Set the filepath to Fallout 4 (desktop) directory",description,"C:\Games\Steam\steamapps\common\Fallout 4")

    def get_image_analysis_fallout4_vr_filepath_config_value() -> ConfigValue:
        description = """ Settings for for the filepath of Steam directory where the steam screenshots are stored. 
        They should located inside your steam directory -> userdata -> Your personal user number -> 760 -> remote -> 611660 -> screenshots
        If you are not using Fallout 4 (VR), you may retain the default setting.
        Copy the complete filepath from your OS file explorer. """
        return ConfigValueString("image_analysis_fallout4_vr_filepath","Set the filepath to Steam Screenshot directory for Fallout 4 VR",description,"C:\\Games\\Steam\\userdata\\YOUR_USER_NUMBER_HERE\\760\\remote\\611660\\screenshots")

    def get_image_analysis_iterative_querying_config_value() -> ConfigValue:
        description = """ Settings for the LLM providers and the LLMs themselves.
If you're using iterative querying input 1
if you're sending the image and the LLM prompt all at once input 0 , then the values from [LLM] will be used for image queries except for the prompts
"""
        return ConfigValueBool("image_analysis_iterative_querying","Use iterative querying",description,False)
 
    @staticmethod
    def get_image_llm_model_config_value() -> ConfigValue:
        model_description = """ model
   Options:
   - OpenRouter: see https://openrouter.ai/docs#models. Take the value displayed under the model heading (eg anthropic/claude-3-sonnet)
   - OpenAI: gpt-4-0125-preview, gpt4-o
   Local model users can ignore this setting as you will instead select your model directly in Kobold / Text generation web UI
   Remember to change your secret key in IMAGE_GPT_SECRET_KEY.txt when switching between OpenRouter and OpenAI services!"""
        return ConfigValueString("image_llm_model","Image LLM Model",model_description,"gpt-4o")
    
    @staticmethod
    def get_image_llm_max_response_sentences_config_value() -> ConfigValue:
        return ConfigValueInt("image_max_response_sentences","Max sentences per response","The maximum number of sentences returned by the image LLM on each response. Lower this value to reduce waffling.\nNote: The setting number_words_tts takes precedence over this setting",999,1,999)
    
    @staticmethod
    def get_image_llm_api_config_value() -> ConfigValue:
        description = """Selects the LLM service to connect to
            By default, the service will be automatically determined based on whether Kobold / textgenwebui is running, and if neither are running, based on the model selected
            If you would prefer to explicitly select the service, you can do so by setting llm_api to one of the options above
            Ensure that you have the correct secret key set in IMAGE_GPT_SECRET_KEY.txt for the service you are using (if using OpenRouter or OpenAI)
            Note that for some services, like textgenwebui, you must enable the openai extension and have the model you want to use preloaded before running Mantella
            Choosing 'Custom' will instead use the URL from the 'LLM Custom Service Url' config value"""
        return ConfigValueSelection("image_llm_api","LLM service",description, "auto", ["auto", "OpenRouter", "OpenAI", "Kobold", "textgenwebui", "Custom"],tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_image_llm_custom_service_url_config_value() -> ConfigValue:
        description = """If selected 'Custom' for 'LLM service', you can enter the url to the custom service here. 
                        A custom LLM service is expected to provide an OpenAI API compatible endpoint"""
        return ConfigValueString("image_llm_custom_service_url","LLM custom service url",description, "http://127.0.0.1:5001/v1",tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_image_llm_custom_token_count_config_value() -> ConfigValue:
        description = """If the model chosen is not recognised by Mantella, the token count for the given model will default to this number
                    If this is not the correct token count for your chosen model, you can change it here
                    Keep in mind that if this number is greater than the actual token count of the model, then Mantella will crash if a given conversation exceeds the model's token limit"""
        return ConfigValueInt("image_llm_custom_token_count","Custom token count",description, 4096, 4096, 9999999,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_image_llm_temperature_config_value() -> ConfigValue:
        return ConfigValueFloat("image_llm_temperature","Temperature","", 1.0, 0, 2,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_image_llm_top_p_config_value() -> ConfigValue:
        return ConfigValueFloat("image_llm_top_p","Top p","", 1.0, 0, 1,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_image_llm_stop_config_value() -> ConfigValue:
        description = """A list of up to FOUR strings, by default only # is used
                        If you want more than one stopping string use this format: string1,string2,string3,string4"""
        return ConfigValueString("image_llm_stop","Stop",description, "#",tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_image_llm_frequency_penalty_config_value() -> ConfigValue:
        return ConfigValueFloat("image_llm_frequency_penalty","Frequency penalty","", 0, -2, 2,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_image_llm_max_tokens_config_value() -> ConfigValue:
        return ConfigValueInt("image_llm_max_tokens","Max tokens","Lowering this value can sometimes result in empty responses", 250, 1, 999999,tags=[ConvigValueTag.advanced])

    