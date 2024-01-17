from faster_whisper import WhisperModel
import speech_recognition as sr
import logging
import src.utils as utils
import requests
import json
import openai

class Transcriber:
    def __init__(self, game_state_manager, config):
        self.game_state_manager = game_state_manager
        self.mic_enabled = config.mic_enabled
        self.language = config.stt_language
        self.task = "transcribe"
        if config.stt_translate == 1:
            # translate to English
            self.task = "translate"
        self.model = config.whisper_model
        self.process_device = config.whisper_process_device
        self.audio_threshold = config.audio_threshold
        self.listen_timeout = config.listen_timeout
        self.whisper_type = config.whisper_type
        self.whisper_url = config.whisper_url

        self.debug_mode = config.debug_mode
        self.debug_use_mic = config.debug_use_mic
        self.default_player_response = config.default_player_response
        self.debug_exit_on_first_exchange = config.debug_exit_on_first_exchange
        self.end_conversation_keyword = config.end_conversation_keyword
        self.radiant_start_prompt = config.radiant_start_prompt
        self.radiant_end_prompt = config.radiant_end_prompt

        self.call_count = 0

        if self.mic_enabled == '1':
            self.recognizer = sr.Recognizer()
            self.recognizer.pause_threshold = config.pause_threshold
            self.microphone = sr.Microphone()

            if self.audio_threshold == 'auto':
                logging.info(f"Audio threshold set to 'auto'. Adjusting microphone for ambient noise...")
                logging.info("If the mic is not picking up your voice, try setting this audio_threshold value manually in MantellaSoftware/config.ini.\n")
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=5)
            else:
                self.recognizer.dynamic_energy_threshold = False
                self.recognizer.energy_threshold = int(self.audio_threshold)
                logging.info(f"Audio threshold set to {self.audio_threshold}. If the mic is not picking up your voice, try lowering this value in MantellaSoftware/config.ini. If the mic is picking up too much background noise, try increasing this value.\n")

            # if using faster_whisper, load model selected by player, otherwise skip this step
            if self.whisper_type == 'faster_whisper':
                if self.process_device == 'cuda':
                    self.transcribe_model = WhisperModel(self.model, device=self.process_device)
                else:
                    self.transcribe_model = WhisperModel(self.model, device=self.process_device, compute_type="float32")


    def get_player_response(self, say_goodbye, radiant_dialogue="false"):
        if radiant_dialogue == "true":
            if self.call_count < 1:
                logging.info('Running radiant dialogue')
                transcribed_text = f'*{self.radiant_start_prompt}*'
                self.call_count += 1
            elif self.call_count <= 1:
                logging.info('Ending radiant dialogue')
                transcribed_text = f'*{self.radiant_end_prompt}*'
                self.call_count += 1
            else:
                logging.info('Radiant dialogue ended')
                transcribed_text = self.end_conversation_keyword
                self.call_count = 0
        elif (self.debug_mode == '1') & (self.debug_use_mic == '0'):
            transcribed_text = self.default_player_response
        else:
            if self.mic_enabled == '1':
                # listen for response
                transcribed_text = self.recognize_input()
            else:
                # text input through console
                if (self.debug_mode == '1') & (self.debug_use_mic == '1'):
                    transcribed_text = input('\nWrite player\'s response: ')
                    logging.info(f'Player wrote: {transcribed_text}')
                # await text input from the game
                else:
                    self.game_state_manager.write_game_info('_mantella_text_input', '')
                    self.game_state_manager.write_game_info('_mantella_text_input_enabled', 'True')
                    transcribed_text = self.game_state_manager.load_data_when_available('_mantella_text_input', '')
                    self.game_state_manager.write_game_info('_mantella_text_input', '')
                    self.game_state_manager.write_game_info('_mantella_text_input_enabled', 'False')

        if (self.debug_mode == '1') & (self.debug_exit_on_first_exchange == '1'):
            if say_goodbye:
                transcribed_text = self.end_conversation_keyword
            else:
                say_goodbye = True
        
        return transcribed_text, say_goodbye


    def recognize_input(self):
        """
        Recognize input from mic and return transcript if activation tag (assistant name) exist
        """
        while True:
            self.game_state_manager.write_game_info('_mantella_status', 'Listening...')
            logging.info('Listening...')
            transcript = self._recognize_speech_from_mic()
            transcript_cleaned = utils.clean_text(transcript)

            conversation_ended = self.game_state_manager.load_data_when_available('_mantella_end_conversation', '')
            if conversation_ended.lower() == 'true':
                return 'goodbye'

            # common phrases hallucinated by Whisper
            if transcript_cleaned in ['', 'thank you', 'thank you for watching', 'thanks for watching', 'the transcript is from the', 'the', 'thank you very much']:
                continue

            self.game_state_manager.write_game_info('_mantella_status', 'Thinking...')
            return transcript
    

    def _recognize_speech_from_mic(self):
        """
        Capture the words from the recorded audio (audio stream --> free text).
        Transcribe speech from recorded from `microphone`.
        """
        @utils.time_it
        def whisper_transcribe(audio):
            # if using faster_whisper (default) return based on faster_whisper's code, if not assume player wants to use server mode and send query to whisper_url set by player.
            if self.whisper_type == 'faster_whisper':
                segments, info = self.transcribe_model.transcribe(audio, task=self.task, language=self.language, beam_size=5, vad_filter=True)
                result_text = ' '.join(segment.text for segment in segments)

                return result_text
            # this code queries the whispercpp server set by the user to obtain the response, this format also allows use of official openai whisper API
            else:
                url = self.whisper_url
                if 'openai' in url:
                    headers = {"Authorization": f"Bearer {openai.api_key}",}
                else:
                    headers = {"Authorization": "Bearer apikey",}
                data = {'model': self.model}
                files = {'file': open(audio, 'rb')}
                response = requests.post(url, headers=headers, files=files, data=data)
                response_data = json.loads(response.text)
                if 'text' in response_data:
                    return response_data['text'].strip()

        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=self.listen_timeout)
            except sr.WaitTimeoutError:
                return ''

        audio_file = 'player_recording.wav'
        with open(audio_file, 'wb') as file:
            file.write(audio.get_wav_data(convert_rate=16000))
        
        transcript = whisper_transcribe(audio_file)
        logging.info(transcript)

        return transcript


    @staticmethod
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
    def _remove_activation_word(transcript, activation_name):
        transcript = transcript.replace(activation_name, '')
        return transcript