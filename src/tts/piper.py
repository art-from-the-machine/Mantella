from src.config.config_loader import ConfigLoader
from src.tts.ttsable import ttsable
import logging
import subprocess
import os
import time
import wave
from src import utils

import sys
from threading import Thread
from queue import Queue, Empty

# https://stackoverflow.com/a/4896288/25532567
ON_POSIX = 'posix' in sys.builtin_module_names

def enqueue_output(out, queue, stop_flag):
    for line in iter(out.readline, b''):
        queue.put(line)
        if stop_flag():
            break
    out.close()

class TTSServiceFailure(Exception):
    pass

class piper(ttsable):
    """Piper TTS handler
    """
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__(config)
        self.__piper_path = config.piper_path

        logging.log(self._loglevel, f'Connecting to Piper...')
        self._check_if_piper_is_running()


    @utils.time_it
    def tts_synthesize(self, voiceline, final_voiceline_file, aggro):
        if len(voiceline) > 3:
            while True:
                self.process.stdin.write(f"synthesize {voiceline}\n")
                self.process.stdin.flush()
                max_wait_time = 5
                start_time = time.time()

                while time.time() - start_time < max_wait_time:
                    exit_code = self.process.poll()
                    if exit_code is not None and exit_code != 0:
                        logging.error(f"Piper process has crashed with exit code: {exit_code}")
                        self._run_piper()
                        self.change_voice(self._last_voice)
                        break
                    elif os.path.exists(final_voiceline_file):
                        try: # don't just check if .wav exists, check if it has contents
                            with wave.open(final_voiceline_file, 'rb') as wav_file:
                                frames = wav_file.getnframes()
                                rate = wav_file.getframerate()
                                duration = frames / float(rate)
                                logging.info(f'"{voiceline}" is {duration} seconds long')
                                if duration > 0:
                                    return
                        except:
                            pass
                    time.sleep(0.01)

                logging.warning(f'Synthesis timed out for voiceline "{voiceline.strip()}". Restarting Piper...')
                self._restart_piper()
                self.change_voice(self._last_voice)


    def change_voice(self, voice: str, in_game_voice: str | None = None, csv_in_game_voice: str | None = None, advanced_voice_model: str | None = None, voice_accent: str | None = None):
        while True:
            logging.log(self._loglevel, 'Loading voice model...')

            voice_cleaned = f"{voice.lower().replace(' ', '')}"

            model_path = self.__piper_path + f'/models/skyrim/low/{voice_cleaned}.onnx' # TODO: change /skyrim and /low parts of the path to dynamic variables
            self.process.stdin.write(f"load_model {model_path}\n")
            self.process.stdin.flush()
            max_wait_time = 5
            start_time = time.time()

            while time.time() - start_time < max_wait_time:
                exit_code = self.process.poll()
                if exit_code is not None and exit_code != 0:
                    logging.error(f"Piper process has crashed with exit code: {exit_code}")
                    self._run_piper()
                    break
                
                try:  
                    line = self.q.get_nowait() # or q.get(timeout=.1)
                    if "Model loaded" in line:
                        self._last_voice = voice
                        return
                except Empty:
                    pass
                time.sleep(0.01)

            logging.warning(f'Voice model loading timed out for "{voice}". Restarting Piper...')
            self._restart_piper()


    def _check_if_piper_is_running(self):
        self._run_piper()
        

    def _run_piper(self):
        try:
            command = f'{self.__piper_path}\\piper.exe'

            self.process = subprocess.Popen(command, cwd=self._voiceline_folder, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1, close_fds=ON_POSIX)

            self.q = Queue()
            self.stop_thread = False
            self.t = Thread(target=enqueue_output, args=(self.process.stdout, self.q, lambda: self.stop_thread))
            self.t.daemon = True # thread dies with the program
            self.t.start()
        
        except Exception as e:
            logging.error(f'Could not run Piper. Ensure that the path "{self.__piper_path}" is correct. Error: {e}')
            raise TTSServiceFailure()


    def _restart_piper(self):
        if self.process:
            self.process.terminate()

        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

        if hasattr(self, 'q'):
            with self.q.mutex:
                self.q.queue.clear()

        if hasattr(self, 't') and self.t.is_alive():
            self.stop_thread = True
            self.t.join(timeout=5)
            self.stop_thread = False

        self._run_piper()