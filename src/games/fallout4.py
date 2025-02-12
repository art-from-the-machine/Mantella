import logging
import os
import shutil
from typing import Any
import pandas as pd
from src.http.file_communication_compatibility import file_communication_compatibility
from src.conversation.context import context
#from src.audio.audio_playback import audio_playback
from src.character_manager import Character
from src.config.config_loader import ConfigLoader
from src.llm.sentence import sentence
from src.games.external_character_info import external_character_info
from src.games.gameable import gameable
import src.utils as utils


class fallout4(gameable):
    FO4_XVASynth_file: str =f"data/Fallout4/FO4_Voice_folder_XVASynth_matches.csv"
    KEY_CONTEXT_CUSTOMVALUES_PLAYERPOSX: str  = "mantella_player_pos_x"
    KEY_CONTEXT_CUSTOMVALUES_PLAYERPOSY: str  = "mantella_player_pos_y"
    KEY_CONTEXT_CUSTOMVALUES_PLAYERROT: str  = "mantella_player_rot"
    KEY_ACTOR_CUSTOMVALUES_POSX: str  = "mantella_actor_pos_x"
    KEY_ACTOR_CUSTOMVALUES_POSY: str  = "mantella_actor_pos_y"

    def __init__(self, config: ConfigLoader):
        super().__init__(config, 'data/Fallout4/fallout4_characters.csv', "Fallout4")
        if config.game == "Fallout4VR":
            self.__compatibility = file_communication_compatibility(config.game_path, int(config.port))# <- creating an object of this starts the listen thread
        self.__tts_service: str = config.tts_service
        encoding = utils.get_file_encoding(fallout4.FO4_XVASynth_file)
        self.__FO4_Voice_folder_and_models_df = pd.read_csv(fallout4.FO4_XVASynth_file, engine='python', encoding=encoding)
        #self.__playback: audio_playback = audio_playback(config)
        self.__last_played_voiceline: str | None = None
        self.__image_analysis_filepath = config.game_path

    @property
    def extender_name(self) -> str:
        return 'F4SE'

    @property
    def game_name_in_filepath(self) -> str:
        return 'fallout4'
    
    @property
    def image_path(self) -> str:
        return self.__image_analysis_filepath
        
    def modify_sentence_text_for_game(self, text:str) -> str:
        """Modifies the text of a sentence before it is sent to the game.
            148 bytes is max for Fallout 4."""
        byte_string: bytes = text.encode('utf-8')
        count_bytes_in_string = len(byte_string)			# Count bytes and not chars
        if count_bytes_in_string < 148:
            return text
        
        cut_length:int = 144
        cut_bytes:bytes = byte_string[0:cut_length]
        if cut_bytes[-1] & 0b10000000:
            last_11xxxxxx_index = 0
            for i in range(-1, -5, -1):
                if cut_bytes[i] & 0b11000000 == 0b11000000:
                    last_11xxxxxx_index = i
                    break
            cut_bytes = cut_bytes[0:len(cut_bytes)+last_11xxxxxx_index]

        result = cut_bytes.decode('utf-8')
        return result + "..." #Dots should be part of ASCII and thus only 1 byte long 

    @utils.time_it
    def load_external_character_info(self, base_id: str, name: str, race: str, gender: int, ingame_voice_model: str) -> external_character_info:
        character_info, is_generic_npc = self.find_character_info(base_id, name, race, gender, ingame_voice_model)
        actor_voice_model_name = ingame_voice_model.split('<')[1].split(' ')[0]

        return external_character_info(name, is_generic_npc, character_info["bio"], actor_voice_model_name, character_info['voice_model'], character_info['fallout4_voice_folder'], character_info['advanced_voice_model'], character_info.get('voice_accent', None)) 
    
    @utils.time_it
    def find_best_voice_model(self, actor_race: str, actor_sex: int, ingame_voice_model: str, library_search:bool = True) -> str:
        voice_model = ''

        actor_voice_model = ingame_voice_model
        if '(' in actor_voice_model and ')' in actor_voice_model:
            actor_voice_model_id = actor_voice_model.split('(')[1].split(')')[0]
        else:
            actor_voice_model_id = actor_voice_model  
        if '<' in actor_voice_model:
            actor_voice_model_name = actor_voice_model.split('<')[1].split(' ')[0]
        else:
            actor_voice_model_name = actor_voice_model  
        #Filtering out endsdiwth Race because depending on the source of the method call it may be present.
        if 'Race <' in actor_race:
            actor_race = actor_race.split('Race <', 1)[1]

            if actor_race.endswith('Race'):
                actor_race = actor_race[:actor_race.rfind('Race')].strip()
        else:
            actor_race = actor_race

        #make the substitutions below to bypass non-functional XVASynth voice models: RobotCompanionMaleDefault, RobotCompanionMaleProcessed,Gen1Synth02 & Gen1Synth03 
        if self.__tts_service=="xvasynth": #only necessary for XVASynth
            male_voice_model_dictionary=fallout4.MALE_VOICE_MODELS_XVASYNTH
            female_voice_model_dictionary = fallout4.FEMALE_VOICE_MODELS_XVASYNTH
            if actor_voice_model_name in  ("DLC01RobotCompanionMaleDefault", "DLC01RobotCompanionMaleProcessed"):
                actor_voice_model_name='robot_assaultron'
                actor_voice_model_id='robot_assaultron'
            if actor_voice_model_name in  ("SynthGen1Male02", "SynthGen1Male03"):
                actor_voice_model_name='gen1synth01'
                actor_voice_model_id='000BBBF0'
        else:
            male_voice_model_dictionary=fallout4.MALE_VOICE_MODELS_NONXVASYNTH
            female_voice_model_dictionary = fallout4.FEMALE_VOICE_MODELS_NONXVASYNTH
        matching_row=''
        # Search for the Matching 'voice_ID'
        if library_search:
            matching_row = self.__FO4_Voice_folder_and_models_df[self.__FO4_Voice_folder_and_models_df['voice_ID'] == actor_voice_model_id]

            # Return the Matching Row's Values
            if not matching_row.empty:
                # Assuming there's only one match, get the value from the 'voice_model' column
                voice_model = matching_row['voice_model'].iloc[0]
            else:
                logging.log(23, "No matching voice ID found. Attempting voice_file_name match.")
      
        

        if voice_model == '':
            # If no match by 'voice_ID' and not found in , search by 'voice_model' (actor_voice_model_name)
            if library_search:
                matching_row_by_name = self.__FO4_Voice_folder_and_models_df[self.__FO4_Voice_folder_and_models_df['voice_file_name'].str.lower() == actor_voice_model_name.lower()]
                if not matching_row_by_name.empty:
                    # If there is a match, set 'voice_model' to 'actor_voice_model_name'
                    voice_model = matching_row_by_name['voice_model'].iloc[0]
            else:
                try: # search for voice model in fallout4_characters.csv
                    if library_search:
                        voice_model = self.character_df.loc[self.character_df['fallout4_voice_folder'].astype(str).str.lower()==actor_voice_model_name.lower(), 'voice_model'].values[0]
                    else:
                        voice_model =self.dictionary_match(voice_model,female_voice_model_dictionary, male_voice_model_dictionary, actor_race,actor_sex)
                except: 
                    voice_model =self.dictionary_match(voice_model,female_voice_model_dictionary, male_voice_model_dictionary,actor_race,actor_sex)
        return voice_model

    def dictionary_match(self,voice_model:str,female_voice_model_dictionary:dict,male_voice_model_dictionary:dict,actor_race:str, actor_sex:int) -> str:
        if actor_race is None:
            actor_race = "Human"
        if actor_sex is None:
            actor_sex = 0
        modified_race_key = actor_race + "Race"
        #except then try to match using gender and race with pre-established dictionaries
        if actor_sex == 1:
            try:
                voice_model = female_voice_model_dictionary[modified_race_key]
            except:
                voice_model = 'femaleboston'
        else:
            try:
                voice_model = male_voice_model_dictionary[modified_race_key]
            except:
                voice_model = 'maleboston'
        return voice_model


    @utils.time_it
    def load_unnamed_npc(self, name: str, actor_race: str, actor_sex: int, ingame_voice_model:str) -> dict[str, Any]:
        """Load generic NPC if character cannot be found in fallout4_characters.csv"""
        # unknown == I couldn't find the IDs for these voice models

        voice_model = self.find_best_voice_model(actor_race, actor_sex, ingame_voice_model)

        try: # search for relevant FO4_Voice_folder_and_models_df for voice_model
            matching_row_by_voicemodel = self.__FO4_Voice_folder_and_models_df[self.__FO4_Voice_folder_and_models_df['voice_model'].str.lower() == voice_model.lower()]
            if not matching_row_by_voicemodel.empty:
                # FO4_voice_folder becomes the matching row of FO4_Voice_folder_XVASynth_matches.csv
                FO4_voice_folder = matching_row_by_voicemodel['voice_file_name'].iloc[0]
            else:
                FO4_voice_folder = voice_model.replace(' ','')
        except: # assume it is simply the voice_model name without spaces
            FO4_voice_folder = voice_model.replace(' ','')
        
        character_info = {
            'name': name,
            'bio': f'You are a {"male" if actor_sex==0 else "female"} {actor_race if actor_race.lower() != name.lower() else ""} {name}.',
            'voice_model': voice_model,
            'advanced_voice_model': '',
            'fallout4_voice_folder': FO4_voice_folder,
        }

        return character_info
    
    @utils.time_it
    def prepare_sentence_for_game(self, queue_output: sentence, context_of_conversation: context, config: ConfigLoader, topicID: int):
        audio_file = queue_output.voice_file
        fuz_file = audio_file.replace(".wav",".fuz")
        speaker = queue_output.speaker

        lip_name = "00001ED2_1"
        voice_name = "MantellaVoice00"

        if not os.path.exists(audio_file):
            return
        mod_folder = config.mod_path
        
        # subtitle = queue_output.sentence
        # Copy FaceFX generated FUZ file
        try:
            fuz_filepath = os.path.normpath(f"{mod_folder}/{voice_name}/{lip_name}.fuz")
            shutil.copyfile(fuz_file, fuz_filepath)
        except Exception as e:
            # only warn on failure
            logging.warning(e)

        self.__last_played_voiceline = queue_output.voice_file
        logging.info(f"{speaker.name}: {queue_output.text}")

    @utils.time_it
    def __delete_last_played_voiceline(self):
        if self.__last_played_voiceline:
            if os.path.exists(self.__last_played_voiceline):
                os.remove(self.__last_played_voiceline)
                self.__last_played_voiceline = None

    @utils.time_it
    def is_sentence_allowed(self, text: str, count_sentence_in_text: int) -> bool:
        return True
    
    @utils.time_it
    def get_weather_description(self, weather_attributes: dict[str, Any]) -> str:
        """Returns a description of the current weather that can be used in the prompts

        Args:
            weather_attributes (dict[str, Any]): The json of weather attributes as transferred by the respective game

        Returns:
            str: A prose description of the weather for the LLM
        """
        return ""

    MALE_VOICE_MODELS_XVASYNTH: dict[str, str] = {
        'AssaultronRace':	'robot_assaultron',
        'DLC01RoboBrainRace':	'robot_mrgutsy',
        'DLC02HandyRace':	'robot_mrhandy',
        'DLC02FeralGhoulRace':	'maleghoul',
        'DLC03_SynthGen2RaceDiMa':	'dima',
        'DLC03RoboBrainRace':	'robot_mrgutsy',
        'EyeBotRace':	'robot_assaultron',
        'GhoulRace':	'maleghoul',
        'FeralGhoulRace':	'maleghoul',
        'FeralGhoulGlowingRace':	'maleghoul',
        'HumanRace':	'maleboston',
        'ProtectronRace':	'robot_assaultron',
        'SupermutantBehemothRace':	'supermutant03',
        'SuperMutantRace':	'supermutant',
        'SynthGen1Race':	'gen1synth01',
        'SynthGen2Race':	'gen1synth01',
        'TurretBubbleRace':	'Dima',
        'TurretTripodRace':	'Dima',
        'TurretWorkshopRace':	'Dima',
    }
    FEMALE_VOICE_MODELS_XVASYNTH: dict[str, str]  = {
        'AssaultronRace':	'robotcompanionfemalprocessed',
        'DLC01RoboBrainRace':	'robotcompanionfemaledefault',
        'DLC02HandyRace':	'robotcompanionfemaledefault',
        'DLC02FeralGhoulRace':	'femaleghoul',
        'DLC03_SynthGen2RaceDiMa':	'robotcompanionfemaledefault',
        'DLC03RoboBrainRace':	'robotcompanionfemaledefault',
        'EyeBotRace':	'robotcompanionfemalprocessed',
        'GhoulRace':	'femaleghoul',
        'FeralGhoulRace':	'femaleghoul',
        'FeralGhoulGlowingRace':	'femaleghoul',
        'HumanRace':	'femaleboston',
        'ProtectronRace':	'robotcompanionfemalprocessed',
        'SupermutantBehemothRace':	'supermutant03',
        'SuperMutantRace':	'supermutant',
        'SynthGen1Race':	'robotcompanionfemalprocessed',
        'SynthGen2Race':	'robotcompanionfemalprocessed',
        'TurretBubbleRace':	'Dima',
        'TurretTripodRace':	'Dima',
        'TurretWorkshopRace':	'Dima',
    }
    MALE_VOICE_MODELS_NONXVASYNTH: dict[str, str] = {
        'AssaultronRace':	'robotassaultron',
        'DLC01RoboBrainRace':	'robotmrgutsy',
        'DLC02HandyRace':	'robotmrhandy',
        'DLC02FeralGhoulRace':	'maleghoul',
        'DLC03_SynthGen2RaceDiMa':	'dlc03maledima',
        'DLC03RoboBrainRace':	'robotmrgutsy',
        'EyeBotRace':	'robotassaultron',
        'GhoulRace':	'maleghoul',
        'FeralGhoulRace':	'maleghoul',
        'FeralGhoulGlowingRace':	'maleghoul',
        'HumanRace':	'maleboston',
        'ProtectronRace':	'robotassaultron',
        'SupermutantBehemothRace':	'crsupermutant03',
        'SuperMutantRace':	'crsupermutant',
        'SynthGen1Race':	'synthgen1male01',
        'SynthGen2Race':	'synthgen1male02',
        'TurretBubbleRace':	'dlc03maledima',
        'TurretTripodRace':	'dlc03maledima',
        'TurretWorkshopRace':	'dlc03maledima',
    }
    FEMALE_VOICE_MODELS_NONXVASYNTH: dict[str, str] = {
        'AssaultronRace':	'dlc01robotcompanionfemaleprocessed',
        'DLC01RoboBrainRace':	'dlc01robotcompanionfemaledefault',
        'DLC02HandyRace':	'dlc01robotcompanionfemaledefault',
        'DLC02FeralGhoulRace':	'femaleghoul',
        'DLC03_SynthGen2RaceDiMa':	'dlc01robotcompanionfemaledefault',
        'DLC03RoboBrainRace':	'dlc01robotcompanionfemaledefault',
        'EyeBotRace':	'dlc01robotcompanionfemaleprocessed',
        'GhoulRace':	'femaleghoul',
        'FeralGhoulRace':	'femaleghoul',
        'FeralGhoulGlowingRace':	'femaleghoul',
        'HumanRace':	'femaleboston',
        'ProtectronRace':	'dlc01robotcompanionfemaleprocessed',
        'SupermutantBehemothRace':	'crsupermutant03',
        'SuperMutantRace':	'crsupermutant',
        'SynthGen1Race':	'synthgen1male01',
        'SynthGen2Race':	'synthgen1male02',
        'TurretBubbleRace':	'dlc03maledima',
        'TurretTripodRace':	'dlc03maledima',
        'TurretWorkshopRace':	'dlc03maledima',
    }