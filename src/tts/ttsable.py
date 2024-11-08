from abc import ABC, abstractmethod
import datetime
import winsound
import logging
from src.config.config_loader import ConfigLoader
import src.utils as utils
import os
from pathlib import Path
from subprocess import STARTUPINFO, STARTF_USESHOWWINDOW
import subprocess
import time
from src.tts.synthesization_options import SynthesizationOptions

class ttsable(ABC):
    """Base class for different TTS services
    """
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__()
        self._config: ConfigLoader = config
        self._loglevel = 29
        self._facefx_path = config.facefx_path
        self._times_checked = 0
        self._tts_print = config.tts_print # to print output to console
        self._save_folder = config.save_folder
        self._output_path = self._save_folder+'data\\tmp'
        self._voiceline_folder = f"{self._output_path}/voicelines"
        os.makedirs(self._voiceline_folder, exist_ok=True)
        self._language = config.language
        self._last_voice = '' # last active voice model
        # determines whether the voiceline should play internally
        #self.debug_mode = config.debug_mode
        #self.play_audio_from_script = config.play_audio_from_script

        if config.game == "Fallout4" or config.game == "Fallout4VR":
            self._game = "Fallout4"
        else: 
            self._game = "Skyrim"


    def synthesize(self, voice: str, voiceline: str, in_game_voice: str, csv_in_game_voice: str, voice_accent: str, synth_options: SynthesizationOptions, advanced_voice_model: str | None = None):
        """Synthesizes a given voiceline
        """
        if self._last_voice == '' or (isinstance(self._last_voice, str) and self._last_voice.lower() not in {isinstance(v, str) and v.lower() for v in {voice, in_game_voice, csv_in_game_voice, advanced_voice_model, f'fo4_{voice}'}}):
            self.change_voice(voice, in_game_voice, csv_in_game_voice, advanced_voice_model, voice_accent)

        logging.log(22, f'Synthesizing voiceline: {voiceline.strip()}')

        final_voiceline_file_name = 'out' # "out" is the file name used by XTTS
        final_voiceline_file =  f"{self._voiceline_folder}/{final_voiceline_file_name}.wav"

        try:
            if os.path.exists(final_voiceline_file):
                os.remove(final_voiceline_file)
            if os.path.exists(final_voiceline_file.replace(".wav", ".lip")):
                os.remove(final_voiceline_file.replace(".wav", ".lip"))
        except:
            logging.warning("Failed to remove spoken voicelines")

        self.tts_synthesize(voiceline, final_voiceline_file, synth_options)
        if not os.path.exists(final_voiceline_file):
            logging.error(f'TTS failed to generate voiceline at: {Path(final_voiceline_file)}')
            raise FileNotFoundError()
        
        self._generate_lip_file(final_voiceline_file, voiceline)

        #rename to unique name        
        if (os.path.exists(final_voiceline_file)):
            try:
                timestamp: str = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f_")
                new_wav_file_name = f"{self._voiceline_folder}/{timestamp + final_voiceline_file_name}.wav" 
                new_lip_file_name = new_wav_file_name.replace(".wav", ".lip")
                new_fuz_file_name = new_wav_file_name.replace(".wav", ".fuz")
                os.rename(final_voiceline_file, new_wav_file_name)

                try:
                    os.rename(final_voiceline_file.replace(".wav", ".lip"), new_lip_file_name)
                except:
                    logging.error(f'Could not rename {final_voiceline_file.replace(".wav", ".lip")}')
                try:
                    fuz_file_name = final_voiceline_file.replace(".wav", ".fuz")
                    if (os.path.exists(fuz_file_name)):
                        os.rename(fuz_file_name, new_fuz_file_name)
                except:
                    logging.error(f'Could not rename {final_voiceline_file.replace(".wav", ".fuz")}')
                final_voiceline_file = new_wav_file_name
            except:
                logging.error(f'Could not rename {final_voiceline_file} or {final_voiceline_file.replace(".wav", ".lip")}')

        # if Debug Mode is on, play the audio file
        # if (self.debug_mode == '1') & (self.play_audio_from_script == '1'):
        #     winsound.PlaySound(final_voiceline_file, winsound.SND_FILENAME)
        return final_voiceline_file


    @abstractmethod
    def change_voice(self, voice: str, in_game_voice: str | None = None, csv_in_game_voice: str | None = None, advanced_voice_model: str | None = None, voice_accent: str | None = None):
        """Change the voice model
        """
        pass


    @abstractmethod
    def tts_synthesize(self, voiceline: str, final_voiceline_file: str, synth_options: SynthesizationOptions):
        """Synthesize the voiceline with the TTS service
        """
        pass


    def _sanitize_voice_name(self, voice_name):
        """Sanitizes the voice name by removing spaces."""
        if isinstance(voice_name, str):
            return voice_name.replace(" ", "").lower()
        else:
            return ''


    def _generate_lip_file(self, wav_file, voiceline, attempts=0):
        def run_facefx_command(command, facefx_path):
            startupinfo = STARTUPINFO()
            startupinfo.dwFlags |= STARTF_USESHOWWINDOW
            
            batch_file_path = Path(facefx_path) / "run_mantella_command.bat"
            with open(batch_file_path, 'w', encoding='utf-8') as file:
                file.write(f"@echo off\n{command} >nul 2>&1")

            subprocess.run(batch_file_path, cwd=facefx_path, creationflags=subprocess.CREATE_NO_WINDOW)
        
        try:
            # check if FonixData.cdf file is besides FaceFXWrapper.exe
            cdf_path = Path(self._facefx_path) / 'FonixData.cdf' 
            if not cdf_path.exists():
                logging.error(f'Could not find FonixData.cdf in "{cdf_path.parent}" required by FaceFXWrapper.')
                raise FileNotFoundError()

            # generate .lip file from the .wav file with FaceFXWrapper
            face_wrapper_executable = Path(self._facefx_path) / "FaceFXWrapper.exe"
            if not face_wrapper_executable.exists():
                logging.error(f'Could not find FaceFXWrapper.exe in "{face_wrapper_executable.parent}" with which to create a lip sync file, download it from: https://github.com/Nukem9/FaceFXWrapper/releases')
                raise FileNotFoundError()
        
            # Run FaceFXWrapper.exe
            r_wav = wav_file.replace(".wav", "_r.wav")
            lip = wav_file.replace(".wav", ".lip")
            commands = [
                face_wrapper_executable.name,
                self._game,
                "USEnglish",
                cdf_path.name,
                f'"{wav_file}"',
                f'"{r_wav}"',
                f'"{lip}"',
                f'"{voiceline}"'
            ]
            command = " ".join(commands)
            run_facefx_command(command, self._facefx_path)

            # remove file created by FaceFXWrapper
            if os.path.exists(wav_file.replace(".wav", "_r.wav")):
                os.remove(wav_file.replace(".wav", "_r.wav"))
            
            if (not os.path.exists(lip)) and attempts < 5:
                logging.warning('Could not generate .lip file. Retrying...')
                time.sleep(0.1)
                attempts += 1
                self._generate_lip_file(wav_file, voiceline, attempts)
            
            #Fallout: generate FUZ file
            if self._game == "Fallout4":    
                fuz_extractor_executable = Path(self._facefx_path) / "Fuz_extractor.exe"
                if not fuz_extractor_executable.exists():
                    logging.error(f'Could not find Fuz_extractor.exe in "{face_wrapper_executable.parent}" with which to create a fuz file, download it from: https://www.nexusmods.com/skyrimspecialedition/mods/55605')
                    raise FileNotFoundError()
            
                xWMAEncode_executable = Path(self._facefx_path) / "xWMAEncode.exe"
                if not xWMAEncode_executable.exists():
                    logging.error(f'Could not find xWMAEncode.exe in "{face_wrapper_executable.parent}" with which to create a fuz file, download it from: https://www.nexusmods.com/skyrimspecialedition/mods/55605')
                    raise FileNotFoundError()

                xwm_file = wav_file.replace(".wav", ".xwm")
                xwmcmds = [
                    xWMAEncode_executable.name,
                    f'"{wav_file}"',
                    f'"{xwm_file}"'
                    ]
                xwm_command = " ".join(xwmcmds)
                run_facefx_command(xwm_command, self._facefx_path)

                fuzfile = wav_file.replace(".wav", ".fuz")
                fuzcmds = [
                    fuz_extractor_executable.name,
                    "-c",
                    f'"{fuzfile}"',
                    f'"{lip}"',
                    f'"{xwm_file}"'
                    ]
                fuz_command = " ".join(fuzcmds)
                run_facefx_command(fuz_command, self._facefx_path)
           
        except Exception as e:
            logging.warning(e)