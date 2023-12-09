import logging
import src.utils as utils
import time
import random

class CharacterDoesNotExist(Exception):
    """Exception raised when NPC name cannot be found in skyrim_characters.csv"""
    pass


class GameStateManager:
    def __init__(self, game_path):
        self.game_path = game_path
        self.prev_game_time = ''


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
        return text
    

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

        return character_name, character_id, location, in_game_time
    
    
    def write_dummy_game_info(self, character_name, character_df):
        """Write fake data to game files when debugging"""
        logging.info(f'Writing dummy game status for debugging character {character_name}')
        voice_model = random.choice(['Female Nord', 'Male Nord'])
        try: # search for voice model in skyrim_characters.csv
            voice_model = character_df.loc[character_df['name'].astype(str).str.lower()==character_name.lower(), 'voice_model'].values[0]
        except: # guess voice model based on sex and race
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

        self.write_game_info('_mantella_actor_voice', f'<{voice_model}')

        relationship = '0'
        self.write_game_info('_mantella_actor_relationship', relationship)

        self.write_game_info('_mantella_current_actor', character_name)

        character_id = '0'
        try: # search for voice model in skyrim_characters.csv
            voice_model = character_df.loc[character_df['name'].astype(str).str.lower()==character_name.lower(), 'base_id_int'].values[0]
        except:
            pass
        self.write_game_info('_mantella_current_actor_id', str(character_id))

        location = 'Skyrim'
        self.write_game_info('_mantella_current_location', location)
        
        in_game_time = '12'
        self.write_game_info('_mantella_in_game_time', in_game_time)

        return character_name, character_id, location, in_game_time
    

    def load_character_name_id(self):
        """Wait for character ID to populate then load character name"""

        character_id = self.load_data_when_available('_mantella_current_actor_id', '')
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
    
    
    def load_unnamed_npc(self, character_name, character_df):
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

        try: # search for relavant skyrim_voice_folder for voice_model
            skyrim_voice_folder = character_df.loc[character_df['voice_model'].astype(str).str.lower()==voice_model.lower(), 'skyrim_voice_folder'].values[0]
        except: # assume it is simply the voice_model name without spaces
            skyrim_voice_folder = voice_model.replace(' ','')
        
        character_info = {
            'name': character_name,
            'bio': f'You are a {character_name}',
            'voice_model': voice_model,
            'skyrim_voice_folder': skyrim_voice_folder,
        }

        return character_info
    
    
    @utils.time_it
    def load_game_state(self, debug_mode, debug_character_name, character_df, character_name, character_id, location, in_game_time):
        """Load game variables from _mantella_ files in Skyrim folder (data passed by the Mantella spell)"""

        if debug_mode == '1':
            character_name, character_id, location, in_game_time = self.debugging_setup(debug_character_name, character_df)
        
        # tell Skyrim papyrus script to start waiting for voiceline input
        self.write_game_info('_mantella_end_conversation', 'False')
        character_id, character_name = self.load_character_name_id()
        try: # load character from skyrim_characters.csv
            character_info = character_df.loc[character_df['name'].astype(str).str.lower()==character_name.lower()].to_dict('records')[0]
            is_generic_npc = False
        except IndexError: # character not found
            try: # try searching by ID
                logging.info(f"Could not find {character_name} in skyrim_characters.csv. Searching by ID {character_id}...")
                character_info = character_df.loc[(character_df['baseid_int'].astype(str)==character_id) | (character_df['baseid_int'].astype(str)==character_id+'.0')].to_dict('records')[0]
                is_generic_npc = False
            except IndexError: # load generic NPC
                logging.info(f"NPC '{character_name}' could not be found in 'skyrim_characters.csv'. If this is not a generic NPC, please ensure '{character_name}' exists in the CSV's 'name' column exactly as written here, and that there is a voice model associated with them.")
                character_info = self.load_unnamed_npc(character_name, character_df)
                is_generic_npc = True

        location = self.load_data_when_available('_mantella_current_location', location)
        if location.lower() == 'none': # location returns none when out in the wild
            location = 'Skyrim'

        in_game_time = self.load_data_when_available('_mantella_in_game_time', in_game_time)

        actor_voice_model = self.load_data_when_available('_mantella_actor_voice', '')
        actor_voice_model_name = actor_voice_model.split('<')[1].split(' ')[0]
        character_info['in_game_voice_model'] = actor_voice_model_name

        actor_relationship_rank = self.load_data_when_available('_mantella_actor_relationship', '')
        try:
            actor_relationship_rank = int(actor_relationship_rank)
        except:
            actor_relationship_rank = 0
        character_info['in_game_relationship_level'] = actor_relationship_rank

        return character_info, location, in_game_time, is_generic_npc
    
    
    @utils.time_it
    def update_game_events(self, message):
        """Add in-game events to player's response"""

        # append in-game events to player's response
        with open(f'{self.game_path}/_mantella_in_game_events.txt', 'r', encoding='utf-8') as f:
            in_game_events_lines = f.readlines()[-5:] # read latest 5 events

        # encapsulate events in {}
        formatted_in_game_events_lines = ['*{}*'.format(line.strip()) for line in in_game_events_lines]
        in_game_events = '\n'.join(formatted_in_game_events_lines)

        is_in_combat = self.load_data_when_available('_mantella_actor_is_enemy', '')
        if is_in_combat.lower() == 'true':
            in_game_events = in_game_events + '\n*You are attacking the player. This is either because you are an enemy or the player has attacked you first.*'

        if len(in_game_events) > 0:
            logging.info(f'In-game events since previous exchange:\n{in_game_events}')
        message = in_game_events + '\n' + message

        # once the events are shared with the NPC, clear the file
        self.write_game_info('_mantella_in_game_events', '')

        # append the time to player's response
        with open(f'{self.game_path}/_mantella_in_game_time.txt', 'r') as f:
            in_game_time = f.readline().strip()
        
        # only pass the in-game time if it has changed
        if (in_game_time != self.prev_game_time) and (in_game_time != ''):
            time_group = utils.get_time_group(in_game_time)

            formatted_in_game_time = f"*The time is {in_game_time} {time_group}.*\n"
            message = formatted_in_game_time + message
            self.prev_game_time = in_game_time

        return message
    
    
    @utils.time_it
    def end_conversation(self, conversation_ended, config, encoding, synthesizer, chat_manager, messages, active_characters, tokens_available):
        """Say final goodbye lines and save conversation to memory"""

        # say goodbyes
        if conversation_ended.lower() != 'true': # say line if NPC is not already deactivated
            latest_character = list(active_characters.items())[-1][1]
            audio_file = synthesizer.synthesize(latest_character.info['voice_model'], latest_character.info['skyrim_voice_folder'], config.goodbye_npc_response)
            chat_manager.save_files_to_voice_folders([audio_file, config.goodbye_npc_response])

        messages.append({"role": "user", "content": config.end_conversation_keyword+'.'})
        messages.append({"role": "assistant", "content": config.end_conversation_keyword+'.'})

        summary = None
        for character_name, character in active_characters.items():
            # If summary has already been generated for another character in a multi NPC conversation (multi NPC memory summaries are shared)
            if summary == None:
                summary = character.save_conversation(encoding, messages, tokens_available, config.llm)
            else:
                _ = character.save_conversation(encoding, messages, tokens_available, config.llm, summary)
        logging.info('Conversation ended.')

        self.write_game_info('_mantella_in_game_events', '')
        self.write_game_info('_mantella_end_conversation', 'True')
        time.sleep(5) # wait a few seconds for everything to register

        return None
    
    
    @utils.time_it
    def reload_conversation(self, config, encoding, synthesizer, chat_manager, messages, active_characters, tokens_available, token_limit, location, in_game_time):
        """Restart conversation to save conversation to memory when token count is reaching its limit"""

        latest_character = list(active_characters.items())[-1][1]
        # let the player know that the conversation is reloading
        audio_file = synthesizer.synthesize(latest_character.info['voice_model'], latest_character.info['skyrim_voice_folder'], config.collecting_thoughts_npc_response)
        chat_manager.save_files_to_voice_folders([audio_file, config.collecting_thoughts_npc_response])

        messages.append({"role": "user", "content": latest_character.info['name']+'?'})
        if len(list(active_characters.items())) > 1:
            collecting_thoughts_response = latest_character.info['name']+': '+config.collecting_thoughts_npc_response+'.'
        else:
            collecting_thoughts_response = config.collecting_thoughts_npc_response+'.'
        messages.append({"role": "assistant", "content": collecting_thoughts_response})

        # save the conversation so far
        summary = None
        for character_name, character in active_characters.items():
            if summary == None:
                summary = character.save_conversation(encoding, messages, tokens_available, config.llm)
            else:
                _ = character.save_conversation(encoding, messages, tokens_available, config.llm, summary)
        # let the new file register on the system
        time.sleep(1)
        # if a new conversation summary file was created, load this latest file
        for character_name, character in active_characters.items():
            conversation_summary_file = character.get_latest_conversation_summary_file_path()

        # reload context
        keys = list(active_characters.keys())
        prompt = config.prompt
        if len(keys) > 1:
            prompt = config.multi_npc_prompt
        context = latest_character.set_context(prompt, location, in_game_time, active_characters, token_limit)

        # add previous few back and forths from last conversation
        messages_wo_system_prompt = messages[1:]
        messages_last_entries = messages_wo_system_prompt[-8:]
        context.extend(messages_last_entries)

        return conversation_summary_file, context, messages
    
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
