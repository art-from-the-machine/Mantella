import json
import logging
import os
from pathlib import Path
import sys
import src.utils as utils
from src.character_manager import Character
from openai.types.chat import ChatCompletionMessageParam

class conversation_log:
    @staticmethod
    def save_conversation_log(character: Character, messages: list[ChatCompletionMessageParam]):
        # save conversation history

        if not character.Is_generic_npc:
            # if this is not the first conversation
            conversation_history_file = conversation_log.__get_path_to_conversation_historyFile(character)
            # transformed_messages = messages.transform_to_openai_messages(messages.get_talk_only())
            if os.path.exists(conversation_history_file):
                with open(conversation_history_file, 'r', encoding='utf-8') as f:
                    conversation_history = json.load(f)

                # add new conversation to conversation history
                conversation_history.append(messages) # append everything except the initial system prompt
            # if this is the first conversation
            else:
                directory = os.path.dirname(conversation_history_file)
                os.makedirs(directory, exist_ok=True)
                conversation_history = messages
            
            with open(conversation_history_file, 'w', encoding='utf-8') as f:
                json.dump(conversation_history, f, indent=4) # save everything except the initial system prompt
        else:
            logging.info('Conversation history will not be saved for this generic NPC.')

    @staticmethod    
    def load_conversation_log(character: Character) -> list[str]:
        conversation_history_file = conversation_log.__get_path_to_conversation_historyFile(character)
        if os.path.exists(conversation_history_file):
            with open(conversation_history_file, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)
            previous_conversations = []
            for conversation in conversation_history:
                previous_conversations.extend(conversation)
            return previous_conversations
        else:
            return []

    @staticmethod    
    def __get_path_to_conversation_historyFile(character: Character) -> str:
        # if the exe is being run by another process, store conversation data in MantellaData rather than the local data folder
        if "--integrated" in sys.argv:
            conversation_folder = str(Path(utils.resolve_path()).parent.parent.parent.parent)+'/MantellaData/conversations'
        else:
            conversation_folder = 'data/conversations'
        return f"{conversation_folder}/{character.Name}/{character.Name}.json"