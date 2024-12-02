import sys
from faster_whisper import WhisperModel
import speech_recognition as sr
import logging
from src.config.config_loader import ConfigLoader
import src.utils as utils
import requests
import json
import io
from pathlib import Path
import base64
from openai import OpenAI
import uuid
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import queue
import threading
import time

@dataclass
class TranscriptionJob:
    id: str
    audio_data: sr.AudioData
    transcript: Optional[str] = None
    started_at: datetime = datetime.now()
    prompt: str = ''
    completed: bool = False

class TranscriptionQueue:
    """Thread-safe queue for managing transcriptions"""
    def __init__(self):
        self.queue = queue.Queue()
        self.is_more_to_come = True
    
    def put(self, capture: TranscriptionJob):
        self.queue.put(capture)
    
    def get(self, timeout: float = None) -> Optional[TranscriptionJob]:
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

class Transcriber:
    def __init__(self, config: ConfigLoader, stt_secret_key_file: str, secret_key_file: str):
        self.loglevel = 27
        # self.mic_enabled = config.mic_enabled
        self.language = config.stt_language
        self.task = "translate" if config.stt_translate == 1 else "transcribe"
        self.model = config.whisper_model
        self.process_device = config.whisper_process_device
        self.audio_threshold = int(config.audio_threshold)
        self.listen_timeout = config.listen_timeout
        self.external_whisper_service = config.external_whisper_service
        self.whisper_service = config.whisper_url
        self.whisper_url = self.__get_endpoint(config.whisper_url)
        self.pause_threshold = config.pause_threshold
        # heavy-handed fix to non_speaking_duration as it it always required to be less than pause_threshold
        self.non_speaking_duration = 0.5 if self.pause_threshold > 0.5 else self.pause_threshold - 0.01
        self.show_mic_warning = True

        self.end_conversation_keyword = config.end_conversation_keyword
        self.radiant_start_prompt = config.radiant_start_prompt
        self.radiant_end_prompt = config.radiant_end_prompt

        self.call_count = 0
        self.__stt_secret_key_file = stt_secret_key_file
        self.__secret_key_file = secret_key_file
        self.__api_key: str | None = self.__get_api_key()
        self.__initial_client: OpenAI | None = None
        if (self.__api_key) and ('openai' in self.whisper_url):
            self.__initial_client = self.__generate_sync_client() # initialize first client in advance to save time
        
        self.__ignore_list = ['', 'thank you', 'thank you for watching', 'thanks for watching', 'the transcript is from the', 'the', 'thank you very much', "thank you for watching and i'll see you in the next video", "we'll see you in the next video", 'see you next time']
        
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = self.pause_threshold
        self.recognizer.non_speaking_duration = self.non_speaking_duration
        self.microphone = sr.Microphone()

        if self.audio_threshold == 'auto':
            logging.log(self.loglevel, f"Audio threshold set to 'auto'. Adjusting microphone for ambient noise...")
            logging.log(self.loglevel, "If the mic is not picking up your voice, try setting this `Speech-to-Text`->`Audio Threshold` value manually in the Mantella UI\n")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=5)
        else:
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.energy_threshold = self.audio_threshold
            logging.log(self.loglevel, f"Audio threshold set to {self.audio_threshold}. If the mic is not picking up your voice, try lowering this `Speech-to-Text`->`Audio Threshold` value in the Mantella UI. If the mic is picking up too much background noise, try increasing this value.\n")

        self.transcribe_model: WhisperModel | None = None
        # if using faster_whisper, load model selected by player, otherwise skip this step
        if not self.external_whisper_service:
            if self.process_device == 'cuda':
                self.transcribe_model = WhisperModel(self.model, device=self.process_device)
            else:
                self.transcribe_model = WhisperModel(self.model, device=self.process_device, compute_type="float32")

        # Thread management
        self.__listen_thread: Optional[threading.Thread] = None
        self.__transcribe_thread: Optional[threading.Thread] = None
        self.__stop_listening = threading.Event()
        self.__stop_transcribing = threading.Event()
        self.__transcription_queue = TranscriptionQueue()
        self.__latest_capture: Optional[TranscriptionJob] = None
        self.__latest_capture_lock = threading.Lock()
        self._speech_started = threading.Event()

    @property
    def stopped_listening(self):
        return self.__stop_listening

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
    def whisper_transcribe(self, audio, prompt: str):
        if self.transcribe_model: # local model
            segments, info = self.transcribe_model.transcribe(audio, task=self.task, language=self.language, beam_size=5, vad_filter=True, initial_prompt=prompt)
            result_text = ' '.join(segment.text for segment in segments)
            return result_text
        elif 'openai' in self.whisper_url: # OpenAI compatible endpoint
            client = self.__generate_sync_client()
            try:
                response_data = client.audio.transcriptions.create(model=self.model, language=self.language, file=audio, prompt=prompt)
            except Exception as e:
                if e.code in [404, 'model_not_found']:
                    if self.whisper_service == 'OpenAI':
                        logging.error(f"Selected Whisper model '{self.model}' does not exist in the OpenAI service. Try changing 'Speech-to-Text'->'Model Size' to 'whisper-1' in the Mantella UI")
                    elif self.whisper_service == 'Groq':
                        logging.error(f"Selected Whisper model '{self.model}' does not exist in the Groq service. Try changing 'Speech-to-Text'->'Model Size' to one of the following models in the Mantella UI: https://console.groq.com/docs/speech-text#supported-models")
                    else:
                        logging.error(f"Selected Whisper model '{self.model}' does not exist in the selected service {self.whisper_service}. Try changing 'Speech-to-Text'->'Model Size' to a compatible model in the Mantella UI")
                else:
                    logging.error(f'STT error: {e}')
                input("Press Enter to exit.")
            client.close()
            return response_data.text.strip()
        else: # custom server model
            data = {'model': self.model, 'prompt': prompt}
            files = {'file': ('audio.wav', audio, 'audio/wav')}
            response = requests.post(self.whisper_url, files=files, data=data)
            if response.status_code != 200:
                logging.error(f'STT Error: {response.content}')
            response_data = json.loads(response.text)
            if 'text' in response_data:
                return response_data['text'].strip()


    @utils.time_it
    def start_listening(self, prompt: str = ''):
        '''Start background listening thread'''
        with self.__latest_capture_lock:
            if self.__listen_thread and self.__listen_thread.is_alive():
                return
            
            self._speech_started.clear()
            self.__stop_listening.clear()
            self.__stop_transcribing.clear()
            self.__transcription_queue.is_more_to_come = True
            
            # Start listening thread
            self.__listen_thread = threading.Thread(
                target=self.__background_listen,
                daemon=True,
                args=[prompt]
            )
            self.__listen_thread.start()
            
            # Start transcription thread
            self.__transcribe_thread = threading.Thread(
                target=self.__process_transcriptions,
                daemon=True
            )
            self.__transcribe_thread.start()
            
            logging.log(self.loglevel, 'Started speech recognition threads')
    
    
    @utils.time_it
    def __process_transcriptions(self):
        '''Transcribe captured mic inputs'''
        while not self.__stop_transcribing.is_set():
            try:
                # Get next capture from queue
                capture = self.__transcription_queue.get(timeout=0.5)
                if not capture:
                    time.sleep(0.01)
                    continue

                audio_data = capture.audio_data.get_wav_data(convert_rate=16_000)
                #transcript = base64.b64encode(audio_data).decode('utf-8')
                audio_file = io.BytesIO(audio_data)
                audio_file.name = 'out.wav'
                transcript = self.whisper_transcribe(audio_file, capture.prompt)

                transcript_cleaned = utils.clean_text(transcript)

                # common phrases hallucinated by Whisper
                if transcript_cleaned in self.__ignore_list:
                    transcript = None
                
                # Update capture with transcription
                capture.transcript = transcript
                capture.completed = True
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f'Error processing mic input: {str(e)}')
                time.sleep(0.1)
    

    @utils.time_it
    def __background_listen(self, prompt: str = '') -> str:
        '''Capture speech from mic input'''
        with self.microphone as source:
            while not self.__stop_listening.is_set():
                try:
                    if not self.__latest_capture: # if another mic input isn't already being processed
                        logging.log(self.loglevel, 'Listening...')
                        audio = self.recognizer.listen(source, timeout=self.listen_timeout)
                        self.__stop_listening.set()
                        logging.log(self.loglevel, 'Speech detected. Transcribing...')

                        capture = TranscriptionJob(
                            id=str(uuid.uuid4()),
                            audio_data=audio,
                            prompt=prompt,
                        )

                        # Store as latest capture
                        with self.__latest_capture_lock:
                            self.__latest_capture = capture
                        
                        # Add to transcription queue
                        self.__transcription_queue.put(capture)
                except sr.WaitTimeoutError:
                    if self.show_mic_warning:
                        logging.warning(f'No microphone input detected after {self.listen_timeout} seconds. Try lowering the `Speech-to-Text`->`Audio Threshold` value in the Mantella UI')
                        self.show_mic_warning = False
                    continue
                except Exception as e:
                    logging.error(f'Error in microphone input: {e}')
                    time.sleep(0.1)


    @utils.time_it
    def get_latest_transcription(self) -> Optional[str]:
        ''' Get the transcription of the most recent speech detection'''
        while True:
            with self.__latest_capture_lock:
                latest_capture = self.__latest_capture

            if latest_capture and latest_capture.completed:
                transcript = latest_capture.transcript
                
                with self.__latest_capture_lock:
                    self.__latest_capture = None
                
                if transcript:
                    logging.log(self.loglevel, f"Player said '{transcript}'")
                else:
                    logging.warning('Could not detect speech from mic input')
                    if self.__stop_listening:
                        self.start_listening()
                
                return transcript
            
            time.sleep(0.01)


    def has_player_spoken(self):
        return True if self.__latest_capture else False


    @staticmethod
    @utils.time_it
    def activation_name_exists(transcript_cleaned, activation_name):
        """Identifies keyword in the input transcript"""

        keyword_found = False
        if transcript_cleaned:
            transcript_words = transcript_cleaned.split()
            if bool(set(transcript_words).intersection([activation_name])):
                keyword_found = True
            elif transcript_cleaned == activation_name:
                keyword_found = True
        
        return keyword_found


    @staticmethod
    @utils.time_it
    def _remove_activation_word(transcript, activation_name):
        transcript = transcript.replace(activation_name, '')
        return transcript
    

    @utils.time_it
    def stop_listening(self):
        '''Stop background listening and transcription'''
        self.__stop_listening.set()
        self.__stop_transcribing.set()
        self.__transcription_queue.is_more_to_come = False
        
        if self.__listen_thread:
            self.__listen_thread.join()
            self.__listen_thread = None
            
        if self.__transcribe_thread:
            self.__transcribe_thread.join()
            self.__transcribe_thread = None
        
        logging.log(self.loglevel, 'Stopped speech recognition threads')