import requests
from requests.exceptions import ConnectionError
import time
import winsound
import logging
import src.utils as utils
import os
import soundfile as sf
import numpy as np
import re
import sys
from pathlib import Path
import json
from subprocess import Popen, PIPE, STDOUT, DEVNULL, STARTUPINFO,STARTF_USESHOWWINDOW
import io
import subprocess
import csv

class TTSServiceFailure(Exception):
    pass

class VoiceModelNotFound(Exception):
    pass

class Synthesizer:
    def __init__(self, config, character_df):
        self.loglevel = 29
        self.xvasynth_path = config.xvasynth_path
        self.facefx_path = config.facefx_path
        self.process_device = config.xvasynth_process_device
        self.times_checked = 0
        # to print output to console
        self.tts_print = config.tts_print
        
        #Added from XTTS implementation
        self.tts_service = config.tts_service
        self.xtts_default_model = config.xtts_default_model
        self.xtts_deepspeed = int(config.xtts_deepspeed)
        self.xtts_lowvram = int(config.xtts_lowvram)
        self.xtts_device = config.xtts_device
        self.xtts_url = config.xtts_url
        self.xtts_data = config.xtts_data
        self.xtts_server_path = config.xtts_server_path
        self.xtts_accent = config.xtts_accent
        self.official_model_list = ["main","v2.0.3","v2.0.2","v2.0.1","v2.0.0"]

        self.synthesize_url = 'http://127.0.0.1:8008/synthesize'
        self.synthesize_batch_url = 'http://127.0.0.1:8008/synthesize_batch'
        self.loadmodel_url = 'http://127.0.0.1:8008/loadModel'
        self.setvocoder_url = 'http://127.0.0.1:8008/setVocoder'

        self.xtts_synthesize_url = f'{self.xtts_url}/tts_to_audio/'
        self.xtts_switch_model = f'{self.xtts_url}/switch_model'
        self.xtts_set_tts_settings = f'{self.xtts_url}/set_tts_settings'
        self.xtts_get_models_list = f'{self.xtts_url}/get_models_list'
        self.xtts_get_speakers_list = f'{self.xtts_url}/speakers_list'
        
        character_df['advanced_voice_model'] = character_df['advanced_voice_model'].fillna('').apply(str)
        character_df['voice_model'] = character_df['voice_model'].fillna('').apply(str)

        self.advanced_voice_model_data = list(set(character_df['advanced_voice_model'].tolist()))
        self.voice_model_data = list(set(character_df['voice_model'].tolist()))
        
        # voice models path (renaming Fallout4VR to Fallout4 to allow for filepath completion)
        if config.game == "Fallout4" or config.game == "Fallout4VR":
            self.game = "Fallout4"
        #(renaming SkyrimVR to Skyrim to allow for filepath completion)
        else: 
            self.game = "Skyrim"
        # check if xvasynth is running; otherwise try to run it
        if self.tts_service == 'xtts':
            logging.log(self.loglevel, f'Connecting to XTTS...')
            self.check_if_xtts_is_running()
            self.available_models = self._get_available_models()
            self.available_speakers = self._get_available_speakers()
            self.generate_filtered_speaker_dicts()
            self.last_model = self.get_first_available_official_model()
            if not self.facefx_path :
                self.facefx_path = self.xtts_server_path + "/plugins/lip_fuz"
        else:
            logging.log(self.loglevel, f'Connecting to xVASynth...')
            self.check_if_xvasynth_is_running()
            if not self.facefx_path :
                self.facefx_path = self.xvasynth_path + "/resources/app/plugins/lip_fuz"


        self.model_path = f"{self.xvasynth_path}/resources/app/models/{self.game}/"
        # output wav / lip files path
        self.output_path = utils.resolve_path()+'/data'

        self.language = config.language

        self.pace = config.pace
        self.use_sr = bool(config.use_sr)
        self.use_cleanup = bool(config.use_cleanup)

        # determines whether the voiceline should play internally
        self.debug_mode = config.debug_mode
        self.play_audio_from_script = config.play_audio_from_script

        # last active voice model
        self.last_voice = ''

        self.model_type = ''
        self.base_speaker_emb = ''
       

    def _get_available_models(self):
        # Code to request and return the list of available models
        response = requests.get(self.xtts_get_models_list)
        if response.status_code == 200:
            # Convert each element in the response to lowercase and remove spaces
            return [model.lower().replace(' ', '') for model in response.json()]
        else:
            return []
            
    def _get_available_speakers(self):
        # Code to request and return the list of available models
        response = requests.get(self.xtts_get_speakers_list)
        return response.json() if response.status_code == 200 else []
    
    def get_first_available_official_model(self):
        # Check in the available models list if there is an official model
        for model in self.official_model_list:
            if model in self.available_models:
                return model
        return None

    def convert_to_16bit(self, input_file, output_file=None):
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

    def synthesize(self, voice, voiceline, in_game_voice, voice_accent, aggro=0, advanced_voice_model=None):
        if self.tts_service == 'xtts':
            selected_voice = None
            speaker_type = None
    
            # Determine the most suitable voice model to use
            if advanced_voice_model and self._voice_exists(advanced_voice_model, 'advanced'):
                selected_voice = advanced_voice_model
                speaker_type = 'advanced_voice_model'
            elif voice and self._voice_exists(voice, 'regular'):
                selected_voice = voice
                speaker_type = 'voice_model'
            elif in_game_voice and self._voice_exists(in_game_voice, 'regular'):
                selected_voice = in_game_voice
                speaker_type = 'game_voice_folder'
            voice = selected_voice
                
        if voice != self.last_voice:
            self.change_voice(voice, voice_accent)
            self.last_voice = voice

        logging.log(22, f'Synthesizing voiceline: {voiceline.strip()}')
        phrases = self._split_voiceline(voiceline)

        if self.tts_service == 'xvasynth':
            phrases = self._split_voiceline(voiceline)
			
            voiceline_files = []
            for phrase in phrases:
                voiceline_file = f"{self.output_path}/voicelines/{utils.clean_text(phrase)[:150]}.wav"
                voiceline_files.append(voiceline_file)

        final_voiceline_file_name = 'out' # "out" is the file name used by XTTS
        final_voiceline_folder = f"{self.output_path}/voicelines"
        final_voiceline_file =  f"{final_voiceline_folder}/{final_voiceline_file_name}.wav"

        try:
            if os.path.exists(final_voiceline_file):
                os.remove(final_voiceline_file)
            if os.path.exists(final_voiceline_file.replace(".wav", ".lip")):
                os.remove(final_voiceline_file.replace(".wav", ".lip"))
        except:
            logging.warning("Failed to remove spoken voicelines")
    
        # Synthesize voicelines
        if self.tts_service == 'xtts':
            self._synthesize_line_xtts(voiceline, final_voiceline_file, voice, speaker_type, aggro)
        else:
            if len(phrases) == 1:
                self._synthesize_line(phrases[0], final_voiceline_file, aggro)
            else:
				# TODO: include batch synthesis for v3 models (batch not needed very often)
                if self.model_type != 'xVAPitch':
                    self._batch_synthesize(phrases, voiceline_files)
                else:
                    for i, voiceline_file in enumerate(voiceline_files):
                        self._synthesize_line(phrases[i], voiceline_files[i])
                self.merge_audio_files(voiceline_files, final_voiceline_file)
        if not os.path.exists(final_voiceline_file):
            logging.error(f'xVASynth failed to generate voiceline at: {Path(final_voiceline_file)}')
            raise FileNotFoundError()

        # FaceFX for creating a LIP file
        try:
            # check if FonixData.cdf file is besides FaceFXWrapper.exe
            cdf_path = Path(self.facefx_path) / 'FonixData.cdf' 
            if not cdf_path.exists():
                logging.error(f'Could not find FonixData.cdf in "{cdf_path.parent}" required by FaceFXWrapper. Look for the Lip Fuz plugin of xVASynth.')
                raise FileNotFoundError()

            # generate .lip file from the .wav file with FaceFXWrapper
            face_wrapper_executable = Path(self.facefx_path) / "FaceFXWrapper.exe"
            if not face_wrapper_executable.exists():
                logging.error(f'Could not find FaceFXWrapper.exe in "{face_wrapper_executable.parent}" with which to create a Lip Sync file, download it from: https://github.com/Nukem9/FaceFXWrapper/releases')
                raise FileNotFoundError()
        
            # Run FaceFXWrapper.exe
            r_wav = final_voiceline_file.replace(".wav", "_r.wav")
            lip = final_voiceline_file.replace(".wav", ".lip")
            commands = [
                face_wrapper_executable.name,
                self.game,
                "USEnglish",
                cdf_path.name,
                f'"{final_voiceline_file}"',
                f'"{r_wav}"',
                f'"{lip}"',
                f'"{voiceline}"'
            ]
            command = " ".join(commands)
            self.run_facefx_command(command)


            # remove file created by FaceFXWrapper
            if os.path.exists(final_voiceline_file.replace(".wav", "_r.wav")):
                os.remove(final_voiceline_file.replace(".wav", "_r.wav"))
        except Exception as e:
            logging.warning(e)

        # if Debug Mode is on, play the audio file
        if (self.debug_mode == '1') & (self.play_audio_from_script == '1'):
            winsound.PlaySound(final_voiceline_file, winsound.SND_FILENAME)
        return final_voiceline_file

    def _group_sentences(self, voiceline_sentences, max_length=150):
        """
        Splits sentences into separate voicelines based on their length (max=max_length)
        Groups sentences if they can be done so without exceeding max_length
        """
        grouped_sentences = []
        temp_group = []
        for sentence in voiceline_sentences:
            if len(sentence) > max_length:
                grouped_sentences.append(sentence)
            elif len(' '.join(temp_group + [sentence])) <= max_length:
                temp_group.append(sentence)
            else:
                grouped_sentences.append(' '.join(temp_group))
                temp_group = [sentence]
        if temp_group:
            grouped_sentences.append(' '.join(temp_group))

        return grouped_sentences
    

    def _split_voiceline(self, voiceline, max_length=150):
        """Split voiceline into phrases by commas, 'and', and 'or'"""

        # Split by commas and "and" or "or"
        chunks = re.split(r'(, | and | or )', voiceline)
        # Join the delimiters back to their respective chunks
        chunks = [chunks[i] + (chunks[i+1] if i+1 < len(chunks) else '') for i in range(0, len(chunks), 2)]
        # Filter out empty chunks
        chunks = [chunk for chunk in chunks if chunk.strip()]

        result = []
        for chunk in chunks:
            if len(chunk) <= max_length:
                if result and result[-1].endswith(' and'):
                    result[-1] = result[-1][:-4]
                    chunk = 'and ' + chunk.strip()
                elif result and result[-1].endswith(' or'):
                    result[-1] = result[-1][:-3]
                    chunk = 'or ' + chunk.strip()
                result.append(chunk.strip())
            else:
                # Split long chunks based on length
                words = chunk.split()
                current_line = words[0]
                for word in words[1:]:
                    if len(current_line + ' ' + word) <= max_length:
                        current_line += ' ' + word
                    else:
                        if current_line.endswith(' and'):
                            current_line = current_line[:-4]
                            word = 'and ' + word
                        if current_line.endswith(' or'):
                            current_line = current_line[:-3]
                            word = 'or ' + word
                        result.append(current_line.strip())
                        current_line = word
                result.append(current_line.strip())

        result = self._group_sentences(result, max_length)
        logging.debug(f'Split sentence into : {result}')

        return result
    

    def merge_audio_files(self, audio_files, voiceline_file_name):
        merged_audio = np.array([])

        for audio_file in audio_files:
            try:
                audio, samplerate = sf.read(audio_file)
                merged_audio = np.concatenate((merged_audio, audio))
            except:
                logging.error(f'Could not find voiceline file: {audio_file}')

        sf.write(voiceline_file_name, merged_audio, samplerate)
    

    @utils.time_it
    def _synthesize_line(self, line, save_path, aggro=0):
        pluginsContext = {}
        # in combat
        if (aggro == 1):
            pluginsContext["mantella_settings"] = {
                "emAngry": 0.6
            }
        data = {
            'pluginsContext': json.dumps(pluginsContext),
            'modelType': self.model_type,
            'sequence': line,
            'pace': self.pace,
            'outfile': save_path,
            'vocoder': 'n/a',
            'base_lang': self.language,
            'base_emb': self.base_speaker_emb,
            'useSR': self.use_sr,
            'useCleanup': self.use_cleanup,
        }

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                requests.post(self.synthesize_url, json=data)
                break  # Exit the loop if the request is successful
            except ConnectionError as e:
                if attempt < max_attempts - 1:  # Not the last attempt
                    logging.warning(f"Connection error while synthesizing voiceline. Restarting xVASynth server... ({attempt})")
                    self.run_xvasynth_server()
                    self.change_voice(self.last_voice)
                else:
                    logging.error(f"Failed to synthesize line after {max_attempts} attempts. Skipping voiceline: {line}")
                    break

    def _sanitize_voice_name(self, voice_name):
        """Sanitizes the voice name by removing spaces."""
        return voice_name.replace(" ", "").lower()

    def _voice_exists(self, voice_name, speaker_type):
        """Checks if the sanitized voice name exists in the specified filtered speakers."""
        sanitized_voice_name = self._sanitize_voice_name(voice_name)
        speakers = []
        
        if speaker_type == 'advanced':
            speakers = self.advanced_filtered_speakers.get(self.language, {}).get('speakers', [])
        elif speaker_type == 'regular':
            speakers = self.voice_filtered_speakers.get(self.language, {}).get('speakers', [])

        return sanitized_voice_name in [self._sanitize_voice_name(speaker) for speaker in speakers]
 
    @utils.time_it
    def _synthesize_line_xtts(self, line, save_path, voice, speaker_type, aggro=0):
        def get_voiceline(voice_name):
            voice_path = f"{self._sanitize_voice_name(voice_name)}"
            data = {
                'text': line,
                'speaker_wav': voice_path,
                'language': self.language,
            }
            return requests.post(self.xtts_synthesize_url, json=data)

        response = get_voiceline(voice.lower())
        if response and response.status_code == 200:
            self.convert_to_16bit(io.BytesIO(response.content), save_path)
            logging.info(f"Successfully synthesized using {speaker_type}: '{voice}'")
            return  # Exit the function successfully after processing
        elif response:
            logging.error(f"Failed with {speaker_type}: '{voice}'. HTTP Error: {response.status_code}")


    def filter_and_log_speakers(self, voice_model_list, log_file_name):
        # Initialize filtered speakers dictionary with all languages
        filtered_speakers = {lang: {'speakers': []} for lang in self.available_speakers}
        # Prepare the header for the CSV log
        languages = sorted(self.available_speakers.keys())
        log_data = [["Voice Model"] + languages]

        # Set to keep track of added (sanitized) voice models to avoid duplicates
        added_voice_models = set()

        # Iterate over each voice model in the list and sanitize
        for voice_model in voice_model_list:
            sanitized_vm = self._sanitize_voice_name(voice_model)
            # Skip if this sanitized voice model has already been processed
            if sanitized_vm in added_voice_models:
                continue

            # Add to tracking set
            added_voice_models.add(sanitized_vm)

            # Initialize log row with sanitized name
            row = [sanitized_vm] + [''] * len(languages)
            # Check each language for the presence of the sanitized voice model
            for i, lang in enumerate(languages, start=1):
                available_lang_speakers = [self._sanitize_voice_name(speaker) for speaker in self.available_speakers[lang]['speakers']]
                if sanitized_vm in available_lang_speakers:
                    # Append sanitized voice model name to the filtered speakers list for the language
                    filtered_speakers[lang]['speakers'].append(sanitized_vm)
                    # Mark as found in this language in the log row
                    row[i] = 'X'

            # Append row to log data
            log_data.append(row)

        # Write log data to CSV file
        with open(f"{log_file_name}_xtts.csv", 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(log_data)

        return filtered_speakers

        # Write to CSV file
        with open(f"{log_file_name}_xtts.csv", 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(log_data)

        return filtered_speakers

    def generate_filtered_speaker_dicts(self):
        # Filter and log advanced voice models
        self.advanced_filtered_speakers = self.filter_and_log_speakers(self.advanced_voice_model_data, "advanced_voice_model_data_log")
        
        # Filter and log regular voice models
        self.voice_filtered_speakers = self.filter_and_log_speakers(self.voice_model_data, "voice_model_data_log")

    @utils.time_it
    def _batch_synthesize(self, grouped_sentences, voiceline_files):
        # line = [text, unknown 1, unknown 2, pace, output_path, unknown 5, unknown 6, pitch_amp]
        linesBatch = [[grouped_sentences[i], '', '', 1, voiceline_files[i], '', '', 1] for i in range(len(grouped_sentences))]
        
        data = {
            'pluginsContext': '{}',
            'modelType': self.model_type,
            'linesBatch': linesBatch,
            'speaker_i': None,
            'vocoder': [],
            'outputJSON': None,
            'useSR': None,
            'useCleanup': None,
        }

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                requests.post(self.synthesize_batch_url, json=data)
                break  # Exit the loop if the request is successful
            except ConnectionError as e:
                if attempt < max_attempts - 1:  # Not the last attempt
                    logging.warning(f"Connection error while synthesizing voiceline. Restarting xVASynth server... ({attempt})")
                    self.run_xvasynth_server()
                    self.change_voice(self.last_voice)
                else:
                    logging.error(f"Failed to synthesize line after {max_attempts} attempts. Skipping voiceline: {linesBatch}")
                    break

    def check_if_xvasynth_is_running(self):
        self.times_checked += 1
        try:
            if (self.times_checked > 10):
                # break loop
                logging.error(f'Could not connect to xVASynth after {self.times_checked} attempts. Ensure that xVASynth is running and restart Mantella.')
                raise TTSServiceFailure()

            # contact local xVASynth server; ~2 second timeout
            response = requests.get('http://127.0.0.1:8008/')
            response.raise_for_status()  # If the response contains an HTTP error status code, raise an exception
        except requests.exceptions.RequestException as err:
            if ('Connection aborted' in err.__str__()):
                # So it is alive
                return

            if (self.times_checked == 1):
                self.run_xvasynth_server()
            # do the web request again; LOOP!!!
            return self.check_if_xvasynth_is_running()
        
    def check_if_xtts_is_running(self):
        self.times_checked += 1
        tts_data_dict = json.loads(self.xtts_data.replace('\n', ''))
        
        try:
            if (self.times_checked > 10):
                # break loop
                logging.error(f'Could not connect to XTTS after {self.times_checked} attempts. Ensure that xtts-api-server is running and restart Mantella.')
                raise TTSServiceFailure()

            # contact local xVASynth server; ~2 second timeout
            response = requests.post(self.xtts_set_tts_settings, json=tts_data_dict)
            response.raise_for_status() 
            
        except requests.exceptions.RequestException as err:
            if ('Connection aborted' in err.__str__()):
                # So it is alive
                return

            if (self.times_checked == 1):
                logging.log(self.loglevel, 'Could not connect to XTTS. Attempting to run headless server...')
                self.run_xtts_server()
      
    def run_xtts_server(self):
        try:
            # Start the server
            command = f'{self.xtts_server_path}\\xtts-api-server-mantella.exe'
    
            # Check if deepspeed should be enabled
            if self.xtts_default_model:
                command += (f" --version {self.xtts_default_model}")
            if self.xtts_deepspeed == 1:
                command += ' --deepspeed'
            if self.xtts_device == "cpu":
                command += ' --device cpu'
            if self.xtts_device == "cuda":
                command += ' --device cuda'
            if self.xtts_lowvram == 1 :
                command += ' --lowvram'

            Popen(command, cwd=self.xtts_server_path, stdout=None, stderr=None, shell=True)
            tts_data_dict = json.loads(self.xtts_data.replace('\n', ''))
            # Wait for the server to be up and running
            server_ready = False
            for _ in range(120):  # try for up to 10 seconds
                try:
                    response = requests.post(self.xtts_set_tts_settings, json=tts_data_dict)
                    if response.status_code == 200:
                        server_ready = True
                        break
                except ConnectionError:
                    pass  # Server not up yet
                time.sleep(1)
        
            if not server_ready:
                logging.error("XTTS server did not start within the expected time.")
                raise TTSServiceFailure()
        
        except Exception as e:
            logging.error(f'Could not run XTTS. Ensure that the path "{self.xtts_server_path}" is correct. Error: {e}')
            raise TTSServiceFailure()

    def run_xvasynth_server(self):
        try:
            # start the process without waiting for a response
            if (self.tts_print == 1):
                # print subprocess output
                Popen(f'{self.xvasynth_path}/resources/app/cpython_{self.process_device}/server.exe', cwd=self.xvasynth_path, stdout=None, stderr=None)
            else:
                # ignore output
                Popen(f'{self.xvasynth_path}/resources/app/cpython_{self.process_device}/server.exe', cwd=self.xvasynth_path, stdout=DEVNULL, stderr=DEVNULL)

            time.sleep(1)
        except:
            logging.error(f'Could not run xVASynth. Ensure that the path "{self.xvasynth_path}" is correct.')
            raise TTSServiceFailure()
 
    def _set_tts_settings_and_test_if_serv_running(self):
        try:
            # Sending a POST request to the API endpoint
            logging.log(self.loglevel, f'Attempting to connect to xTTS...')
            tts_data_dict = json.loads(self.xtts_data.replace('\n', ''))
            response = requests.post(self.xtts_set_tts_settings, json=tts_data_dict)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            # Log the error
            logging.error(f'Could not reach the API at "{self.xtts_set_tts_settings}". Error: {e}')
            # Wait for user input before exiting
            logging.error(f'You should run xTTS api server before running Mantella.')
            input('\nPress any key to stop Mantella...')
            sys.exit(0)
            
    @utils.time_it
    def change_voice(self, voice, voice_accent=None):
        logging.log(self.loglevel, 'Loading voice model...')
        
        if self.tts_service == 'xtts':
            # Format the voice string to match the model naming convention
            voice = f"{voice.lower().replace(' ', '')}"
            if voice in self.available_models and voice != self.last_model :
                requests.post(self.xtts_switch_model, json={"model_name": voice})
                self.last_model = voice
            elif self.last_model not in self.official_model_list and voice != self.last_model :
                voice = self.get_first_available_official_model()
                voice = f"{voice.lower().replace(' ', '')}"
                requests.post(self.xtts_switch_model, json={"model_name": voice})
                self.last_model = voice

            if (self.xtts_accent == 1) and (voice_accent != None):
                self.language = voice_accent
            
        else :
            #this is a game check for Fallout4/Skyrim to correctly search the XVASynth voice models for the right game.
            if self.game == "Fallout4" or self.game == "Fallout4VR":
                XVASynthAcronym="f4_"
                XVASynthModNexusLink="https://www.nexusmods.com/fallout4/mods/49340?tab=files"
            else:
                XVASynthAcronym="sk_"
                XVASynthModNexusLink = "https://www.nexusmods.com/skyrimspecialedition/mods/44184?tab=files"
            voice_path = f"{self.model_path}{XVASynthAcronym}{voice.lower().replace(' ', '')}"

            if not os.path.exists(voice_path+'.json'):
                logging.error(f"Voice model does not exist in location '{voice_path}'. Please ensure that the correct path has been set in config.ini (xvasynth_folder) and that the model has been downloaded from https://www.nexusmods.com/skyrimspecialedition/mods/44184?tab=files (Ctrl+F for 'sk_{voice.lower().replace(' ', '')}').")
                raise VoiceModelNotFound()

            with open(voice_path+'.json', 'r', encoding='utf-8') as f:
                voice_model_json = json.load(f)

            try:
                base_speaker_emb = voice_model_json['games'][0]['base_speaker_emb']
                base_speaker_emb = str(base_speaker_emb).replace('[','').replace(']','')
            except:
                base_speaker_emb = None

            self.base_speaker_emb = base_speaker_emb
            self.model_type = voice_model_json.get('modelType')
        
            model_change = {
                'outputs': None,
                'version': '3.0',
                'model': voice_path, 
                'modelType': self.model_type,
                'base_lang': self.language, 
                'pluginsContext': '{}',
            }
            #For some reason older 1.0 model will load in a way where they only emit high pitched static noise about 20-30% of the time, this series of run_backupmodel calls below 
            #are here to prevent the static issues by loading the model by following a sequence of model versions of 
            # 3.0 -> 1.1  (will fail to load) -> 3.0 -> 1.1 -> make a dummy voice sample with _synthesize_line -> 1.0 (will fail to load) -> 3.0 -> 1.0 again
            if voice_model_json.get('modelVersion') == 1.0:
                logging.log(self.loglevel, '1.0 model detected running following sequence to bypass voice model issues : 3.0 -> 1.1  (will fail to load) -> 3.0 -> 1.1 -> make a dummy voice sample with _synthesize_line -> 1.0 (will fail to load) -> 3.0 -> 1.0 again')
                if self.game == "Fallout4" or self.game == "Fallout4VR":
                    backup_voice='piper'
                    self.run_backup_model(backup_voice)
                    backup_voice='maleeventoned'
                    self.run_backup_model(backup_voice)
                    backup_voice='piper'
                    self.run_backup_model(backup_voice)
                    backup_voice='maleeventoned'
                    self.run_backup_model(backup_voice)
                    self._synthesize_line("test phrase", f"{self.output_path}/FO4_data/temp.wav")
                else:
                    backup_voice='malenord'
                    self.run_backup_model(backup_voice)
            try:
                requests.post(self.loadmodel_url, json=model_change)
                self.last_voice = voice
                logging.log(self.loglevel, f'Target model {voice} loaded.')
            except:
                logging.error(f'Target model {voice} failed to load.')
                #This step is vital to get older voice models (1,1 and lower) to run
                if self.game == "Fallout4" or self.game == "Fallout4VR":
                    backup_voice='piper'
                else:
                    backup_voice='malenord'
                self.run_backup_model(backup_voice)
                try:
                    requests.post(self.loadmodel_url, json=model_change)
                    self.last_voice = voice
                    logging.log(self.loglevel, f'Voice model {voice} loaded.')
                except:
                    logging.error(f'model {voice} failed to load try restarting Mantella')
                    input('\nPress any key to stop Mantella...')
                    sys.exit(0)


    def run_backup_model(self, voice):
        logging.log(self.loglevel, f'Attempting to load backup model {voice}.')
        #This function exists only to force XVASynth to play older models properly by resetting them by loading models in sequence
        
        #If for some reason the model fails to load (for example, because it's an older model) then Mantella will attempt to load a backup model. 
        #This will allow the older model to load without errors 
            
        if self.game == "Fallout4" or self.game == "Fallout4VR":
            XVASynthAcronym="f4_"
            XVASynthModNexusLink="https://www.nexusmods.com/fallout4/mods/49340?tab=files"
            #voice='maleeventoned'
        else:
            XVASynthAcronym="sk_"
            XVASynthModNexusLink = "https://www.nexusmods.com/skyrimspecialedition/mods/44184?tab=files"
            #voice='malenord'
        voice_path = f"{self.model_path}{XVASynthAcronym}{voice.lower().replace(' ', '')}"
        if not os.path.exists(voice_path+'.json'):
            logging.error(f"Voice model does not exist in location '{voice_path}'. Please ensure that the correct path has been set in config.ini (xvasynth_folder) and that the model has been downloaded from {XVASynthModNexusLink} (Ctrl+F for '{XVASynthAcronym}{voice.lower().replace(' ', '')}').")
            raise VoiceModelNotFound()

        with open(voice_path+'.json', 'r', encoding='utf-8') as f:
            voice_model_json = json.load(f)

        try:
            base_speaker_emb = voice_model_json['games'][0]['base_speaker_emb']
            base_speaker_emb = str(base_speaker_emb).replace('[','').replace(']','')
        except:
            base_speaker_emb = None

        backup_model_type = voice_model_json.get('modelType')
        
        backup_model_change = {
            'outputs': None,
            'version': '3.0',
            'model': voice_path, 
            'modelType': backup_model_type,
            'base_lang': self.language, 
            'pluginsContext': '{}',
        }
        try:
            requests.post(self.loadmodel_url, json=backup_model_change)
            logging.log(self.loglevel, f'Backup model {voice} loaded.')
        except:
            logging.error(f"Backup model {voice} failed to load")

    def run_facefx_command(self, command):
        startupinfo = STARTUPINFO()
        startupinfo.dwFlags |= STARTF_USESHOWWINDOW
        
        batch_file_path = Path(self.facefx_path) / "run_mantella_command.bat"
        with open(batch_file_path, 'w') as file:
            file.write(f"@echo off\n{command} >nul 2>&1")

        subprocess.run(batch_file_path, cwd=self.facefx_path, creationflags=subprocess.CREATE_NO_WINDOW)
