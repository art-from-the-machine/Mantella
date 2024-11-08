import asyncio
from threading import Lock
import wave
import logging
import time
import re
import unicodedata
from openai import APIConnectionError
from src.games.gameable import gameable
from src.conversation.action import action
from src.llm.sentence_queue import sentence_queue
from src.config.config_loader import ConfigLoader
from src.llm.sentence import sentence as mantella_sentence #<- Do not collide with frequent and logical use of "sentence" when generating text from the LLM
import src.utils as utils
from src.characters_manager import Characters
from src.character_manager import Character
from src.llm.messages import message
from src.llm.message_thread import message_thread
from src.llm.openai_client import openai_client
from src.tts.ttsable import ttsable
from src.tts.synthesization_options import SynthesizationOptions

class ChatManager:
    def __init__(self, game: gameable, config: ConfigLoader, tts: ttsable, client: openai_client):
        self.loglevel = 28
        self.__game: gameable = game
        self.__config: ConfigLoader = config
        # self.max_response_sentences = config.max_response_sentences
        # self.language = config.language
        # self.wait_time_buffer = config.wait_time_buffer
        self.__tts: ttsable = tts
        self.__client: openai_client = client
        self.__is_generating: bool = False
        self.__stop_generation: bool = False
        self.__tts_access_lock = Lock()
        # self.__number_words_tts: int = config.number_words_tts
        self.__end_of_sentence_chars = ['.', '?', '!', ':', ';']
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in self.__end_of_sentence_chars]

    def generate_sentence(self, text: str, character_to_talk: Character, is_system_generated_sentence: bool = False) -> mantella_sentence:
        """Generates the audio for a text and returns the corresponding sentence

        Args:
            text (str): the text to be voices
            character_to_talk (Character): the character to say the sentence
            is_system_generated_sentence (bool, optional): Is this sentence system generated? Defaults to False.

        Returns:
            mantella_sentence | None: _description_
        """
        with self.__tts_access_lock:
            try:
                synth_options = SynthesizationOptions(character_to_talk.is_in_combat)
                audio_file = self.__tts.synthesize(character_to_talk.tts_voice_model, text, character_to_talk.in_game_voice_model, character_to_talk.csv_in_game_voice_model, character_to_talk.voice_accent, synth_options, character_to_talk.advanced_voice_model)
            except Exception as e:
                error_text = f"Text-to-Speech Error: {e}"
                logging.log(29, error_text)
                return mantella_sentence(character_to_talk, text, "", 0, True, error_text)
            return mantella_sentence(character_to_talk, text, audio_file, self.get_audio_duration(audio_file), is_system_generated_sentence)

    def num_tokens(self, content_to_measure: message | str | message_thread | list[message]) -> int:
        """Measures the length of an input in tokens

        Args:
            content_to_measure (message | str | message_thread | list[message]): the input to measure the tokens of

        Returns:
            int: count tokens in the input
        """
        if isinstance(content_to_measure, message_thread) or isinstance(content_to_measure, list):
            return openai_client.num_tokens_from_messages(content_to_measure)
        else:
            return openai_client.num_tokens_from_message(content_to_measure, None)

    def generate_response(self, messages: message_thread, characters: Characters, blocking_queue: sentence_queue, actions: list[action]):
        """Starts generating responses by the LLM for the current state of the input messages

        Args:
            messages (message_thread): _description_
            characters (Characters): _description_
            blocking_queue (sentence_queue): _description_
            actions (list[action]): _description_
        """
        if(not characters.last_added_character):
            return
        self.__is_generating = True
        
        asyncio.run(self.process_response(characters.last_added_character, blocking_queue, messages, characters, actions))
    
    def stop_generation(self):
        """Stops the current generation and only returns once this stop has been successful
        """
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
        duration = frames / float(rate) + self.__config.wait_time_buffer
        return duration
 
    def clean_sentence(self, sentence: str) -> str:
        def remove_as_a(sentence: str) -> str:
            """Remove 'As an XYZ,' from beginning of sentence"""
            if sentence.startswith('As a'):
                if ', ' in sentence:
                    logging.log(28, f"Removed '{sentence.split(', ')[0]} from response")
                    sentence = sentence.replace(sentence.split(', ')[0]+', ', '')
            return sentence
        
        def parse_asterisks_brackets(sentence: str) -> str:
            if ('*' in sentence):
                original_sentence = sentence
                sentence = re.sub(r'\*[^*]*?\*', '', sentence)
                sentence = sentence.replace('*', '')

                if sentence != original_sentence:
                    removed_text = original_sentence.replace(sentence.strip(), '').strip()
                    logging.log(28, f"Removed asterisks text from response: {removed_text}")

            if ('(' in sentence) or (')' in sentence):
                # Check if sentence contains two brackets
                bracket_check = re.search(r"\(.*\)", sentence)
                if bracket_check:
                    logging.log(28, f"Removed brackets text from response: {sentence}")
                    # Remove text between brackets
                    sentence = re.sub(r"\(.*?\)", "", sentence)
                else:
                    logging.log(28, f"Removed response containing single bracket: {sentence}")
                    sentence = ''

            return sentence
        
        if ('Well, well, well' in sentence):
            sentence = sentence.replace('Well, well, well', 'Well well well')

        sentence = remove_as_a(sentence)
        sentence = sentence.replace('\n', ' ')
        sentence = sentence.replace('"','')
        sentence = sentence.replace('[', '(')
        sentence = sentence.replace(']', ')')
        sentence = sentence.replace('{', '(')
        sentence = sentence.replace('}', ')')
        # local models sometimes get the idea in their head to use double asterisks **like this** in sentences instead of single
        # this converts double asterisks to single so that they can be filtered out appropriately
        sentence = sentence.replace('**','*')
        if self.__config.try_filter_narration:
            sentence = parse_asterisks_brackets(sentence)
        sentence = sentence.strip() + " "
        return sentence

    def __matching_action_keyword(self, keyword: str, actions: list[action]) -> action | None:
        for a in actions:
            if keyword.lower() == a.keyword.lower():
                return a
        return None
    
    def __character_switched_to(self, extracted_keyword: str, charaters_in_conversation: Characters) -> Character | None:
        for actor in charaters_in_conversation.get_all_characters():
            actor_name = actor.name.lower()
            if actor_name.startswith(extracted_keyword.lower()):
                return actor
        return None

    async def process_response(self, active_character: Character, blocking_queue: sentence_queue, messages : message_thread, characters: Characters, actions: list[action]):
        """Stream response from LLM one sentence at a time"""

        try:
            sentence = ''
            remaining_content = ''
            full_reply = ''
            num_sentences = 0
            #Added from xTTS implementation
            accumulated_sentence = ''
            cumulative_sentence_bool = False
            current_sentence: str = ""
            actions_in_sentence: list[action] = []
            while True:
                try:
                    start_time = time.time()
                    async for content in self.__client.streaming_call(messages=messages, is_multi_npc=characters.contains_multiple_npcs()):
                        if self.__stop_generation:
                            break
                        if not content:
                            continue
                        
                        sentence += content
                        # Check for the last occurrence of sentence-ending punctuation within first 150 chars
                        last_punctuation = max(sentence.rfind(p,0, 148) for p in self.__end_of_sentence_chars)
                        
                        asterisks_count = sentence.count('*')
                        if (last_punctuation != -1) and (asterisks_count % 2 == 0):
                            # Split the sentence at the last punctuation mark
                            remaining_content = sentence[last_punctuation + 1:]
                            # if sentence is contained in bracket or asterisk, include the bracket / asterisk
                            if remaining_content.strip() in ['*',')','}',']']:
                                current_sentence = sentence
                                remaining_content = ''
                            else:
                                current_sentence = sentence[:last_punctuation + 1]

                            current_sentence = self.clean_sentence(current_sentence)
                            if not current_sentence:
                                sentence = remaining_content
                                continue
                            
                            if not self.__game.is_sentence_allowed(current_sentence, num_sentences):
                                continue
                            
                            # New logic to handle conditions based on the presence of a colon and the state of `accumulated_sentence`
                            content_edit = unicodedata.normalize('NFKC', current_sentence)
                            if ':' in content_edit:
                                if accumulated_sentence:  # accumulated_sentence is not empty
                                    cumulative_sentence_bool = True
                                else:  # accumulated_sentence is empty
                                    # Split the sentence at the colon
                                    parts = content_edit.split(':', 1)
                                    keyword_extraction = parts[0].strip().lstrip("*").lstrip('"').strip() #This is very rough. Should use a Regex
                                    current_sentence = parts[1].strip() if len(parts) > 1 else ''
                                    # if LLM is switching character
                                    # Find the first character whose name starts with keyword_extraction
                                    if keyword_extraction == "Player":
                                        logging.log(28, f"Stopped LLM from speaking on behalf of the player")
                                        break
                                    character_switched_to: Character | None = self.__character_switched_to(keyword_extraction, characters)
                                    if character_switched_to:
                                        if character_switched_to.is_player_character:
                                            logging.log(28, f"Stopped LLM from speaking on behalf of the player")
                                            break
                                        else:
                                            logging.log(28, f"Switched to {character_switched_to.name}")
                                            active_character = character_switched_to
                                            full_reply += f"{keyword_extraction}: "
                                            self.__tts.change_voice(active_character.tts_voice_model, voice_accent=active_character.voice_accent)
                                    else:
                                        action_to_take: action | None = self.__matching_action_keyword(keyword_extraction, actions)
                                        if action_to_take:
                                            logging.log(28, action_to_take.info_text)
                                            actions_in_sentence.append(action_to_take)
                                            full_reply += f"{keyword_extraction}: "
                                            sentence = remaining_content

                            # Accumulate sentences if less than X words
                            if len(accumulated_sentence.split()) + len(current_sentence.split()) < self.__config.number_words_tts and cumulative_sentence_bool == False:
                                accumulated_sentence += current_sentence
                                sentence = remaining_content
                                continue
                            else:
                                if cumulative_sentence_bool == True:
                                    sentence = accumulated_sentence
                                else:
                                    sentence = accumulated_sentence + current_sentence
                                accumulated_sentence = ''
                                if len(sentence.strip()) <= 3:
                                    logging.log(28, f'Skipping voiceline that is too short: {sentence}')
                                    break
                                
                                logging.log(self.loglevel, f"LLM returned sentence took {time.time() - start_time} seconds to execute")
                                # Generate the audio and return the audio file path
                                # Put the audio file path in the sentence_queue
                                
                                # Try to get the sentence below 148 characters which is the max for Fallout4
                                while len(sentence.encode('utf-8')) > 148:			# Count bytes and not chars
                                    for p in [',', ' ']:                    		# First look for comma, then space
                                        lastp = sentence.rfind(p, 0, 148)
                                        if lastp != -1:
                                            remaining_content = sentence[lastp+1:] + remaining_content
                                            sentence = sentence[:lastp+1]
                                            break
                                   
                                #logging.info(f"[{len(sentence)}] {sentence}")
                                
                                new_sentence = self.generate_sentence(' ' + sentence + ' ', active_character)
                                blocking_queue.put(new_sentence)

                                has_interrupting_action = False
                                if not new_sentence.error_message:
                                    for a in actions_in_sentence:
                                        has_interrupting_action |= a.is_interrupting
                                        new_sentence.actions.append( a.identifier)
                                else:
                                    break
                                
                                full_reply += sentence
                                num_sentences += 1
                                if cumulative_sentence_bool == True :
                                    sentence = current_sentence + remaining_content
                                    cumulative_sentence_bool = False
                                else :
                                    sentence = remaining_content
                                remaining_content = ''
                                actions_in_sentence = []

                                # stop processing LLM response if:
                                # max_response_sentences reached (and the conversation isn't radiant)
                                # conversation has switched from radiant to multi NPC (this allows the player to "interrupt" radiant dialogue and include themselves in the conversation)
                                # the conversation has ended
                                # contains_player_character() == not radiant
                                # the NPC should perform an interrupting action like opening their inventory (subsequent lines get cut off anyway when the game pauses to open the inventory menu)
                                if (num_sentences >= self.__config.max_response_sentences and characters.contains_player_character()) or (has_interrupting_action):
                                    break

                    break
                except Exception as e:
                    logging.error(f"LLM API Error: {e}")                    
                    error_response = "I can't find the right words at the moment."
                    new_sentence = self.generate_sentence(error_response, active_character)
                    blocking_queue.put(new_sentence)
                    if new_sentence.error_message:
                        break
                    else:
                        for a in actions_in_sentence:
                            new_sentence.actions.append( a.identifier)
                    logging.log(self.loglevel, 'Retrying connection to API...')
                    time.sleep(5)

            # Check if there is any accumulated sentence at the end
            if accumulated_sentence and len(accumulated_sentence.strip()) > 3:
                # Generate the audio and return the audio file path
                # Might need to check for len > 150 here
                try:
                    new_sentence = self.generate_sentence(' ' + accumulated_sentence + ' ', active_character)
                    blocking_queue.put(new_sentence)
                    full_reply += accumulated_sentence
                    accumulated_sentence = ''
                except Exception as e:
                    accumulated_sentence = ''
                    logging.error(f"TTS Error: {e}")

            # Mark the end of the response
            # await sentence_queue.put(None)
        except Exception as e:
            if isinstance(e, APIConnectionError):
                if (hasattr(e, 'code')) and (e.code in [401, 'invalid_api_key']): # incorrect API key
                    logging.error(f"Invalid API key. Please ensure you have selected the right model for your service (OpenAI / OpenRouter) via the 'model' setting in MantellaSoftware/config.ini. If you are instead trying to connect to a local model, please ensure the service is running.")
                elif isinstance(e, UnboundLocalError):
                    logging.error('No voice file generated for voice line. Please check your TTS service for errors. The reason for this error is often because a voice model could not be found.')
                else:
                    logging.error(f"LLM API Error: {e}")
            else:
                logging.error(f"LLM API Error: {e}")
        finally:
            logging.log(23, f"Full response saved ({self.__client.calculate_tokens_from_text(full_reply)} tokens): {full_reply.strip()}")
            blocking_queue.is_more_to_come = False
            # This sentence is required to make sure there is one in case the game is already waiting for it
            # before the ChatManager realises there is not another message coming from the LLM
            blocking_queue.put(mantella_sentence(active_character,"","",0, True))
            self.__is_generating = False
