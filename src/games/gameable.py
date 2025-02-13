from abc import ABC, abstractmethod
import json
import logging
import os
from pathlib import Path
from typing import Any
import pandas as pd
from src.conversation.conversation_log import conversation_log
from src.conversation.context import context
from src.config.config_loader import ConfigLoader
from src.llm.sentence import sentence
from src.games.external_character_info import external_character_info
import src.utils as utils
import sounddevice as sd
import soundfile as sf
import threading
import wave

class gameable(ABC):
    """Abstract class for different implementations of games to support. 
    Make a subclass for every game that Mantella is supposed to support and implement this interface
    Anything that is specific to a certain game should end up in one of these subclasses.
    If there are new areas where a game specific handling is required, add new methods to this and implement them in all of the subclasses

    Args:
        ABC (_type_): _description_
    """
    @utils.time_it
    def __init__(self, config: ConfigLoader, path_to_character_df: str, mantella_game_folder_path: str):
        try:
            self.__character_df: pd.DataFrame = self.__get_character_df(path_to_character_df)
        except:
            logging.error(f'Unable to read / open {path_to_character_df}. If you have recently edited this file, please try reverting to a previous version. This error is normally due to using special characters, or saving the CSV in an incompatible format.')
            input("Press Enter to exit.")
        
        self._is_vr: bool = 'vr' in config.game.lower()
        #Apply character overrides
        mod_overrides_folder = os.path.join(*[config.mod_path_base, self.extender_name, "Plugins","MantellaSoftware","data",f"{mantella_game_folder_path}","character_overrides"])
        self.__apply_character_overrides(mod_overrides_folder, self.__character_df.columns.values.tolist())
        personal_overrides_folder = os.path.join(config.save_folder, f"data/{mantella_game_folder_path}/character_overrides")     
        self.__apply_character_overrides(personal_overrides_folder, self.__character_df.columns.values.tolist())

        self.__conversation_folder_path = config.save_folder + f"data/{mantella_game_folder_path}/conversations"
        conversation_log.game_path = self.__conversation_folder_path
    
    @property
    def character_df(self) -> pd.DataFrame:
        return self.__character_df
    
    @property
    def is_vr(self) -> bool:
        return self._is_vr
    
    @property
    @abstractmethod
    def game_name_in_filepath(self) -> str:
        """ Return the appropriate game name """
        pass
    
    @property
    @abstractmethod
    def extender_name(self) -> str:
        """ Return name of the appropriate script extender (SKSE/F4SE) """
        pass

    @abstractmethod
    def modify_sentence_text_for_game(self, text:str) -> str:
        """Modifies the text of a sentence before it is sent to the game."""
        pass

    @property
    def conversation_folder_path(self) -> str:
        return self.__conversation_folder_path
    
    @property
    @abstractmethod
    def image_path(self) -> str:
        """ Return the path to the image file created by in-game screenshots"""
        pass
    
    @utils.time_it
    def __get_character_df(self, file_name: str) -> pd.DataFrame:
        encoding = utils.get_file_encoding(file_name)
        character_df = pd.read_csv(file_name, engine='python', encoding=encoding)

        return character_df
    
    @abstractmethod
    def load_external_character_info(self, base_id: str, name: str, race: str, gender: int, actor_voice_model_name: str)-> external_character_info:
        """This loads extra information about a character that can not be gained from the game. i.e. bios or voice_model_names for TTS

        Args:
            id (str): the id of the character to get the extra information from
            name (str): the name of the character to get the extra information from
            race (str): the race of the character to get the extra information from
            gender (int): the gender of the character to get the extra information from
            actor_voice_model_name (str): the ingame voice model name of the character to get the extra information from

        Returns:
            external_character_info: the missing information
        """
        pass    

    @abstractmethod
    def prepare_sentence_for_game(self, queue_output: sentence, context_of_conversation: context, config: ConfigLoader, topicID: int, isFirstLine: bool):
        """Does what ever is needed to play a sentence ingame

        Args:
            queue_output (sentence): the sentence to play
            context_of_conversation (context): the context of the conversation
            config (ConfigLoader): the current config
            topicID (int): the Mantella dialogue line to write to
            isFirstLine (bool): whether this is the first voiceline of a given response
        """
        pass

    @abstractmethod
    def is_sentence_allowed(self, text: str, count_sentence_in_text: int) -> bool:
        """Checks a sentence generated by the LLM for game specific stuff

        Args:
            text (str): the sentence text to check
            count_sentence_in_text (int): count of sentence in text

        Returns:
            bool: True if sentence is allowed, False otherwise
        """
        pass

    @abstractmethod
    def load_unnamed_npc(self, name: str, actor_race: str, actor_sex: int, ingame_voice_model:str) -> dict[str, Any]:
        """Loads a generic NPC if the NPC is not found in the CSV file

         Args:
            name (str): the name of the character
            race (str): the race of the character
            gender (int): the gender of the character
            ingame_voice_model (str): the ingame voice model name of the character

        Returns:
            dict[str, Any]: A dictionary containing NPC info (name, bio, voice_model, advanced_voice_model, voice_folder)
        """
        pass

    @abstractmethod
    def get_weather_description(self, weather_attributes: dict[str, Any]) -> str:
        """Returns a description of the current weather that can be used in the prompts

        Args:
            weather_attributes (dict[str, Any]): The json of weather attributes as transferred by the respective game

        Returns:
            str: A prose description of the weather for the LLM
        """
        pass

    @abstractmethod
    def find_best_voice_model(self, actor_race: str, actor_sex: int, ingame_voice_model: str, library_search:bool = True) -> str:
        """Returns the voice model which most closely matches the NPC

        Args:
            actor_race (str): The race of the NPC
            actor_sex (int): The sex of the NPC
            ingame_voice_model (str): The in-game voice model provided for the NPC

        Returns:
            str: The voice model which most closely matches the NPC
        """
        pass

    @utils.time_it
    def _get_matching_df_rows_matcher(self, base_id: str, character_name: str, race: str) -> pd.Series | None:
        character_name_lower = character_name.lower()
        race_lower = race.lower()
        
        full_id_len = 6
        full_id_search = base_id[-full_id_len:].lstrip('0')  # Strip leading zeros from the last 6 characters

        # Function to remove leading zeros from hexadecimal ID strings
        def vectorized_remove_zeros(series):
            return series.fillna('').astype(str).str.lstrip('0')
        
        def vectorized_partial_id_match(series, length):
            str_series = series.fillna('').astype(str)
            # Create mask for strings long enough
            length_mask = str_series.str.len() >= length
            # Apply different logic based on length
            result = pd.Series('', index=series.index)  # Default to empty string
            result[length_mask] = str_series[length_mask].str[-length:].str.lstrip('0')
            result[~length_mask] = str_series[~length_mask].str.lstrip('0')
            return result.str.lower()

        df_id_cleaned = vectorized_remove_zeros(self.character_df['base_id']).str.lower()
        id_match = df_id_cleaned == full_id_search.lower()
        name_match = self.character_df['name'].astype(str).str.lower() == character_name_lower

        race_match = self.character_df['race'].astype(str).str.lower() == race_lower

        # Partial ID match with decreasing lengths
        partial_id_match = pd.Series(False, index=self.character_df.index)
        for length in [5, 4, 3]:
            if partial_id_match.any():
                break
            partial_id_search = base_id[-length:].lstrip('0').lower()  # strip leading zeros from partial ID search
            partial_id_match = vectorized_partial_id_match(self.character_df['base_id'], length) == partial_id_search

        ordered_matchers = {
            'name, ID, race': name_match & id_match & race_match, # match name, full ID, race (needed for Fallout 4 NPCs like Curie)
            'name, ID': name_match & id_match, # match name and full ID
            'name, partial ID, race': name_match & partial_id_match & race_match, # match name, partial ID, and race
            'name, partial ID': name_match & partial_id_match, # match name and partial ID
            'name, race': name_match & race_match, # match name and race
            'name': name_match, # match just name
            'ID': id_match # match just ID
        }

        for matcher in ordered_matchers:
            view = self.character_df.loc[ordered_matchers[matcher]]
            if view.shape[0] == 1: #If there is exactly one match
                logging.info(f'Matched {character_name} in CSV by {matcher}')
                return ordered_matchers[matcher]
            
        return None

    @utils.time_it
    def find_character_info(self, base_id: str, character_name: str, race: str, gender: int, ingame_voice_model: str):
        character_race = race.split('<')[1].split('Race ')[0] # TODO: check if this covers "character_currentrace.split('<')[1].split('Race ')[0]" from FO4
        matcher = self._get_matching_df_rows_matcher(base_id, character_name, character_race)
        if isinstance(matcher, type(None)):
            logging.info(f"Could not find {character_name} in {self.game_name_in_filepath}_characters.csv. Loading as a generic NPC.")
            character_info = self.load_unnamed_npc(character_name, character_race, gender, ingame_voice_model)
            is_generic_npc = True
        else:
            result = self.character_df.loc[matcher]
            character_info = result.to_dict('records')[0]
            if (character_info['voice_model'] is None) or (pd.isnull(character_info['voice_model'])) or (character_info['voice_model'] == ''):
                character_info['voice_model'] = self.find_best_voice_model(race, gender, ingame_voice_model) 
            is_generic_npc = False                                   

        return character_info, is_generic_npc
    
    @utils.time_it
    def __apply_character_overrides(self, overrides_folder: str, character_df_column_headers: list[str]):
        os.makedirs(overrides_folder, exist_ok=True)
        override_files: list[str] = os.listdir(overrides_folder)
        for file in override_files:
            try:
                filename, extension = os.path.splitext(file)
                full_path_file = os.path.join(overrides_folder,file)
                if extension == ".json":
                    with open(full_path_file) as fp:
                        json_object = json.load(fp)
                        if isinstance(json_object, dict):#Otherwise it is already a list
                            json_object = [json_object]
                        for json_content in json_object:
                            content: dict[str, str] = json_content
                            name = content.get("name", "")
                            base_id = content.get("base_id", "")
                            race = content.get("race", "")
                            matcher = self._get_matching_df_rows_matcher(base_id, name, race)
                            if isinstance(matcher, type(None)): #character not in csv, add as new row
                                row = []
                                for entry in character_df_column_headers:
                                    value = content.get(entry, "")
                                    row.append(value)
                                self.character_df.loc[len(self.character_df.index)] = row
                            else: #character is in csv, update row
                                for entry in character_df_column_headers:
                                    value = content.get(entry, None)
                                    if value and value != "":
                                        self.character_df.loc[matcher, entry] = value
                elif extension == ".csv":
                    extra_df = self.__get_character_df(full_path_file)
                    for i in range(extra_df.shape[0]):#for each row in df
                        name = self.get_string_from_df(extra_df.iloc[i], "name")
                        base_id = self.get_string_from_df(extra_df.iloc[i], "base_id")
                        race = self.get_string_from_df(extra_df.iloc[i], "race")
                        matcher = self._get_matching_df_rows_matcher(base_id, name, race)
                        if isinstance(matcher, type(None)): #character not in csv, add as new row
                            row = []
                            for entry in character_df_column_headers:
                                value = self.get_string_from_df(extra_df.iloc[i], entry)
                                row.append(value)
                            self.character_df.loc[len(self.character_df.index)] = row
                        else: #character is in csv, update row
                            for entry in character_df_column_headers:
                                value = extra_df.iloc[i].get(entry, None)
                                if value and not pd.isna(value) and value != "":
                                    self.character_df.loc[matcher, entry] = value
            except Exception as e:
                logging.log(logging.WARNING, f"Could not load character override file '{file}' in '{overrides_folder}'. Most likely there is an error in the formating of the file. Error: {e}")

    @staticmethod
    @utils.time_it
    def get_string_from_df(iloc, column_name: str) -> str:
        entry = iloc.get(column_name, "")
        if pd.isna(entry): entry = ""
        elif not isinstance(entry, str): entry = str(entry)
        return entry        

    @staticmethod
    @utils.time_it
    def play_audio_async(filename: str, volume: float = 0.5):
        """
        Play audio file asynchronously with volume control
        
        Args:
            filename (str): Path to audio file
            volume (float): Volume multiplier (0.0 to 1.0)
        """
        def audio_thread():
            data, samplerate = sf.read(filename)
            data = data * volume
            sd.play(data, samplerate)
            
        thread = threading.Thread(target=audio_thread)
        thread.start()

    @staticmethod
    @utils.time_it
    def send_muted_voiceline_to_game_folder(audio_file: str, filename: str, voice_folder_path: str):
        """
        Save muted voiceline to game folder, keeping the audio duration of the original file
        
        Args:
            audio_file (str): Path to the audio file
            filename (str): Name of the audio file to save in the game folder
            voice_folder_path (str): Game path to save the muted audio file to
        """
        # Create a muted version of the wav file
        with wave.open(audio_file, 'rb') as wav_file:
            params = wav_file.getparams()
            frames = wav_file.readframes(wav_file.getnframes())
        
        # Create muted frames (all zeros) with same length as original
        muted_frames = b'\x00' * len(frames)

        # Save muted wav file to game folder
        with wave.open(os.path.join(voice_folder_path, f"{filename}.wav"), 'wb') as muted_wav:
            muted_wav.setparams(params)
            muted_wav.writeframes(muted_frames)