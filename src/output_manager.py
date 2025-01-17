import asyncio
from threading import Lock
import wave
import logging
import time
import unicodedata
from openai import APIConnectionError
from src.llm.output.actions_parser import actions_parser
from src.llm.output.change_character_parser import change_character_parser
from src.llm.output.clean_sentence_parser import clean_sentence_parser
from src.llm.output.narration_parser import narration_parser
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.output.sentence_end_parser import sentence_end_parser
from src.llm.sentence_content import sentence_content
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
from src.llm.llm_client import LLMClient
from src.tts.ttsable import ttsable
from src.tts.synthesization_options import SynthesizationOptions

class ChatManager:
    def __init__(self, config: ConfigLoader, tts: ttsable, client: LLMClient):
        self.loglevel = 28
        self.__config: ConfigLoader = config
        self.__tts: ttsable = tts
        self.__client: LLMClient = client
        self.__is_generating: bool = False
        self.__stop_generation = asyncio.Event()
        self.__tts_access_lock = Lock()
        self.__is_first_sentence: bool = False
        self.__end_of_sentence_chars = ['.', '?', '!', ':', ';', '。', '？', '！', '；', '：']
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in self.__end_of_sentence_chars]

    @property
    def tts(self) -> ttsable:
        return self.__tts
    
    @utils.time_it
    def generate_sentence(self, content: sentence_content) -> mantella_sentence:
        """Generates the audio for a text and returns the corresponding sentence

        Args:
            text (str): the text to be voices
            character_to_talk (Character): the character to say the sentence
            is_system_generated_sentence (bool, optional): Is this sentence system generated? Defaults to False.

        Returns:
            mantella_sentence | None: _description_
        """

        character_to_talk = content.speaker
        text = ' ' + content.text + ' '

        with self.__tts_access_lock:
            try:
                if self.__config.narration_handling == "use narrator" and content.is_narration:
                    synth_options = SynthesizationOptions(False, self.__is_first_sentence)
                    audio_file = self.__tts.synthesize(self.__config.narrator_voice, text, self.__config.narrator_voice, self.__config.narrator_voice, "en", synth_options, self.__config.narrator_voice)
                else:
                    synth_options = SynthesizationOptions(character_to_talk.is_in_combat, self.__is_first_sentence)
                    audio_file = self.__tts.synthesize(character_to_talk.tts_voice_model, text, character_to_talk.in_game_voice_model, character_to_talk.csv_in_game_voice_model, character_to_talk.voice_accent, synth_options, character_to_talk.advanced_voice_model)
            except Exception as e:
                utils.play_error_sound()
                error_text = f"Text-to-Speech Error: {e}"
                logging.log(29, error_text)
                return mantella_sentence(sentence_content(character_to_talk, text, content.is_narration, True), "", 0, error_text)
            self.__is_first_sentence = False
            return mantella_sentence(sentence_content(character_to_talk, text, content.is_narration, content.is_system_generated_sentence), audio_file, self.get_audio_duration(audio_file))

    @utils.time_it
    def change_speaker(self, npc: Character):
        self.__tts.change_voice(npc.tts_voice_model, npc.in_game_voice_model, npc.csv_in_game_voice_model, npc.advanced_voice_model, voice_accent=npc.voice_accent, voice_gender=npc.gender, voice_race=npc.race)

    @utils.time_it
    def num_tokens(self, content_to_measure: message | str | message_thread | list[message]) -> int:
        """Measures the length of an input in tokens

        Args:
            content_to_measure (message | str | message_thread | list[message]): the input to measure the tokens of

        Returns:
            int: count tokens in the input
        """
        if isinstance(content_to_measure, message_thread) or isinstance(content_to_measure, list):
            return self.__client.num_tokens_from_messages(content_to_measure)
        else:
            return self.__client.num_tokens_from_message(content_to_measure)

    @utils.time_it
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
    def get_audio_duration(self, audio_file: str):
        """Check if the external software has finished playing the audio file"""

        with wave.open(audio_file, 'r') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()

        # wait `buffer` seconds longer to let processes finish running correctly
        duration = frames / float(rate)
        return duration
 
    @utils.time_it
    async def process_response(self, active_character: Character, blocking_queue: sentence_queue, messages : message_thread, characters: Characters, actions: list[action]):
        """Stream response from LLM one sentence at a time"""

        max_character_per_sentence = 148 #Fallout max
        sentence_end: sentence_end_parser = sentence_end_parser(self.__config.number_words_tts, max_character_per_sentence)
        parser_chain: list[output_parser] = [
            clean_sentence_parser(),
            change_character_parser(characters, self.change_speaker), #Hand the change_speaker function to the character parser to get an immediate update of the character
            narration_parser(),
            sentence_end,
            actions_parser(actions)
        ]
        full_reply: str = ''
        last_generated_sentence_content: sentence_content | None = None
        self.__is_first_sentence = True
        try:
            sentence: str = ''
            settings: sentence_generation_settings = sentence_generation_settings(active_character)
            while True:
                try:
                    # start_time = time.time()
                    async for content in self.__client.streaming_call(messages=messages, is_multi_npc=characters.contains_multiple_npcs()):
                        if self.__stop_generation.is_set():
                            break
                        if not content:
                            continue
                        
                        sentence += content
                        cut_sentence_content: sentence_content | None = None
                        for parser in parser_chain:
                            if cut_sentence_content: #If a sentence has been cut by a previous parser in the chain
                                parser.modify_sentence_content(cut_sentence_content, settings) #Hand it only to the modify methods of subsequent parsers
                                if settings.stop_generation:
                                    break
                            else: #Try to cut until a parser finds a way to cut the output
                                cut_sentence_content, sentence = parser.cut_sentence(sentence, settings)
                        if settings.stop_generation:
                            break

                        if cut_sentence_content: #If the parsers have produced a new sentence
                            if not last_generated_sentence_content: #If we don't have a last sentence, set the first one as last and wait for the second
                                last_generated_sentence_content = cut_sentence_content
                            else:
                                if sentence_end.count_words(cut_sentence_content.text) < self.__config.number_words_tts: #narration and character parser max produce sentences shorter than allowed
                                    if last_generated_sentence_content.speaker == cut_sentence_content.speaker and last_generated_sentence_content.is_narration == cut_sentence_content.is_narration:
                                        #If the previous sentence was by the same speaker and was/wasn't a narration as well, add the sentence that is too short to the last one
                                        last_generated_sentence_content.append_other_sentence_content(cut_sentence_content.text, cut_sentence_content.actions)
                                        cut_sentence_content = None
                                        continue
                                    
                                #If there was a change in speaker or narration flag we can never join them with the next sentence so we just send out the last one
                                if self.__stop_generation.is_set():
                                    break
                                if not self.__config.narration_handling == "cut narrations" or not last_generated_sentence_content.is_narration:                                    
                                    new_sentence = self.generate_sentence(last_generated_sentence_content)
                                    blocking_queue.put(new_sentence)
                                    full_reply += last_generated_sentence_content.text                                
                                last_generated_sentence_content = cut_sentence_content
                    break #if the streaming_call() completed without exception, break the while loop
                            
                except Exception as e:
                    utils.play_error_sound()
                    logging.error(f"LLM API Error: {e}")                    
                    error_response = "I can't find the right words at the moment."
                    new_sentence = self.generate_sentence(sentence_content(active_character, error_response, False, True))
                    blocking_queue.put(new_sentence)
                    if new_sentence.error_message:
                        break
                    # else:
                    #     for a in actions_in_sentence:
                    #         new_sentence.actions.append( a.identifier)
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
            if last_generated_sentence_content:
                new_sentence = self.generate_sentence(last_generated_sentence_content)
                blocking_queue.put(new_sentence)
                full_reply += last_generated_sentence_content.text
            logging.log(23, f"Full response saved ({self.__client.calculate_tokens_from_text(full_reply)} tokens): {full_reply.strip()}")
            blocking_queue.is_more_to_come = False
            # This sentence is required to make sure there is one in case the game is already waiting for it
            # before the ChatManager realises there is not another message coming from the LLM
            blocking_queue.put(mantella_sentence(sentence_content(active_character,"",False, True),"",0))
            self.__is_generating = False