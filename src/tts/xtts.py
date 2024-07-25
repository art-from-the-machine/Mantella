from src.config.config_loader import ConfigLoader
from src.tts.ttsable import ttsable
import logging
import requests
from typing import Any
import soundfile as sf
import numpy as np
import csv
import io
import json
from subprocess import Popen
import time

class TTSServiceFailure(Exception):
    pass

class xtts(ttsable):
    """XTTS TTS handler
    """
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
        self.__voice_accent = self._language
        self.__official_model_list = ["main","v2.0.3","v2.0.2","v2.0.1","v2.0.0"]
        self.__xtts_synthesize_url = f'{self.__xtts_url}/tts_to_audio/'
        self.__xtts_switch_model = f'{self.__xtts_url}/switch_model'
        self.__xtts_set_tts_settings = f'{self.__xtts_url}/set_tts_settings'
        self.__xtts_get_models_list = f'{self.__xtts_url}/get_models_list'
        self.__xtts_get_speakers_list = f'{self.__xtts_url}/speakers_list'
        self.__advanced_voice_model_data = list(set(game.character_df['advanced_voice_model'].fillna('').apply(str).tolist()))
        self.__voice_model_data = list(set(game.character_df['voice_model'].fillna('').apply(str).tolist()))
        self.__csv_voice_folder_data = list(set(game.character_df['skyrim_voice_folder'].tolist())) if 'skyrim' in config.game.lower() else list(set(game.character_df['fallout4_voice_folder'].tolist()))
        self.__speaker_type = ''
        if not self._facefx_path :
            self._facefx_path = self.__xtts_server_path + "/plugins/lip_fuz"

        logging.log(self._loglevel, f'Connecting to XTTS...')
        self._check_if_xtts_is_running()

        self.__available_models = self._get_available_models()
        self.__available_speakers = self._get_available_speakers()
        self._generate_filtered_speaker_dicts()
        self.__last_model = self._get_first_available_official_model()


    def tts_synthesize(self, voiceline, final_voiceline_file, aggro):
        self._synthesize_line_xtts(voiceline, final_voiceline_file)
    

    def change_voice(self, voice: str, in_game_voice: str | None = None, csv_in_game_voice: str | None = None, advanced_voice_model: str | None = None, voice_accent: str | None = None):
        logging.log(self._loglevel, 'Loading voice model...')

        selected_voice: str | None = None
    
        # Determine the most suitable voice model to use
        if advanced_voice_model and self._voice_exists(advanced_voice_model, 'advanced'):
            selected_voice = advanced_voice_model
            self.__speaker_type = 'advanced_voice_model'
        elif voice and self._voice_exists(voice, 'regular'):
            selected_voice = voice
            self.__speaker_type = 'voice_model'
        elif in_game_voice and self._voice_exists(in_game_voice, 'regular'):
            selected_voice = in_game_voice
            self.__speaker_type = 'game_voice_folder'
        elif csv_in_game_voice and self._voice_exists(csv_in_game_voice, 'csv_voice_folder'):
            selected_voice = csv_in_game_voice
            self.__speaker_type = 'csv_game_voice_folder'

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
            requests.post(self.__xtts_switch_model, json={"model_name": voice})
            self.__last_model = voice
        elif self.__last_model not in self.__official_model_list and voice != self.__last_model :
            first_available_voice_model = self._get_first_available_official_model()
            if first_available_voice_model:
                voice = f"{first_available_voice_model.lower().replace(' ', '')}"
                requests.post(self.__xtts_switch_model, json={"model_name": voice})
                self.__last_model = voice

        if (self.__xtts_accent == 1) and (voice_accent != None):
            self.__voice_accent = voice_accent


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
        
        
    def _get_available_speakers(self) -> dict[str, Any]:
        # Code to request and return the list of available models
        try:
            response = requests.get(self.__xtts_get_speakers_list)
            return response.json() if response.status_code == 200 else {}
        except requests.exceptions.ConnectionError as e:
            logging.warning(e)
            return {}
    
    
    def _get_first_available_official_model(self):
        # Check in the available models list if there is an official model
        for model in self.__official_model_list:
            if model in self.__available_models:
                return model
        return None
    
    
    def _generate_filtered_speaker_dicts(self):
        def filter_and_log_speakers(voice_model_list, log_file_name, available_speakers, sanitize_voice_name_func):
            # Initialize filtered speakers dictionary with all languages
            filtered_speakers = {lang: {'speakers': []} for lang in available_speakers}
            # Prepare the header for the CSV log
            languages = sorted(available_speakers.keys())
            log_data = [["Voice Model"] + languages]

            # Set to keep track of added (sanitized) voice models to avoid duplicates
            added_voice_models = set()

            # Iterate over each voice model in the list and sanitize
            for voice_model in voice_model_list:
                sanitized_vm = sanitize_voice_name_func(voice_model)
                # Skip if this sanitized voice model has already been processed
                if sanitized_vm in added_voice_models:
                    continue

                # Add to tracking set
                added_voice_models.add(sanitized_vm)

                # Initialize log row with sanitized name
                row = [sanitized_vm] + [''] * len(languages)
                # Check each language for the presence of the sanitized voice model
                for i, lang in enumerate(languages, start=1):
                    available_lang_speakers = [sanitize_voice_name_func(speaker) for speaker in available_speakers[lang]['speakers']]
                    if sanitized_vm in available_lang_speakers:
                        # Append sanitized voice model name to the filtered speakers list for the language
                        filtered_speakers[lang]['speakers'].append(sanitized_vm)
                        # Mark as found in this language in the log row
                        row[i] = 'X'

                # Append row to log data
                log_data.append(row)

            # Write log data to CSV file
            with open(f"{self._save_folder}data/{log_file_name}_xtts.csv", 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(log_data)

            return filtered_speakers
        
        # Filter and log advanced voice models
        self.advanced_filtered_speakers = filter_and_log_speakers(self.__advanced_voice_model_data, "advanced_voice_model_data_log", self.__available_speakers, self._sanitize_voice_name)
        
        # Filter and log regular voice models
        self.voice_filtered_speakers = filter_and_log_speakers(self.__voice_model_data, "voice_model_data_log", self.__available_speakers, self._sanitize_voice_name)

        # Filter and log voice folder names according to CSV
        self.csv_voice_folder_speakers = filter_and_log_speakers(self.__csv_voice_folder_data, "csv_voice_folder_data_log", self.__available_speakers, self._sanitize_voice_name)

    
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


    def _voice_exists(self, voice_name, speaker_type):
        """Checks if the sanitized voice name exists in the specified filtered speakers."""
        sanitized_voice_name = self._sanitize_voice_name(voice_name)
        speakers = []
        
        if speaker_type == 'advanced':
            speakers = self.advanced_filtered_speakers.get(self._language, {}).get('speakers', [])
        elif speaker_type == 'regular':
            speakers = self.voice_filtered_speakers.get(self._language, {}).get('speakers', [])
        elif speaker_type == 'csv_voice_folder':
            speakers = self.csv_voice_folder_speakers.get(self._language, {}).get('speakers', [])

        return sanitized_voice_name in [self._sanitize_voice_name(speaker) for speaker in speakers]
    

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
            logging.error(f"Failed with {self.__speaker_type}: '{self._last_voice}'. HTTP Error: {response.status_code}")


    def _check_if_xtts_is_running(self):
        self._times_checked += 1
        tts_data_dict = json.loads(self.__xtts_data.replace('\n', ''))
        
        try:
            if (self._times_checked > 10):
                # break loop
                logging.error(f'Could not connect to XTTS after {self._times_checked} attempts. Ensure that xtts-api-server is running and restart Mantella.')
                raise TTSServiceFailure()

            # contact local XTTS server; ~2 second timeout
            response = requests.post(self.__xtts_set_tts_settings, json=tts_data_dict)
            response.raise_for_status() 
            
        except requests.exceptions.RequestException as err:
            if ('Connection aborted' in err.__str__()):
                # so it is alive
                return

            if (self._times_checked == 1):
                logging.log(self._loglevel, 'Could not connect to XTTS. Attempting to run headless server...')
                self._run_xtts_server()
        

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
            tts_data_dict = json.loads(self.__xtts_data.replace('\n', ''))
            # Wait for the server to be up and running
            server_ready = False
            for _ in range(180):  # try for up to three minutes
                try:
                    response = requests.post(self.__xtts_set_tts_settings, json=tts_data_dict)
                    if response.status_code == 200:
                        server_ready = True
                        break
                except Exception:
                    pass  # Server not up yet
                time.sleep(1)
        
            if not server_ready:
                logging.error("XTTS server did not start within the expected time.")
                raise TTSServiceFailure()
        
        except Exception as e:
            logging.error(f'Could not run XTTS. Ensure that the path "{self.__xtts_server_path}" is correct. Error: {e}')
            #raise TTSServiceFailure()