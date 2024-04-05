import json
import os
import logging
import src.utils as utils
from pathlib import Path
import sys

from src.llm.message_thread import message_thread

class Character:
    def __init__(self, info, language, is_generic_npc, game):
        self.info = info
        self.name = info['name']
        self.bio = info['bio']
        self.is_in_combat = info['is_in_combat']
        self.relationship_rank = info['in_game_relationship_level']
        self.language = language
        self.is_generic_npc = is_generic_npc
        self.in_game_voice_model = info['in_game_voice_model']
        self.voice_model = info['voice_model']
        self.voice_accent = info.get('lang_override', None)

        # if the exe is being run by another process, store conversation data in MantellaData rather than the local data folder
        if "--integrated" in sys.argv:
            self.conversation_folder = str(Path(utils.resolve_path()).parent.parent.parent.parent)+'/MantellaData/conversations'
        else:
            self.conversation_folder = f"data/{game.replace('VR','')}/conversations"
        
        self.conversation_history_file = f"{self.conversation_folder}/{self.name}/{self.name}.json"
        self.conversation_summary_file = self.get_latest_conversation_summary_file_path()
        self.conversation_summary = ''

    def get_latest_conversation_summary_file_path(self):
        """Get latest conversation summary by file name suffix"""

        if os.path.exists(f"{self.conversation_folder}/{self.name}"):
            # get all files from the directory
            files = os.listdir(f"{self.conversation_folder}/{self.name}")
            # filter only .txt files
            txt_files = [f for f in files if f.endswith('.txt')]
            if len(txt_files) > 0:
                file_numbers = [int(os.path.splitext(f)[0].split('_')[-1]) for f in txt_files]
                latest_file_number = max(file_numbers)
                logging.info(f"Loaded latest summary file: {self.conversation_folder}/{self.name}_summary_{latest_file_number}.txt")
            else:
                logging.info(f"{self.conversation_folder}/{self.name} does not exist. A new summary file will be created.")
                latest_file_number = 1
        else:
            logging.info(f"{self.conversation_folder}/{self.name} does not exist. A new summary file will be created.")
            latest_file_number = 1
        
        conversation_summary_file = f"{self.conversation_folder}/{self.name}/{self.name}_summary_{latest_file_number}.txt"
        return conversation_summary_file
    
    def save_conversation_log(self, messages: message_thread):
        # save conversation history

        if not self.is_generic_npc:
            # if this is not the first conversation
            transformed_messages = messages.transform_to_openai_messages(messages.get_talk_only())
            if os.path.exists(self.conversation_history_file):
                with open(self.conversation_history_file, 'r', encoding='utf-8') as f:
                    conversation_history = json.load(f)

                # add new conversation to conversation history
                conversation_history.append(transformed_messages) # append everything except the initial system prompt
            # if this is the first conversation
            else:
                directory = os.path.dirname(self.conversation_history_file)
                os.makedirs(directory, exist_ok=True)
                conversation_history = transformed_messages
            
            with open(self.conversation_history_file, 'w', encoding='utf-8') as f:
                json.dump(conversation_history, f, indent=4) # save everything except the initial system prompt
        else:
            logging.info('Conversation history will not be saved for this generic NPC.')
    
    def load_conversation_log(self) -> list[str]:
        if os.path.exists(self.conversation_history_file):
            with open(self.conversation_history_file, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)
            previous_conversations = []
            for conversation in conversation_history:
                previous_conversations.extend(conversation)
            return previous_conversations
        else:
            return []