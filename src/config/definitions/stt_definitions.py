from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString


class STTDefinitions:
    @staticmethod
    def get_use_automatic_audio_threshold_folder_config_value() -> ConfigValue:
        return ConfigValueBool("use_automatic_audio_threshold", "Automatic Audio Threshold","Should the microphone automatically try to adjust for background noise?\nIf you get stuck at 'Listening...', disable this setting and manually set the audio threshold in the setting below.", False)
    
    @staticmethod
    def get_audio_threshold_folder_config_value() -> ConfigValue:
        audio_threshold_description = """Controls how much background noise is filtered out.
                                        If the mic is not picking up speech, try lowering this value.
                                        If the mic is picking up too much background noise, try increasing this value."""
        return ConfigValueInt("audio_threshold","Audio Threshold",audio_threshold_description, 175, 1, 999)
    
    @staticmethod
    def get_model_size_config_value() -> ConfigValue:
        description = """The size of the Whisper model used. Some languages require larger models. The base.en model works well enough for English.
                        See here for a comparison of languages and their Whisper performance: 
                        https://github.com/openai/whisper#available-models-and-languages"""
        return ConfigValueSelection("model_size", "Model Size", description, "base", ["tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "medium.en", "large-v1", "large-v2", "whisper-1"])

    @staticmethod
    def get_pause_threshold_config_value() -> ConfigValue:
        description = """How long to wait (in seconds) before converting mic input to text.
                    If you feel like you are being cut off before you finish your response, increase this value.
                    If you feel like there is too much of a delay between you finishing your response and the text conversion, decrease this value."""
        return ConfigValueFloat("pause_threshold","Pause Threshold", description, 1.0, 1.0, 999, tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_listen_timeout_config_value() -> ConfigValue:
        description = """How long to wait (in seconds) for the player to speak before retrying.
                    This needs to be set to ensure that Mantella can periodically check if the conversation has ended."""
        return ConfigValueInt("listen_timeout","Listen Timeout",  description, 30, 0, 999, tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_stt_language_config_value() -> ConfigValue:
        description = """The player's spoken language."""
        return ConfigValueSelection("stt_language","STT Language",description,"default",["default","en", "ar", "cs", "da", "de", "el", "es", "fi", "fr", "hi", "hu", "it", "ja", "ko", "nl", "pl", "pt", "ro", "ru", "sv", "sw", "uk", "ha", "tr", "vi", "yo"], tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_stt_translate_config_value() -> ConfigValue:
        description = """Translate the transcribed speech to English if supported by the Speech-To-Text engine (only impacts faster_whisper option, no impact on whispercpp, which is controlled by your server).
                        STTs that support this function: Whisper (faster_whisper)."""
        return ConfigValueBool("stt_translate", "STT Translate",description, False, tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_process_device_config_value() -> ConfigValue:
        return ConfigValueSelection("process_device", "Process Device", "Whether to run Whisper on your CPU or NVIDIA GPU (with CUDA installed) (only impacts faster_whisper option, no impact on whispercpp, which is controlled by your server).","cpu",["cpu","cuda"], tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_whisper_type_config_value() -> ConfigValue:
        description = """Intended for advanced use only. Allows using whispercpp (https://github.com/ggerganov/whisper.cpp) in server mode instead of the default faster_whisper.
                        Alternatively, can be used to run Whisper via the OpenAI API.
                        The main benefits would be to reduce VRAM usage when using larger whisper models, to enable use of distil-whisper models,
                        to share a whisper speech to text service between AI mods like Mantella and Herika, or run the whispercpp server in a cloud service.
                        In whispercpp server mode, the server settings, not the ones above, will control the model you use and CPU vs GPU usage.  
                        You are expected to "bring your own server" and have whispercpp running while running Mantella.
                        If the default works for you, DO NOT change this variable. 
                        To change to whispercpp server mode / OpenAI API instead, enter whispercpp. 
                        Additionally, if using the OpenAI API, ensure your GPT_SECRET_KEY.txt is an OpenAI key, 'Whisper URL' is "https://api.openai.com/v1/audio/transcriptions" below, and 'Model Size' is "whisper-1" above"""
        return ConfigValueString("whisper_type","Whisper Type", description, "faster_whisper", tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_whisper_url_config_value() -> ConfigValue:
        description = """Intended for advanced use only. Allows entering a OpenAI-compatible server URL. If you set whispercpp above in 'Whisper Type', then enter the whispercpp server URL here.
                        Note that if you are also using the Herika mod, the default 8080 port used by whispercpp server may conflict with Herika. You can change the port to, e.g., 8070 instead to avoid the conflict.
                        Examples: http://127.0.0.1:8080/inference (default) / http://127.0.0.1:8070/inference (if you use the optional --port 8070 comand line argument), https://api.openai.com/v1/audio/transcriptions (if using OpenAI API)"""
        return ConfigValueString("whisper_url","Whisper URL",description, "http://127.0.0.1:8080/inference", tags=[ConvigValueTag.advanced])
    