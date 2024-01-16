import os
import logging
import json
import time
import src.utils as utils
import src.chat_response as chat_response

class Character:
    def __init__(self, info, language, is_generic_npc, memory_prompt, resummarize_prompt):
        self.info = info
        self.name = info['name']
        self.bio = info['bio']
        self.is_in_combat = info['is_in_combat']
        self.relationship_rank = info['in_game_relationship_level']
        self.language = language
        self.is_generic_npc = is_generic_npc
        self.in_game_voice_model = info['in_game_voice_model']
        self.voice_model = info['voice_model']
        self.memory_prompt = memory_prompt
        self.resummarize_prompt = resummarize_prompt
        self.conversation_history_file = f"data/conversations/{self.name}/{self.name}.json"
        self.conversation_summary_file = self.get_latest_conversation_summary_file_path()
        self.conversation_summary = ''


    def get_latest_conversation_summary_file_path(self):
        """Get latest conversation summary by file name suffix"""

        if os.path.exists(f"data/conversations/{self.name}"):
            # get all files from the directory
            files = os.listdir(f"data/conversations/{self.name}")
            # filter only .txt files
            txt_files = [f for f in files if f.endswith('.txt')]
            if len(txt_files) > 0:
                file_numbers = [int(os.path.splitext(f)[0].split('_')[-1]) for f in txt_files]
                latest_file_number = max(file_numbers)
                logging.info(f"Loaded latest summary file: data/conversations/{self.name}_summary_{latest_file_number}.txt")
            else:
                logging.info(f"data/conversations/{self.name} does not exist. A new summary file will be created.")
                latest_file_number = 1
        else:
            logging.info(f"data/conversations/{self.name} does not exist. A new summary file will be created.")
            latest_file_number = 1
        
        conversation_summary_file = f"data/conversations/{self.name}/{self.name}_summary_{latest_file_number}.txt"
        return conversation_summary_file
    

    def set_context(self, prompt, location, in_game_time, active_characters, token_limit, radiant_dialogue):
        # if conversation history exists, load it
        if os.path.exists(self.conversation_history_file):
            with open(self.conversation_history_file, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)

            previous_conversations = []
            for conversation in conversation_history:
                previous_conversations.extend(conversation)

            with open(self.conversation_summary_file, 'r', encoding='utf-8') as f:
                previous_conversation_summaries = f.read()

            self.conversation_summary = previous_conversation_summaries

            context = self.create_context(prompt, location, in_game_time, active_characters, token_limit, radiant_dialogue, len(previous_conversations), previous_conversation_summaries)
        else:
            context = self.create_context(prompt, location, in_game_time, active_characters, token_limit, radiant_dialogue)

        return context
    

    def create_context(self, prompt, location='Skyrim', time='12', active_characters=None, token_limit=4096, radiant_dialogue='false', trust_level=0, conversation_summary='', prompt_limit_pct=0.75):
        if self.relationship_rank == 0:
            if trust_level < 1:
                trust = 'a stranger'
            elif trust_level < 10:
                trust = 'an acquaintance'
            elif trust_level < 50:
                trust = 'a friend'
            elif trust_level >= 50:
                trust = 'a close friend'
        elif self.relationship_rank == 4:
            trust = 'a lover'
        elif self.relationship_rank > 0:
            trust = 'a friend'
        elif self.relationship_rank < 0:
            trust = 'an enemy'
        if len(conversation_summary) > 0:
            conversation_summary = f"Below is a summary for each of your previous conversations:\n\n{conversation_summary}"

        time_group = utils.get_time_group(time)

        keys = list(active_characters.keys())

        if len(keys) == 1: # Single NPC prompt
            character_desc = prompt.format(
                name=self.name, 
                bio=self.bio, 
                trust=trust, 
                location=location, 
                time=time, 
                time_group=time_group, 
                language=self.language, 
                conversation_summary=conversation_summary
            )
        else: # Multi NPC prompt
            if radiant_dialogue == 'false': # don't mention player if radiant dialogue
                keys_w_player = ['the player'] + keys
            else:
                keys_w_player = keys
            
            # Join all but the last key with a comma, and add the last key with "and" in front
            character_names_list = ', '.join(keys[:-1]) + ' and ' + keys[-1]
            character_names_list_w_player = ', '.join(keys_w_player[:-1]) + ' and ' + keys_w_player[-1]

            bio_descriptions = []
            for character_name, character in active_characters.items():
                bio_descriptions.append(f"{character_name}: {character.bio}")

            formatted_bios = "\n".join(bio_descriptions)

            conversation_histories = []
            for character_name, character in active_characters.items():
                conversation_histories.append(f"{character_name}: {character.conversation_summary}")

            formatted_histories = "\n".join(conversation_histories)
            
            character_desc = prompt.format(
                name=self.name, 
                names=character_names_list,
                names_w_player=character_names_list_w_player,
                language=self.language,
                location=location,
                time=time,
                time_group=time_group,
                bios=formatted_bios,
                conversation_summaries=formatted_histories)
        
            prompt_num_tokens = chat_response.num_tokens_from_messages([{"role": "system", "content": character_desc}])
            prompt_token_limit = (round(token_limit*prompt_limit_pct,0))
            # If the full prompt is too long, exclude NPC memories from prompt
            if prompt_num_tokens > prompt_token_limit:
                character_desc = prompt.format(
                    name=self.name, 
                    names=character_names_list,
                    names_w_player=character_names_list_w_player,
                    language=self.language,
                    location=location,
                    time=time,
                    time_group=time_group,
                    bios=formatted_bios,
                    conversation_summaries='NPC memories not available.')
                
                prompt_num_tokens = chat_response.num_tokens_from_messages([{"role": "system", "content": character_desc}])
                prompt_token_limit = (round(token_limit*prompt_limit_pct,0))
                # If the prompt with all bios included is too long, exclude NPC bios and just list the names of NPCs in the conversation
                if prompt_num_tokens > prompt_token_limit:
                    character_desc = prompt.format(
                        name=self.name, 
                        names=character_names_list,
                        names_w_player=character_names_list_w_player,
                        language=self.language,
                        location=location,
                        time=time,
                        time_group=time_group,
                        bios='NPC backgrounds not available.',
                        conversation_summaries='NPC memories not available.')
        
        logging.info(character_desc)
        context = [{"role": "system", "content": character_desc}]
        return context
        

    def save_conversation(self, encoding, messages, tokens_available, llm, summary=None, summary_limit_pct=0.45):
        if self.is_generic_npc:
            logging.info('A summary will not be saved for this generic NPC.')
            return None
        
        summary_limit = round(tokens_available*summary_limit_pct,0)

        # save conversation history
        # if this is not the first conversation
        if os.path.exists(self.conversation_history_file):
            with open(self.conversation_history_file, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)

            # add new conversation to conversation history
            conversation_history.append(messages[1:]) # append everything except the initial system prompt
        # if this is the first conversation
        else:
            directory = os.path.dirname(self.conversation_history_file)
            os.makedirs(directory, exist_ok=True)
            conversation_history = [messages[1:]]
        
        with open(self.conversation_history_file, 'w', encoding='utf-8') as f:
            json.dump(conversation_history, f, indent=4) # save everything except the initial system prompt

        # if this is not the first conversation
        if os.path.exists(self.conversation_summary_file):
            with open(self.conversation_summary_file, 'r', encoding='utf-8') as f:
                previous_conversation_summaries = f.read()
        # if this is the first conversation
        else:
            directory = os.path.dirname(self.conversation_summary_file)
            os.makedirs(directory, exist_ok=True)
            previous_conversation_summaries = ''

        # If summary has not already been generated for another character in a multi NPC conversation (multi NPC memory summaries are shared)
        if summary == None:
            while True:
                try:
                    new_conversation_summary = self.summarize_conversation(messages, llm)
                    break
                except:
                    logging.error('Failed to summarize conversation. Retrying...')
                    time.sleep(5)
                    continue
        else:
            new_conversation_summary = summary
        conversation_summaries = previous_conversation_summaries + new_conversation_summary

        with open(self.conversation_summary_file, 'w', encoding='utf-8') as f:
            f.write(conversation_summaries)

        # if summaries token limit is reached, summarize the summaries
        if len(encoding.encode(conversation_summaries)) > summary_limit:
            logging.info(f'Token limit of conversation summaries reached ({len(encoding.encode(conversation_summaries))} / {summary_limit} tokens). Creating new summary file...')
            while True:
                try:
                    prompt = self.resummarize_prompt.format(
                        name=self.name,
                        language=self.language
                    )
                    long_conversation_summary = self.summarize_conversation(conversation_summaries, llm, prompt)
                    break
                except:
                    logging.error('Failed to summarize conversation. Retrying...')
                    time.sleep(5)
                    continue

            # Split the file path and increment the number by 1
            base_directory, filename = os.path.split(self.conversation_summary_file)
            file_prefix, old_number = filename.rsplit('_', 1)
            old_number = os.path.splitext(old_number)[0]
            new_number = int(old_number) + 1
            new_conversation_summary_file = os.path.join(base_directory, f"{file_prefix}_{new_number}.txt")

            with open(new_conversation_summary_file, 'w', encoding='utf-8') as f:
                f.write(long_conversation_summary)
        
        return new_conversation_summary
    

    def summarize_conversation(self, conversation, llm, prompt=None):
        summary = ''
        if len(conversation) > 5:
            conversation = conversation[3:-2] # drop the context (0) hello (1,2) and "Goodbye." (-2, -1) lines
            if prompt == None:
                prompt = self.memory_prompt.format(
                    name=self.name,
                    language=self.language
                )
            context = [{"role": "system", "content": prompt}]
            summary, _ = chat_response.chatgpt_api(f"{conversation}", context, llm)

            summary = summary.replace('The assistant', self.name)
            summary = summary.replace('the assistant', self.name)
            summary = summary.replace('an assistant', self.name)
            summary = summary.replace('an AI assistant', self.name)
            summary = summary.replace('The user', 'The player')
            summary = summary.replace('the user', 'the player')
            summary += '\n\n'

            logging.info(f"Conversation summary saved.")
        else:
            logging.info(f"Conversation summary not saved. Not enough dialogue spoken.")

        return summary