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
    
    @staticmethod
    def get_audio_threshold_config_value() -> ConfigValue:
        audio_threshold_description = """Controls how much background noise is filtered out (from 0-1).
                                        If the mic is not picking up speech, try lowering this value.
                                        If the mic is picking up too much background noise, try increasing this value."""
        return ConfigValueFloat("audio_threshold","Audio Threshold",audio_threshold_description, 0.4, 0, 1)
    
    @staticmethod
    def get_allow_interruption_config_value() -> ConfigValue:
        description = """Sets whether the player can interrupt NPCs mid-response. 
                        Disable this setting if your microphone tends to pick up background noise or is picking up in-game speech. Alternatively, try increasing `Audio Threshold`."""
        return ConfigValueBool("allow_interruption", "Allow Interruption", description, True, tags=[ConfigValueTag.share_row])
    
    @staticmethod
    def get_save_mic_input_config_value() -> ConfigValue:
        description = """Whether to save captured mic input to Documents/My Games/Mantella/data/tmp/mic/.
                        Enable this setting to test your mic quality.
                        Disable this setting to improve performance."""
        return ConfigValueBool("save_mic_input", "Save Mic Input", description, False, tags=[ConfigValueTag.share_row])
    
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
                    Set this value to 0 for faster response times."""
        return ConfigValueFloat("pause_threshold","Pause Threshold", description, 0.25, 0, 999, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_play_cough_sound_config_value() -> ConfigValue:
        description = """If enabled, a generic cough sound will play when the speech-to-text service fails to transcribe player input.
                        Enable this setting if you are playing in VR / full screen and need an audio cue to know when you haven't been heard.
                        Disable this setting if its annoying."""
        return ConfigValueBool("play_cough_sound", "Cough Error Sound", description, True, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_listen_timeout_config_value() -> ConfigValue:
        description = """How long to wait (in seconds) for the player to speak before retrying.
                    This needs to be set to ensure that Mantella can periodically check if the conversation has ended."""
        return ConfigValueInt("listen_timeout","Listen Timeout",  description, 30, 0, 999, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_moonshine_model_size_config_value() -> ConfigValue:
        description = """The size of the Moonshine model to use (sorted from smallest to largest). The larger the model, the more accurate the transcription (at the cost of speed)."""
        options = ["moonshine/tiny/quantized_4bit", 
                   "moonshine/tiny/quantized", 
                   "moonshine/tiny/float", 
                   "moonshine/base/quantized_4bit",
                   "moonshine/base/quantized",
                   "moonshine/base/float"
                   ]
        return ConfigValueSelection("moonshine_model_size", "Moonshine Model", description, "moonshine/tiny/quantized", options, allows_free_edit=True, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
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
    def get_proactive_mic_mode_config_value() -> ConfigValue:
        description = """If enabled, mic input will be transcribed continuously (every `Refresh Frequency` seconds) as long as speech is detected.
                        Enable this setting to improve response times.
                        Disable this setting to improve performance."""
        return ConfigValueBool("proactive_mic_mode", "Proactive Mode", description, False, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_min_refresh_secs_config_value() -> ConfigValue:
        description = """Controls how frequently mic input is transcribed by Moonshine / Whisper.
                        Increase this value if the frequency is too intense for your hardware.
                        Decrease this value to improve response times."""
        return ConfigValueFloat("min_refresh_secs", "Refresh Frequency", description, 0.3, 0.01, 999, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
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
        return ConfigValueSelection("process_device", "Whisper Process Device", description,"cpu",["cpu","cuda"], tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_moonshine_folder_config_value(is_hidden: bool = False) -> ConfigValue:
        description = "The folder where Moonshine models are installed (where tiny/ and base/ folders exist)."
        return ConfigValueString("moonshine_folder", "Moonshine Folder", description, "", is_hidden=is_hidden, tags=[ConfigValueTag.advanced])

    @staticmethod
    def get_silence_auto_response_enabled_config_value() -> ConfigValue:
        description = """If enabled, the AI will automatically generate a response if the player is silent for a period of time."""
        return ConfigValueBool("silence_auto_response_enabled", "Auto-Response on Silence", description, False, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_silence_auto_response_timeout_config_value() -> ConfigValue:
        description = """How long to wait (in seconds) for the player to speak before automatically generating a response."""
        return ConfigValueFloat("silence_auto_response_timeout", "Silence Timeout", description, 30.0, 1, 999, tags=[ConfigValueTag.advanced, ConfigValueTag.share_row])
    
    @staticmethod
    def get_silence_auto_response_max_count_config_value() -> ConfigValue:
        description = """The maximum number of consecutive auto-responses before auto-response is disabled (until the player speaks again).
                        This is mainly to prevent runaway API costs if the player leaves the conversation running unattended."""
        return ConfigValueInt("silence_auto_response_max_count", "Max Consecutive Silences", description, 5, 1, 999, tags=[ConfigValueTag.advanced, ConfigValueTag.share_row])
    
    @staticmethod
    def get_silence_auto_response_message_config_value() -> ConfigValue:
        description = """The message sent to the AI when the player is silent."""
        return ConfigValueString("silence_auto_response_message", "Silence Message", description, "...", tags=[ConfigValueTag.advanced])