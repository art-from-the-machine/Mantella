import logging
import os
import shutil
from typing import Any
import pandas as pd
from src.http.file_communication_compatibility import file_communication_compatibility
from src.conversation.context import context
from src.audio.audio_playback import audio_playback
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
        self.__config: ConfigLoader = config
        encoding = utils.get_file_encoding(fallout4.FO4_XVASynth_file)
        self.__FO4_Voice_folder_and_models_df = pd.read_csv(fallout4.FO4_XVASynth_file, engine='python', encoding=encoding)
        self.__playback: audio_playback = audio_playback(config)
        self.__last_played_voiceline: str | None = None


    @utils.time_it
    def load_external_character_info(self, base_id: str, name: str, race: str, gender: int, ingame_voice_model: str) -> external_character_info:
        character_info, is_generic_npc = self.find_character_info(base_id, name, race, gender, ingame_voice_model)
        actor_voice_model_name = ingame_voice_model.split('<')[1].split(' ')[0]

        return external_character_info(name, is_generic_npc, character_info["bio"], actor_voice_model_name, character_info['voice_model'], character_info['fallout4_voice_folder'], character_info['advanced_voice_model'], character_info.get('voice_accent', None)) 
    
    @utils.time_it
    def find_best_voice_model(self, actor_race: str, actor_sex: int, ingame_voice_model: str) -> str:
        voice_model = ''

        actor_voice_model = ingame_voice_model
        actor_voice_model_id = actor_voice_model.split('(')[1].split(')')[0]
        actor_voice_model_name = actor_voice_model.split('<')[1].split(' ')[0]

        #make the substitutions below to bypass non-functional XVASynth voice models: RobotCompanionMaleDefault, RobotCompanionMaleProcessed,Gen1Synth02 & Gen1Synth03 
        if actor_voice_model_name in  ("DLC01RobotCompanionMaleDefault", "DLC01RobotCompanionMaleProcessed"):
            actor_voice_model_name='robot_assaultron'
            actor_voice_model_id='robot_assaultron'
        if actor_voice_model_name in  ("SynthGen1Male02", "SynthGen1Male03"):
            actor_voice_model_name='gen1synth01'
            actor_voice_model_id='000BBBF0'

        matching_row=''
        # Search for the Matching 'voice_ID'
        matching_row = self.__FO4_Voice_folder_and_models_df[self.__FO4_Voice_folder_and_models_df['voice_ID'] == actor_voice_model_id]

        # Return the Matching Row's Values
        if not matching_row.empty:
            # Assuming there's only one match, get the value from the 'voice_model' column
            voice_model = matching_row['voice_model'].iloc[0]
        else:
            logging.log(23, "No matching voice ID found. Attempting voice_file_name match.")
      
        if voice_model == '':
            # If no match by 'voice_ID' and not found in , search by 'voice_model' (actor_voice_model_name)
            matching_row_by_name = self.__FO4_Voice_folder_and_models_df[self.__FO4_Voice_folder_and_models_df['voice_file_name'].str.lower() == actor_voice_model_name.lower()]
            if not matching_row_by_name.empty:
                # If there is a match, set 'voice_model' to 'actor_voice_model_name'
                voice_model = matching_row_by_name['voice_model'].iloc[0]
            else:
                try: # search for voice model in fallout4_characters.csv
                    voice_model = self.character_df.loc[self.character_df['fallout4_voice_folder'].astype(str).str.lower()==actor_voice_model_name.lower(), 'voice_model'].values[0]
                except: 
                    modified_race_key = actor_race + "Race"
                    #except then try to match using gender and race with pre-established dictionaries
                    if actor_sex == 1:
                        try:
                            voice_model = fallout4.FEMALE_VOICE_MODELS[modified_race_key]
                        except:
                            voice_model = 'femaleboston'
                    else:
                        try:
                            voice_model = fallout4.MALE_VOICE_MODELS[modified_race_key]
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
    def prepare_sentence_for_game(self, queue_output: sentence, context_of_conversation: context, config: ConfigLoader):
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
        logging.info(f"{speaker.name}: {queue_output.sentence}")

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
    
    @property
    def extender_name(self) -> str:
        return 'F4SE'


    MALE_VOICE_MODELS: dict[str, str] = {
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
    FEMALE_VOICE_MODELS: dict[str, str]  = {
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