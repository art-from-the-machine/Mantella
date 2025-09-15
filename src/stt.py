import sys
import numpy as np
from faster_whisper import WhisperModel
import logging
from src.config.config_loader import ConfigLoader
import src.utils as utils
import requests
import json
import io
from pathlib import Path
from openai import OpenAI
from typing import Optional
from datetime import datetime
import queue
import threading
import time
import os
import wave
from moonshine_onnx import MoonshineOnnxModel, load_tokenizer
import onnxruntime as ort
from scipy.io import wavfile
from sounddevice import InputStream
from silero_vad import VADIterator, load_silero_vad

import onnxruntime as ort
ort.set_default_logger_severity(4)

class Transcriber:
    """Handles real-time speech-to-text transcription using Moonshine."""
    
    SAMPLING_RATE = 16000
    CHUNK_SIZE = 512  # Required chunk size for Silero VAD
    CHUNK_DURATION = CHUNK_SIZE / SAMPLING_RATE  # Explicit calculation of chunk duration in seconds
    LOOKBACK_CHUNKS = 5  # Number of chunks to keep in buffer when not recording
    
    @utils.time_it
    def __init__(self, config: ConfigLoader, stt_secret_key_file: str, secret_key_file: str):
        self.loglevel = 27
        self.language = config.stt_language
        self.task = "translate" if config.stt_translate else "transcribe"
        self.stt_service = config.stt_service
        self.full_moonshine_model = config.moonshine_model
        self.moonshine_model, self.moonshine_precision = self.full_moonshine_model.rsplit('/', 1)
        self.moonshine_folder = config.moonshine_folder
        self.moonshine_model_path = os.path.join(self.moonshine_folder, self.full_moonshine_model)
        self.whisper_model = config.whisper_model
        self.process_device = config.whisper_process_device
        self.listen_timeout = config.listen_timeout
        self.external_whisper_service = config.external_whisper_service
        self.whisper_service = config.whisper_url
        self.whisper_url = self.__get_endpoint(config.whisper_url)
        self.prompt = ''
        self.show_mic_warning = True
        self.play_cough_sound = config.play_cough_sound
        self.transcription_times = []
        self.proactive_mic_mode = config.proactive_mic_mode
        self.min_refresh_secs = config.min_refresh_secs # Minimum time between transcription updates
        self.refresh_freq = self.min_refresh_secs // self.CHUNK_DURATION # Number of chunks between transcription updates
        self.pause_threshold = config.pause_threshold
        self.audio_threshold = config.audio_threshold
        logging.log(self.loglevel, f"Audio threshold set to {self.audio_threshold}. If the mic is not picking up your voice, try lowering this `Speech-to-Text`->`Audio Threshold` value in the Mantella UI. If the mic is picking up too much background noise, try increasing this value.\n")

        self.__audio_input_error_count = 0
        self.__mic_input_process_error_count = 0
        self.__processing_audio_error_count = 0
        self.__warning_frequency = 5
        
        self.__save_mic_input = config.save_mic_input
        if self.__save_mic_input:
            self.__mic_input_path: str = config.save_folder+'data\\tmp\\mic'
            os.makedirs(self.__mic_input_path, exist_ok=True)

        self.__stt_secret_key_file = stt_secret_key_file
        self.__secret_key_file = secret_key_file
        self.__api_key: str | None = self.__get_api_key()
        self.__initial_client: OpenAI | None = None
        if (self.stt_service == 'whisper') and (self.__api_key) and ('openai' in self.whisper_url) and (self.external_whisper_service):
            self.__initial_client = self.__generate_sync_client() # initialize first client in advance to save time

        self.__ignore_list = ['', 'thank you', 'thank you for watching', 'thanks for watching', 'the transcript is from the', 'the', 'thank you very much', "thank you for watching and i'll see you in the next video", "we'll see you in the next video", 'see you next time']
        
        self.transcribe_model: WhisperModel | MoonshineOnnxModel | None = None
        if self.stt_service == 'whisper':
            # if using faster_whisper, load model selected by player, otherwise skip this step
            if not self.external_whisper_service:
                if self.process_device == 'cuda':
                    logging.error(f'''Depending on your NVIDIA CUDA version, setting the Whisper process device to `cuda` may cause errors! For more information, see here: https://github.com/SYSTRAN/faster-whisper#gpu''')
                    try:
                        self.transcribe_model = WhisperModel(self.whisper_model, device=self.process_device)
                    except Exception as e:
                        utils.play_error_sound()
                        raise e
                else:
                    self.transcribe_model = WhisperModel(self.whisper_model, device=self.process_device, compute_type="float32")
        else:
            if self.language != 'en':
                logging.warning(f"Selected language is '{self.language}', but Moonshine only supports English. Please change the selected speech-to-text model to Whisper in `Speech-to-Text`->`STT Service` in the Mantella UI")

            if self.moonshine_model == 'moonshine/tiny':
                logging.warning('Speech-to-text model set to Moonshine Tiny. If mic input is being transcribed incorrectly, try switching to a larger model in the `Speech-to-Text` tab of the Mantella UI')
            
            if os.path.exists(f'{self.moonshine_model_path}/encoder_model.onnx'):
                logging.log(self.loglevel, 'Loading local Moonshine model...')
                self.transcribe_model = MoonshineOnnxModel(models_dir=self.moonshine_model_path, model_name=self.moonshine_model)
            else:
                logging.log(self.loglevel, 'Loading Moonshine model from Hugging Face...')
                self.transcribe_model = MoonshineOnnxModel(model_name=self.moonshine_model, model_precision=self.moonshine_precision)
            self.tokenizer = load_tokenizer()
        
        # Initialize VAD
        self.vad_model = load_silero_vad(onnx=True)
        self.vad_iterator: VADIterator = self._create_vad_iterator()
        
        # Audio processing state
        self._audio_buffer = np.array([], dtype=np.float32)
        self._audio_queue = queue.Queue()
        self._stream: Optional[InputStream] = None
        
        # Threading and synchronization
        self._lock = threading.Lock()
        self._processing_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Speech detection state
        self._speech_detected = False
        self._speech_start_time = 0
        self._speech_end_time = 0
        self._last_update_time = 0
        self._current_transcription = ""
        self._transcription_ready = threading.Event()
        self._consecutive_empty_count = 0
        self._max_consecutive_empty = 10

    @property
    def is_listening(self) -> bool:
        """Returns True if actively listening."""
        return self._processing_thread is not None and self._processing_thread.is_alive()

    @property
    def has_player_spoken(self) -> bool:
        """Check if speech has been detected."""
        with self._lock:
            return self._speech_detected
        

    @utils.time_it
    def __generate_sync_client(self):
        if self.__initial_client:
            client = self.__initial_client
            self.__initial_client = None # do not reuse the same client
        else:
            client = OpenAI(api_key=self.__api_key, base_url=self.whisper_url)

        return client
    

    @utils.time_it
    def __get_endpoint(self, whisper_url):
        known_endpoints = {
            'OpenAI': 'https://api.openai.com/v1',
            'Groq': 'https://api.groq.com/openai/v1',
            'whisper.cpp': 'http://127.0.0.1:8080/inference',
        }
        if whisper_url in known_endpoints:
            return known_endpoints[whisper_url]
        else: # if not found, use value as is
            return whisper_url
        

    @utils.time_it
    def __get_api_key(self) -> str:
        if self.external_whisper_service:
            try: # first check mod folder for stt secret key
                mod_parent_folder = str(Path(utils.resolve_path()).parent.parent.parent)
                with open(mod_parent_folder+'\\'+self.__stt_secret_key_file, 'r') as f:
                    api_key: str = f.readline().strip()
            except: # check locally (same folder as exe) for stt secret key
                try:
                    with open(self.__stt_secret_key_file, 'r') as f:
                        api_key: str = f.readline().strip()
                except:
                    try: # first check mod folder for secret key
                        mod_parent_folder = str(Path(utils.resolve_path()).parent.parent.parent)
                        with open(mod_parent_folder+'\\'+self.__secret_key_file, 'r') as f:
                            api_key: str = f.readline().strip()
                    except: # check locally (same folder as exe) for secret key
                        with open(self.__secret_key_file, 'r') as f:
                            api_key: str = f.readline().strip()
                
            if not api_key:
                logging.error(f'''No secret key found in GPT_SECRET_KEY.txt. Please create a secret key and paste it in your Mantella mod folder's GPT_SECRET_KEY.txt file.
If using OpenAI, see here on how to create a secret key: https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key
If you would prefer to run speech-to-text locally, please ensure the `Speech-to-Text`->`External Whisper Service` setting in the Mantella UI is disabled.''')
                input("Press Enter to continue.")
                sys.exit(0)
            return api_key


    @utils.time_it
    def _transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio using Moonshine model."""
        # Count speech end time from when the last transcribe is called
        self._speech_end_time = time.time()
        if self.stt_service == 'moonshine':
            transcription = self.moonshine_transcribe(audio)
        else:
            transcription = self.whisper_transcribe(audio, self.prompt)

        self.transcription_times.append((time.time() - self._speech_end_time))
        if (self.proactive_mic_mode) and (len(self.transcription_times) % 5 == 0):
            max_transcription_time = max(self.transcription_times[-5:])
            if max_transcription_time > self.min_refresh_secs:
                logging.warning(f'Mic transcription took {round(max_transcription_time,3)} to process. To improve performance, try setting `Speech-to-Text`->`Refresh Frequency` to a value slightly higher than {round(max_transcription_time,3)} in the Mantella UI')

        if self.proactive_mic_mode:
            logging.log(self.loglevel, f'Interim transcription: {transcription}')
        
        # Only update the transcription if it contains a value, otherwise keep the existing transcription
        if transcription:
            return transcription
        else:
            self._consecutive_empty_count += 1
            return self._current_transcription


    @utils.time_it
    def whisper_transcribe(self, audio: np.ndarray, prompt: str):
        if self.transcribe_model: # local model
            segments, _ = self.transcribe_model.transcribe(audio, task=self.task, language=self.language, beam_size=5, vad_filter=False, initial_prompt=prompt)
            result_text = ' '.join(segment.text for segment in segments)
            if utils.clean_text(result_text) in self.__ignore_list: # common phrases hallucinated by Whisper
                return ''
            return result_text
        
        # Server versions of Whisper require the audio data to be a file type
        audio_file = io.BytesIO()
        wavfile.write(audio_file, self.SAMPLING_RATE, audio)
        # Audio file needs a name or else Whisper gets angry
        audio_file.name = 'out.wav'
        # Log request payload characteristics (safe: no secrets or raw audio)
        try:
            audio_size_bytes = audio_file.getbuffer().nbytes
        except Exception:
            audio_size_bytes = -1

        if 'openai' in self.whisper_url: # OpenAI compatible endpoint
            logging.log(self.loglevel, f"STT request → OpenAI-compatible endpoint: url={self.whisper_url}, service={self.whisper_service}, model={self.whisper_model}, language={self.language}, prompt_len={len(prompt)}, audio_bytes={audio_size_bytes}, filename={getattr(audio_file, 'name', 'out.wav')}")
            client = self.__generate_sync_client()
            try:
                response_data = client.audio.transcriptions.create(model=self.whisper_model, language=self.language, file=audio_file, prompt=prompt)
            except Exception as e:
                utils.play_error_sound()
                if e.code in [404, 'model_not_found']:
                    if self.whisper_service == 'OpenAI':
                        logging.error(f"Selected Whisper model '{self.whisper_model}' does not exist in the OpenAI service. Try changing 'Speech-to-Text'->'Model Size' to 'whisper-1' in the Mantella UI")
                    elif self.whisper_service == 'Groq':
                        logging.error(f"Selected Whisper model '{self.whisper_model}' does not exist in the Groq service. Try changing 'Speech-to-Text'->'Model Size' to one of the following models in the Mantella UI: https://console.groq.com/docs/speech-text#supported-models")
                    else:
                        logging.error(f"Selected Whisper model '{self.whisper_model}' does not exist in the selected service {self.whisper_service}. Try changing 'Speech-to-Text'->'Model Size' to a compatible model in the Mantella UI")
                else:
                    logging.error(f'STT error: {e}')
                input("Press Enter to exit.")
            client.close()
            if utils.clean_text(response_data.text) in self.__ignore_list: # common phrases hallucinated by Whisper
                return ''
            return response_data.text.strip()
        else: # custom server model
            logging.log(self.loglevel, f"STT request → custom endpoint: method=POST url={self.whisper_url}, model={self.whisper_model}, language={self.language}, prompt_len={len(prompt)}, file=('audio.wav', bytes={audio_size_bytes}, content_type='audio/wav')")
            data = {'model': self.whisper_model, 'prompt': prompt}
            files = {'file': ('audio.wav', audio_file, 'audio/wav')}
            response = requests.post(self.whisper_url, files=files, data=data)
            if response.status_code != 200:
                logging.error(f'STT Error: {response.content}')
            response_data = json.loads(response.text)
            if 'text' in response_data:
                if utils.clean_text(response_data['text']) in self.__ignore_list: # common phrases hallucinated by Whisper
                    return ''
                return response_data['text'].strip()
            

    @utils.time_it
    def moonshine_transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio using Moonshine model"""
        tokens = self.transcribe_model.generate(audio[np.newaxis, :].astype(np.float32))
        text = self.tokenizer.decode_batch(tokens)[0]
        text = self.ensure_sentence_ending(text)
        
        return text
    

    def ensure_sentence_ending(self, text: str) -> str:
        '''Moonshine transcriptions tend to be missing sentence-ending characters, which can confuse LLMs'''
        if not text:  # Handle empty string
            return text
        
        end_chars = {'.', '?', '!', ':', ';', '。'}
        
        if text[-1] == ',':
            return text[:-1] + '.'
        elif text[-1] not in end_chars:
            return text + '.'
        
        return text


    @utils.time_it
    def start_listening(self, prompt: str = '') -> None:
        '''Start background listening thread'''
        if self._running:
            return
            
        self._running = True
        self._reset_state()
        self.prompt = prompt
        
        # Start audio stream
        self._stream = InputStream(
            samplerate=self.SAMPLING_RATE,
            channels=1,
            blocksize=self.CHUNK_SIZE,
            dtype=np.float32,
            callback=self._create_input_callback(self._audio_queue),
            latency = 'low'
        )
        self._stream.start()
        
        # Start processing thread
        self._processing_thread = threading.Thread(
            target=self._process_audio,
            daemon = True
        )
        self._processing_thread.start()
        logging.log(self.loglevel, 'Listening...')


    def _process_audio(self) -> None:
        """Process audio data in a separate thread."""
        lookback_size = self.LOOKBACK_CHUNKS * self.CHUNK_SIZE
        chunk_count = 0
        
        while self._running:
            try:
                # Get audio chunk and status from queue
                chunk, status = self._audio_queue.get(timeout=0.1)
                if status:
                    if self.__processing_audio_error_count % self.__warning_frequency == 0:
                        logging.log(23, f"STT WARNING: Processing audio error: {status}")
                    self.__processing_audio_error_count += 1
                    continue

                with self._lock:
                    # Update audio buffer
                    self._audio_buffer = np.concatenate((self._audio_buffer, chunk))
                    if not self._speech_detected:
                        # Keep limited lookback buffer when not recording
                        self._audio_buffer = self._audio_buffer[-lookback_size:]
                    
                    # Process with VAD
                    speech_dict = self.vad_iterator(chunk)
                    
                    # Handle speech detection
                    if speech_dict:
                        if "start" in speech_dict and not self._speech_detected:
                            logging.log(self.loglevel, 'Speech detected')
                            self._speech_detected = True
                            self._speech_start_time = time.time()
                            self._last_update_time = time.time()
                        
                        if "end" in speech_dict and self._speech_detected:
                            logging.log(self.loglevel, 'Speech ended')
                            # If proactive mode is disabled, transcribe mic input only when speech end has been detected
                            if not self.proactive_mic_mode:
                                self._current_transcription = self._transcribe(self._audio_buffer)
                            if self.__save_mic_input:
                                self._save_audio(self._audio_buffer)

                            self._transcription_ready.set()
                            self._reset_state()
                    
                    # Update transcription periodically during speech
                    elif self._speech_detected:
                        chunk_count += 1
                        
                        # Check for maximum speech duration
                        if (len(self._audio_buffer) / self.SAMPLING_RATE) > self.listen_timeout:
                            logging.warning(f'Listen timeout of {self.listen_timeout} seconds reached. Processing mic input...')
                            self._current_transcription = self._transcribe(self._audio_buffer)
                            self._transcription_ready.set()

                            self._reset_state()
                            self._soft_reset_vad()
                        # Regular update during speech
                        elif (self.proactive_mic_mode) and (chunk_count >= self.refresh_freq):
                            logging.debug(f'Transcribing {self.min_refresh_secs} of mic input...')
                            self._current_transcription = self._transcribe(self._audio_buffer)

                            if self._consecutive_empty_count >= self._max_consecutive_empty:
                                logging.warning(f'Could not transcribe input')
                                self._transcription_ready.set()
                                self._reset_state()
                                self._soft_reset_vad()

                            chunk_count = 0  # Reset counter
            
            except queue.Empty:
                logging.debug('Queue is empty')
                continue
            except Exception as e:
                if self.__mic_input_process_error_count % self.__warning_frequency == 0:
                    logging.log(23, f'STT WARNING: Error processing mic input: {str(e)}')
                self.__mic_input_process_error_count += 1
                self._reset_state()
                time.sleep(0.1)


    def _create_vad_iterator(self) -> VADIterator:
        """Create a new VAD iterator with configured parameters."""
        return VADIterator(
            model=self.vad_model,
            sampling_rate=self.SAMPLING_RATE,
            threshold=self.audio_threshold,
            min_silence_duration_ms=int(self.pause_threshold * 1000),
            speech_pad_ms = 30 # default
        )


    def _create_input_callback(self, q: queue.Queue):
        """Create callback for audio input stream."""
        def input_callback(indata, frames, time, status):
            if status:
                if self.__audio_input_error_count % self.__warning_frequency == 0:
                    logging.log(23, f"STT WARNING: Audio input error: {status}")
                self.__audio_input_error_count += 1
            # Store both data and status in queue
            q.put((indata.copy().flatten(), status))
        return input_callback


    def _soft_reset_vad(self) -> None:
        """Soft reset VAD iterator without affecting model state."""
        self.vad_iterator.triggered = False
        self.vad_iterator.temp_end = 0
        self.vad_iterator.current_sample = 0


    def _reset_state(self) -> None:
        """Reset internal state."""
        self._speech_detected = False
        self._audio_buffer = np.array([], dtype=np.float32)
        self.vad_iterator = self._create_vad_iterator()
        self._consecutive_empty_count = 0


    @utils.time_it
    def _save_audio(self, audio: np.ndarray) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = os.path.join(self.__mic_input_path, f'mic_input_{timestamp}.wav')
        with wave.open(audio_path, 'wb') as wf:
            wf.setnchannels(1)  # Mono audio
            wf.setsampwidth(2)  # 16-bit audio
            wf.setframerate(self.SAMPLING_RATE)
            # Convert float32 to int16
            audio_int16 = (audio * 32767).astype(np.int16)
            wf.writeframes(audio_int16.tobytes())


    @utils.time_it
    def hot_swap_settings(self, new_config: ConfigLoader) -> bool:
        """Apply updated STT settings without rebuilding the model when possible.

        Returns True if applied in place; False if a full reinit is required.
        """
        try:
            heavy_change = False

            # Service switch requires rebuild
            if getattr(new_config, 'stt_service', self.stt_service) != self.stt_service:
                heavy_change = True

            # Whisper-specific rebuild conditions
            if self.stt_service == 'whisper' or getattr(new_config, 'stt_service', self.stt_service) == 'whisper':
                if getattr(new_config, 'whisper_model', self.whisper_model) != self.whisper_model:
                    heavy_change = True
                if getattr(new_config, 'whisper_process_device', self.process_device) != self.process_device:
                    heavy_change = True
                if getattr(new_config, 'external_whisper_service', self.external_whisper_service) != self.external_whisper_service:
                    heavy_change = True
                new_endpoint = self.__get_endpoint(getattr(new_config, 'whisper_url', self.whisper_url))
                if new_endpoint != self.whisper_url:
                    heavy_change = True

            # Moonshine-specific rebuild conditions
            if self.stt_service == 'moonshine' or getattr(new_config, 'stt_service', self.stt_service) == 'moonshine':
                if getattr(new_config, 'moonshine_model', self.full_moonshine_model) != self.full_moonshine_model:
                    heavy_change = True
                if getattr(new_config, 'moonshine_folder', self.moonshine_folder) != self.moonshine_folder:
                    heavy_change = True

            if heavy_change:
                return False

            # In-place updates with synchronization
            with self._lock:
                self.language = new_config.stt_language
                self.task = "translate" if new_config.stt_translate else "transcribe"

                self.listen_timeout = new_config.listen_timeout
                self.proactive_mic_mode = new_config.proactive_mic_mode
                self.min_refresh_secs = new_config.min_refresh_secs
                self.refresh_freq = self.min_refresh_secs // self.CHUNK_DURATION
                self.play_cough_sound = new_config.play_cough_sound

                # VAD thresholds
                vad_threshold_changed = (self.audio_threshold != new_config.audio_threshold) or (self.pause_threshold != new_config.pause_threshold)
                self.audio_threshold = new_config.audio_threshold
                self.pause_threshold = new_config.pause_threshold

                # Update service URL mapping
                self.whisper_service = new_config.whisper_url
                self.whisper_url = self.__get_endpoint(new_config.whisper_url)

                # Save mic input path
                self.__save_mic_input = new_config.save_mic_input
                if self.__save_mic_input:
                    self.__mic_input_path = new_config.save_folder+'data\\tmp\\mic'
                    os.makedirs(self.__mic_input_path, exist_ok=True)

                if vad_threshold_changed:
                    self.vad_iterator = self._create_vad_iterator()
                else:
                    self._soft_reset_vad()

            # Refresh API key/client if using external service
            if self.external_whisper_service:
                try:
                    self.__api_key = self.__get_api_key()
                    self.__initial_client = None
                    if (self.stt_service == 'whisper') and (self.__api_key) and ('openai' in self.whisper_url):
                        self.__initial_client = self.__generate_sync_client()
                except Exception as e:
                    logging.warning(f"Failed to update STT API key during hot-swap: {e}")

            logging.info("Applied STT hot-swap settings in place.")
            return True
        except Exception as e:
            logging.error(f"STT hot-swap failed: {e}")
            return False


    @utils.time_it
    def get_latest_transcription(self) -> str:
        """Get the latest transcription, blocking until speech ends."""
        while True:
            self._transcription_ready.wait()
            with self._lock:
                transcription = self._current_transcription
                self._current_transcription = ''
                if transcription:
                    self._transcription_ready.clear()
                    self._speech_detected = False
                    logging.log(self.loglevel, f"Player said '{transcription.strip()}'")
                    return transcription
                
            if self.play_cough_sound:
                utils.play_no_mic_input_detected_sound()
            logging.warning('Could not detect speech from mic input')

            self._transcription_ready.clear()
            self._speech_detected = False
            self._current_transcription = ''

            time.sleep(0.1)


    def stop_listening(self) -> None:
        """Stop listening for speech."""
        if not self._running:
            return
            
        self._running = False
        self._speech_detected = False
        
        # Stop and clean up audio stream
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
        # Wait for processing thread to finish
        if self._processing_thread:
            self._processing_thread.join()  # timeout=1.0 Add timeout to prevent hanging
            self._processing_thread = None
        
        # Clear queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
                
        self._reset_state()
        logging.log(self.loglevel, 'Stopped listening for mic input')


    @staticmethod
    @utils.time_it
    def activation_name_exists(transcript: str, activation_names: str | list[str]) -> bool:
        """Identifies keyword in the input transcript"""
        if not transcript:
            return False
        
        # Convert to a list even if there is only one activation name
        if isinstance(activation_names, str):
            activation_names = [activation_names]

        # Check for a match among individual words in the transcript
        transcript_words = transcript.split()
        if set(transcript_words).intersection(activation_names):
            return True
        
        # Alternatively, if the entire transcript is a keyword, return True
        for activation_name in activation_names:
            if transcript == activation_name:
                return True
        
        return False


    @staticmethod
    @utils.time_it
    def _remove_activation_word(transcript, activation_name):
        transcript = transcript.replace(activation_name, '')
        return transcript