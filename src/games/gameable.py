from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
from typing import Any, TYPE_CHECKING
import yaml
import pandas as pd
from src.conversation.conversation_log import conversation_log
if TYPE_CHECKING:
    from src.conversation.context import Context
from src.config.config_loader import ConfigLoader
from src.llm.sentence import Sentence
from src.games.external_character_info import external_character_info
import src.utils as utils
import sounddevice as sd
import soundfile as sf
import threading
import wave
import shutil

logger = utils.get_logger()


class Gameable(ABC):
    """Abstract class for different implementations of games to support. 
    Make a subclass for every game that Mantella is supposed to support and implement this interface
    Anything that is specific to a certain game should end up in one of these subclasses.
    If there are new areas where a game specific handling is required, add new methods to this and implement them in all of the subclasses

    Args:
        ABC (_type_): _description_
    """
    MANTELLA_VOICE_FOLDER = "MantellaVoice00"

    @utils.time_it
    def __init__(self, config: ConfigLoader, path_to_character_df: str, mantella_game_folder_path: str):
        try:
            self.__character_df: pd.DataFrame = self.__get_character_df(path_to_character_df)
        except:
            logger.error(f'Unable to read / open {path_to_character_df}. If you have recently edited this file, please try reverting to a previous version. This error is normally due to using special characters, or saving the CSV in an incompatible format.')
            input("Press Enter to exit.")
        
        self._is_vr: bool = config.game.is_vr
        #Apply character overrides
        mod_overrides_folder = os.path.join(*[config.mod_path_base, self.extender_name, "Plugins","MantellaSoftware","data",f"{mantella_game_folder_path}","character_overrides"])
        self.__apply_character_overrides(mod_overrides_folder, self.__character_df.columns.values.tolist())
        personal_overrides_folder = os.path.join(config.save_folder, f"data/{mantella_game_folder_path}/character_overrides")
        self.__apply_character_overrides(personal_overrides_folder, self.__character_df.columns.values.tolist())

        self.__conversation_folder_path = os.path.join(config.save_folder, "data", mantella_game_folder_path, "conversations")
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
        character_df['wiki'] = ""
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
    def prepare_sentence_for_game(self, queue_output: Sentence, context_of_conversation: 'Context', config: ConfigLoader, topicID: int, isFirstLine: bool):
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

    def resolve_npc_refid_by_name(self, name: str) -> str | None:
        """Resolve an NPC name to their ref_id
        
        Only returns a result if exactly one NPC with that name exists in the character CSV
        This prevents ambiguity when multiple NPCs share the same name (eg guards)
        
        Args:
            name: The name of the NPC to look up
            
        Returns:
            str | None: ref_id if exactly one match found, None otherwise
        """
        ref_id = None
        name_lower = name.lower()
        name_match = self.character_df['name'].astype(str).str.lower() == name_lower
        matching_rows = self.character_df.loc[name_match]
        
        if matching_rows.shape[0] == 1:
            row = matching_rows.iloc[0]
            ref_id = str(row.get('ref_id', ''))
            if ref_id:
                logger.info(f"Resolved NPC '{name}' to ref_id '{ref_id}'")
            else:
                logger.warning(f"NPC '{name}' found but has no ref_id in CSV")
        elif matching_rows.shape[0] > 1:
            logger.warning(f"Multiple NPCs found with name '{name}' ({matching_rows.shape[0]} matches) - cannot resolve unambiguously")
        else:
            logger.warning(f"No NPC found with name '{name}' in character CSV")
        
        return ref_id

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
        
        logger.info(f"[MATCH] base_id='{full_id_search}', name='{character_name_lower}', race='{race_lower}' → ID:{id_match.sum()}, Name:{name_match.sum()}, Race:{race_match.sum()}")

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
                logger.info(f'Matched {character_name} in CSV by {matcher}')
                return ordered_matchers[matcher]
            
        return None

    @utils.time_it
    def find_character_info(self, base_id: str, character_name: str, race: str, gender: int, ingame_voice_model: str):
        character_race = race.split('<')[1].split('Race')[0].strip().rstrip('>') # Remove 'Race' suffix and trailing '>'
        logger.info(f"[FIND] name='{character_name}', base_id='{base_id}', race='{character_race}'")
        matcher = self._get_matching_df_rows_matcher(base_id, character_name, character_race)
        if isinstance(matcher, type(None)):
            logger.info(f"Could not find {character_name} in {self.game_name_in_filepath}_characters.csv. Loading as a generic NPC. race: {character_race} gender: {gender} ingame_voice_model: {ingame_voice_model}")
            character_info = self.load_unnamed_npc(character_name, character_race, gender, ingame_voice_model)
            is_generic_npc = True
        else:
            result = self.character_df.loc[matcher]
            character_info = result.to_dict('records')[0]
            if (character_info['voice_model'] is None) or (pd.isnull(character_info['voice_model'])) or (character_info['voice_model'] == ''):
                character_info['voice_model'] = self.find_best_voice_model(race, gender, ingame_voice_model) 
            is_generic_npc = False
        
        # Convert NaN values to None to prevent JSON serialization errors in TTS
        for key, value in character_info.items():
            if pd.isna(value):
                character_info[key] = None

        return character_info, is_generic_npc
    
    # Fields that should never be overwritten (used for matching/identity)
    PROTECTED_OVERRIDE_FIELDS = ['base_id', 'ref_id', 'baseid_int', 'refid_int', 'name']

    @utils.time_it
    def __apply_character_overrides(self, overrides_folder: str, character_df_column_headers: list[str]):
        """Load and apply all character override files from the overrides folder."""
        os.makedirs(overrides_folder, exist_ok=True)
        
        for file in os.listdir(overrides_folder):
            try:
                full_path = os.path.join(overrides_folder, file)
                extension = os.path.splitext(file)[1].lower()
                
                if extension == ".json":
                    self.__apply_json_override(full_path, character_df_column_headers)
                elif extension in [".yaml", ".yml"]:
                    self.__apply_yaml_override(full_path, character_df_column_headers)
                elif extension == ".csv":
                    self.__apply_csv_override(full_path, character_df_column_headers)
                    
            except Exception as e:
                logger.warning(f"Could not load character override file '{file}' in '{overrides_folder}'. Most likely there is an error in the formating of the file. Error: {e}")

    def __apply_json_override(self, file_path: str, column_headers: list[str]):
        """Apply overrides from a JSON file."""
        with open(file_path, encoding='utf-8') as fp:
            data = json.load(fp)
            entries = [data] if isinstance(data, dict) else data
            for content in entries:
                self.__apply_single_override(content, column_headers, "JSON")

    def __apply_yaml_override(self, file_path: str, column_headers: list[str]):
        """Apply overrides from a YAML file (supports multi-line bios and structured content)."""
        with open(file_path, 'r', encoding='utf-8') as fp:
            data = yaml.safe_load(fp)
            entries = [data] if isinstance(data, dict) else data
            for content in entries:
                self.__apply_single_override(content, column_headers, "YAML")

    def __apply_csv_override(self, file_path: str, column_headers: list[str]):
        """Apply overrides from a CSV file."""
        extra_df = self.__get_character_df(file_path)
        for i in range(extra_df.shape[0]):
            row_data = extra_df.iloc[i]
            name = self.get_string_from_df(row_data, "name")
            base_id = self.get_string_from_df(row_data, "base_id")
            race = self.get_string_from_df(row_data, "race")
            
            matcher = self._get_matching_df_rows_matcher(base_id, name, race)
            if matcher is None:
                # Add new character
                row = [self.get_string_from_df(row_data, col) for col in column_headers]
                self.character_df.loc[len(self.character_df.index)] = row
            else:
                # Update existing character
                for col in column_headers:
                    value = row_data.get(col, None)
                    if value and not pd.isna(value) and value != "":
                        self.character_df.loc[matcher, col] = value

    def __apply_single_override(self, content: dict, column_headers: list[str], source_type: str):
        """Apply a single character override to the DataFrame."""
        name = content.get("name", "")
        base_id = content.get("base_id", "")
        race = content.get("race", "")
        
        matcher = self._get_matching_df_rows_matcher(base_id, name, race)
        
        if matcher is None:
            # Character not in CSV - add as new row
            self.__add_new_character(content, column_headers)
        else:
            # Character exists - update row
            self.__update_existing_character(content, column_headers, matcher, base_id, source_type)

    def __add_new_character(self, content: dict, column_headers: list[str]):
        """Add a new character row to the DataFrame."""
        row = [content.get(col, "") for col in column_headers]
        self.character_df.loc[len(self.character_df.index)] = row
        logger.info(f"[OVERRIDE] Added new character: {content.get('name', 'Unknown')}")

    def __update_existing_character(self, content: dict, column_headers: list[str], matcher, base_id: str, source_type: str):
        """Update an existing character in the DataFrame."""
        logger.info(f"[OVERRIDE {source_type}] Updating character base_id={base_id}")
        
        # Handle 'name' specially - use it as 'prompt_name' instead of overwriting the internal name
        if content.get('name'):
            logger.info(f"[OVERRIDE {source_type}] Setting prompt_name='{content['name']}'")
            self.character_df.loc[matcher, 'prompt_name'] = content['name']
        
        # Update all fields including wiki
        for col in column_headers + ['wiki']:  # Include wiki even if not in CSV headers
            if col in self.PROTECTED_OVERRIDE_FIELDS:
                continue
            value = content.get(col)
            # Skip None values (YAML null) and empty strings
            if value is None or value == "":
                continue
            preview = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            logger.info(f"[OVERRIDE {source_type}] Setting {col}='{preview}'")
            self.character_df.loc[matcher, col] = value

    @utils.time_it
    def _create_all_voice_folders(self, mod_path: str, voice_folder_col: str):
        all_voice_folders = self.character_df[voice_folder_col]
        all_voice_folders = all_voice_folders.loc[all_voice_folders.notna()]
        example_folder = os.path.join(mod_path, self.MANTELLA_VOICE_FOLDER)
        set_of_voice_folders = set()
        for voice_folder in all_voice_folders:
            voice_folder = str.strip(voice_folder)
            if voice_folder and not set_of_voice_folders.__contains__(voice_folder):
                set_of_voice_folders.add(voice_folder)
                in_game_voice_folder_path = os.path.join(mod_path, voice_folder)
                if not os.path.exists(in_game_voice_folder_path):
                    os.mkdir(in_game_voice_folder_path)
                    for file_name in os.listdir(example_folder):
                        source_file_path = os.path.join(example_folder, file_name)
                        if os.path.isfile(source_file_path):
                            shutil.copy(source_file_path, in_game_voice_folder_path)

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

