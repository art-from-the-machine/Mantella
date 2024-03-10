import asyncio
import os
import queue
from threading import Lock
import wave
import logging
import time
import shutil
import re
import unicodedata
from src.conversation.action import action
from src.llm.sentence_queue import sentence_queue
from src.config_loader import ConfigLoader
from src.llm.sentence import sentence
import src.utils as utils
from src.characters_manager import Characters
from src.character_manager import Character
from src.llm.messages import message
from src.llm.message_thread import message_thread
from src.llm.openai_client import openai_client
from src.tts import Synthesizer

class Extract:
    def __init__(self, extract: str, whole: str) -> None:
        self.__extract: str = extract
        self.__rest: str = str.replace(whole, extract, "")
    
    @property
    def Extract(self) -> str:
        return self.__extract
    
    @property
    def Rest(self) -> str:
        return self.__rest

class ChatManager:
    def __init__(self, config: ConfigLoader, tts: Synthesizer, client: openai_client):
        self.loglevel = 28
        self.mod_folder = config.mod_path
        self.max_response_sentences = config.max_response_sentences
        self.language = config.language
        self.wait_time_buffer = config.wait_time_buffer
        self.__tts: Synthesizer = tts
        self.__client: openai_client = client
        self.__is_generating: bool = False
        self.__stop_generation: bool = False
        self.__tts_access_lock = Lock()

        self.wav_file = f'MantellaDi_MantellaDialogu_00001D8B_1.wav'
        self.lip_file = f'MantellaDi_MantellaDialogu_00001D8B_1.lip'

        self.end_of_sentence_chars = ['.', '?', '!', ':', ';']
        self.end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in self.end_of_sentence_chars]

    def generate_sentence(self, text: str, character_to_talk: Character, is_system_generated_sentence: bool = False) -> sentence | None:
        with self.__tts_access_lock:
            try:
                audio_file = self.__tts.synthesize(character_to_talk.TTS_voice_model, text, character_to_talk.Is_in_combat)
            except Exception as e:            
                logging.error(f"Text-to-Speech Error: {e}")
                return None
            return sentence(character_to_talk, text, audio_file, self.get_audio_duration(audio_file), is_system_generated_sentence)

    def num_tokens(self, content_to_measure: message | str | message_thread | list[message]) -> int:
        if isinstance(content_to_measure, message_thread) or isinstance(content_to_measure, list):
            return openai_client.num_tokens_from_messages(content_to_measure)
        else:
            return openai_client.num_tokens_from_message(content_to_measure, None)

    def generate_response(self, messages: message_thread, characters: Characters, blocking_queue: sentence_queue, actions: list[action]):
        if(not characters.last_added_character):
            return
        # blocking_queue.Is_more_to_come = True
        self.__is_generating = True
        
        asyncio.run(self.process_response(characters.last_added_character, blocking_queue, messages, characters, actions))
    
    def stop_generation(self):
        if not self.__is_generating:
            return
        
        self.__stop_generation = True
        while self.__is_generating:
            time.sleep(0.1)
        self.__stop_generation = False
        return

    def get_audio_duration(self, audio_file: str):
        """Check if the external software has finished playing the audio file"""

        with wave.open(audio_file, 'r') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()

        # wait `buffer` seconds longer to let processes finish running correctly
        duration = frames / float(rate) + self.wait_time_buffer
        return duration
    

    def setup_voiceline_save_location(self, in_game_voice_folder):
        """Save voice model folder to Mantella Spell if it does not already exist"""
        self.in_game_voice_model = in_game_voice_folder

        in_game_voice_folder_path = f"{self.mod_folder}/{in_game_voice_folder}/"
        if not os.path.exists(in_game_voice_folder_path):
            os.mkdir(in_game_voice_folder_path)

            # copy voicelines from one voice folder to this new voice folder
            # this step is needed for Skyrim to acknowledge the folder
            example_folder = f"{self.mod_folder}/MaleNord/"
            for file_name in os.listdir(example_folder):
                source_file_path = os.path.join(example_folder, file_name)

                if os.path.isfile(source_file_path):
                    shutil.copy(source_file_path, in_game_voice_folder_path)

            # self.game_state_manager.write_game_info('_mantella_status', 'Error with Mantella.exe. Please check MantellaSoftware/logging.log')
            logging.warn("Unknown NPC detected. This NPC will be able to speak once you restart Skyrim. To learn how to add memory, a background, and a voice model of your choosing to this NPC, see here: https://github.com/art-from-the-machine/Mantella#adding-modded-npcs")
            time.sleep(5)
            return True
        return False    

    @utils.time_it
    def remove_files_from_voice_folders(self):
        for sub_folder in os.listdir(self.mod_folder):
            try:
                os.remove(f"{self.mod_folder}/{sub_folder}/{self.wav_file}")
                os.remove(f"{self.mod_folder}/{sub_folder}/{self.lip_file}")
            except:
                continue

    async def send_response(self, sentence_queue: asyncio.Queue[sentence|None], event: asyncio.Event, blocking_queue: queue.Queue[sentence]):
        """Send response from sentence queue generated by `process_response()`"""

        while True:
            queue_output: sentence | None = await sentence_queue.get()
            if queue_output is None:
                logging.info('End of sentences')
                break
            blocking_queue.put_nowait(queue_output)
            event.set()
            # # send the audio file to the external software and wait for it to finish playing
            # await self.send_audio_to_external_software(queue_output)
            # event.set()

            # audio_duration = self.get_audio_duration(queue_output.Voice_file)
            # # wait for the audio playback to complete before getting the next file
            # logging.info(f"Waiting {int(round(audio_duration,4))} seconds...")
            # await asyncio.sleep(audio_duration)

    def clean_sentence(self, sentence: str) -> str:
        def remove_as_a(sentence: str) -> str:
            """Remove 'As an XYZ,' from beginning of sentence"""
            if sentence.startswith('As a'):
                if ', ' in sentence:
                    logging.info(f"Removed '{sentence.split(', ')[0]} from response")
                    sentence = sentence.replace(sentence.split(', ')[0]+', ', '')
            return sentence
        
        def parse_asterisks_brackets(sentence: str) -> str:
            if ('*' in sentence):
                # Check if sentence contains two asterisks
                asterisk_check = re.search(r"(?<!\*)\*(?!\*)[^*]*\*(?!\*)", sentence)
                if asterisk_check:
                    logging.info(f"Removed asterisks text from response: {sentence}")
                    # Remove text between two asterisks
                    sentence = re.sub(r"(?<!\*)\*(?!\*)[^*]*\*(?!\*)", "", sentence)
                else:
                    logging.info(f"Removed response containing single asterisks: {sentence}")
                    sentence = ''

            if ('(' in sentence) or (')' in sentence):
                # Check if sentence contains two brackets
                bracket_check = re.search(r"\(.*\)", sentence)
                if bracket_check:
                    logging.info(f"Removed brackets text from response: {sentence}")
                    # Remove text between brackets
                    sentence = re.sub(r"\(.*?\)", "", sentence)
                else:
                    logging.info(f"Removed response containing single bracket: {sentence}")
                    sentence = ''

            return sentence
        
        if ('Well, well, well' in sentence):
            sentence = sentence.replace('Well, well, well', 'Well well well')

        sentence = remove_as_a(sentence)
        sentence = sentence.replace('"','')
        sentence = sentence.replace('[', '(')
        sentence = sentence.replace(']', ')')
        sentence = sentence.replace('{', '(')
        sentence = sentence.replace('}', ')')
        # local models sometimes get the idea in their head to use double asterisks **like this** in sentences instead of single
        # this converts double asterisks to single so that they can be filtered out appropriately
        sentence = sentence.replace('**','*')
        sentence = parse_asterisks_brackets(sentence)
        sentence = sentence.strip() + " "
        return sentence

    # def find_last_sentence_terminator(self, sentence_to_check: str) -> Extract:
    #     last_punctuation_index: int = -1
    #     for stop_char in self.end_of_sentence_chars:
    #         last_punctuation_index = max(last_punctuation_index, sentence_to_check.rfind(stop_char))
    #     if last_punctuation_index != -1:
    #         sentence = sentence_to_check[:last_punctuation_index + 1]
    #         return Extract(sentence, sentence_to_check)
    #     return Extract(sentence_to_check, sentence_to_check)

    # async def generate_sentence(self, messages : message_thread) -> AsyncGenerator[str | None, None]:
    #     sentence = ''
    #     async for content in self.__client.streaming_call(messages):
    #         if content is not None:
    #             sentence += content
    #             # Check for the last occurrence of sentence-ending punctuation
    #             sentence_and_rest: Extract = self.find_last_sentence_terminator(sentence)

    #             if ('assist' in content) and (num_sentences>0):
    #                 logging.info(f"'assist' keyword found. Ignoring sentence which begins with: {sentence}")
    #                 break

    #             content_edit = unicodedata.normalize('NFKC', content)
    #             # check if content marks the end of a sentence
    #             if (any(char in content_edit for char in self.end_of_sentence_chars)):
    #                 yield self.clean_sentence(sentence)
    #         else:
    #             break

    # def keyword_extraction(self, sentence: str, characters_in_conversation: Characters, possible_keywords: list[str]) -> list[str]:

    def __does_try_to_speak_for_player(self, keyword: str, actors_in_conversation: Characters) -> bool:
        pc: Character | None = actors_in_conversation.get_player_character()
        return keyword == "Player" or (pc != None and pc.Name.__contains__(keyword))
    
    def __matching_action_keyword(self, keyword: str, actions: list[action]) -> action | None:
        for a in actions:
            if keyword.lower() == a.Keyword.lower():
                return a
        return None

    async def process_response(self, active_character: Character, blocking_queue: sentence_queue, messages : message_thread, characters: Characters, actions: list[action]):
        """Stream response from LLM one sentence at a time"""

        try:
            complete_sentence = ''
            remaining_content = ''
            full_reply = ''
            num_sentences = 0
            action_taken = False
            actions_in_sentence: list[action] = []
            while True:
                try:
                    start_time = time.time()
                    async for content in self.__client.streaming_call(messages= messages):
                        if self.__stop_generation:
                            break
                        if content is not None:
                            complete_sentence += content
                            # Check for the last occurrence of sentence-ending punctuation
                            last_punctuation = max(complete_sentence.rfind('.'), complete_sentence.rfind('!'), complete_sentence.rfind(':'), complete_sentence.rfind('?'))
                            if last_punctuation != -1:
                                # Split the sentence at the last punctuation mark
                                remaining_content = complete_sentence[last_punctuation + 1:]
                                complete_sentence = complete_sentence[:last_punctuation + 1]

                            if ('assist' in content) and (num_sentences>0):
                                logging.info(f"'assist' keyword found. Ignoring sentence which begins with: {complete_sentence}")
                                break

                            content_edit = unicodedata.normalize('NFKC', content)
                            # check if content marks the end of a sentence
                            if (any(char in content_edit for char in self.end_of_sentence_chars)):
                                complete_sentence = self.clean_sentence(complete_sentence)

                                if len(complete_sentence.strip()) < 3:
                                    logging.info(f'Skipping voiceline that is too short: {complete_sentence}')
                                    break

                                logging.log(self.loglevel, f"LLM returned sentence took {time.time() - start_time} seconds to execute")

                                if complete_sentence and ':' in content_edit:
                                    keyword_extraction = complete_sentence.strip()[:-1] #.lower()
                                    # if LLM is switching character
                                    # Find the first character whose name starts with keyword_extraction
                                    matching_character_key = next((key for key in characters.get_all_names() if key.startswith(keyword_extraction)), None)
                                    if matching_character_key:
                                        logging.info(f"Switched to {matching_character_key}")
                                        active_character = characters.get_character_by_name(matching_character_key)
                                        self.__tts.change_voice(active_character.TTS_voice_model)

                                        # Find the index of the matching character
                                        # self.character_num = characters.get_all_names().index(matching_character_key)

                                        full_reply += complete_sentence
                                        complete_sentence = remaining_content
                                        action_taken = True
                                    elif self.__does_try_to_speak_for_player(keyword_extraction, characters):
                                        logging.info(f"Stopped LLM from speaking on behalf of the player")
                                        break
                                    else:
                                        action_to_take: action | None = self.__matching_action_keyword(keyword_extraction, actions)
                                        if action_to_take:
                                            logging.info(action_to_take.Info_text)
                                            actions_in_sentence.append(action_to_take)
                                            full_reply += complete_sentence
                                            complete_sentence = remaining_content
                                            action_taken = True

                                if action_taken == False:
                                    # Generate the audio and return the audio file path
                                    # Put the audio file path in the sentence_queue
                                    new_sentence = self.generate_sentence(' ' + complete_sentence + ' ', active_character)
                                    
                                    if new_sentence:
                                        for a in actions_in_sentence:
                                            new_sentence.Actions.append(a.Game_action_identifier)
                                        blocking_queue.put(new_sentence)
                                    else:
                                        break
                                    # await sentence_queue.put(self.generate_sentence(' ' + complete_sentence + ' ', active_character))
                                    actions_in_sentence = []
                                    full_reply += complete_sentence
                                    num_sentences += 1
                                    complete_sentence = remaining_content
                                    remaining_content = ''

                                else:
                                    action_taken = False
                    break
                except Exception as e:
                    logging.error(f"LLM API Error: {e}")
                    error_response = "I can't find the right words at the moment."
                    new_sentence = self.generate_sentence(error_response, active_character)
                    if new_sentence:
                        blocking_queue.put(new_sentence)                
                    logging.log(self.loglevel, 'Retrying connection to API...')
                    time.sleep(5)

            # Mark the end of the response
            # await sentence_queue.put(None)
        except Exception as e:
            logging.error(f"LLM API Error: {e}")
        finally:
            logging.log(23, f"Full response saved ({self.__client.calculate_tokens_from_text(full_reply)} tokens): {full_reply}")
            blocking_queue.Is_more_to_come = False
            # This sentence is required to make sure there is one in case the game is already waiting for it
            # before the ChatManager realises there is not another message coming from the LLM
            blocking_queue.put(sentence(active_character,"","",0, True))
            self.__is_generating = False
