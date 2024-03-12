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
import pandas as pd
import sys
from pathlib import Path
import json
from subprocess import Popen, PIPE, STDOUT, DEVNULL, STARTUPINFO,STARTF_USESHOWWINDOW
import io

class TTSServiceFailure(Exception):
    pass

class VoiceModelNotFound(Exception):
    pass

class Synthesizer:
    def __init__(self, config):
        self.loglevel = 29
        self.xvasynth_path = config.xvasynth_path
        self.facefx_path = config.facefx_path
        self.process_device = config.xvasynth_process_device
        self.times_checked = 0
        # to print output to console
        self.tts_print = config.tts_print
        
        #Added from xTTS implementation
        self.use_external_xtts = int(config.use_external_xtts)
        self.xtts_default_model = config.xtts_default_model
        self.xtts_deepspeed = int(config.xtts_deepspeed)
        self.xtts_lowvram = int(config.xtts_lowvram)
        self.xtts_device = config.xtts_device
        self.xtts_set_tts_settings = config.xtts_set_tts_settings
        self.xTTS_tts_data = config.xTTS_tts_data
        self.xtts_server_path = config.xtts_server_path
        self.synthesize_url_xtts = config.xtts_synthesize_url
        self.switch_model_url = config.xtts_switch_model
        self.xtts_get_models_list = config.xtts_get_models_list
        self.official_model_list = ["main","v2.0.3","v2.0.2","v2.0.1","v2.0.0"]

        # check if xvasynth is running; otherwise try to run it
        if self.use_external_xtts == 1:
            self.check_if_xtts_is_running()
            self.available_models = self._get_available_models()
            if not self.facefx_path :
                self.facefx_path = self.xtts_server_path + "/plugins/lip_fuz"
        else:
            self.check_if_xvasynth_is_running()
            if not self.facefx_path :
                self.facefx_path = self.xvasynth_path + "/resources/app/plugins/lip_fuz"

        # voice models path
        self.model_path = f"{self.xvasynth_path}/resources/app/models/skyrim/"
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

        self.synthesize_url = 'http://127.0.0.1:8008/synthesize'
        self.synthesize_batch_url = 'http://127.0.0.1:8008/synthesize_batch'
        self.loadmodel_url = 'http://127.0.0.1:8008/loadModel'
        self.setvocoder_url = 'http://127.0.0.1:8008/setVocoder'
       

    def _get_available_models(self):
        # Code to request and return the list of available models
        response = requests.get(self.xtts_get_models_list)
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

    def synthesize(self, voice, voiceline, aggro=0):
        if voice != self.last_voice:
            self.change_voice(voice)

        logging.log(22, f'Synthesizing voiceline: {voiceline}')
        phrases = self._split_voiceline(voiceline)

        # make voice model folder if it doesn't already exist
        if not os.path.exists(f"{self.output_path}/voicelines/{self.last_voice}"):
            os.makedirs(f"{self.output_path}/voicelines/{self.last_voice}")
            
        if self.use_external_xtts == 0:
            phrases = self._split_voiceline(voiceline)
			
            voiceline_files = []
            for phrase in phrases:
                voiceline_file = f"{self.output_path}/voicelines/{self.last_voice}/{utils.clean_text(phrase)[:150]}.wav"
                voiceline_files.append(voiceline_file)

        final_voiceline_file_name = 'out' # "out" is the file name used by XTTS
        final_voiceline_folder = f"{self.output_path}/voicelines/{self.last_voice}"
        final_voiceline_file =  f"{final_voiceline_folder}/{final_voiceline_file_name}.wav"

        try:
            if os.path.exists(final_voiceline_file):
                os.remove(final_voiceline_file)
            if os.path.exists(final_voiceline_file.replace(".wav", ".lip")):
                os.remove(final_voiceline_file.replace(".wav", ".lip"))
        except:
            logging.warning("Failed to remove spoken voicelines")
    
        # Synthesize voicelines
        if self.use_external_xtts == 1:
            self._synthesize_line_xtts(voiceline, final_voiceline_file, voice, aggro)
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
            cdf_path = f'{self.facefx_path}/FonixData.cdf'
            if not os.path.exists(Path(cdf_path)):
                logging.error(f'Could not find FonixData.cdf in "{Path(cdf_path).parent}" required by FaceFXWrapper. Look for the Lip Fuz plugin of xVASynth.')
                raise FileNotFoundError()

            # generate .lip file from the .wav file with FaceFXWrapper
            face_wrapper_executable = f'{self.facefx_path}/FaceFXWrapper.exe';
            if os.path.exists(face_wrapper_executable):
                # Run FaceFXWrapper.exe
                self.run_command(f'{face_wrapper_executable} "Skyrim" "USEnglish" "{self.facefx_path}/FonixData.cdf" "{final_voiceline_file}" "{final_voiceline_file.replace(".wav", "_r.wav")}" "{final_voiceline_file.replace(".wav", ".lip")}" "{voiceline}"')
            else:
                logging.error(f'Could not find FaceFXWrapper.exe in "{Path(face_wrapper_executable).parent}" with which to create a Lip Sync file, download it from: https://github.com/Nukem9/FaceFXWrapper/releases')
                raise FileNotFoundError()

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
        requests.post(self.synthesize_url, json=data)

    @utils.time_it
    def _synthesize_line_xtts(self, line, save_path, voice, aggro=0):
        voice_path = f"{voice.lower().replace(' ', '')}"
        data = {
            'text': line,
            'speaker_wav': voice_path,
            'language': self.language
        }
        response = requests.post(self.synthesize_url_xtts, json=data)

        # Check if the response is successful
        if response.status_code == 200:
            # Convert the audio file to 16-bit format only if the POST request was successful
            self.convert_to_16bit(io.BytesIO(response.content), save_path)
        else:
            logging.error(f"Failed to synthesize line with xTTS: {response.status_code} - {response.text}")


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
        requests.post(self.synthesize_batch_url, json=data)

    def check_if_xvasynth_is_running(self):
        self.times_checked += 1

        try:
            if (self.times_checked > 10):
                # break loop
                logging.error('Could not connect to xVASynth multiple times. Ensure that xVASynth is running and restart Mantella.')
                raise TTSServiceFailure()

            # contact local xVASynth server; ~2 second timeout
            logging.log(self.loglevel, f'Attempting to connect to xVASynth... ({self.times_checked})')
            response = requests.get('http://127.0.0.1:8008/')
            response.raise_for_status()  # If the response contains an HTTP error status code, raise an exception
        except requests.exceptions.RequestException as err:
            if ('Connection aborted' in err.__str__()):
                # So it is alive
                return

            if (self.times_checked == 1):
                logging.log(self.loglevel, 'Could not connect to xVASynth. Attempting to run headless server...')
                self.run_xvasynth_server()

            # do the web request again; LOOP!!!
            return self.check_if_xvasynth_is_running()
        
    def check_if_xtts_is_running(self):
        self.times_checked += 1
        tts_data_dict = json.loads(self.xTTS_tts_data.replace('\n', ''))
        
        try:
            if (self.times_checked > 10):
                # break loop
                logging.error('Could not connect to xTTS multiple times. Ensure that xtts-api-server is running and restart Mantella.')
                raise TTSServiceFailure()

            # contact local xVASynth server; ~2 second timeout
            logging.log(self.loglevel, f'Attempting to connect to xTTS... ({self.times_checked})')
            response = requests.post(self.xtts_set_tts_settings, json=tts_data_dict)
            response.raise_for_status() 
            
        except requests.exceptions.RequestException as err:
            if ('Connection aborted' in err.__str__()):
                # So it is alive
                return

            if (self.times_checked == 1):
                logging.log(self.loglevel, 'Could not connect to xVASynth. Attempting to run headless server...')
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
            tts_data_dict = json.loads(self.xTTS_tts_data.replace('\n', ''))
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
        except:
            logging.error(f'Could not run xVASynth. Ensure that the path "{self.xvasynth_path}" is correct.')
            raise TTSServiceFailure()
            
    @utils.time_it
    def change_voice(self, voice):
        logging.log(self.loglevel, 'Loading voice model...')
        if self.use_external_xtts == 1:
            # Format the voice string to match the model naming convention
            voice_path = f"{voice.lower().replace(' ', '')}"
            model_voice = voice_path
            # Check if the specified voice is available
            if voice_path not in self.available_models and voice != self.last_voice:
                logging.log(self.loglevel, f'Voice "{voice}" not in available models. Available models: {self.available_models}')
                # Use the first available official model as a fallback
                model_voice = self.get_first_available_official_model()
                if model_voice is None:
                    # Handle the case where no official model is available
                    raise ValueError("No available voice model found.")
                # Update the voice_path with the fallback model
                model_voice = f"{model_voice.lower().replace(' ', '')}"

            # Request to switch the voice model
            requests.post(self.switch_model_url, json={"model_name": model_voice})
            
        else :
            voice_path = f"{self.model_path}sk_{voice.lower().replace(' ', '')}"
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
            requests.post(self.loadmodel_url, json=model_change)

        self.last_voice = voice

        logging.log(self.loglevel, 'Voice model loaded.')

    def run_command(self, command):
        startupinfo = STARTUPINFO()
        startupinfo.dwFlags |= STARTF_USESHOWWINDOW

        sp = Popen(command, startupinfo=startupinfo, stdout=PIPE, stderr=PIPE)

        stdout, stderr = sp.communicate()
        stderr = stderr.decode("utf-8")

    def log_subprocess_output(self, pipe):
        for line in iter(pipe.readline, b''): # b'\n'-separated lines
            logging.log(self.loglevel, '%r', line)