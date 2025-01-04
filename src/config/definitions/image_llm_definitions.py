from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_bool import ConfigValueBool


class ImageLLMDefinitions:
    @staticmethod
    def get_image_analysis_skyrim_filepath_config_value() -> ConfigValue:
        description = """ Settings for for the filepath of Skyrim (desktop) director.
        If SUP_SKSE is used to take screenshots the filepath is the one pointing to where the executable is located.
        If Steam is used to take screenshots the filepath is the one for the Steam directory where the steam screenshots are stored. Steam overlay must be enabled for it to work.
        For steam screenshots they should located inside your steam directory -> userdata -> Your personal user number -> 760 -> remote -> 489830 -> screenshots
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
        description = """ Settings for for the filepath of Fallout 4 (desktop) directory where the executable is located. 
        If you are not using Fallout 4 (desktop), you may retain the default setting.
        Copy the complete filepath from your OS file explorer.  """
        return ConfigValueString("image_analysis_fallout4_vr_filepath","Set the filepath to Steam Screenshot directory for Fallout 4 VR",description,"C:\Games\Steam\steamapps\common\Fallout 4 VR")

    def get_image_analysis_iterative_querying_config_value() -> ConfigValue:
        description = """ Selecting this will mean that Mantella will ask a LLM for an image description then make a second request to obtain a NPC response, the second request can be from a entirely different LLM.
If you're using iterative querying input True (or check the box)
if you're sending the image and the LLM prompt all at once input False (or uncheck the box) , then the values from [LLM] will be used for image queries except for the prompts
"""
        return ConfigValueBool("image_analysis_iterative_querying","Use iterative querying (two steps image analysis method)",description,False)
    
    @staticmethod
    def delete_steam_images_after_use() -> ConfigValue:
        description = """Check this to automatically delete steam screenshots taking while Mantella was active. The screenshots will be deleted after the conversation has ended."""
        return ConfigValueBool("delete_steam_screenshots_after_use","Delete steam screenshots after the conversation has ended",description,True, tags=[ConfigValueTag.advanced])
    
    