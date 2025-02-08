import logging
import os
import time
from src.games.gameable import gameable
from src.llm.llm_client import LLMClient
from src.llm.message_thread import message_thread
from src.llm.messages import user_message
from src.characters_manager import Characters
from src.character_manager import Character
from src.remember.remembering import remembering
from src import utils

class summaries(remembering):
    """ Stores a conversation as a summary in a text file.
        Loads the latest summary from disk for a prompt text.
    """
    def __init__(self, game: gameable, memory_prompt: str, resummarize_prompt: str, client: LLMClient, language_name: str, summary_limit_pct: float = 0.3) -> None:
        super().__init__()
        self.loglevel = 28
        self.__game: gameable = game
        self.__summary_limit_pct: float = summary_limit_pct
        self.__client: LLMClient = client
        self.__language_name: str = language_name
        self.__memory_prompt: str = memory_prompt
        self.__resummarize_prompt:str = resummarize_prompt

    @utils.time_it
    def get_prompt_text(self, npcs_in_conversation: Characters, world_id: str) -> str:
        """Load the conversation summaries for all NPCs in the conversation and returns them as one string

        Args:
            npcs_in_conversation (Characters): the npcs to load the summaries for

        Returns:
            str: a concatenation of the summaries as a single string
        """
        paragraphs = []
        for character in npcs_in_conversation.get_all_characters():
            if not character.is_player_character:          
                conversation_summary_file = self.__get_latest_conversation_summary_file_path(character, world_id)      
                if os.path.exists(conversation_summary_file):
                    with open(conversation_summary_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                paragraphs.append(line.strip())
        if paragraphs:
            result = "\n".join(paragraphs)
            return f"Below is a summary of past events:\n{result}"
        else:
            return ""

    @utils.time_it
    def save_conversation_state(self, messages: message_thread, npcs_in_conversation: Characters, world_id: str, is_reload=False):
        summary = ''
        for npc in npcs_in_conversation.get_all_characters():
            if not npc.is_player_character:
                if len(summary) < 1: # if a summary has not already been generated, make one
                    summary = self.__create_new_conversation_summary(messages, npc.name)
                if len(summary) > 0 or is_reload: # if a summary has been generated, give the same summary to all NPCs
                    self.__append_new_conversation_summary(summary, npc, world_id)

    @utils.time_it
    def __get_latest_conversation_summary_file_path(self, character: Character, world_id: str) -> str:
        """Get latest conversation summary by file name suffix"""

        # if multiple NPCs in a conversation have the same name (eg Whiterun Guard) their names are appended with number IDs
        # these IDs need to be removed when saving the conversation
        name: str = utils.remove_trailing_number(character.name)
        name_ref: str = f'{name} - {character.ref_id}'
        
        name_ref_conversation_folder_path = os.path.join(self.__game.conversation_folder_path, world_id, name_ref)
        if os.path.exists(name_ref_conversation_folder_path): # search by name and reference number
            character_conversation_folder_path = name_ref_conversation_folder_path
        else: # search by just name
            character_conversation_folder_path = os.path.join(self.__game.conversation_folder_path, world_id, name)
        
        if os.path.exists(character_conversation_folder_path):
            # get all files from the directory
            files = os.listdir(character_conversation_folder_path)
            # filter only .txt files
            txt_files = [f for f in files if f.endswith('.txt')]
            if len(txt_files) > 0:
                file_numbers = [int(os.path.splitext(f)[0].split('_')[-1]) for f in txt_files]
                latest_file_number = max(file_numbers)
                logging.info(f"Loaded latest summary file: {character_conversation_folder_path}/{name}_summary_{latest_file_number}.txt")
            else:
                logging.info(f"{name_ref_conversation_folder_path} does not exist. A new summary file will be created.")
                latest_file_number = 1
        else:
            logging.info(f"{name_ref_conversation_folder_path} does not exist. A new summary file will be created.")
            latest_file_number = 1
        
        conversation_summary_file = f"{character_conversation_folder_path}/{name}_summary_{latest_file_number}.txt"
        return conversation_summary_file

    @utils.time_it
    def __create_new_conversation_summary(self, messages: message_thread, npc_name: str) -> str:
        prompt = self.__memory_prompt.format(
                    name=npc_name,
                    language=self.__language_name,
                    game=self.__game
                )
        while True:
            try:
                if len(messages) >= 5:
                    return self.summarize_conversation(messages.transform_to_dict_representation(messages.get_talk_only()), prompt, npc_name)
                else:
                    logging.info(f"Conversation summary not saved. Not enough dialogue spoken.")
                break
            except:
                logging.error('Failed to summarize conversation. Retrying...')
                time.sleep(5)
                continue
        return ""

    @utils.time_it
    def __append_new_conversation_summary(self, new_summary: str, npc: Character, world_id: str):
        # if this is not the first conversation
        conversation_summary_file = self.__get_latest_conversation_summary_file_path(npc, world_id)
        if os.path.exists(conversation_summary_file):
            with open(conversation_summary_file, 'r', encoding='utf-8') as f:
                previous_conversation_summaries = f.read()
        # if this is the first conversation
        else:
            directory = os.path.dirname(conversation_summary_file)
            os.makedirs(directory, exist_ok=True)
            previous_conversation_summaries = ''
       
        if len(new_summary) > 0:
            conversation_summaries = previous_conversation_summaries + new_summary
            with open(conversation_summary_file, 'w', encoding='utf-8') as f:
                f.write(conversation_summaries)
        else:
            conversation_summaries = previous_conversation_summaries
            

        summary_limit = round(self.__client.token_limit*self.__summary_limit_pct,0)

        count_tokens_summaries = self.__client.calculate_tokens_from_text(conversation_summaries)
        # if summaries token limit is reached, summarize the summaries
        if count_tokens_summaries > summary_limit:
            logging.info(f'Token limit of conversation summaries reached ({count_tokens_summaries} / {summary_limit} tokens). Creating new summary file...')
            while True:
                try:
                    prompt = self.__resummarize_prompt.format(
                        name=npc.name,
                        language=self.__language_name,
                        game=self.__game
                    )
                    long_conversation_summary = self.summarize_conversation(conversation_summaries, prompt, npc.name)
                    break
                except:
                    logging.error('Failed to summarize conversation. Retrying...')
                    time.sleep(5)
                    continue

            # Split the file path and increment the number by 1
            base_directory, filename = os.path.split(conversation_summary_file)
            file_prefix, old_number = filename.rsplit('_', 1)
            old_number = os.path.splitext(old_number)[0]
            new_number = int(old_number) + 1
            new_conversation_summary_file = os.path.join(base_directory, f"{file_prefix}_{new_number}.txt")

            with open(new_conversation_summary_file, 'w', encoding='utf-8') as f:
                f.write(long_conversation_summary)
            
            # npc.conversation_summary_file = self.__get_latest_conversation_summary_file_path(npc)

    @utils.time_it
    def summarize_conversation(self, text_to_summarize: str, prompt: str, npc_name: str) -> str:
        summary = ''
        if len(text_to_summarize) > 5:
            messages = message_thread(prompt)
            messages.add_message(user_message(text_to_summarize))
            summary = self.__client.request_call(messages)
            if not summary:
                logging.info(f"Summarizing conversation failed.")
                return ""

            summary = summary.replace('The assistant', npc_name)
            summary = summary.replace('the assistant', npc_name)
            summary = summary.replace('an assistant', npc_name)
            summary = summary.replace('an AI assistant', npc_name)
            summary = summary.replace('The user', 'The player')
            summary = summary.replace('the user', 'the player')
            summary += '\n\n'

            logging.log(self.loglevel, f'Conversation summary: {summary.strip()}')
            logging.info(f"Conversation summary saved")
        else:
            logging.info(f"Conversation summary not saved. Not enough dialogue spoken.")

        return summary