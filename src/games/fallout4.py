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
    WAV_FILE: str  = f'MantellaDi_MantellaDialogu_00001D8B_1.wav' #not used anymore since FO4 caches audio in a way that prevent wav file substitutions while the game is running
    LIP_FILE: str  = f'00001ED2_1.lip'
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
        self.create_all_voice_folders(self.__config)
        self.__last_played_voiceline: str | None = None

    def create_all_voice_folders(self, config: ConfigLoader):
        all_voice_folders = self.character_df["fallout4_voice_folder"]
        all_voice_folders = all_voice_folders.loc[all_voice_folders.notna()]
        set_of_voice_folders = set()
        for voice_folder in all_voice_folders:
            voice_folder = str.strip(voice_folder)
            if voice_folder and not set_of_voice_folders.__contains__(voice_folder):
                set_of_voice_folders.add(voice_folder)
                in_game_voice_folder_path = f"{config.mod_path}/{voice_folder}/"
                if not os.path.exists(in_game_voice_folder_path):
                    os.mkdir(in_game_voice_folder_path)
                    example_folder = f"{config.mod_path}/maleboston/"
                    for file_name in os.listdir(example_folder):
                        source_file_path = os.path.join(example_folder, file_name)

                        if os.path.isfile(source_file_path):
                            shutil.copy(source_file_path, in_game_voice_folder_path)

    def load_external_character_info(self, id: str, name: str, race: str, gender: int, ingame_voice_model: str) -> external_character_info:
        character_info, is_generic_npc = self.find_character_info(id, name, race, gender, ingame_voice_model)
        actor_voice_model_name = ingame_voice_model.split('<')[1].split(' ')[0]

        return external_character_info(name, is_generic_npc, character_info["bio"], actor_voice_model_name, character_info['voice_model'], character_info['fallout4_voice_folder'], character_info['advanced_voice_model'], character_info.get('voice_accent', None)) 
    
    def load_unnamed_npc(self, name: str, race: str, gender: int, ingame_voice_model:str) -> dict[str, Any]:
        """Load generic NPC if character cannot be found in fallout4_characters.csv"""
        # unknown == I couldn't find the IDs for these voice models

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

        actor_race = race
        actor_sex = gender

        logging.log(23, f"Current voice actor is voice model {actor_voice_model_name} with ID {actor_voice_model_id} gender {actor_sex} race {actor_race} ")

        voice_model = ''
        matching_row=''
        FO4_voice_folder=''
        # Search for the Matching 'voice_ID'
        matching_row = self.__FO4_Voice_folder_and_models_df[self.__FO4_Voice_folder_and_models_df['voice_ID'] == actor_voice_model_id]

        # Return the Matching Row's Values
        if not matching_row.empty:
            # Assuming there's only one match, get the value from the 'voice_model' column
            voice_model = matching_row['voice_model'].iloc[0]
            FO4_voice_folder = matching_row['voice_file_name'].iloc[0]
            logging.log(23, f"Matched voice model with ID to {FO4_voice_folder}")  # Or use the variable as needed
        else:
            logging.log(23, "No matching voice ID found. Attempting voice_file_name match.")
      
        if voice_model == '':
            # If no match by 'voice_ID' and not found in , search by 'voice_model' (actor_voice_model_name)
            matching_row_by_name = self.__FO4_Voice_folder_and_models_df[self.__FO4_Voice_folder_and_models_df['voice_file_name'].str.lower() == actor_voice_model_name.lower()]
            if not matching_row_by_name.empty:
                # If there is a match, set 'voice_model' to 'actor_voice_model_name'
                voice_model = matching_row_by_name['voice_model'].iloc[0]
                FO4_voice_folder = matching_row_by_name['voice_file_name'].iloc[0]
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
        if FO4_voice_folder == '':
            try: # search for relevant FO4_Voice_folder_and_models_df for voice_model
                matching_row_by_voicemodel = self.__FO4_Voice_folder_and_models_df[self.__FO4_Voice_folder_and_models_df['voice_model'].str.lower() == voice_model.lower()]
                if not matching_row_by_voicemodel.empty:
                    # FO4_voice_folder becomes the matching row of FO4_Voice_folder_XVASynth_matches.csv
                    FO4_voice_folder = matching_row_by_voicemodel['voice_file_name'].iloc[0]
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
        self.__delete_last_played_voiceline()

        audio_file = queue_output.voice_file
        if not os.path.exists(audio_file):
            return
        mod_folder = config.mod_path
        # subtitle = queue_output.sentence
        speaker: Character = queue_output.speaker
        if config.add_voicelines_to_all_voice_folders:
            for sub_folder in os.scandir(mod_folder):
                if not sub_folder.is_dir():
                    continue
                # Copy FaceFX generated LIP file
                try:
                    shutil.copyfile(audio_file.replace(".wav", ".lip"), f"{sub_folder.path}/{self.LIP_FILE}")
                except Exception as e:
                    # only warn on failure
                    logging.warning(e)
        else:
            # Copy FaceFX generated LIP file
            try:
                voice_folder_path = f"{mod_folder}/{speaker.in_game_voice_model}"
                if not os.path.exists(voice_folder_path):
                    os.makedirs(voice_folder_path)
                shutil.copyfile(audio_file.replace(".wav", ".lip"), f"{voice_folder_path}/{self.LIP_FILE}")
            except Exception as e:
                logging.error(f"Failed to create directory or copy lip file: {e}")

        logging.log(23, f"{speaker.name} should speak")

        player_pos_x: float | None = context_of_conversation.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_PLAYERPOSX)
        player_pos_y: float | None = context_of_conversation.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_PLAYERPOSY)
        player_rot: float | None = context_of_conversation.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_PLAYERROT)
        speaker_pos_x: float | None =  speaker.get_custom_character_value(self.KEY_ACTOR_CUSTOMVALUES_POSX)
        speaker_pos_y: float | None = speaker.get_custom_character_value(self.KEY_ACTOR_CUSTOMVALUES_POSY)
        if player_pos_x and player_pos_y and player_rot and speaker_pos_x and speaker_pos_y:
            player_pos: tuple[float, float] = (float(player_pos_x), float(player_pos_y))
            speaker_pos: tuple[float,float] = (float(speaker_pos_x), float(speaker_pos_y))
            self.__playback.play_adjusted_volume(queue_output, speaker_pos, player_pos, float(player_rot))
            self.__last_played_voiceline = queue_output.voice_file

    def __delete_last_played_voiceline(self):
        if self.__last_played_voiceline:
            if os.path.exists(self.__last_played_voiceline):
                os.remove(self.__last_played_voiceline)
                self.__last_played_voiceline = None

    def is_sentence_allowed(self, text: str, count_sentence_in_text: int) -> bool:
        return True
    
    def get_weather_description(self, weather_attributes: dict[str, Any]) -> str:
        """Returns a description of the current weather that can be used in the prompts

        Args:
            weather_attributes (dict[str, Any]): The json of weather attributes as transferred by the respective game

        Returns:
            str: A prose description of the weather for the LLM
        """
        return ""

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