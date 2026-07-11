from src.config.config_loader import ConfigLoader
from src.tts.ttsable import TTSable
from src.tts.synthesization_options import SynthesizationOptions
from src.llm.client_base import ClientBase
from src import utils
import requests
import io

logger = utils.get_logger()


class OpenAICompatibleTTS(TTSable):
    """Generic client for any TTS server exposing an OpenAI-compatible /v1/audio/speech endpoint
    """
    supports_streaming = True

    @utils.time_it
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__(config)
        base_url = config.openai_tts_url
        if base_url.endswith('/v1'):
            self.__synthesize_url = f'{base_url}/audio/speech'
        else:
            self.__synthesize_url = f'{base_url}/v1/audio/speech'
        self.__base_url = base_url
        self.__model = config.openai_tts_model
        self.__speed = config.openai_tts_speed
        self.__api_key = self._resolve_api_key()
        self.__voice = ''

        logger.log(self._loglevel, f'Connecting to OpenAI-compatible TTS server at {self.__base_url}...')
        self._check_if_service_is_running()


    @utils.time_it
    def change_voice(self, voice: str, in_game_voice: str | None = None, csv_in_game_voice: str | None = None, advanced_voice_model: str | None = None, voice_accent: str | None = None, voice_gender: int | None = None, voice_race: str | None = None):
        for voice_type in [advanced_voice_model, voice, in_game_voice, csv_in_game_voice]:
            if isinstance(voice_type, str) and voice_type.strip():
                self.__voice = self._sanitize_voice_name(voice_type)
                self._last_voice = voice_type
                return
        logger.log(self._loglevel, 'Error could not identify voice model!')


    def _build_request(self, voiceline: str) -> tuple[dict, dict]:
        data = {
            'model': self.__model,
            'input': voiceline,
            'voice': self.__voice,
            'response_format': 'wav',
            'speed': self.__speed,
        }
        headers = {'Authorization': f'Bearer {self.__api_key}'}
        return data, headers


    def _build_stream_request(self, voiceline: str) -> tuple[str, dict, dict | None]:
        data, headers = self._build_request(voiceline)
        return self.__synthesize_url, data, headers


    @utils.time_it
    def _synthesize_voiceline(self, voiceline: str, final_voiceline_file: str, synth_options: SynthesizationOptions):
        data, headers = self._build_request(voiceline)
        try:
            response = self._session.post(self.__synthesize_url, json=data, headers=headers, timeout=(5, 60))
        except requests.exceptions.RequestException as e:
            logger.error(f'Could not reach OpenAI-compatible TTS server at {self.__base_url}: {e}')
            return

        if response.status_code != 200:
            logger.error(f"OpenAI-compatible TTS failed with voice '{self.__voice}'. HTTP {response.status_code}: {response.text[:300]}")
            return

        try:
            self._convert_to_16bit(io.BytesIO(response.content), final_voiceline_file)
        except Exception as e:
            # some servers stream WAVs with unknown data lengths in their headers, which soundfile may reject
            logger.warning(f'Could not re-encode WAV from TTS server ({e}). Saving raw response instead')
            with open(final_voiceline_file, 'wb') as f:
                f.write(response.content)


    @utils.time_it
    def _resolve_api_key(self) -> str:
        if utils.is_local_url(self.__base_url):
            return 'abc123'
        api_key = ClientBase._get_api_key(self.__base_url, show_error=False)
        if api_key:
            return api_key
        logger.warning(f"No API key found for '{self.__base_url}' in secret_keys.json. Sending requests without authentication. If your TTS server requires a key, add an entry named after this URL")
        return 'abc123'


    @utils.time_it
    def _check_if_service_is_running(self):
        try:
            # any HTTP response (even a 404 on the bare base URL) means the server is reachable
            self._session.get(self.__base_url, timeout=2)
        except requests.exceptions.RequestException:
            logger.warning(f'Could not connect to OpenAI-compatible TTS server at {self.__base_url}. Voicelines will fail to generate until the server is available. Please check that the server is running and that the URL is correct in the TTS settings')
