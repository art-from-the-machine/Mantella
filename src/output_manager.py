import asyncio
from threading import Lock
import logging
import time
import unicodedata
import wave
from openai import APIConnectionError
from src.llm.output.sentence_accumulator import sentence_accumulator
from src.config.definitions.llm_definitions import NarrationHandlingEnum
from src.llm.output.max_count_sentences_parser import max_count_sentences_parser
from src.llm.output.sentence_length_parser import sentence_length_parser
from src.llm.output.actions_parser import actions_parser
from src.llm.output.change_character_parser import change_character_parser
from src.llm.output.narration_parser import narration_parser
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.output.sentence_end_parser import sentence_end_parser
from src.llm.sentence_content import SentenceTypeEnum, SentenceContent
from src.conversation.action import Action
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
    def __init__(self, config: ConfigLoader, tts: TTSable, client: AIClient, multi_npc_client: AIClient | None = None, api_file: str = "secret_keys.json"):
        self.loglevel = 28
        self.__config: ConfigLoader = config
        self.__tts: TTSable = tts
        self.__client: AIClient = client
        self.__multi_npc_client: AIClient | None = multi_npc_client
        self.__api_file: str = api_file  # Store API file path for secret key resolution
        self.__is_generating: bool = False
        self.__stop_generation = asyncio.Event()
        self.__tts_access_lock = Lock()
        self.__is_first_sentence: bool = False
        self.__end_of_sentence_chars = ['.', '?', '!', ';', '。', '？', '！', '；', '：']
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in self.__end_of_sentence_chars]
        self.__per_character_clients: dict[str, AIClient] = {}  # Cache for per-character LLM clients

    def update_multi_npc_client(self, multi_npc_client: AIClient | None):
        """Update the multi-NPC client for hot swapping"""
        self.__multi_npc_client = multi_npc_client

    def update_primary_client(self, primary_client: AIClient):
        """Update the primary client for conversations (used for random LLM selection)"""
        self.__client = primary_client
    
    def clear_per_character_client_cache(self):
        """Clear the per-character client cache to force recreation with new settings"""
        self.__per_character_clients.clear()
        logging.info("Cleared per-character LLM client cache")
    
    def _get_per_character_client(self, character: Character) -> AIClient:
        """Get or create a per-character LLM client based on the character's settings.
        
        Args:
            character: The character to get the client for
            
        Returns:
            AIClient: The appropriate LLM client for the character
        """
        # Check if per-character LLM overrides are enabled
        if not self.__config.allow_per_character_llm_overrides:
            return self.__client
        
        # Use cache key based on character ref_id and LLM settings
        cache_key = f"{character.ref_id}_{character.llm_service}_{character.llm_model}"
        
        # Return cached client if available
        if cache_key in self.__per_character_clients:
            return self.__per_character_clients[cache_key]
        
        # Check if character has any LLM override settings
        if not character.llm_service or not character.llm_model:
            # No override, use default client
            return self.__client
        
        # Create per-character client based on character's LLM settings
        try:
            from src.llm.service_provider import llm_service_factory
            
            # Get the appropriate service provider
            service_provider = llm_service_factory.get_provider(character.llm_service)
            if not service_provider:
                logging.warning(f"Unknown LLM service '{character.llm_service}' for character {character.name}. Using default client.")
                return self.__client
            
            # Create client using the service provider
            per_char_client = service_provider.create_client(character.llm_model, self.__config)
            
            # Cache the client
            self.__per_character_clients[cache_key] = per_char_client
            logging.info(f"Created per-character LLM client for {character.name} using {service_provider.get_display_name()} with model: {character.llm_model}")
            return per_char_client
            
        except Exception as e:
            logging.error(f"Failed to create per-character LLM client for {character.name}: {e}. Using default client.")
            return self.__client
    
    @property
    def tts(self) -> TTSable:
        return self.__tts
    
    @utils.time_it
    def hot_swap_settings(self, config: ConfigLoader, tts: TTSable, client: AIClient) -> bool:
        """Attempts to hot-swap settings without ending the conversation.
        
        Args:
            config: Updated config loader instance
            tts: Updated TTS instance
            client: Updated AI client instance
            
        Returns:
            bool: True if hot-swap was successful, False otherwise
        """
        try:
            # Update basic components
            self.__config = config
            self.__tts = tts
            self.__client = client
            
            # Clear per-character client cache so they get recreated with new settings
            self.__per_character_clients.clear()
            
            # Reset first sentence flag for new TTS instance
            self.__is_first_sentence = False
            
            logging.info("ChatManager hot-swap completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"ChatManager hot-swap failed: {e}")
            return False
    
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
            try:
                duration = utils.get_audio_duration(audio_file)
            except (FileNotFoundError, wave.Error) as e:
                logging.error(f"Could not get audio duration for {audio_file}: {e}")
                # Return sentence with zero duration so conversation can continue
                return Sentence(SentenceContent(character_to_talk, text, content.sentence_type, content.is_system_generated_sentence, content.actions), audio_file, 0)
            
            return Sentence(SentenceContent(character_to_talk, text, content.sentence_type, content.is_system_generated_sentence, content.actions), audio_file, duration)

    @utils.time_it
    def generate_response(self, messages: message_thread, characters: Characters, blocking_queue: SentenceQueue, actions: list[Action]):
        """Starts generating responses by the LLM for the current state of the input messages

        Args:
            messages (message_thread): _description_
            characters (Characters): _description_
            blocking_queue (SentenceQueue): _description_
            actions (list[Action]): _description_
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
    async def process_response(self, active_character: Character, blocking_queue: SentenceQueue, messages : message_thread, characters: Characters, actions: list[Action]):
        """Stream response from LLM one sentence at a time"""

        raw_response: str = ''  # Track the raw response
        first_token = True
        parsed_sentence: SentenceContent | None = None
        pending_sentence: SentenceContent | None = None
        self.__is_first_sentence = True
        is_multi_npc = characters.contains_multiple_npcs()
        max_response_sentences = self.__config.max_response_sentences_single if not is_multi_npc else self.__config.max_response_sentences_multi
        max_retries = 5
        retries = 0

        parser_chain: list[output_parser] = [
            change_character_parser(characters)]
        if self.__config.narration_handling != NarrationHandlingEnum.DEACTIVATE_HANDLING_OF_NARRATIONS:
            parser_chain.append(narration_parser(self.__config.narration_start_indicators, self.__config.narration_end_indicators, 
                                                 self.__config.speech_start_indicators, self.__config.speech_end_indicators))
        parser_chain.extend([
            sentence_end_parser(),
            actions_parser(actions),
            sentence_length_parser(self.__config.number_words_tts),
            max_count_sentences_parser(max_response_sentences, not characters.contains_player_character())
        ])

        cut_indicators: set[str] = set()
        for parser in parser_chain:
            indicators = parser.get_cut_indicators()
            for i in indicators:
                cut_indicators.add(i)
        accumulator: sentence_accumulator = sentence_accumulator(list(cut_indicators))
       
        try:
            current_sentence: str = ''
            settings: sentence_generation_settings = sentence_generation_settings(active_character)
            # llm_logged = False  # Track if we've logged the LLM model for this response
            while retries < max_retries:
                try:
                    start_time = time.time()
                    # Select client: multi-NPC always takes precedence in group conversations, then per-character for one-on-one
                    if is_multi_npc and self.__multi_npc_client:
                        # Always use multi-NPC client in multi-NPC conversations (overrides per-character settings)
                        # Random LLM selection for multi-NPC is handled at conversation start, not per-message
                        current_client = self.__multi_npc_client
                    else:
                        # For one-on-one conversations, check for per-character override, then use default
                        per_char_client = self._get_per_character_client(active_character)
                        if per_char_client != self.__client:
                            # Use per-character client if character has specific LLM override
                            current_client = per_char_client
                        else:
                            # Use default client
                            current_client = self.__client
                    # Log which LLM model is being used
                    if hasattr(current_client, 'model_name'):
                        logging.info(f"[LLM: {current_client.model_name}]")
                    else:
                        logging.info(f"[LLM: {type(current_client).__name__}]")
                    async for content in current_client.streaming_call(messages=messages, is_multi_npc=is_multi_npc):
                        if self.__stop_generation.is_set():
                            break
                        if not content:
                            continue

                        if first_token:
                            logging.log(self.loglevel, f"LLM took {round(time.time() - start_time, 5)} seconds to respond")
                            first_token = False
                        
                        raw_response += content
                        accumulator.accumulate(content)
                        while accumulator.has_next_sentence():
                            current_sentence = accumulator.get_next_sentence()
                            # current_sentence += content
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
                            accumulator.refuse(current_sentence)
                            # Process sentences from the parser chain
                            if parsed_sentence:
                                if not self.__config.narration_handling == NarrationHandlingEnum.CUT_NARRATIONS or parsed_sentence.sentence_type != SentenceTypeEnum.NARRATION:
                                    new_sentence = self.generate_sentence(parsed_sentence)
                                    # if new_sentence.text.strip() and not llm_logged:
                                    #     logging.info(f"[LLM: {current_client.model_name}]")
                                    #     llm_logged = True
                                    blocking_queue.put(new_sentence)
                                    parsed_sentence = None
                        if settings.stop_generation:
                                break
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
                    # if new_sentence.text.strip() and not llm_logged:
                    #     logging.info(f"[LLM: {current_client.model_name}]")
                    #     llm_logged = True
                    blocking_queue.put(new_sentence)
            
            if pending_sentence:
                if not self.__config.narration_handling == NarrationHandlingEnum.CUT_NARRATIONS or pending_sentence.sentence_type != SentenceTypeEnum.NARRATION:
                    new_sentence = self.generate_sentence(pending_sentence)
                    # if new_sentence.text.strip() and not llm_logged:
                    #     logging.info(f"[LLM: {current_client.model_name}]")
                    #     llm_logged = True
                    blocking_queue.put(new_sentence)
            logging.log(23, f"Full raw response ({self.__client.get_count_tokens(raw_response)} tokens): {raw_response.strip()}")
            blocking_queue.is_more_to_come = False
            # This sentence is required to make sure there is one in case the game is already waiting for it
            # before the ChatManager realises there is not another message coming from the LLM
            blocking_queue.put(Sentence(SentenceContent(active_character,"",SentenceTypeEnum.SPEECH, True),"",0))
            self.__is_generating = False