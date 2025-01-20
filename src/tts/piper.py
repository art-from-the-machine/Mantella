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
from src.tts.synthesization_options import SynthesizationOptions
from src.games.gameable import gameable

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
    @utils.time_it
    def __init__(self, config: ConfigLoader, game: gameable) -> None:
        super().__init__(config)
        self.__game: gameable = game
        self.__piper_path = config.piper_path
        self.__models_path = self.__piper_path + f'/models/{self.__game.game_name_in_filepath}/low/' # TODO: change /low parts of the path to dynamic variables
        self.__selected_voice = None
        self.__waiting_for_voice_load = False
        self._current_actor_gender = None
        self._current_actor_race = None

        logging.log(self._loglevel, f'Connecting to Piper...')
        self._check_if_piper_is_running()

        self.__available_models = self.get_available_models(self.__models_path)


    @utils.time_it
    def get_available_models(self, folder_path):
        try:
            models = [f.replace('.onnx','') for f in os.listdir(folder_path) if f.endswith('.onnx')]
            return models
        except FileNotFoundError:
            utils.play_error_sound()
            raise FileNotFoundError
        except PermissionError:
            utils.play_error_sound()
            raise PermissionError

    
    def __write_to_stdin(self, text):
        if self.process.stdin:
            self.process.stdin.write(text)
            self.process.stdin.flush()

    @utils.time_it
    def tts_synthesize(self, voiceline: str, final_voiceline_file: str, synth_options: SynthesizationOptions):
        if self.__waiting_for_voice_load:
            self._check_voice_changed()

        # Piper tends to overexaggerate sentences with exclamation marks, which works well for combat but not for casual conversation
        if not synth_options.aggro:
            voiceline = voiceline.replace('!','.')
        else:
            voiceline = voiceline.replace('.','!')
        voiceline = voiceline.replace('*','') # Drop *. Piper reads them aloud. "*She waves.*" -> "Asterisk She waves. Asterisk"

        attempts = 0
        while attempts < 3:
            self.__write_to_stdin(f"synthesize {voiceline}\n")
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
                            logging.debug(f'"{voiceline}" is {duration} seconds long')
                            if duration > 0:
                                return
                    except:
                        pass
                time.sleep(0.01)

            logging.warning(f'Synthesis timed out for voiceline "{voiceline.strip()}". Restarting Piper...')
            self._restart_piper()
            self.change_voice(self._last_voice)
            attempts += 1
    
    @utils.time_it
    def _check_voice_changed(self):
        while True:
            max_wait_time = 5
            start_time = time.time()

            while time.time() - start_time < max_wait_time:
                exit_code = self.process.poll()
                if exit_code is not None and exit_code != 0:
                    logging.error(f"Piper process has crashed with exit code: {exit_code}")
                    self.__waiting_for_voice_load = False
                    self._run_piper()
                    break
                
                try:  
                    line = self.q.get_nowait() # or q.get(timeout=.1)
                    if "Model loaded" in line:
                        logging.log(self._loglevel, f'Model {self.__selected_voice} loaded')
                        self.__waiting_for_voice_load = False
                        self._last_voice = self.__selected_voice
                        return
                except Empty:
                    pass
                time.sleep(0.01)

            logging.warning(f'Voice model loading timed out for "{self.__selected_voice}". Restarting Piper...')
            self.__waiting_for_voice_load = False
            self._restart_piper()
            self.change_voice(self.__selected_voice)

    @utils.time_it
    def _select_voice_type(self, voice: str, in_game_voice: str | None, csv_in_game_voice: str | None, advanced_voice_model: str | None, voice_gender: int | None, voice_race: str | None):
        # check if model name in each CSV column exists, with advanced_voice_model taking precedence over other columns
        try:
            for voice_type in [advanced_voice_model, voice, in_game_voice, csv_in_game_voice]:
                if voice_type:
                    voice_cleaned = str(voice_type).lower().replace(' ', '')
                    if voice_cleaned in self.__available_models:
                        return voice_cleaned
            logging.log(self._loglevel, f'Could not find voice model {in_game_voice}.onnx in {self.__models_path} attempting to load a backup model')
            voice_type=self.__game.find_best_voice_model(voice_race, voice_gender, in_game_voice, library_search=False)
            if voice_type:
                voice_cleaned = str(voice_type).lower().replace(' ', '')
            return voice_cleaned    
        except Exception as e :
            utils.play_error_sound()
            logging.error(f'Could not find a backup voice model {in_game_voice}.onnx in {self.__models_path}. Error :{e}')
            return None

    @utils.time_it
    def change_voice(self, voice: str, in_game_voice: str | None = None, csv_in_game_voice: str | None = None, advanced_voice_model: str | None = None, voice_accent: str | None = None, voice_gender: str | None = None, voice_race: str | None = None):
        if voice_gender is not None:
            self._current_actor_gender = voice_gender
        if voice_race is not None:
            self._current_actor_race = voice_race

        if self.__waiting_for_voice_load:
            self._check_voice_changed()
        else:
            logging.log(self._loglevel, 'Loading voice model...')

            self.__selected_voice = self._select_voice_type(voice, in_game_voice, csv_in_game_voice, advanced_voice_model, self._current_actor_gender, self._current_actor_race)
            model_path = self.__models_path + f'{self.__selected_voice}.onnx'

            self.__write_to_stdin(f"load_model {model_path}\n")
            self.__waiting_for_voice_load = True

    @utils.time_it
    def _check_if_piper_is_running(self):
        self._run_piper()
        
    @utils.time_it
    def _run_piper(self):
        try:
            command = f'{self.__piper_path}\\piper.exe'

            self.process = subprocess.Popen(
                command, 
                cwd=self._voiceline_folder, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                universal_newlines=True, 
                encoding='utf-8',
                bufsize=1, 
                close_fds=ON_POSIX,
            )

            self.q = Queue()
            self.stop_thread = False
            self.t = Thread(target=enqueue_output, args=(self.process.stdout, self.q, lambda: self.stop_thread))
            self.t.daemon = True # thread dies with the program
            self.t.start()
        
        except Exception as e:
            utils.play_error_sound()
            logging.error(f'Could not run Piper. Ensure that the path "{self.__piper_path}" is correct. Error: {e}')
            raise TTSServiceFailure()

    @utils.time_it
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
