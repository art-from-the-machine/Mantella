import logging
import os
import shutil
from typing import Any
from src.conversation.context import context
from src.character_manager import Character
from src.config.config_loader import ConfigLoader
from src.llm.sentence import sentence
from src.games.external_character_info import external_character_info
from src.games.gameable import gameable
import src.utils as utils


class skyrim(gameable):
    WAV_FILE = f'MantellaDi_MantellaDialogu_00001D8B_1.wav'
    LIP_FILE = f'MantellaDi_MantellaDialogu_00001D8B_1.lip'

    def __init__(self, config: ConfigLoader):
        super().__init__('data/Skyrim/skyrim_characters.csv', "Skyrim")
        self.__create_all_voice_folders(config)

    def __create_all_voice_folders(self, config: ConfigLoader):
        all_voice_folders = self.character_df["skyrim_voice_folder"]
        all_voice_folders = all_voice_folders.loc[all_voice_folders.notna()]
        set_of_voice_folders = set()
        for voice_folder in all_voice_folders:
            voice_folder = str.strip(voice_folder)
            if voice_folder and not set_of_voice_folders.__contains__(voice_folder):
                set_of_voice_folders.add(voice_folder)
                in_game_voice_folder_path = f"{config.mod_path}/{voice_folder}/"
                if not os.path.exists(in_game_voice_folder_path):
                    os.mkdir(in_game_voice_folder_path)
                    example_folder = f"{config.mod_path}/MaleNord/"
                    for file_name in os.listdir(example_folder):
                        source_file_path = os.path.join(example_folder, file_name)

                        if os.path.isfile(source_file_path):
                            shutil.copy(source_file_path, in_game_voice_folder_path)

    def load_external_character_info(self, id: str, name: str, race: str, gender: int, ingame_voice_model: str) -> external_character_info:
        character_info, is_generic_npc = self.find_character_info(id, name, race, gender, ingame_voice_model)
        actor_voice_model_name = ingame_voice_model.split('<')[1].split(' ')[0]

        return external_character_info(name, is_generic_npc, character_info["bio"], actor_voice_model_name, character_info['voice_model'], character_info['skyrim_voice_folder'], character_info['advanced_voice_model'], character_info.get('voice_accent', None))

    def load_unnamed_npc(self, name: str, race: str, gender: int, ingame_voice_model:str) -> dict[str, Any]:
        """Load generic NPC if character cannot be found in skyrim_characters.csv"""
        # unknown == I couldn't find the IDs for these voice models
        
        actor_voice_model = ingame_voice_model
        actor_voice_model_id = actor_voice_model.split('(')[1].split(')')[0]
        actor_voice_model_name = actor_voice_model.split('<')[1].split(' ')[0]

        actor_race = race
        actor_sex = gender

        voice_model = ''

        for key in skyrim.VOICE_MODEL_IDS:
            # using endswith because sometimes leading zeros are ignored
            if actor_voice_model_id.endswith(key):
                voice_model = skyrim.VOICE_MODEL_IDS[key]
                break
        
        # if voice_model not found in the voice model ID list
        if voice_model == '':
            try: # search for voice model in skyrim_characters.csv
                voice_model = self.character_df.loc[self.character_df['skyrim_voice_folder'].astype(str).str.lower()==actor_voice_model_name.lower(), 'voice_model'].values[0]
            except: # guess voice model based on sex and race
                modified_race_key = actor_race + "Race"
                if actor_sex == 1:
                    try:
                        voice_model = self.FEMALE_VOICE_MODELS[modified_race_key]
                    except:
                        voice_model = 'Female Nord'
                else:
                    try:
                        voice_model = self.MALE_VOICE_MODELS[modified_race_key]
                    except:
                        voice_model = 'Male Nord'

        try: # search for relavant skyrim_voice_folder for voice_model
            skyrim_voice_folder = self.character_df.loc[self.character_df['voice_model'].astype(str).str.lower()==voice_model.lower(), 'skyrim_voice_folder'].values[0]
        except: # assume it is simply the voice_model name without spaces
            skyrim_voice_folder = voice_model.replace(' ','')
        
        character_info = {
            'name': name,
            'bio': f'You are a {name}',
            'voice_model': voice_model,
            'advanced_voice_model': '',
            'skyrim_voice_folder': skyrim_voice_folder,
        }

        return character_info
    
    @utils.time_it
    def prepare_sentence_for_game(self, queue_output: sentence, context_of_conversation: context, config: ConfigLoader):
        """Save voicelines and subtitles to the correct game folders"""

        audio_file = queue_output.voice_file
        if not os.path.exists(audio_file):
            return
        mod_folder = config.mod_path
        # subtitle = queue_output.sentence
        speaker: Character = queue_output.speaker
        if config.add_voicelines_to_all_voice_folders:
            for sub_folder in os.scandir(config.mod_path):
                if sub_folder.is_dir():
                    shutil.copyfile(audio_file, f"{sub_folder.path}/{self.WAV_FILE}")
                    shutil.copyfile(audio_file.replace(".wav", ".lip"), f"{sub_folder.path}/{self.LIP_FILE}")
        else:
            shutil.copyfile(audio_file, f"{mod_folder}/{speaker.in_game_voice_model}/{self.WAV_FILE}")
            shutil.copyfile(audio_file.replace(".wav", ".lip"), f"{mod_folder}/{speaker.in_game_voice_model}/{self.LIP_FILE}")
        
        os.remove(audio_file)
        os.remove(audio_file.replace(".wav", ".lip"))

        logging.log(23, f"{speaker.name} should speak")

    def is_sentence_allowed(self, text: str, count_sentence_in_text: int) -> bool:
        if ('assist' in text) and (count_sentence_in_text > 0):
            logging.log(23, f"'assist' keyword found. Ignoring sentence: {text.strip()}")
            return False
        return True
 
    MALE_VOICE_MODELS: dict[str, str] = {
        'ArgonianRace': 'Male Argonian',
        'BretonRace': 'Male Even Toned',
        'DarkElfRace': 'Male Dark Elf Commoner',
        'HighElfRace': 'Male Elf Haughty',
        'ImperialRace': 'Male Even Toned',
        'KhajiitRace': 'Male Khajit',
        'NordRace': 'Male Nord',
        'OrcRace': 'Male Orc',
        'RedguardRace': 'Male Even Toned',
        'WoodElfRace': 'Male Young Eager',
    }
    FEMALE_VOICE_MODELS: dict[str, str]  = {
        'ArgonianRace': 'Female Argonian',
        'BretonRace': 'Female Even Toned',
        'DarkElfRace': 'Female Dark Elf Commoner',
        'HighElfRace': 'Female Elf Haughty',
        'ImperialRace': 'Female Even Toned',
        'KhajiitRace': 'Female Khajit',
        'NordRace': 'Female Nord',
        'OrcRace': 'Female Orc',
        'RedguardRace': 'Female Sultry',
        'WoodElfRace': 'Female Young Eager',
    }
    VOICE_MODEL_IDS = {
        '0002992B':	'Dragon',
        '2470000': 'Male Dark Elf Commoner',
        '18469': 'Male Dark Elf Cynical',
        '00013AEF':	'Female Argonian',
        '00013AE3':	'Female Commander',
        '00013ADE':	'Female Commoner',
        '00013AE4':	'Female Condescending',
        '00013AE5': 'Female Coward',
        '00013AF3':	'Female Dark Elf',
        'unknown': 'Female Dark Elf Commoner',
        '00013AF1':	'Female Elf Haughty',
        '00013ADD':	'Female Even Toned',
        '00013AED':	'Female Khajiit',
        '00013AE7':	'Female Nord',
        '00013AE2':	'Female Old Grumpy',
        '00013AE1':	'Female Old Kindly',
        '00013AEB':	'Female Orc',
        '00013BC3':	'Female Shrill',
        '00012AE0':	'Female Sultry',
        'unknown': 'Female Vampire',
        '00013ADC':	'Female Young Eager',
        '00013AEE':	'Male Argonian',
        'unknown': 'Male Bandit',
        '00013ADA':	'Male Brute',
        '00013AD8':	'Male Commander',
        '00013AD3': 'Male Commoner',
        '000EA266': 'Male Commoner Accented',
        '00013AD9':	'Male Condescending',
        '00013ADB':	'Male Coward',
        '00013AF2':	'Male Dark Elf Commoner',
        'unknown': 'Male Dark Elf Cynical',
        '00013AD4':	'Male Drunk',
        '00013AF0':	'Male Elf Haughty',
        '00013AD2':	'Male Even Toned',
        '000EA267':	'Male Even Toned Accented',
        '000AA8D3':	'Male Guard', # not in csv
        '00013AEC':	'Male Khajiit',
        '00013AE6':	'Male Nord',
        '000E5003':	'Male Nord Commander',
        '00013AD7':	'Male Old Grumpy',
        '00013AD6':	'Male Old Kindly',
        '00013AEA':	'Male Orc',
        '00013AD5':	'Male Sly Cynical',
        '0001B55F':	'Male Soldier',
        'unknown': 'Male Vampire',
        'unknown': 'Male Warlock',
        '00012AD1':	'Male Young Eager',
    }
