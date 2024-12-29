import os
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString

class VisionDefinitions:
    @staticmethod
    def get_vision_enabled_config_value() -> ConfigValue:
        description = """If enabled, in-game screenshots are passed to the chosen LLM with each player response. This feature is only compatible with LLMs that accept image as well as text input.
                        **Please ensure your game window is visible on screen when running and is not blocked by other windows!**"""
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