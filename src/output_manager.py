import asyncio
from threading import Lock
import logging
import time
import unicodedata
from openai import APIConnectionError
from src.config.definitions.llm_definitions import NarrationHandlingEnum
from src.llm.output.max_count_sentences_parser import max_count_sentences_parser
from src.llm.output.sentence_length_parser import sentence_length_parser
from src.llm.output.actions_parser import actions_parser
from src.llm.output.change_character_parser import change_character_parser
from src.llm.output.clean_sentence_parser import clean_sentence_parser
from src.llm.output.narration_parser import narration_parser
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.output.sentence_end_parser import sentence_end_parser
from src.llm.sentence_content import SentenceTypeEnum, SentenceContent
from src.conversation.action import action
from src.llm.sentence_queue import SentenceQueue
from src.config.config_loader import ConfigLoader
from src.llm.sentence import Sentence
from src import utils
from src.characters_manager import Characters
from src.character_manager import Character
from src.llm.message_thread import message_thread
from src.llm.ai_client import AIClient
from src.tts.ttsable import TTSable
from src.tts.synthesization_options import SynthesizationOptions

class ChatManager:
    def __init__(self, config: ConfigLoader, tts: TTSable, client: AIClient):
        self.loglevel = 28
        self.__config: ConfigLoader = config
        self.__tts: TTSable = tts
        self.__client: AIClient = client
        self.__is_generating: bool = False
        self.__stop_generation = asyncio.Event()
        self.__tts_access_lock = Lock()
        self.__is_first_sentence: bool = False
        self.__end_of_sentence_chars = ['.', '?', '!', ';', '。', '？', '！', '；', '：']
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in self.__end_of_sentence_chars]

    @property
    def tts(self) -> TTSable:
        return self.__tts
    
    @utils.time_it
    def generate_sentence(self, content: SentenceContent) -> Sentence:
        """Generates the audio for a text and returns the corresponding sentence

        Args:
            text (str): the text to be voices
            character_to_talk (Character): the character to say the sentence
            is_system_generated_sentence (bool, optional): Is this sentence system generated? Defaults to False.

        Returns:
            Sentence | None: _description_
        """

        character_to_talk = content.speaker
        text = ' ' + content.text + ' '
        
        # Check for short voicelines before sending to TTS
        if len(content.text.strip()) < 3:
            logging.warning(f"Skipping TTS for voiceline that is too-short: '{content.text.strip()}'")
            # Return a sentence object without audio - skipping TTS entirely
            return Sentence(SentenceContent(character_to_talk, text, content.sentence_type, True), "", 0)

        with self.__tts_access_lock:
            try:
                if self.__config.narration_handling == NarrationHandlingEnum.USE_NARRATOR and content.sentence_type == SentenceTypeEnum.NARRATION:
                    synth_options = SynthesizationOptions(False, self.__is_first_sentence)
                    audio_file = self.__tts.synthesize(self.__config.narrator_voice, text, self.__config.narrator_voice, self.__config.narrator_voice, "en", synth_options, self.__config.narrator_voice)
                else:
                    synth_options = SynthesizationOptions(character_to_talk.is_in_combat, self.__is_first_sentence)
                    audio_file = self.__tts.synthesize(character_to_talk.tts_voice_model, text, character_to_talk.in_game_voice_model, character_to_talk.csv_in_game_voice_model, character_to_talk.voice_accent, synth_options, character_to_talk.advanced_voice_model)
            except Exception as e:
                utils.play_error_sound()
                error_text = f"Text-to-Speech Error: {e}"
                logging.log(29, error_text)
                return Sentence(SentenceContent(character_to_talk, text, content.sentence_type, True), "", 0, error_text)
            self.__is_first_sentence = False
            return Sentence(SentenceContent(character_to_talk, text, content.sentence_type, content.is_system_generated_sentence, content.actions), audio_file, utils.get_audio_duration(audio_file))

    @utils.time_it
    def generate_response(self, messages: message_thread, characters: Characters, blocking_queue: SentenceQueue, actions: list[action]):
        """Starts generating responses by the LLM for the current state of the input messages

        Args:
            messages (message_thread): _description_
            characters (Characters): _description_
            blocking_queue (SentenceQueue): _description_
            actions (list[action]): _description_
        """
        if(not characters.last_added_character):
            return
        self.__is_generating = True
        
        asyncio.run(self.process_response(characters.last_added_character, blocking_queue, messages, characters, actions))
    
    @utils.time_it
    def stop_generation(self):
        """Stops the current generation and only returns once this stop has been successful
        """
        self.__stop_generation.set()
        while self.__is_generating:
            time.sleep(0.01)
        self.__stop_generation.clear()
        return
 
    @utils.time_it
    async def process_response(self, active_character: Character, blocking_queue: SentenceQueue, messages : message_thread, characters: Characters, actions: list[action]):
        """Stream response from LLM one sentence at a time"""

        raw_response: str = ''  # Track the raw response
        first_token = True
        parsed_sentence: SentenceContent | None = None
        pending_sentence: SentenceContent | None = None
        self.__is_first_sentence = True
        max_retries = 5
        retries = 0

        parser_chain: list[output_parser] = [
            clean_sentence_parser(),
            change_character_parser(characters)]
        if self.__config.narration_handling != NarrationHandlingEnum.DEACTIVATE_HANDLING_OF_NARRATIONS:
            parser_chain.append(narration_parser(self.__config.narration_start_indicators, self.__config.narration_end_indicators, 
                                                 self.__config.speech_start_indicators, self.__config.speech_end_indicators))
        parser_chain.extend([
            sentence_end_parser(),
            actions_parser(actions),
            sentence_length_parser(self.__config.number_words_tts),
            max_count_sentences_parser(self.__config.max_response_sentences, not characters.contains_player_character())
        ])
       
        try:
            current_sentence: str = ''
            settings: sentence_generation_settings = sentence_generation_settings(active_character)
            while retries < max_retries:
                try:
                    start_time = time.time()
                    async for content in self.__client.streaming_call(messages=messages, is_multi_npc=characters.contains_multiple_npcs()):
                        if self.__stop_generation.is_set():
                            break
                        if not content:
                            continue

                        if first_token:
                            logging.log(self.loglevel, f"LLM took {round(time.time() - start_time, 5)} seconds to respond")
                            first_token = False
                        
                        current_sentence += content
                        raw_response += content
                        parsed_sentence: SentenceContent | None = None
                        # Apply parsers
                        for parser in parser_chain:
                            if not parsed_sentence:  # Try to extract a complete sentence
                                parsed_sentence, current_sentence = parser.cut_sentence(current_sentence, settings)
                            if parsed_sentence:  # Apply modifications if we already have a sentence
                                parsed_sentence, pending_sentence = parser.modify_sentence_content(parsed_sentence, pending_sentence, settings)
                            if settings.stop_generation:
                                break
                        if settings.stop_generation:
                            break
                        
                        # Process sentences from the parser chain
                        if parsed_sentence:
                            if not self.__config.narration_handling == NarrationHandlingEnum.CUT_NARRATIONS or parsed_sentence.sentence_type != SentenceTypeEnum.NARRATION:
                                new_sentence = self.generate_sentence(parsed_sentence)
                                blocking_queue.put(new_sentence)
                                parsed_sentence = None
                    break #if the streaming_call() completed without exception, break the while loop
                            
                except Exception as e:
                    retries += 1
                    utils.play_error_sound()
                    logging.error(f"LLM API Error: {e}")
                    
                    error_response = "I can't find the right words at the moment."
                    new_sentence = self.generate_sentence(SentenceContent(active_character, error_response, SentenceTypeEnum.SPEECH, True))
                    blocking_queue.put(new_sentence)
                    if new_sentence.error_message: # If the error message itself has an error, just give up
                        break
                    
                    if retries >= max_retries:
                        logging.log(self.loglevel, f"Max retries reached ({retries}).")
                        break
                    
                    logging.log(self.loglevel, 'Retrying connection to API...')
                    time.sleep(5)

        except Exception as e:
            utils.play_error_sound()
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
            # Handle any remaining content
            if parsed_sentence:
                if not self.__config.narration_handling == NarrationHandlingEnum.CUT_NARRATIONS or parsed_sentence.sentence_type != SentenceTypeEnum.NARRATION:
                    new_sentence = self.generate_sentence(parsed_sentence)
                    blocking_queue.put(new_sentence)
            
            if pending_sentence:
                if not self.__config.narration_handling == NarrationHandlingEnum.CUT_NARRATIONS or pending_sentence.sentence_type != SentenceTypeEnum.NARRATION:
                    new_sentence = self.generate_sentence(pending_sentence)
                    blocking_queue.put(new_sentence)
            logging.log(23, f"Full raw response ({self.__client.get_count_tokens(raw_response)} tokens): {raw_response.strip()}")
            blocking_queue.is_more_to_come = False
            # This sentence is required to make sure there is one in case the game is already waiting for it
            # before the ChatManager realises there is not another message coming from the LLM
            blocking_queue.put(Sentence(SentenceContent(active_character,"",SentenceTypeEnum.SPEECH, True),"",0))
            self.__is_generating = False