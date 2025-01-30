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
import base64
from openai import OpenAI
import uuid
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import queue
import threading
import time
import os
import wave
from moonshine_onnx import MoonshineOnnxModel, load_tokenizer
import onnxruntime as ort
from numpy.typing import NDArray

from sounddevice import InputStream
from silero_vad import VADIterator, load_silero_vad

class Transcriber:
    """Handles real-time speech-to-text transcription using Moonshine."""
    
    SAMPLING_RATE = 16000
    CHUNK_SIZE = 512  # Required chunk size for Silero VAD
    LOOKBACK_CHUNKS = 5  # Number of chunks to keep in buffer when not recording
    VAD_THRESHOLD = 0.4
    SILENCE_DURATION = 0.5  # Duration of silence to mark end of speech
    MIN_REFRESH_SECS = 0.25  # Minimum time between transcription updates
    MAX_SPEECH_SECS = 15  # Maximum duration for a single speech segment
    
    def __init__(self, model_name: str = "moonshine/tiny"):
        """Initialize the transcriber with specified model."""
        logging.basicConfig(
            level=logging.DEBUG,  # Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            format='%(asctime)s - %(levelname)s - %(message)s',  # Log message format
        )
        
        # Initialize Moonshine model and tokenizer
        self.model = MoonshineOnnxModel(model_name=model_name)
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
        self._last_update_time = 0
        self.speech_end_time = 0
        self._current_transcription = ""
        self._transcription_ready = threading.Event()
        
        # Warm up the model
        self._transcribe(np.zeros(self.SAMPLING_RATE, dtype=np.float32))

    def _create_vad_iterator(self) -> VADIterator:
        """Create a new VAD iterator with configured parameters."""
        return VADIterator(
            model=self.vad_model,
            sampling_rate=self.SAMPLING_RATE,
            threshold=self.VAD_THRESHOLD,
            min_silence_duration_ms=int(self.SILENCE_DURATION * 1000),
            speech_pad_ms = 30 # default
        )

    def _create_input_callback(self, q: queue.Queue):
        """Create callback for audio input stream."""
        def input_callback(indata, frames, time, status):
            if status:
                logging.error(f"Audio input error: {status}")
            # Store both data and status in queue, following demo pattern
            q.put((indata.copy().flatten(), status))
        return input_callback

    def _soft_reset_vad(self) -> None:
        """Soft reset VAD iterator without affecting model state."""
        self.vad_iterator.triggered = False
        self.vad_iterator.temp_end = 0
        self.vad_iterator.current_sample = 0

    def _process_audio(self) -> None:
        """Process audio data in a separate thread."""
        lookback_size = self.LOOKBACK_CHUNKS * self.CHUNK_SIZE
        
        while self._running:
            try:
                # Get audio chunk and status from queue
                chunk, status = self._audio_queue.get(timeout=0.1)
                if status:
                    logging.error(f"Processing audio error: {status}")
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
                            logging.debug('Speech detected')
                            self._speech_detected = True
                            self._speech_start_time = time.time()
                            self._last_update_time = time.time()
                        
                        if "end" in speech_dict and self._speech_detected:
                            logging.debug('Speech ended')
                            self.speech_end_time = time.time()
                            # Finalize transcription
                            self._current_transcription = self._transcribe(self._audio_buffer)
                            self._transcription_ready.set()

                            self._reset_state()
                    
                    # Update transcription periodically during speech
                    elif self._speech_detected:
                        current_time = time.time()
                        
                        # Check for maximum speech duration
                        if (len(self._audio_buffer) / self.SAMPLING_RATE) > self.MAX_SPEECH_SECS:
                            logging.debug('Max speech time reached')
                            self._current_transcription = self._transcribe(self._audio_buffer)
                            self._transcription_ready.set()

                            self._reset_state()
                            self._soft_reset_vad()
                        # Regular update during speech
                        elif current_time - self._last_update_time >= self.MIN_REFRESH_SECS:
                            logging.debug('Refreshing transcribe...')
                            self._current_transcription = self._transcribe(self._audio_buffer)

                            self._last_update_time = current_time
            
            except queue.Empty:
                logging.debug('Queue is empty')
                continue
            except Exception as e:
                logging.error(f"Error processing audio: {e}")
                self._reset_state()
                time.sleep(0.1)

    def _transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio using Moonshine model."""
        # Ensure audio is at least 1 second (SAMPLING_RATE samples)
        if len(audio) < self.SAMPLING_RATE:
            audio = np.pad(audio, (0, self.SAMPLING_RATE - len(audio)))
        
        tokens = self.model.generate(audio[np.newaxis, :].astype(np.float32))
        return self.tokenizer.decode_batch(tokens)[0]

    def _reset_state(self) -> None:
        """Reset internal state."""
        self._audio_buffer = np.array([], dtype=np.float32)
        self.vad_iterator = self._create_vad_iterator()

    def start_listening(self) -> None:
        """Start listening for speech."""
        if self._running:
            return
            
        self._running = True
        self._reset_state()
        
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
        self._processing_thread = threading.Thread(target=self._process_audio)
        self._processing_thread.daemon = True  # Allow program to exit if thread is running
        self._processing_thread.start()
        logging.debug('Listening...')

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
        logging.debug('Stopped listening')

    @property
    def has_speech_started(self) -> bool:
        """Check if speech has been detected."""
        with self._lock:
            return self._speech_detected

    def get_latest_transcription(self) -> str:
        """Get the latest transcription, blocking until speech ends."""
        while True:
            self._transcription_ready.wait()
            with self._lock:
                transcription = self._current_transcription
                if transcription:
                    self._transcription_ready.clear()
                    logging.info(f'Got speech in {time.time() - self.speech_end_time} seconds')
                    return transcription
                
            logging.warning('No speech detected. Retrying...')

            self._transcription_ready.clear()
            self._speech_detected = False

            time.sleep(0.1)