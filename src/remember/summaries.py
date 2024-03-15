import json
import logging
import os
import time
from src.llm.openai_client import openai_client
from src.llm.message_thread import message_thread
from src.llm.messages import user_message
from src.characters_manager import Characters
from src.character_manager import Character
from src.remember.remembering import remembering

class summaries(remembering):
    """ Stores a conversation as a summary in a text file.
        Loads the latest summary from disk for a prompt text.
    """
    def __init__(self, memory_prompt: str, resummarize_prompt: str, client: openai_client, language_name: str, summary_limit_pct: float = 0.45) -> None:
        super().__init__()
        self.__summary_limit_pct: float = summary_limit_pct
        self.__client: openai_client = client
        self.__language_name: str = language_name
        self.__memory_prompt: str = memory_prompt
        self.__resummarize_prompt:str = resummarize_prompt

    def get_prompt_text(self, npcs_in_conversation: Characters) -> str:
        """Load the conversation summaries for all NPCs in the conversation and returns them as one string

        Args:
            npcs_in_conversation (Characters): the npcs to load the summaries for

        Returns:
            str: a concatenation of the summaries as a single string
        """
        result = ""
        for character in npcs_in_conversation.get_all_characters():
            if os.path.exists(character.conversation_history_file) and os.path.exists(character.conversation_summary_file):
                with open(character.conversation_summary_file, 'r', encoding='utf-8') as f:
                    previous_conversation_summaries = f.read()
                    character.conversation_summary = previous_conversation_summaries
                    if len(npcs_in_conversation) == 1 and len(previous_conversation_summaries) > 0:
                        result = f"Below is a summary for each of your previous conversations:\n\n{previous_conversation_summaries}"
                    elif len(npcs_in_conversation) > 1 and len(previous_conversation_summaries) > 0:
                        result += f"{character.name}: {previous_conversation_summaries}"
        return result

    def save_conversation_state(self, messages: message_thread, npcs_in_conversation: Characters):
        summary = ''
        non_generic_npc = []
        for npc in npcs_in_conversation.get_all_characters():
            if npc.is_generic_npc:
                logging.info('A summary will not be saved for this generic NPC.')
            else:
                non_generic_npc.append(npc)
        for npc in non_generic_npc:            
            if len(summary) < 1:
                summary = self.__create_new_conversation_summary(messages, npc.name)
            if len(summary) > 0:# Should for what ever reason the first summary to fail, don't even try to continue here
                self.__append_new_conversation_summary(summary, npc)

    def __create_new_conversation_summary(self, messages: message_thread, npc_name: str) -> str:
        prompt = self.__memory_prompt.format(
                    name=npc_name,
                    language=self.__language_name
                )
        while True:
            try:
                if len(messages) > 5:
                    return self.summarize_conversation(messages.transform_to_dict_representation(messages.get_talk_only()), prompt, npc_name)
                else:
                    logging.info(f"Conversation summary not saved. Not enough dialogue spoken.")
                break
            except:
                logging.error('Failed to summarize conversation. Retrying...')
                time.sleep(5)
                continue
        return ""

    def __append_new_conversation_summary(self, new_summary: str, npc: Character):
        # if this is not the first conversation
        if os.path.exists(npc.conversation_summary_file):
            with open(npc.conversation_summary_file, 'r', encoding='utf-8') as f:
                previous_conversation_summaries = f.read()
        # if this is the first conversation
        else:
            directory = os.path.dirname(npc.conversation_summary_file)
            os.makedirs(directory, exist_ok=True)
            previous_conversation_summaries = ''
       
        conversation_summaries = previous_conversation_summaries + new_summary
        with open(npc.conversation_summary_file, 'w', encoding='utf-8') as f:
            f.write(conversation_summaries)

        summary_limit = round(self.__client.token_limit*self.__summary_limit_pct,0)

        count_tokens_summaries = self.__client.calculate_tokens_from_text(conversation_summaries)
        # if summaries token limit is reached, summarize the summaries
        if count_tokens_summaries > summary_limit:
            logging.info(f'Token limit of conversation summaries reached ({count_tokens_summaries} / {summary_limit} tokens). Creating new summary file...')
            while True:
                try:
                    prompt = self.__resummarize_prompt.format(
                        name=npc.name,
                        language=self.__language_name
                    )
                    long_conversation_summary = self.summarize_conversation(conversation_summaries, prompt, npc.name)
                    break
                except:
                    logging.error('Failed to summarize conversation. Retrying...')
                    time.sleep(5)
                    continue

            # Split the file path and increment the number by 1
            base_directory, filename = os.path.split(npc.conversation_summary_file)
            file_prefix, old_number = filename.rsplit('_', 1)
            old_number = os.path.splitext(old_number)[0]
            new_number = int(old_number) + 1
            new_conversation_summary_file = os.path.join(base_directory, f"{file_prefix}_{new_number}.txt")

            with open(new_conversation_summary_file, 'w', encoding='utf-8') as f:
                f.write(long_conversation_summary)
            
            npc.conversation_summary_file = npc.get_latest_conversation_summary_file_path()

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

            logging.info(f"Conversation summary saved.")
        else:
            logging.info(f"Conversation summary not saved. Not enough dialogue spoken.")

        return summary