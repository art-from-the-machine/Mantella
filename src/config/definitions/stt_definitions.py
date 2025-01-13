from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult


class STTDefinitions:
    class WhisperProcessDeviceChecker(ConfigValueConstraint[str]):
        def __init__(self) -> None:
            super().__init__()

        def apply_constraint(self, value_to_apply_to: str) -> ConfigValueConstraintResult:
            if value_to_apply_to == 'cuda':
                return ConfigValueConstraintResult(f'''
Depending on your NVIDIA CUDA version, setting the Whisper process device to `cuda` may cause errors! For more information, see here: [github.com/SYSTRAN/faster-whisper#gpu](https://github.com/SYSTRAN/faster-whisper#gpu)''')
            else:
                return ConfigValueConstraintResult()
    
    @staticmethod
    def get_use_automatic_audio_threshold_folder_config_value() -> ConfigValue:
        description = """Sets whether the microphone should automatically try to adjust for background noise.
        If you get stuck at 'Listening...', disable this setting and manually set the audio threshold in the setting below."""
        return ConfigValueBool("use_automatic_audio_threshold", "Automatic Audio Threshold", description, False)
    
    @staticmethod
    def get_audio_threshold_folder_config_value() -> ConfigValue:
        audio_threshold_description = """Controls how much background noise is filtered out.
                                        If the mic is not picking up speech, try lowering this value.
                                        If the mic is picking up too much background noise, try increasing this value."""
        return ConfigValueInt("audio_threshold","Audio Threshold",audio_threshold_description, 175, 0, 999)
    
    @staticmethod
    def get_stt_service_config_value() -> ConfigValue:
        description = """Choose between running Moonshine or Whisper as your speech to text service.
                        Moonshine runs faster than Whisper on a CPU, but only support English.
                        Whisper can run on a CPU, GPU, or via an external service (see Advanced settings below)."""
        options = ["Moonshine", "Whisper"]
        return ConfigValueSelection("stt_service", "STT Service", description, "Moonshine", options, allows_free_edit=False)
    
    @staticmethod
    def get_pause_threshold_config_value() -> ConfigValue:
        description = """How long to wait (in seconds) before converting mic input to text.
                    If you feel like you are being cut off before you finish your response, increase this value.
                    If you feel like there is too much of a delay between you finishing your response and the text conversion, decrease this value.
                    It is recommended to set to this value to at least 0.1."""
        return ConfigValueFloat("pause_threshold","Pause Threshold", description, 1.0, 0, 999, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_listen_timeout_config_value() -> ConfigValue:
        description = """How long to wait (in seconds) for the player to speak before retrying.
                    This needs to be set to ensure that Mantella can periodically check if the conversation has ended."""
        return ConfigValueInt("listen_timeout","Listen Timeout",  description, 30, 0, 999, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_moonshine_model_size_config_value() -> ConfigValue:
        description = """The size of the Moonshine model to use. The larger the model, the more accurate the transcription (at the cost of speed)."""
        options = ["moonshine/tiny", "moonshine/base"]
        return ConfigValueSelection("moonshine_model_size", "Moonshine Model", description, "moonshine/tiny", options, allows_free_edit=True, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_whisper_model_size_config_value() -> ConfigValue:
        description = """The size of the Whisper model used. Some languages require larger models. The base.en model works well enough for English.
                        See here for a comparison of languages and their Whisper performance: 
                        https://github.com/openai/whisper#available-models-and-languages"""
        options = ["tiny", "tiny.en", 
                   "base", "base.en", 
                   "small", "small.en", "distil-small.en", 
                   "medium", "medium.en", "distil-medium.en", 
                   "large-v1", "large-v2", "large-v3", "distil-large-v2", "distil-large-v3", 
                   "whisper-1"]
        return ConfigValueSelection("whisper_model_size", "Whisper Model", description, "base", options, allows_free_edit=True, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_external_whisper_service_config_value() -> ConfigValue:
        description = """Allows running of Whisper externally. When enabled, Mantella will call the URL set in 'Whisper URL' instead of running Whisper locally."""
        return ConfigValueBool("external_whisper_service","External Whisper Service", description, False, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_whisper_url_config_value() -> ConfigValue:
        description = """The external Whisper service URL Mantella will connect to (if 'External Whisper Service' is enabled). 
                        Some services require an API secret key. This secret key either needs to be set in your `GPT_SECRET_KEY.txt` file, or by creating a new text file called `STT_SECRET_KEY.txt` in the same folder as `GPT_SECRET_KEY.txt` and adding the API key there. If you don't see the service you would like to connect to in the dropdown list, you can also manually enter a URL to connect to.
                        
                        Known services:
	                        OpenAI: Ensure 'Speech-to-Text'->'Model Size' is set to `whisper-1`. Requires an OpenAI secret key.
                            Groq: Ensure 'Speech-to-Text'->'Model Size' is set to one of the following: https://console.groq.com/docs/speech-text#supported-models. Requires a Groq secret key.
                            whisper.cpp: whisper.cpp (https://github.com/ggerganov/whisper.cpp) can be connected to when it is run in server mode. No secret key is required. Ensure the server is running before starting Mantella. By default, selecting whisper.cpp will connect to the URL http://127.0.0.1:8080/inference, but you can also manually enter a URL in this field if you have selected a port other than 8080 or are running whisper.cpp on another machine."""
        return ConfigValueSelection("whisper_url", "Whisper Service", description, "OpenAI", ["OpenAI", "Groq", "whisper.cpp"], allows_free_edit=True, tags=[ConfigValueTag.advanced])

    @staticmethod
    def get_stt_language_config_value() -> ConfigValue:
        description = """The player's spoken language."""
        return ConfigValueSelection("stt_language","Whisper STT Language",description,"default",["default","en", "ar", "cs", "da", "de", "el", "es", "fi", "fr", "hi", "hu", "it", "ja", "ko", "nl", "pl", "pt", "ro", "ru", "sv", "sw", "uk", "ha", "tr", "vi", "yo"], tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_stt_translate_config_value() -> ConfigValue:
        description = """Translate the transcribed speech to English if supported by the Speech-To-Text engine (only impacts faster_whisper option, no impact on whispercpp, which is controlled by your server).
                        STTs that support this function: Whisper (faster_whisper)."""
        return ConfigValueBool("stt_translate", "Whisper STT Translate",description, False, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_process_device_config_value() -> ConfigValue:
        description = "Whether to run Whisper on your CPU or NVIDIA GPU (with CUDA installed) (only impacts faster_whisper option, no impact on whispercpp, which is controlled by your server)."
        return ConfigValueSelection("process_device", "Whisper Process Device", description,"cpu",["cpu","cuda"], constraints=[STTDefinitions.WhisperProcessDeviceChecker()], tags=[ConfigValueTag.advanced])