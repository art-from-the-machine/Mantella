import sys
from faster_whisper import WhisperModel
import speech_recognition as sr
import logging
from typing import Any, Hashable
import regex
from collections import deque
from src.config.config_loader import ConfigLoader
import src.utils as utils
import requests
import json
import io
import os
import time
import random
from threading import Thread
from filelock import FileLock
from src.llm.openai_client import openai_client
from src.conversation.conversation_log import conversation_log  # Import conversation management module
from pathlib import Path

class Transcriber:
    def __init__(self, config: ConfigLoader, secret_key_file: str):
        self.loglevel = 27
        self.language = config.stt_language
        self.task = "transcribe"
        if config.stt_translate == 1:
            self.task = "translate"  # Translate to English
        self.model = config.whisper_model
        self.process_device = config.whisper_process_device
        self.audio_threshold = config.audio_threshold
        self.listen_timeout = config.listen_timeout
        self.whisper_type = config.whisper_type
        self.whisper_url = config.whisper_url

        self.end_conversation_keyword = config.end_conversation_keyword
        self.radiant_start_prompt = config.radiant_start_prompt
        self.radiant_end_prompt = config.radiant_end_prompt
        
        self.call_count = 0
        self.__secret_key_file = secret_key_file
        self.__api_key: str | None = None
        self.__ignore_list = ['', 'thank you', 'thank you for watching', 'thanks for watching', 'the transcript is from the', 'the', 'thank you very much', "thank you for watching and i'll see you in the next video", "we'll see you in the next video", 'see you next time']

        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = config.pause_threshold
        self.microphone = sr.Microphone()

        if self.audio_threshold == 'auto':
            logging.log(self.loglevel, "Audio threshold set to 'auto'. Adjusting microphone for ambient noise...")
            logging.log(self.loglevel, "If the mic is not picking up your voice, try setting this audio_threshold value manually in MantellaSoftware/config.ini.\n")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=5)
        else:
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.energy_threshold = int(self.audio_threshold)
            logging.log(self.loglevel, f"Audio threshold set to {self.audio_threshold}. If the mic is not picking up your voice, try lowering this value in MantellaSoftware/config.ini. If the mic is picking up too much background noise, try increasing this value.\n")

        if self.whisper_type == 'faster_whisper':
            if self.process_device == 'cuda':
                self.transcribe_model = WhisperModel(self.model, device=self.process_device)
            else:
                self.transcribe_model = WhisperModel(self.model, device=self.process_device, compute_type="float32")

    def __get_api_key(self) -> str:
        if not self.__api_key:
            try:  # First check mod folder for secret key
                mod_parent_folder = str(Path(utils.resolve_path()).parent.parent.parent)
                with open(mod_parent_folder + '\\' + self.__secret_key_file, 'r') as f:
                    self.__api_key: str = f.readline().strip()
            except:  # Check locally (same folder as exe) for secret key
                with open(self.__secret_key_file, 'r') as f:
                    self.__api_key: str = f.readline().strip()

            if not self.__api_key:
                logging.error(f'''No secret key found in GPT_SECRET_KEY.txt. Please create a secret key and paste it in your Mantella mod folder's GPT_SECRET_KEY.txt file.
If you are using OpenRouter (default), you can create a secret key in Account -> Keys once you have created an account: https://openrouter.ai/
If using OpenAI, see here on how to create a secret key: https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key
If you are running a model locally, please ensure the service (Kobold / Text generation web UI) is running.''')
                input("Press Enter to continue.")
                sys.exit(0)
        return self.__api_key

    def recognize_input(self, prompt: str):
        """
        Recognize input from mic or simulate it and return transcript if activation tag (assistant name) exists.
        """
        # Import GlobalManager inside the method to avoid circular import
        from src.http.routes.global_manager import GlobalManager  # Import the global manager

        # Access the GameStateManager via the GlobalManager
        game_manager = GlobalManager.get_instance()  # Get the GameStateManager instance
        

        while True:
            logging.log(self.loglevel, 'Listening...')

            # Fetch thought_input inside the loop to check for new input dynamically
            thought_input = game_manager.get_thought_input()

            if thought_input:
                # Use the input thought and clear the variable
                transcript = self.simulate_recognize_input(thought_input)
                if transcript:  # Only clear if the thought was processed successfully
                    game_manager.clean_thought_input()  # Clear after use
                    logging.info("Cleared after using the input thought command.")
                cleaned = transcript
            else:
                # Otherwise, capture the input from the microphone
                transcript = self._recognize_speech_from_mic(prompt)
                cleaned = utils.clean_text(transcript)

            if transcript is None:
                continue

            transcript_cleaned = cleaned

            # Check and continue if the cleaned input is in the ignore list
            if transcript_cleaned in self.__ignore_list:
                continue

            return transcript_cleaned

    def simulate_recognize_input(self, command: str):
        """
        Simulate recognizing input without using the microphone.
        This method mimics _recognize_speech_from_mic but uses injected text instead.
        """
        logging.log(self.loglevel, f"Simulating injected input: {command}")
        transcript_cleaned = utils.clean_text_thoughts(command)

        if transcript_cleaned in self.__ignore_list:
            logging.warning(f"Ignoring injected input: {command}")
            return None

        return transcript_cleaned

    def _recognize_speech_from_mic(self, prompt: str):
        """
        Capture the words from the recorded audio (audio stream --> free text).
        Transcribe speech from recorded from microphone.
        """
        @utils.time_it
        def whisper_transcribe(audio, prompt: str):
            if self.whisper_type == 'faster_whisper':
                segments, info = self.transcribe_model.transcribe(audio, task=self.task, language=self.language, beam_size=5, vad_filter=True, initial_prompt=prompt)
                result_text = ' '.join(segment.text for segment in segments)
                return result_text
            else:
                url = self.whisper_url
                headers = {"Authorization": f"Bearer {self.__get_api_key()}"}
                data = {'model': self.model, 'prompt': prompt}
                files = {'file': ('audio.wav', audio, 'audio/wav')}
                response = requests.post(url, headers=headers, files=files, data=data)
                response_data = json.loads(response.text)
                if 'text' in response_data:
                    return response_data['text'].strip()

        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=self.listen_timeout)
            except sr.WaitTimeoutError:
                return ''
        
        audio_data = audio.get_wav_data(convert_rate=16000)
        audio_file = io.BytesIO(audio_data)
        transcript = whisper_transcribe(audio_file, prompt)
        logging.log(self.loglevel, transcript)

        return transcript

    @staticmethod
    def activation_name_exists(transcript_cleaned, activation_name):
        """Identify the keyword in the input transcript."""

        keyword_found = False
        if transcript_cleaned:
            transcript_words = transcript_cleaned.split()
            if bool(set(transcript_words).intersection([activation_name])):
                keyword_found = True
            elif transcript_cleaned == activation_name:
                keyword_found = True

        return keyword_found

    @staticmethod
    def _remove_activation_word(transcript, activation_name):
        transcript = transcript.replace(activation_name, '')
        return transcript
