import logging
from src.llm.messages import user_message
import src.utils as utils
import time
import random

class CharacterDoesNotExist(Exception):
    """Exception raised when NPC name cannot be found in skyrim_characters.csv/fallout4_characters.csv"""
    pass


class GameStateManager:
    def __init__(self, game_path, game, synthesizer):
        self.game_path = game_path
        self.prev_game_time = ''
        self.game = game
        self.synthesizer = synthesizer

    def write_game_info(self, text_file_name, text):
        max_attempts = 2
        delay_between_attempts = 5

        for attempt in range(max_attempts):
            try:
                with open(f'{self.game_path}/{text_file_name}.txt', 'w', encoding='utf-8') as f:
                    f.write(text)
                break
            except PermissionError:
                print(f'Permission denied to write to {text_file_name}.txt. Retrying...')
                if attempt + 1 == max_attempts:
                    raise
                else:
                    time.sleep(delay_between_attempts)
        return None
    

    def load_data_when_available(self, text_file_name, text):
        while text == '':
            with open(f'{self.game_path}/{text_file_name}.txt', 'r', encoding='utf-8') as f:
                text = f.readline().strip()
            # decrease stress on CPU while waiting for file to populate
            time.sleep(0.01)
        return text
    
    def wait_for_conversation_init(self):
        self.load_data_when_available('_mantella_current_actor_id', '')

    @utils.time_it
    def reset_game_info(self):
        self.write_game_info('_mantella_current_actor', '')
        character_name = ''

        self.write_game_info('_mantella_current_actor_id', '')
        character_id = ''

        self.write_game_info('_mantella_current_location', '')
        location = ''

        self.write_game_info('_mantella_in_game_time', '')
        in_game_time = ''

        self.write_game_info('_mantella_active_actors', '')

        self.write_game_info('_mantella_in_game_events', '')

        self.write_game_info('_mantella_status', 'False')

        self.write_game_info('_mantella_actor_is_enemy', 'False')
        self.write_game_info('_mantella_actor_is_in_combat', 'False')

        self.write_game_info('_mantella_actor_relationship', '')

        self.write_game_info('_mantella_character_selection', 'True')

        self.write_game_info('_mantella_say_line', 'False')
        self.write_game_info('_mantella_say_line_2', 'False')
        self.write_game_info('_mantella_say_line_3', 'False')
        self.write_game_info('_mantella_say_line_4', 'False')
        self.write_game_info('_mantella_say_line_5', 'False')
        self.write_game_info('_mantella_say_line_6', 'False')
        self.write_game_info('_mantella_say_line_7', 'False')
        self.write_game_info('_mantella_say_line_8', 'False')
        self.write_game_info('_mantella_say_line_9', 'False')
        self.write_game_info('_mantella_say_line_10', 'False')
        self.write_game_info('_mantella_actor_count', '0')

        self.write_game_info('_mantella_player_input', '')

        self.write_game_info('_mantella_aggro', '')

        self.write_game_info('_mantella_radiant_dialogue', 'False')
        self.write_game_info('_mantella_audio_ready', 'False')

        return character_name, character_id, location, in_game_time
    
    
    def write_dummy_game_info(self, character_name, character_df):
        """Write fake data to game files when debugging"""
        logging.info(f'Writing dummy game status for debugging character {character_name}')
        actor_sex = random.choice(['Female','Male'])
        actor_race = random.choice(['ArgonianRace','BretonRace','DarkElfRace','HighElfRace','ImperialRace','KhajiitRace','NordRace','OrcRace','RedguardRace','WoodElfRace'])
        try:
            actor_sex = character_df.loc[character_df['name'].astype(str).str.lower()==character_name.lower(), 'gender'].values[0]
        except:
            pass
        try:
            actor_race = character_df.loc[character_df['name'].astype(str).str.lower()==character_name.lower(), 'race'].values[0]
        except:
            pass
        self.write_game_info('_mantella_actor_race', f'<{actor_race}')
        self.write_game_info('_mantella_actor_sex', actor_sex)
        voice_model = random.choice(['Female Nord', 'Male Nord'])
        try: # search for voice model in skyrim_characters.csv/fallout4_characters.csv"
            voice_model = character_df.loc[character_df['name'].astype(str).str.lower()==character_name.lower(), 'voice_model'].values[0]
        except: # guess voice model based on sex and race
            if actor_sex == 'Female':
                try:
                    voice_model = _female_voice_models[actor_race]
                except:
                    voice_model = 'Female Nord'
            else:
                try:
                    voice_model = _male_voice_models[actor_race]
                except:
                    voice_model = 'Male Nord'

        self.write_game_info('_mantella_actor_voice', f'<{voice_model} (0000)>')

        relationship = '0'
        self.write_game_info('_mantella_actor_relationship', relationship)

        self.write_game_info('_mantella_current_actor', character_name)

        character_id = '0'
        try: # search for voice model in skyrim_characters.csv/fallout4_characters.csv"
            voice_model = character_df.loc[character_df['name'].astype(str).str.lower()==character_name.lower(), 'base_id_int'].values[0]
        except:
            pass
        self.write_game_info('_mantella_current_actor_id', str(character_id))

        if self.game == "Fallout4" or self.game == "Fallout4VR":
            location = 'the Commonwealth'
        else:
            location = 'Skyrim'
        self.write_game_info('_mantella_current_location', location)
        
        in_game_time = '12'
        self.write_game_info('_mantella_in_game_time', in_game_time)
        self.write_game_info('_mantella_actor_count', '1')
        return character_name, character_id, location, in_game_time
    

    def load_character_name_id(self):
        """Wait for character ID to populate then load character name"""

        character_id = self.load_data_when_available('_mantella_current_actor_id', '')
        try:
            character_id = hex(int(character_id)).replace('x','')
        except:
            logging.warning('Could not find ID for the selected NPC')
        
        time.sleep(0.5) # wait for file to register
        with open(f'{self.game_path}/_mantella_current_actor.txt', 'r') as f:
            character_name = f.readline().strip()
        
        return character_id, character_name
    
    
    def debugging_setup(self, debug_character_name, character_df):
        """Select character based on debugging parameters"""

        # None == in-game character chosen by spell
        if debug_character_name == 'None':
            character_id, character_name = self.load_character_name_id()
        else:
            character_name = debug_character_name
            debug_character_name = ''

        character_name, character_id, location, in_game_time = self.write_dummy_game_info(character_name, character_df)

        return character_name, character_id, location, in_game_time
    

    def select_generic_voice(self, actor_sex, actor_race):
        if 'skyrim' in self.game.lower():
            if actor_sex == '1':
                try:
                    voice_model = _female_voice_models[actor_race]
                except:
                    voice_model = 'Female Nord'
            else:
                try:
                    voice_model = _male_voice_models[actor_race]
                except:
                    voice_model = 'Male Nord'
        else:
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

        return voice_model
    
    
    def skyrim_load_unnamed_npc(self, character_name, character_df):
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

        actor_voice_model = self.load_data_when_available('_mantella_actor_voice', '')
        actor_voice_model_id = actor_voice_model.split('(')[1].split(')')[0]
        actor_voice_model_name = actor_voice_model.split('<')[1].split(' ')[0]

        actor_race = self.load_data_when_available('_mantella_actor_race', '')
        actor_race = actor_race.split('<')[1].split(' ')[0]

        actor_sex = self.load_data_when_available('_mantella_actor_sex', '')

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
                voice_model = self.select_generic_voice(actor_sex, actor_race)

        try: # search for relevant skyrim_voice_folder for voice_model
            skyrim_voice_folder = character_df.loc[character_df['voice_model'].astype(str).str.lower()==voice_model.lower(), 'skyrim_voice_folder'].values[0]
        except: # assume it is simply the voice_model name without spaces
            skyrim_voice_folder = voice_model.replace(' ','')
        
        character_info = {
            'name': character_name,
            'bio': f'You are a {character_name}',
            'voice_model': voice_model,
            'advanced_voice_model': '',
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
                    voice_model = self.select_generic_voice(actor_sex, actor_race)
        
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
            'advanced_voice_model': '',
            'fallout4_voice_folder': FO4_voice_folder,
        }

        return character_info
    


    @utils.time_it
    def load_game_state(self, debug_mode, debug_character_name, character_df, character_name, character_id, location, in_game_time, FO4_Voice_folder_and_models_df):
        """Load game variables from _mantella_ files in Skyrim/Fallout4 folder (data passed by the Mantella spell)"""

        if debug_mode == '1':
            character_name, character_id, location, in_game_time = self.debugging_setup(debug_character_name, character_df)
        
        # tell Skyrim/Fallout4 papyrus script to start waiting for voiceline input
        self.write_game_info('_mantella_end_conversation', 'False')
        character_id, character_name = self.load_character_name_id()

        def find_character_info(character_name, character_id, character_race, character_df):
            full_id_len = 6
            full_id_search = character_id[-full_id_len:]
            partial_id_len = 3
            partial_id_search = character_id[-partial_id_len:]

            name_match = character_df['name'].astype(str).str.lower() == character_name.lower()
            id_match = character_df['base_id'].astype(str).str.lower().str[-full_id_len:] == full_id_search
            partial_id_match = character_df['base_id'].astype(str).str.lower().str[-partial_id_len:] == partial_id_search
            race_match = character_df['race'].astype(str).str.lower() == character_race.lower()

            is_generic_npc = False
            try: # match name, full ID, race (needed for Fallout 4 NPCs like Curie)
                character_info = character_df.loc[name_match & id_match & race_match].to_dict('records')[0]
            except IndexError:
                try: # match name and full ID
                    character_info = character_df.loc[name_match & id_match].to_dict('records')[0]
                except IndexError:
                    try: # match name, partial ID, and race
                         character_info = character_df.loc[name_match & partial_id_match & race_match].to_dict('records')[0]
                    except IndexError:
                        try: # match name and partial ID
                            character_info = character_df.loc[name_match & partial_id_match].to_dict('records')[0]
                        except IndexError:
                            try: # match name and race
                                character_info = character_df.loc[name_match & race_match].to_dict('records')[0]
                            except IndexError:
                                try: # match just name
                                    character_info = character_df.loc[name_match].to_dict('records')[0]
                                except IndexError:
                                    try: # match just ID
                                        character_info = character_df.loc[id_match].to_dict('records')[0]
                                    except IndexError: # treat as generic NPC
                                        csvprefix = 'fallout4' if self.game in ["Fallout4", "Fallout4VR"] else 'skyrim'
                                        logging.info(f"Could not find {character_name} in {csvprefix}_characters.csv. Loading as a generic NPC.")

                                        if self.game in ["Fallout4", "Fallout4VR"]:
                                            character_info = self.FO4_load_unnamed_npc(character_name, character_df, FO4_Voice_folder_and_models_df)
                                        else:
                                            character_info = self.skyrim_load_unnamed_npc(character_name, character_df)
                                        is_generic_npc = True

            return character_info, is_generic_npc
        
        character_race = self.load_data_when_available('_mantella_actor_race', '')
        character_race = character_race.split('<')[1].split('Race ')[0]

        character_sex = self.load_data_when_available('_mantella_actor_sex', '')

        character_info, is_generic_npc = find_character_info(character_name, character_id, character_race, character_df)

        actor_voice_model = self.load_data_when_available('_mantella_actor_voice', '')
        actor_voice_model_name = actor_voice_model.split('<')[1].split(' ')[0]
        character_info['in_game_voice_model'] = actor_voice_model_name

        csv_in_game_voice = character_info['skyrim_voice_folder'] if 'skyrim' in self.game.lower() else character_info['fallout4_voice_folder']
        try: # try loading NPC voice model
            self.synthesizer.change_voice(character_info['voice_model'], character_info['in_game_voice_model'], csv_in_game_voice, character_info['advanced_voice_model'], character_info.get('voice_accent', None))
        except: # try loading generic voice model for NPC
            logging.error('Could not load voice model. Attempting to load a generic voice model...')
            character_info['voice_model'] = self.select_generic_voice(character_sex, character_race)
            self.synthesizer.change_voice(character_info['voice_model'], character_info['in_game_voice_model'], csv_in_game_voice, character_info['advanced_voice_model'], character_info.get('voice_accent', None))
        
        location = self.load_data_when_available('_mantella_current_location', location)
        if location.lower() == 'none': # location returns none when out in the wild
            if self.game == "Fallout4" or self.game == "Fallout4VR":
                location='Boston area'
            else:
                location='Skyrim'

        in_game_time = self.load_data_when_available('_mantella_in_game_time', in_game_time)

        # Is Player in combat with NPC
        is_in_combat = self.load_data_when_available('_mantella_actor_is_enemy', '')
        character_info['is_in_combat'] = is_in_combat

        actor_relationship_rank = self.load_data_when_available('_mantella_actor_relationship', '')
        try:
            actor_relationship_rank = int(actor_relationship_rank)
        except:
            actor_relationship_rank = 0
        character_info['in_game_relationship_level'] = actor_relationship_rank

        return character_info, location, in_game_time, is_generic_npc
        
    
    @utils.time_it
    def update_game_events(self, message: user_message) -> user_message:
        """Add in-game events to player's response"""

        # append in-game events to player's response
        with open(f'{self.game_path}/_mantella_in_game_events.txt', 'r', encoding='utf-8') as f:
            in_game_events_lines = f.readlines()[-5:] # read latest 5 events

        message.add_event(in_game_events_lines)

        is_in_combat = self.load_data_when_available('_mantella_actor_is_enemy', '')
        if is_in_combat.lower() == 'true':
            message.add_event(['\n*You are attacking the player. This is either because you are an enemy or the player has attacked you first.*'])

        if message.count_ingame_events() > 0:            
            logging.info(f'In-game events since previous exchange:\n{message.get_ingame_events_text()}')

        # once the events are shared with the NPC, clear the file
        self.write_game_info('_mantella_in_game_events', '')

        # append the time to player's response
        with open(f'{self.game_path}/_mantella_in_game_time.txt', 'r') as f:
            in_game_time = f.readline().strip()
        
        # only pass the in-game time if it has changed
        if (in_game_time != self.prev_game_time) and (in_game_time != ''):
            time_group = utils.get_time_group(in_game_time)
            try: # convert to 12hr clock
                in_game_time = int(in_game_time)
                in_game_time = in_game_time - 12 if in_game_time > 12 else in_game_time
                in_game_time = str(in_game_time)
            except:
                pass

            message.set_ingame_time(in_game_time, time_group)
            self.prev_game_time = in_game_time

        return message
    
    @utils.time_it
    def end_conversation(self):
        logging.info('Conversation ended.')

        self.write_game_info('_mantella_in_game_events', '')
        self.write_game_info('_mantella_end_conversation', 'True')
        time.sleep(5) # wait a few seconds for everything to register

        return None
        
_male_voice_models = {
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
_female_voice_models = {
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