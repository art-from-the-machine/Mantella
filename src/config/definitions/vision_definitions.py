import os
from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection

class VisionDefinitions:
    @staticmethod
    def get_vision_enabled_config_value() -> ConfigValue:
        return ConfigValueBool("vision_enabled", "Vision Enabled", "If enabled, in-game screenshots are passed to the chosen LLM with each player response. This feature is only compatible with LLMs that accept image as well as text inputs.", False)
    
    @staticmethod
    def get_save_screenshot_config_value() -> ConfigValue:
        return ConfigValueBool("save_screenshot", "Save Screenshots", "Whether to save screenshots to Documents/My Games/Mantella/data/tmp/images/. Disable this setting to improve performance.", False)

    @staticmethod
    def get_image_quality_config_value() -> ConfigValue:
        return ConfigValueInt("image_quality", "Screenshot Quality", "The quality of the image passed to the LLM. Higher values improve the LLM's understanding of passed images. Lower values improve performance.", 50, 1, 100, tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_resize_method_config_value() -> ConfigValue:
        return ConfigValueSelection("resize_method", "Resize Method", "The image scaling algorithm used to resize in-game screenshots. Algorithms are sorted from fastest / lowest quality (Nearest) to slowest / highest quality (Lanczos).", "Nearest", ["Nearest", "Linear", "Cubic", "Lanczos"], tags=[ConvigValueTag.advanced])