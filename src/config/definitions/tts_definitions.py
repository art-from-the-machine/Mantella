import os
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_path import ConfigValuePath
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult


class TTSDefinitions:
    class ResourceFolderExistsChecker(ConfigValueConstraint[str]):
        def __init__(self) -> None:
            super().__init__(f"Selected folder must contain subfolder '\\resources\\'!")

        def apply_constraint(self, value_to_apply_to: str) -> ConfigValueConstraintResult:
            if not os.path.exists(f"{value_to_apply_to}\\resources\\"):
                return ConfigValueConstraintResult(f'''
The selected folder for xVASynth is missing the expected subfolder '\\resources\\'. 
If you have trouble installing the xVASynth version from Nexus, try installing it from Steam.''')
            else:
                return ConfigValueConstraintResult()

    @staticmethod
    def get_xvasynth_folder_config_value() -> ConfigValue:
        return ConfigValuePath("xvasynth_folder", "xVASynth Folder", "The folder you have xVASynth downloaded to (the folder that contains xVASynth.exe).", "C:\\Games\\Steam\\steamapps\\common\\xVASynth","xVASynth.exe",[TTSDefinitions.ResourceFolderExistsChecker()])
    
    @staticmethod
    def get_xtts_folder_config_value() -> ConfigValue:
        return ConfigValuePath("xtts_server_folder", "XTTS Folder", "The folder you have the XTTS server downloaded to (the folder that contains xtts-api-server-mantella.exe).", "C:\\Games\\Steam\\steamapps\\common\\XTTS","xtts-api-server-mantella.exe")
    
    @staticmethod
    def get_piper_folder_config_value(is_hidden: bool = False) -> ConfigValue:
        #Note(Leidtier): Because this is a Frankenparameter, I just set it to be a string. It SHOULD be a path, but this would require a different handling of the default empty state
        return ConfigValueString("piper_folder", "Piper Folder", "The folder where Piper is installed (where piper.exe exists).", "", is_hidden=is_hidden)

    @staticmethod
    def get_lipgen_folder_config_value(is_hidden: bool = False) -> ConfigValue:
        #Note(Leidtier): Because this is a Frankenparameter, I just set it to be a string. It SHOULD be a path, but this would require a different handling of the default empty state
        description = """The LipGenerator program is required by Bethesda games to accurately lip sync voicelines.
                        Please install the Creation Kit from Steam. Once installed, set this path to be the same path as your game folder (where the exectuable is located)."""
        return ConfigValueString("lipgen_folder", "LipGenerator Folder", description, "", is_hidden=is_hidden)
    
    @staticmethod
    def get_facefx_folder_config_value(is_hidden: bool = False) -> ConfigValue:
        #Note(Leidtier): Because this is a Frankenparameter, I just set it to be a string. It SHOULD be a path, but this would require a different handling of the default empty state
        facefx_discription = """The FaceFXWrapper is an alternative program to LipGenerator. Lip sync generation is required by Bethesda games to accurately lip sync voicelines.
                                This path does not need to be set if you have the LipGenerator folder configured."""
        return ConfigValueString("facefx_folder", "FaceFXWrapper Folder", facefx_discription, "", is_hidden=is_hidden)
    
    @staticmethod
    def get_tts_service_config_value() -> ConfigValue:
        return ConfigValueSelection("tts_service","TTS Service","The TTS service used by Mantella.","Piper",["Piper", "xVASynth", "XTTS"])
    
    @staticmethod
    def get_number_words_tts_config_value() -> ConfigValue:
        description = """Minimum threshold of words in a sentence needed before sending to the TTS service.
                        TTS services often struggle with synthesizing short voicelines, so increasing this threshold can improve quality."""
        return ConfigValueInt("number_words_tts","Number of Words TTS",description, 3, 1, 999999)
    
    @staticmethod
    def get_lip_generation_config_value() -> ConfigValue:
        description = """Whether to generate lip sync files for spoken voicelines. Disable this setting to improve response times.
                        Set to 'Lazy' to skip lip syncing only for the first sentence spoken of every response."""
        return ConfigValueSelection("lip_generation","Lip File Generation",description,"Enabled",["Enabled","Lazy","Disabled"],tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_fast_response_mode_config_value() -> ConfigValue:
        description = """Whether to play the first voiceline of every response directly from the Mantella exe instead of in-game.
                        Enable this setting to improve response times.
                        Disable this setting to play all voicelines natively in-game."""
        return ConfigValueBool("fast_response_mode","Fast Response Mode", description, False, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_fast_response_mode_volume_config_value() -> ConfigValue:
        description = """Adjust the volume of the first delivered voiceline (from 1-100) if Fast Response Mode is enabled."""
        return ConfigValueInt("fast_response_mode_volume","Fast Response Mode Volume", description, 40, 1, 100, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    # XTTS Section

    @staticmethod
    def get_xtts_url_config_value() -> ConfigValue:
        description = """The URL that your XTTS server is running on.
                        Examples:
                        http://127.0.0.1:8020 when running XTTS locally.
                        https://{POD_ID}-8020.proxy.runpod.net when running XTTS in a RunPod GPU pod."""
        return ConfigValueString("xtts_url","XTTS URL",description, "http://127.0.0.1:8020",tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_xtts_default_model_config_value() -> ConfigValue:
        return ConfigValueSelection("xtts_default_model","XTTS Default Model","Official base XTTS-V2 model to use.", "main",["v2.0.0", "v2.0.1", "v2.0.2", "v2.0.3", "main"],tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_xtts_device_config_value() -> ConfigValue:
        return ConfigValueSelection("xtts_device","XTTS Device","Set to cpu or cuda (NVIDIA GPUs only). You can also specify which NVIDIA GPU to use (cuda:0, cuda:1 etc)", "cpu" ,["cpu", "cuda", "cuda:0", "cuda:1", "cuda:2","cuda:3", "cuda:4", "cuda:5", "cuda:6", "cuda:7"],tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_xtts_deepspeed_config_value() -> ConfigValue:
        return ConfigValueBool("xtts_deepspeed","XTTS DeepSpeed","Allows you to speed up processing by several times (highly recommended for NVIDIA GPU players!).\nOnly usable with an NVIDIA GPU that supports CUDA 11.8+.", False, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_xtts_lowvram_config_value() -> ConfigValue:
        description = """The mode in which the model will be stored in RAM and when the processing occurs it will move to VRAM. The difference in speed is small.
                    If you don't want to pre-generate the latents for every speaker, enable this setting or else it will generate the latents at every start."""
        return ConfigValueBool("xtts_lowvram","XTTS Low VRAM", description, True, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_xtts_data_config_value() -> ConfigValue:
        value = """{"temperature": 0.75,
                    "length_penalty": 1.0,
                    "repetition_penalty": 5.0,
                    "top_k": 50,
                    "top_p": 0.85,
                    "speed": 1,
                    "enable_text_splitting": true,
                    "stream_chunk_size": 100}"""
        return ConfigValueString("xtts_data","XTTS Data","Default settings passed to the XTTS API server.", value,tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_xtts_accent_config_value() -> ConfigValue:
        description = """Note that this setting is only available for Skyrim.
        Changes the 'accent' of NPCs by sending the language value from data/Skyrim/skyrim_characters.csv's lang_override column to XTTS.\nThis helps give NPC's unique-sounding voices, even when they use the same base voice model."""
        return ConfigValueBool("xtts_accent", "XTTS Accent", description, False, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    # xVASynth section
    @staticmethod
    def get_tts_process_device_config_value() -> ConfigValue:
        description = "Whether to run xVASynth server (unless already running) on your CPU or a NVIDIA GPU (with CUDA installed).\nThis setting has a minimal effect on response times."
        return ConfigValueSelection("tts_process_device","xVASynth Process Device", description, "cpu", ["cpu", "gpu"], tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_pace_config_value() -> ConfigValue:
        description = """The default speed of talking. The effect can vary between voices.
                        0.5 = 2x faster; 2 = 2x slower"""
        return ConfigValueFloat("pace","xVASynth Pace", description, 1.0, 0.1, 2.0, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_use_cleanup_config_value() -> ConfigValue:
        description = """Whether to try to reduce noise and the robot-sounding nature of xVASynth generated speech.
                        Has a slight impact on processing speed for the CPU.
                        Not meant to be used on voices that have post-effects attached to them (echoes, reverbs, etc)."""
        return ConfigValueBool("use_cleanup","xVASynth Cleanup",description, False, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_use_sr_config_value() -> ConfigValue:
        description = """Whether to improve the quality of your audio through Super-resolution of 22050Hz audio into 48000Hz audio.
                        This is a fairly slow process on CPUs, but on some GPUs it can be relatively fast."""
        return ConfigValueBool("use_sr","xVASynth Super Resolution",description, False, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_tts_print_config_value() -> ConfigValue:
        return ConfigValueBool("tts_print","Print TTS Output","Print the output from the TTS service in the Mantella.exe window.", False, tags=[ConfigValueTag.advanced])

    






