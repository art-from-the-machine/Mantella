import os
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString

class VisionDefinitions:
    @staticmethod
    def get_vision_enabled_config_value() -> ConfigValue:
        description = """If enabled, in-game screenshots are passed to the chosen LLM with each player response. 
                        This feature is only compatible with LLMs that accept image as well as text input, unless `Custom Vision Model` is enabled.
                        Please ensure your game window is visible on screen when running and is not blocked by other windows!"""
        return ConfigValueBool("vision_enabled", "Vision", description, False)
    
    @staticmethod
    def get_low_resolution_mode_config_value() -> ConfigValue:
        description = "Resizes the image to 512x512 pixels (cropping the edges of the longest side). Enable this setting to lower API costs and improve performance."
        return ConfigValueBool("low_resolution_mode", "Low Resolution Mode", description, True, tags=[ConfigValueTag.share_row])
    
    @staticmethod
    def get_save_screenshot_config_value() -> ConfigValue:
        description = "Whether to save screenshots to Documents/My Games/Mantella/data/tmp/images/. Disable this setting to improve performance."
        return ConfigValueBool("save_screenshot", "Save Screenshots", description, True, tags=[ConfigValueTag.share_row])  

    @staticmethod
    def get_image_quality_config_value() -> ConfigValue:
        description = "The quality of the image passed to the LLM from 1-100. Higher values improve the LLM's understanding of passed images. Lower values slightly improve performance. This setting has no affect on API costs."
        return ConfigValueInt("image_quality", "Screenshot Quality", description, 50, 1, 100, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_resize_method_config_value() -> ConfigValue:
        description = "The image scaling algorithm used to resize in-game screenshots to match the target resolution. Algorithms are sorted from fastest / lowest quality (Nearest) to slowest / highest quality (Lanczos)."
        return ConfigValueSelection("resize_method", "Resize Method", description, "Nearest", ["Nearest", "Linear", "Cubic", "Lanczos"], tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_capture_offset_config_value() -> ConfigValue:
        value = '{"left": 0, "right": 0, "top": 0, "bottom": 0}'
        description = '''The number of pixels to offset the capture window. Adjust these numbers with either positive or negative values if the game window is not being captured in the correct dimensions.'''
        return ConfigValueString("capture_offset", "Capture Offset", description, value, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_custom_vision_model_config_value() -> ConfigValue:
        description = """Whether to call a separate vision-capable LLM for image handling (NPCs will still respond using the model chosen in the `Large Language Model` tab).
                        If enabled, please configure the vision-capable LLM to connect to below.
                        Note that calling a separate LLM for image handling will increase response times."""
        return ConfigValueBool("custom_vision_model", "Custom Vision Model", description, False, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_vision_llm_api_config_value() -> ConfigValue:
        description = """Selects the vision model service to connect to (either local or via an API).
        
            If you are connecting to a local service (KoboldCpp, textgenwebui etc), please ensure that the service is running and a model is loaded. You can also enter a custom URL to connect to other LLM services that provide an OpenAI compatible endpoint.
            After selecting a service, select the model using the option below. Press the *Update* button to load a list of models available from the service.

            Some services require an API secret key. This secret key either needs to be set in your `GPT_SECRET_KEY.txt` file, or by creating a new text file called `IMAGE_SECRET_KEY.txt` in the same folder as `GPT_SECRET_KEY.txt` and adding the API key there."""
        options = ["OpenRouter", "OpenAI", "KoboldCpp", "textgenwebui"]
        return ConfigValueSelection("vision_llm_api", "Custom Vision Model Service", description, "OpenRouter", options, allows_free_edit=True, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_vision_model_config_value() -> ConfigValue:
        model_description = """Select the vision model to use. Press the *Update* button to load a list of models available from the service selected above.
                            The list does not provide all details about the models. For additional information please refer to the corresponding sites:
                            - OpenRouter: https://openrouter.ai/models?modality=text%2Bimage-%3Etext
                            - OpenAI: https://platform.openai.com/docs/models https://openai.com/api/pricing/"""
        return ConfigValueSelection("vision_model", "Custom Vision Model", model_description, "google/gemma-3-4b-it:free", ["Custom Model"], allows_values_not_in_options=True, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_vision_custom_token_count_config_value() -> ConfigValue:
        description = """If the vision model chosen is not recognised by Mantella, the token count for the given model will default to this number.
                    If this is not the correct token count for your chosen model, you can change it here.
                    Keep in mind that if this number is greater than the actual token count of the model, then Mantella will crash if a given conversation exceeds the model's token limit."""
        return ConfigValueInt("vision_custom_token_count", "Custom Vision Model Token Count", description, 4096, 4096, 9999999, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_vision_llm_params_config_value() -> ConfigValue:
        value = """{
                        "max_tokens": 100,
                        "stop": ["#"]
                    }"""
        description = """Parameters passed as part of the request to the vision model.
                        A list of the most common parameters can be found here: https://openrouter.ai/docs/parameters.
                        Note that available parameters can vary per LLM provider."""
        return ConfigValueString("vision_llm_params", "Custom Vision Model Parameters", description, value, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_use_game_screenshots_config_value() -> ConfigValue:
        description = """Whether to use screenshots taken in-game instead of relying on Mantella to capture the game window (Fallout 4 only).
                        Enable this setting to improve screenshot capture reliability. Otherwise please ensure your game window is visible on screen when running and is not blocked by other windows.
                        If enabled, please ensure you configure screenshot capture settings in the Mantella Pip-Boy settings window."""
        return ConfigValueBool("use_game_screenshots", "Use Game Screenshots", description, False, tags=[ConfigValueTag.advanced])