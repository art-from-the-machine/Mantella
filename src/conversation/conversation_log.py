import json
import logging
import os
from pathlib import Path
import sys
import src.utils as utils
from src.character_manager import Character
from openai.types.chat import ChatCompletionMessageParam

class conversation_log:
    game_path: str = "" # <- This gets set in the __init__ of gameable. Not clean but cleaner than other options

    @staticmethod
    def save_conversation_log(character: Character, messages: list[ChatCompletionMessageParam], world_id: str):
        # save conversation history

        if not character.is_generic_npc:
            if len(messages) > 0:
                # if this is not the first conversation
                conversation_history_file = conversation_log.__get_path_to_conversation_history_file(character, world_id)
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
                    conversation_history = [messages] # wrap the first conversation in a list
                
                with open(conversation_history_file, 'w', encoding='utf-8') as f:
                    json.dump(conversation_history, f, indent=4) # save everything except the initial system prompt
        else:
            logging.log(23, 'Conversation history will not be saved for this generic NPC.')

    @staticmethod    
    def load_conversation_log(character: Character, world_id: str) -> list[str]:
        conversation_history_file = conversation_log.__get_path_to_conversation_history_file(character, world_id)
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
    def __get_path_to_conversation_history_file(character: Character, world_id: str) -> str:
        return f"{conversation_log.game_path}/{world_id}/{character.name}/{character.name}.json"
