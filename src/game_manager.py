import os
import shutil
import pandas as pd
import logging
from typing import Any, Hashable
from src.conversation.action import action
from src.llm.sentence import sentence
from src.output_manager import ChatManager
from src.remember.remembering import remembering
from src.remember.summaries import summaries
from src.config_loader import ConfigLoader
from src.llm.openai_client import openai_client
from src.conversation.conversation import conversation
from src.conversation.context import context
from src.character_manager import Character
import src.utils as utils
from src.http.communication_constants import communication_constants as comm_consts

class CharacterDoesNotExist(Exception):
    """Exception raised when NPC name cannot be found in skyrim_characters.csv/fallout4_characters.csv"""
    pass


class GameStateManager:
    TOKEN_LIMIT_PERCENT: float = 0.45

    WAV_FILE = f'MantellaDi_MantellaDialogu_00001D8B_1.wav'
    LIP_FILE = f'MantellaDi_MantellaDialogu_00001D8B_1.lip'


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

    def __init__(self, chat_manager: ChatManager, config: ConfigLoader, language_info: dict[Hashable, str], client: openai_client, character_df: pd.DataFrame):        
        self.__config: ConfigLoader = config
        self.__language_info: dict[Hashable, str] = language_info 
        self.__client: openai_client = client
        self.__chat_manager: ChatManager = chat_manager
        self.__rememberer: remembering = summaries(config.memory_prompt, config.resummarize_prompt, client, language_info['language'])
        self.__character_df: pd.DataFrame = character_df
        self.__talk: conversation | None = None
        self.__actions: list[action] =  [action(comm_consts.ACTION_NPC_OFFENDED, config.offended_npc_response, f"The player offended the NPC"),
                                                action(comm_consts.ACTION_NPC_FORGIVEN, config.forgiven_npc_response, f"The player made up with the NPC"),
                                                action(comm_consts.ACTION_NPC_FOLLOW, config.follow_npc_response, f"The NPC is willing to follow the player")]

    ###### react to calls from the game #######
    def start_conversation(self, inputJson: dict[str, Any]) -> dict[str, Any]:
        if self.__talk: #This should only happen if game and server are out of sync due to some previous error -> close conversation and start a new one
            self.__talk.end()
            self.__talk = None
        context_for_conversation = context(self.__config, self.__rememberer, self.__language_info, self.__client.is_text_too_long)
        self.__talk = conversation(context_for_conversation, self.__chat_manager, self.__rememberer, self.__client.are_messages_too_long, self.__actions)
        self.__update_context(inputJson)
        self.__talk.start_conversation()
        
        return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTTYPE_STARTCONVERSATIONCOMPLETED}
    
    def continue_conversation(self, inputJson: dict[str, Any]) -> dict[str, Any]:
        if(not self.__talk ):
            return self.error_message("No running conversation at this point")
        
        self.__update_context(inputJson)
        
        if inputJson.__contains__(comm_consts.KEY_REQUEST_EXTRA_ACTIONS):
            extra_actions: list[str] = inputJson[comm_consts.KEY_REQUEST_EXTRA_ACTIONS]
            if extra_actions.__contains__(comm_consts.ACTION_RELOADCONVERSATION):
                self.__talk.reload_conversation()

        replyType, sentence_to_play = self.__talk.continue_conversation()
        reply: dict[str, Any] = {comm_consts.KEY_REPLYTYPE: replyType}
        if sentence_to_play:
            self.save_files_to_voice_folders(sentence_to_play)
            reply[comm_consts.KEY_REPLYTYPE_NPCTALK] = self.sentence_to_json(sentence_to_play)
        return reply

    def player_input(self, inputJson: dict[str, Any]) -> dict[str, Any]:
        if(not self.__talk ):
            return self.error_message("No running conversation at this point")
        
        player_text: str = inputJson[comm_consts.KEY_REQUESTTYPE_PLAYERINPUT]
        self.__update_context(inputJson)
        self.__talk.process_player_input(player_text)
        return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_NPCTALK}

    def end_conversation(self, inputJson: dict[str, Any]) -> dict[str, Any]:
        if(self.__talk):
            self.__talk.end()
            self.__talk = None
        return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_ENDCONVERSATION}

    ####### JSON constructions #########

    def character_to_json(self, character_to_jsonfy: Character) -> dict[str, Any]:
        return {
            comm_consts.KEY_ACTOR_ID: character_to_jsonfy.Id,
            comm_consts.KEY_ACTOR_NAME: character_to_jsonfy.Name,
        }
    
    def sentence_to_json(self, sentence_to_prepare: sentence) -> dict[str, Any]:
        return {
            comm_consts.KEY_ACTOR_SPEAKER: sentence_to_prepare.Speaker.Name, #self.character_to_json(sentence_to_prepare.Speaker),
            comm_consts.KEY_ACTOR_LINETOSPEAK: sentence_to_prepare.Sentence,
            comm_consts.KEY_ACTOR_VOICEFILE: self.WAV_FILE,
            comm_consts.KEY_ACTOR_DURATION: sentence_to_prepare.Voice_line_duration,
            comm_consts.KEY_ACTOR_ACTIONS: sentence_to_prepare.Actions
        }

    ##### utils #######

    def __update_context(self,  json: dict[str, Any]):
        if self.__talk:
            for actorJson in json[comm_consts.KEY_ACTORS]:
                actor: Character | None = self.load_character(actorJson)
                if actor:
                    self.__talk.add_or_update_character(actor)
            location: str = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_LOCATION]
            time: int = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_TIME]
            ingame_events: list[str] = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_INGAMEEVENTS]
            self.__talk.update_context(location, time, ingame_events)

    @utils.time_it
    def save_files_to_voice_folders(self, queue_output: sentence):
        """Save voicelines and subtitles to the correct game folders"""

        audio_file = queue_output.Voice_file
        mod_folder = self.__config.mod_path
        # subtitle = queue_output.Sentence
        speaker: Character = queue_output.Speaker
        if self.__config.add_voicelines_to_all_voice_folders == '1':
            for sub_folder in os.scandir(self.__config.mod_path):
                if sub_folder.is_dir():
                    shutil.copyfile(audio_file, f"{sub_folder.path}/{self.WAV_FILE}")
                    shutil.copyfile(audio_file.replace(".wav", ".lip"), f"{sub_folder.path}/{self.LIP_FILE}")
        else:
            shutil.copyfile(audio_file, f"{mod_folder}/{speaker.In_game_voice_model}/{self.WAV_FILE}")
            shutil.copyfile(audio_file.replace(".wav", ".lip"), f"{mod_folder}/{speaker.In_game_voice_model}/{self.LIP_FILE}")
        
        os.remove(audio_file)
        os.remove(audio_file.replace(".wav", ".lip"))

        logging.info(f"{speaker.Name} (character {speaker.Name}) should speak")
        # if self.character_num == 0:
        #     self.game_state_manager.write_game_info('_mantella_say_line', subtitle.strip())
        # else:
        #     say_line_file = '_mantella_say_line_'+str(self.character_num+1)
        #     self.game_state_manager.write_game_info(say_line_file, subtitle.strip())


    # def debugging_setup(self, debug_character_name, character_df):
    #     """Select character based on debugging parameters"""

    #     # None == in-game character chosen by spell
    #     if debug_character_name == 'None':
    #         character_id, character_name = self.load_character_name_id()
    #     else:
    #         character_name = debug_character_name
    #         debug_character_name = ''

    #     character_name, character_id, location, in_game_time = self.write_dummy_game_info(character_name, character_df)

    #     return character_name, character_id, location, in_game_time
    
    
    def load_unnamed_npc(self, name: str, race: str, gender: int, ingame_voice_model:str, character_df: pd.DataFrame):
        """Load generic NPC if character cannot be found in skyrim_characters.csv"""
        # unknown == I couldn't find the IDs for these voice models
        voice_model_ids = {
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

        actor_voice_model = ingame_voice_model
        actor_voice_model_id = actor_voice_model.split('(')[1].split(')')[0]
        actor_voice_model_name = actor_voice_model.split('<')[1].split(' ')[0]

        actor_race = race
        actor_race = actor_race.split('<')[1].split(' ')[0]

        actor_sex = gender

        voice_model = ''
        for key in voice_model_ids:
            # using endswith because sometimes leading zeros are ignored
            if actor_voice_model_id.endswith(key):
                voice_model = voice_model_ids[key]
                break
        
        # if voice_model not found in the voice model ID list
        if voice_model == '':
            try: # search for voice model in skyrim_characters.csv
                voice_model = character_df.loc[character_df['skyrim_voice_folder'].astype(str).str.lower()==actor_voice_model_name.lower(), 'voice_model'].values[0]
            except: # guess voice model based on sex and race
                if actor_sex == '1':
                    try:
                        voice_model = self.FEMALE_VOICE_MODELS[actor_race]
                    except:
                        voice_model = 'Female Nord'
                else:
                    try:
                        voice_model = self.MALE_VOICE_MODELS[actor_race]
                    except:
                        voice_model = 'Male Nord'

        try: # search for relavant skyrim_voice_folder for voice_model
            skyrim_voice_folder = character_df.loc[character_df['voice_model'].astype(str).str.lower()==voice_model.lower(), 'skyrim_voice_folder'].values[0]
        except: # assume it is simply the voice_model name without spaces
            skyrim_voice_folder = voice_model.replace(' ','')
        
        character_info = {
            'name': name,
            'bio': f'You are a {name}',
            'voice_model': voice_model,
            'skyrim_voice_folder': skyrim_voice_folder,
        }

        return character_info
    
    def FO4_load_unnamed_npc(self, character_name, character_df, FO4_Voice_folder_and_models_df):
        """Load generic NPC if character cannot be found in fallout4_characters.csv"""
        # unknown == I couldn't find the IDs for these voice models

        actor_voice_model = self.load_data_when_available('_mantella_actor_voice', '')
        actor_voice_model_id = actor_voice_model.split('(')[1].split(')')[0]
        actor_voice_model_name = actor_voice_model.split('<')[1].split(' ')[0]

        #make the substitutions below to bypass non-functional XVASynth voice models: RobotCompanionMaleDefault, RobotCompanionMaleProcessed,Gen1Synth02 & Gen1Synth03 
        if actor_voice_model_name in  ("DLC01RobotCompanionMaleDefault", "DLC01RobotCompanionMaleProcessed"):
            actor_voice_model_name='robot_assaultron'
            actor_voice_model_id='robot_assaultron'
        if actor_voice_model_name in  ("SynthGen1Male02", "SynthGen1Male03"):
            actor_voice_model_name='gen1synth01'
            actor_voice_model_id='000BBBF0'

        actor_race = self.load_data_when_available('_mantella_actor_race', '')
        actor_race = actor_race.split('<')[1].split(' ')[0]

        actor_sex = self.load_data_when_available('_mantella_actor_sex', '')

        logging.info(f"Current voice actor is voice model {actor_voice_model_name} with ID {actor_voice_model_id} gender {actor_sex} race {actor_race} ")

        voice_model = ''
        matching_row=''
        FO4_voice_folder=''
        # Search for the Matching 'voice_ID'
        matching_row = FO4_Voice_folder_and_models_df[FO4_Voice_folder_and_models_df['voice_ID'] == actor_voice_model_id]

        # Return the Matching Row's Values
        if not matching_row.empty:
            # Assuming there's only one match, get the value from the 'voice_model' column
            voice_model = matching_row['voice_model'].iloc[0]
            FO4_voice_folder = matching_row['voice_file_name'].iloc[0]
            logging.info(f"Matched voice model with ID to {FO4_voice_folder}")  # Or use the variable as needed
        else:
            logging.info("No matching voice ID found. Attempting voice_file_name match.")
      
        if voice_model == '':
            # If no match by 'voice_ID' and not found in , search by 'voice_model' (actor_voice_model_name)
            matching_row_by_name = FO4_Voice_folder_and_models_df[FO4_Voice_folder_and_models_df['voice_file_name'].str.lower() == actor_voice_model_name.lower()]
            if not matching_row_by_name.empty:
                # If there is a match, set 'voice_model' to 'actor_voice_model_name'
                voice_model = matching_row_by_name['voice_model'].iloc[0]
                FO4_voice_folder = matching_row_by_name['voice_file_name'].iloc[0]
            else:
                try: # search for voice model in fallout4_characters.csv
                    voice_model = character_df.loc[character_df['fallout4_voice_folder'].astype(str).str.lower()==actor_voice_model_name.lower(), 'voice_model'].values[0]
                except: 
                    #except then try to match using gender and race with pre-established dictionaries
                    if actor_sex == '1':
                        try:
                            voice_model = _FO4_female_voice_models[actor_race]
                        except:
                            voice_model = 'femaleboston'
                    else:
                        try:
                            voice_model = _FO4_male_voice_models[actor_race]
                        except:
                            voice_model = 'maleboston'
        if FO4_voice_folder == '':
            try: # search for relevant FO4_Voice_folder_and_models_df for voice_model
                matching_row_by_voicemodel = FO4_Voice_folder_and_models_df[FO4_Voice_folder_and_models_df['voice_model'].str.lower() == voice_model.lower()]
                if not matching_row_by_voicemodel.empty:
                    # FO4_voice_folder becomes the matching row of FO4_Voice_folder_XVASynth_matches.csv
                    FO4_voice_folder = matching_row_by_voicemodel['voice_file_name'].iloc[0]
            except: # assume it is simply the voice_model name without spaces
                FO4_voice_folder = voice_model.replace(' ','')
        
        character_info = {
            'name': character_name,
            'bio': f'You are a {character_name}',
            'voice_model': voice_model,
            'fallout4_voice_folder': FO4_voice_folder,
        }

        return character_info
    


    @utils.time_it
    def load_character(self, json: dict) -> Character | None:
        try:
            character_id = json[comm_consts.KEY_ACTOR_ID]
            character_name: str = json[comm_consts.KEY_ACTOR_NAME]
            gender: int = json[comm_consts.KEY_ACTOR_GENDER]
            race: str = json[comm_consts.KEY_ACTOR_RACE]
            actor_voice_model = json[comm_consts.KEY_ACTOR_VOICETYPE]
            actor_voice_model_name = actor_voice_model.split('<')[1].split(' ')[0]
            is_in_combat: bool = json[comm_consts.KEY_ACTOR_ISINCOMBAT]
            is_enemy: bool = json[comm_consts.KEY_ACTOR_ISENEMY]
            relationship_rank: int = json[comm_consts.KEY_ACTOR_RELATIONSHIPRANK]
            custom_values: dict[str, Any] = {}
            if json.__contains__(comm_consts.KEY_ACTOR_CUSTOMVALUES):
                custom_values = json[comm_consts.KEY_ACTOR_CUSTOMVALUES]
            is_generic_npc = False
            bio: str = ""
            voice_model: str = "MaleNord"
            is_player_character: bool = json[comm_consts.KEY_ACTOR_ISPLAYER]            
            if not is_player_character and self.__talk and not self.__talk.contains_character(character_id):#If this is not the player and the character has not already been loaded
                try: # load character from skyrim_characters.csv
                    character_info = self.__character_df.loc[self.__character_df['name'].astype(str).str.lower()==character_name.lower()].to_dict('records')[0]
                    bio = character_info["bio"]
                    voice_model = character_info['voice_model']
                except IndexError: # character not found
                    try: # try searching by ID
                        logging.info(f"Could not find {character_name} in skyrim_characters.csv. Searching by ID {character_id}...")
                        character_info = self.__character_df.loc[(self.__character_df['baseid_int'].astype(str)==character_id) | (self.__character_df['baseid_int'].astype(str)==character_id+'.0')].to_dict('records')[0]
                        is_generic_npc = False
                    except IndexError: # load generic NPC
                        logging.info(f"NPC '{character_name}' could not be found in 'skyrim_characters.csv'. If this is not a generic NPC, please ensure '{character_name}' exists in the CSV's 'name' column exactly as written here, and that there is a voice model associated with them.")
                        character_info = self.load_unnamed_npc(character_name, race, gender, actor_voice_model_name, self.__character_df)
                        is_generic_npc = True
            

            return Character(character_id,
                            character_name,
                            gender,
                            race,
                            is_player_character,
                            bio,
                            is_in_combat,
                            is_enemy,
                            relationship_rank,
                            is_generic_npc,
                            actor_voice_model_name,
                            voice_model,
                            custom_values)
        except CharacterDoesNotExist:                 
            logging.info('Restarting...')
            return None 
        
    def error_message(self, message: str) -> dict[str, Any]:
        return {
                comm_consts.KEY_REPLYTYPE: "error",
                "mantella_message": message
            }    

_FO4_male_voice_models = {
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
_FO4_female_voice_models = {
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

_FO4_male_voice_models = {
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
_FO4_female_voice_models = {
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