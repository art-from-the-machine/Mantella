from abc import ABC, abstractmethod
import datetime
import winsound
import logging
from src.config.config_loader import ConfigLoader
import src.utils as utils
import os
from pathlib import Path
from subprocess import DEVNULL, STARTUPINFO, STARTF_USESHOWWINDOW
import subprocess
import time
from src.tts.synthesization_options import SynthesizationOptions
import requests
import shutil

class ttsable(ABC):
    """Base class for different TTS services
    """
    @utils.time_it
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__()
        self._config: ConfigLoader = config
        self._loglevel = 29
        self._lipgen_path = config.lipgen_path
        self.__has_lipgen_warning_happened = False
        self._facefx_path = config.facefx_path
        self._times_checked = 0
        self._tts_print = config.tts_print # to print output to console
        self._save_folder = config.save_folder
        self._voiceline_folder = ttsable.get_temp_voiceline_folder()
        os.makedirs(f"{self._voiceline_folder}/save", exist_ok=True)
        self._language = config.language
        self._last_voice = '' # last active voice model
        self._lip_generation_enabled = config.lip_generation
        # determines whether the voiceline should play internally
        #self.debug_mode = config.debug_mode
        #self.play_audio_from_script = config.play_audio_from_script

        if config.game == "Fallout4" or config.game == "Fallout4VR":
            self._game = "Fallout4"
        else: 
            self._game = "Skyrim"

    @staticmethod
    def get_temp_voiceline_folder():
        output_path = os.getenv('TMP')
        return f"{output_path}/voicelines"

    @utils.time_it
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
        
        if (self._lip_generation_enabled == 'enabled') or (self._lip_generation_enabled == 'lazy' and not synth_options.is_first_line_of_response):
            self._generate_voiceline_files(final_voiceline_file, voiceline)
        elif (self._lip_generation_enabled in ['lazy', 'disabled'] and self._game == "Fallout4"):
            self._generate_voiceline_files(final_voiceline_file, voiceline, skip_lip_generation=True)
        
        #rename to unique name        
        if (os.path.exists(final_voiceline_file)):
            #timestamp: str = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f_")
            #new_wav_file_name = f"{self._voiceline_folder}/save/{timestamp + final_voiceline_file_name}.wav" 

            #Use a sanitized version of the voice text as filename
            unique_name: str  = f'{voice} {voiceline.strip()}'[:150]
            new_name: str = "".join(c for c in unique_name if c not in r'\/:*?"<>|.')
            new_wav_file_name = f'{self._voiceline_folder}/save/{new_name.strip()}.wav'

            new_lip_file_name = new_wav_file_name.replace(".wav", ".lip")
            new_fuz_file_name = new_wav_file_name.replace(".wav", ".fuz")

            if os.path.exists(new_wav_file_name):       #Repeated phrase, delete previous file
                os.remove(new_wav_file_name)

            try:
                os.rename(final_voiceline_file, new_wav_file_name)
            except Exception as ex:
                logging.warning(f'{type(ex).__name__}: {ex.args}')

            if (self._lip_generation_enabled == 'enabled') or (self._lip_generation_enabled == 'lazy' and not synth_options.is_first_line_of_response):
                try:
                    if os.path.exists(new_lip_file_name):
                        os.remove(new_lip_file_name)
                    os.rename(final_voiceline_file.replace(".wav", ".lip"), new_lip_file_name)
                except:
                    logging.error(f'Could not rename {final_voiceline_file.replace(".wav", ".lip")}')
            try:
                fuz_file_name = final_voiceline_file.replace(".wav", ".fuz")
                if (os.path.exists(fuz_file_name)):
                    if os.path.exists(new_fuz_file_name):
                        os.remove(new_fuz_file_name)
                    os.rename(fuz_file_name, new_fuz_file_name)
            except:
                logging.error(f'Could not rename {final_voiceline_file.replace(".wav", ".fuz")}')
            final_voiceline_file = new_wav_file_name

        # if Debug Mode is on, play the audio file
        # if (self.debug_mode == '1') & (self.play_audio_from_script == '1'):
        #     winsound.PlaySound(final_voiceline_file, winsound.SND_FILENAME)
        return final_voiceline_file


    @abstractmethod
    @utils.time_it
    def change_voice(self, voice: str, in_game_voice: str | None = None, csv_in_game_voice: str | None = None, advanced_voice_model: str | None = None, voice_accent: str | None = None, voice_gender: int | None = None, voice_race: str | None = None):
        """Change the voice model
        """
        pass


    @abstractmethod
    @utils.time_it
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


    @staticmethod
    @utils.time_it
    def _send_request(url, data):
        requests.post(url, json=data)


    @staticmethod
    def get_lip_placeholder_path(game: str):
        return Path(utils.resolve_path()) / "data" / game / "placeholder" / "placeholder.lip"
    

    @staticmethod
    @utils.time_it
    def run_facefx_command(command, facefx_path) -> None:
        startupinfo = STARTUPINFO()
        startupinfo.dwFlags |= STARTF_USESHOWWINDOW
        
        batch_file_path = Path(facefx_path) / "run_mantella_command.bat"
        with open(batch_file_path, 'w', encoding='utf-8') as file:
            file.write(f"@echo off\n{command} >nul 2>&1")

        subprocess.run(batch_file_path, cwd=facefx_path, creationflags=subprocess.CREATE_NO_WINDOW)
    

    @staticmethod
    @utils.time_it
    def generate_fuz_file(facefx_path: str, lipgen_path: str, voiceline_folder: str, wav_file: str, lip_file: str) -> None:
        """
        Generate a .fuz file (for Fallout 4) from a given .wav audio file and its corresponding .lip file.

        This function first attempts to create the .fuz file using Bethesda's official LipFuzer tool.
        If LipFuzer.exe is found in the expected location, it is executed with the appropriate parameters.
        If the tool is not found, the function falls back to a manual method that uses Fuz_extractor.exe and
        xWMAEncode.exe (both expected to be located in the facefx_path directory).

        Args:
            facefx_path (str): The directory containing FaceFX-related executables (e.g., Fuz_extractor.exe, xWMAEncode.exe)
            lipgen_path (str): The base directory where the LipFuzer tool is located
            voiceline_folder (str): The directory containing the voiceline files
            wav_file (str): The full path to the input .wav audio file
            lip_file (str): The full path to the input .lip file
        """
        #Fuz files needed for Fallout only
        #LipFuzer is Bethesda's official fuz creator
        LipFuz_path = Path(lipgen_path) / "LipFuzer/LipFuzer.exe"

        if os.path.exists(LipFuz_path):
            args: str = f'"{LipFuz_path}" -s "{voiceline_folder}" -d "{voiceline_folder}" -a wav --norec'
            run_result: subprocess.CompletedProcess = subprocess.run(args, cwd=facefx_path, stdout=DEVNULL, stderr=DEVNULL,
                                                                        creationflags=subprocess.CREATE_NO_WINDOW)
            if run_result.returncode != 0:
                logging.warning(f'LipFuzer returned {run_result.returncode}')
        else:
            #Fall back to using Fuz_extractor and xWMAencode if LipFuzer not found
            logging.warning('Could not find LipFuzer.exe: please install or update the creation kit from Steam')
            fuz_extractor_executable = Path(facefx_path) / "Fuz_extractor.exe"
            if not fuz_extractor_executable.exists():
                logging.error(f'Could not find Fuz_extractor.exe in "{facefx_path}" with which to create a fuz file, download it from: https://www.nexusmods.com/skyrimspecialedition/mods/55605')
                raise FileNotFoundError()
    
            xWMAEncode_executable = Path(facefx_path) / "xWMAEncode.exe"
            if not xWMAEncode_executable.exists():
                logging.error(f'Could not find xWMAEncode.exe in "{facefx_path}" with which to create a fuz file, download it from: https://www.nexusmods.com/skyrimspecialedition/mods/55605')
                raise FileNotFoundError()

            xwm_file = wav_file.replace(".wav", ".xwm")
            xwmcmds = [
                xWMAEncode_executable.name,
                f'"{wav_file}"',
                f'"{xwm_file}"'
                ]
            xwm_command = " ".join(xwmcmds)
            ttsable.run_facefx_command(xwm_command, facefx_path)

            fuzfile = wav_file.replace(".wav", ".fuz")
            fuzcmds = [
                fuz_extractor_executable.name,
                "-c",
                f'"{fuzfile}"',
                f'"{lip_file}"',
                f'"{xwm_file}"'
                ]
            fuz_command = " ".join(fuzcmds)
            ttsable.run_facefx_command(fuz_command, facefx_path)


    @utils.time_it
    def _generate_voiceline_files(self, wav_file: str, voiceline: str, skip_lip_generation: bool = False):
        """Generates .lip files for voicelines using Bethesda's LipGen tool
        with FaceFXWrapper as fallback. Additionally generates a .fuz file which is required for Fallout 4
        Args:
            wav_file (str): The path to the input .wav file containing the voiceline audio
            voiceline (str): The corresponding text voiceline used to help lip sync generation
            skip_lip_generation (bool): Whether to skip the lip file generation process and use a placeholder .lip file instead (useful for when FaceFXWrapper is experiencing issues)
        """
        def copy_placeholder_lip_file(lip_file: str, game: str) -> None:
            """
            .lip files are needed to generate .fuz files (required by Fallout 4)
            If generating lip files via FaceFXWrapper fails, this function ensures a .lip file exists by copying from a placeholder file
            """
            lip_placeholder_path = self.get_lip_placeholder_path(game)
            if not lip_placeholder_path.exists():
                raise FileNotFoundError(f"The source file does not exist: {lip_placeholder_path}")
            else:
                shutil.copy(lip_placeholder_path, lip_file)


        def generate_facefx_lip_file(facefx_path: str, wav_file: str, lip_file: str, voiceline: str, game: str) -> None:
            # Bethesda's LipGen:
            LipGen_path = Path(self._lipgen_path) / "LipGenerator/LipGenerator.exe"
            languages = {
                "fr" : 'French',
                'es' : 'Spanish',
                'de' : 'German',
                'it' : 'Italian',
                'ko' : 'Korean',
                'jp' : 'Japanese'}

            if os.path.exists(LipGen_path):
                language_parm = languages.get(self._language, 'USEnglish')

                #Using subprocess.run to retrieve the exit code
                args: str = f'"{LipGen_path}" "{wav_file}" "{voiceline}" -Language:{language_parm} -Automated'
                run_result: subprocess.CompletedProcess = subprocess.run(args, cwd=facefx_path, stderr=DEVNULL, stdout=DEVNULL,
                                                                         creationflags=subprocess.CREATE_NO_WINDOW)
                if run_result.returncode != 0 and len(voiceline) > 11 :
                    #Very short sentences sometimes fail to generate a .lip file, so skip warning
                    logging.warning(f'Lipgen returned {run_result.returncode}')
            else:
                if not self.__has_lipgen_warning_happened:
                    logging.warning('Could not find LipGenerator.exe. Please install or update the Creation Kit from Steam for faster lip sync generation')
                    self.__has_lipgen_warning_happened = True
                # Fall back to using FaceFXWrapper if LipGen not detected
                face_wrapper_executable: Path = Path(self._facefx_path) / "FaceFXWrapper.exe"
                if not face_wrapper_executable.exists():
                    logging.error(f'Could not find FaceFXWrapper.exe in "{face_wrapper_executable.parent}" with which to create a lip sync file, download it from: https://github.com/Nukem9/FaceFXWrapper/releases')
                    raise FileNotFoundError()

                cdf_path = Path(facefx_path) / 'FonixData.cdf' 
                if not cdf_path.exists():
                    logging.error(f'Could not find FonixData.cdf in "{cdf_path.parent}" required by FaceFXWrapper.')
                    raise FileNotFoundError()
        
                # Run FaceFXWrapper.exe
                r_wav = wav_file.replace(".wav", "_r.wav")
                commands = [
                    face_wrapper_executable.name,
                    game,
                    "USEnglish",
                    cdf_path.name,
                    f'"{wav_file}"',
                    f'"{r_wav}"',
                    f'"{lip_file}"',
                    f'"{voiceline}"'
                ]
                command = " ".join(commands)
                ttsable.run_facefx_command(command, facefx_path)

                # remove file created by FaceFXWrapper
                if os.path.exists(wav_file.replace(".wav", "_r.wav")):
                    os.remove(wav_file.replace(".wav", "_r.wav"))


        try:
            
            # path to store .lip file (next to voiceline .wav)
            lip_file: str = wav_file.replace(".wav", ".lip")
            
            if not skip_lip_generation:
                generate_facefx_lip_file(self._facefx_path, wav_file, lip_file, voiceline, self._game)
            else:
                copy_placeholder_lip_file(lip_file, self._game)
            
            # Fallout 4 requires voicelines in a .fuz format
            if self._game == "Fallout4":    
                self.generate_fuz_file(self._facefx_path, self._lipgen_path, self._voiceline_folder, wav_file, lip_file)
        
        except Exception as e:
            logging.warning(e)