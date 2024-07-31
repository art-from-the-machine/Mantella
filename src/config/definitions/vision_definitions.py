import os
from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString

class VisionDefinitions:
    @staticmethod
    def get_vision_enabled_config_value() -> ConfigValue:
        return ConfigValueBool("vision_enabled", "Vision", "If enabled, in-game screenshots are passed to the chosen LLM with each player response. This feature is only compatible with LLMs that accept image as well as text inputs.", False)
    
    @staticmethod
    def get_save_screenshot_config_value() -> ConfigValue:
        return ConfigValueBool("save_screenshot", "Save Screenshots", "Whether to save screenshots to Documents/My Games/Mantella/data/tmp/images/. Disable this setting to improve performance.", False)

    @staticmethod
    def get_image_quality_config_value() -> ConfigValue:
        return ConfigValueInt("image_quality", "Screenshot Quality", "The quality of the image passed to the LLM. Higher values improve the LLM's understanding of passed images. Lower values improve performance.", 50, 1, 100, tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_resize_image_config_value() -> ConfigValue:
        return ConfigValueBool("resize_image", "Resize Image", "Resize image to a height of 512 pixels. Enable this setting to lower API costs / improve performance.", True, tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_resize_method_config_value() -> ConfigValue:
        return ConfigValueSelection("resize_method", "Resize Method", "The image scaling algorithm used to resize in-game screenshots if Resize Image is enabled. Algorithms are sorted from fastest / lowest quality (Nearest) to slowest / highest quality (Lanczos).", "Nearest", ["Nearest", "Linear", "Cubic", "Lanczos"], tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_capture_offset_config_value() -> ConfigValue:
        value = '{"left": 0, "right": 0, "top": 0, "bottom": 0}'
        description = '''The number of pixels to offset the capture window. Adjust these numbers with either positive or negative values if the game window is not being captured in the correct dimensions.'''
        return ConfigValueString("capture_offset", "Capture Offset", description, value, tags=[ConvigValueTag.advanced])