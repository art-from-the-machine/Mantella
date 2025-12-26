import json
import os
from pathlib import Path
import sys
import src.utils as utils
from src.character_manager import Character
from openai.types.chat import ChatCompletionMessageParam


class conversation_log:
    game_path: str = "" # <- This gets set in the __init__ of gameable. Not clean but cleaner than other options

    @staticmethod
    @utils.time_it
    def save_conversation_log(character: Character, messages: list[ChatCompletionMessageParam], world_id: str):
        # save conversation history

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

    @staticmethod   
    @utils.time_it 
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
    @utils.time_it
    def get_conversation_log_length(character: Character, world_id: str) -> int:
        conversation_history_file = conversation_log.__get_path_to_conversation_history_file(character, world_id)
        if os.path.exists(conversation_history_file):
            with open(conversation_history_file, 'r', encoding='utf-8') as f:
                conversation_history = json.load(f)
            return sum(len(conversation) for conversation in conversation_history)
        else:
            return 0

    @staticmethod    
    @utils.time_it
    def __get_path_to_conversation_history_file(character: Character, world_id: str) -> str:
        # if multiple NPCs in a conversation have the same name (eg Whiterun Guard) their names are appended with number IDs
        # these IDs need to be removed when saving the conversation
        name: str = utils.remove_trailing_number(character.name)
        non_ref_path = f"{conversation_log.game_path}/{world_id}/{name}/{name}.json"
        ref_path = f"{conversation_log.game_path}/{world_id}/{name} - {character.ref_id}/{name}.json"

        if os.path.exists(non_ref_path): # if a conversation folder already exists for this NPC, use it
            return non_ref_path
        else: # else include the NPC's reference ID in the folder name to differentiate generic NPCs
            return ref_path
