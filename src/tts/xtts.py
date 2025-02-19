from src.config.config_loader import ConfigLoader
from src.tts.ttsable import ttsable
import logging
import requests
from typing import Any
import soundfile as sf
import numpy as np
import io
import json
from subprocess import Popen
import time
from src.tts.synthesization_options import SynthesizationOptions
from src import utils
from threading import Thread

class TTSServiceFailure(Exception):
    pass

class xtts(ttsable):
    """XTTS TTS handler
    """
    @utils.time_it
    def __init__(self, config: ConfigLoader, game) -> None:
        super().__init__(config)
        self.__xtts_default_model = config.xtts_default_model
        self.__xtts_deepspeed = config.xtts_deepspeed
        self.__xtts_lowvram = config.xtts_lowvram
        self.__xtts_device = config.xtts_device
        self.__xtts_url = config.xtts_url
        self.__xtts_data = config.xtts_data
        self.__xtts_server_path = config.xtts_server_path
        self.__xtts_accent = config.xtts_accent
        self._language = self._language if self._language != 'zh' else 'zh-cn'
        self.__voice_accent = self._language
        self.__official_model_list = ["main","v2.0.3","v2.0.2","v2.0.1","v2.0.0"]
        self.__xtts_synthesize_url = f'{self.__xtts_url}/tts_to_audio/'
        self.__xtts_switch_model = f'{self.__xtts_url}/switch_model'
        self.__xtts_set_tts_settings = f'{self.__xtts_url}/set_tts_settings'
        self.__xtts_get_models_list = f'{self.__xtts_url}/get_models_list'
        self.__xtts_get_speakers_list = f'{self.__xtts_url}/speakers_list'
        if not self._facefx_path :
            self._facefx_path = self.__xtts_server_path + "/plugins/lip_fuz"

        logging.log(self._loglevel, f'Connecting to XTTS...')
        self._check_if_xtts_is_running()

        if self.__xtts_default_model in ['main','v2.0.2']:
            self.__available_models = ['v2.0.2']
        else:
            self.__available_models = self._get_available_models()
        self.__available_speakers = self._get_available_speakers()
        self.__available_speakers = [self._sanitize_voice_name(speaker) for speaker in self.__available_speakers]
        self.__last_model = self._get_first_available_official_model()
        self._set_xtts_settings()


    @utils.time_it
    def tts_synthesize(self, voiceline: str, final_voiceline_file: str, synth_options: SynthesizationOptions):
        self._synthesize_line_xtts(voiceline, final_voiceline_file)
    

    @utils.time_it
    def change_voice(self, voice: str, in_game_voice: str | None = None, csv_in_game_voice: str | None = None, advanced_voice_model: str | None = None, voice_accent: str | None = None, voice_gender: int | None = None, voice_race: str | None = None):
        logging.log(self._loglevel, 'Loading voice model...')

        selected_voice: str | None = self._select_voice_type(voice, in_game_voice, csv_in_game_voice, advanced_voice_model)

        if (selected_voice and selected_voice.lower() in ['maleeventoned','femaleeventoned']) and (self._game == 'Fallout4'):
            selected_voice = 'fo4_'+ selected_voice
        
        if not selected_voice:
            logging.log(self._loglevel, 'Error could not identify voice model!')
            return
        
        voice = selected_voice
        self._last_voice = selected_voice

        # Format the voice string to match the model naming convention
        voice = f"{voice.lower().replace(' ', '')}"
        if voice in self.__available_models and voice != self.__last_model :
            thread = Thread(target=self._send_request, args=(self.__xtts_switch_model, {"model_name": voice}), daemon=True)
            thread.start()
            self.__last_model = voice
        elif self.__last_model not in self.__official_model_list and voice != self.__last_model :
            first_available_voice_model = self._get_first_available_official_model()
            if first_available_voice_model:
                voice = f"{first_available_voice_model.lower().replace(' ', '')}"
                thread = Thread(target=self._send_request, args=(self.__xtts_switch_model, {"model_name": voice}), daemon=True)
                thread.start()
                self.__last_model = voice

        if (self.__xtts_accent == 1) and (voice_accent != None):
            if voice_accent == '':
                self.__voice_accent = self._language
            else:
                voice_accent = voice_accent if voice_accent != 'zh' else 'zh-cn'
                self.__voice_accent = voice_accent


    @utils.time_it
    def _get_available_models(self):
        # Code to request and return the list of available models
        try:
            response = requests.get(self.__xtts_get_models_list)
            if response.status_code == 200:
                # Convert each element in the response to lowercase and remove spaces
                return [model.lower().replace(' ', '') for model in response.json()]
            else:
                return []
        except requests.exceptions.ConnectionError as e:
            logging.warning(e)
            return []
        
        
    @utils.time_it
    def _get_available_speakers(self) -> dict[str, Any]:
        # Code to request and return the list of available models
        try:
            response = requests.get(self.__xtts_get_speakers_list)
            if response.status_code == 200:
                all_speakers = response.json()
                current_language_speakers = all_speakers.get(self._language, {}).get('speakers', [])
                if len(current_language_speakers) == 0: # if there are no speakers for the chosen language, fall back to English voice models
                    logging.warning(f"No voice models found in XTTS's speakers/{self._language} folder. Attempting to load English voice models instead...")
                    self._language = 'en'
                    current_language_speakers = all_speakers.get(self._language, {}).get('speakers', [])
                return current_language_speakers
            else:
                return {}
        except requests.exceptions.ConnectionError as e:
            logging.warning(e)
            return {}
    
    
    @utils.time_it
    def _get_first_available_official_model(self):
        # Check in the available models list if there is an official model
        for model in self.__official_model_list:
            if model in self.__available_models:
                return model
        return None

    
    @utils.time_it
    def _convert_to_16bit(self, input_file, output_file=None):
        if output_file is None:
            output_file = input_file
        # Read the audio file
        data, samplerate = sf.read(input_file)

        # Directly convert to 16-bit if data is in float format and assumed to be in the -1.0 to 1.0 range
        if np.issubdtype(data.dtype, np.floating):
            # Ensure no value exceeds the -1.0 to 1.0 range before conversion (optional, based on your data's characteristics)
            # data = np.clip(data, -1.0, 1.0)  # Uncomment if needed
            data_16bit = np.int16(data * 32767)
        elif not np.issubdtype(data.dtype, np.int16):
            # If data is not floating-point or int16, consider logging or handling this case explicitly
            # For simplicity, this example just converts to int16 without scaling
            data_16bit = data.astype(np.int16)
        else:
            # If data is already int16, no conversion is necessary
            data_16bit = data

        # Write the 16-bit audio data back to a file
        sf.write(output_file, data_16bit, samplerate, subtype='PCM_16')


    @utils.time_it
    def _select_voice_type(self, voice: str, in_game_voice: str | None, csv_in_game_voice: str | None, advanced_voice_model: str | None):
        # check if model name in each CSV column exists, with advanced_voice_model taking precedence over other columns
        for voice_type in [advanced_voice_model, voice, in_game_voice, csv_in_game_voice]:
            if voice_type:
                voice_cleaned = self._sanitize_voice_name(voice_type)
                if voice_cleaned in self.__available_speakers:
                    return voice_cleaned
        logging.error(f'Could not find voice model {voice} in XTTS models list')
    

    @utils.time_it
    def _synthesize_line_xtts(self, line, save_path):
        def get_voiceline(voice_name):
            voice_path = f"{self._sanitize_voice_name(voice_name)}"
            data = {
                'text': line,
                'speaker_wav': voice_path,
                'language': self._language,
                'accent': self.__voice_accent,
            }
            return requests.post(self.__xtts_synthesize_url, json=data)

        response = get_voiceline(self._last_voice.lower())
        if response and response.status_code == 200:
            self._convert_to_16bit(io.BytesIO(response.content), save_path)
        elif response:
            logging.error(f"Failed with '{self._last_voice}'. HTTP Error: {response.status_code}")


    @utils.time_it
    def _set_xtts_settings(self):
        tts_data_dict = json.loads(self.__xtts_data.replace('\n', ''))
        thread = Thread(target=self._send_request, args=(self.__xtts_set_tts_settings, tts_data_dict), daemon=True)
        thread.start()

    
    @utils.time_it
    def _check_if_xtts_is_running(self):
        try:
            # contact local XTTS server; ~2 second timeout
            response = requests.get(self.__xtts_url, timeout=2)
            if response.status_code >= 500:
                logging.log(self._loglevel, 'Could not connect to XTTS. Attempting to run headless server...')
                self._run_xtts_server()
        except requests.exceptions.RequestException as err:
            if ('Connection aborted' in err.__str__()):
                # so it is alive
                return

            logging.log(self._loglevel, 'Could not connect to XTTS. Attempting to run headless server...')
            self._run_xtts_server()
        

    @utils.time_it
    def _run_xtts_server(self):
        try:
            # Start the server
            command = f'{self.__xtts_server_path}\\xtts-api-server-mantella.exe'
    
            # Check if deepspeed should be enabled
            if self.__xtts_default_model:
                command += (f" --version {self.__xtts_default_model}")
            if self.__xtts_deepspeed:
                command += ' --deepspeed'
            if self.__xtts_device == "cpu":
                command += ' --device cpu'
            if self.__xtts_device == "cuda":
                command += ' --device cuda'
            if self.__xtts_lowvram:
                command += ' --lowvram'

            Popen(command, cwd=self.__xtts_server_path, stdout=None, stderr=None, shell=True)
            # Wait for the server to be up and running
            server_ready = False
            for _ in range(180):  # try for up to three minutes
                try:
                    response = requests.get(self.__xtts_url, timeout=2)
                    if response.status_code < 500:
                        server_ready = True
                        break
                except Exception:
                    pass  # Server not up yet
                time.sleep(1)
        
            if not server_ready:
                logging.error("XTTS server did not start within the expected time.")
                raise TTSServiceFailure()
        
        except Exception as e:
            utils.play_error_sound()
            logging.error(f'Could not run XTTS. Ensure that the path "{self.__xtts_server_path}" is correct. Error: {e}')
            #raise TTSServiceFailure()