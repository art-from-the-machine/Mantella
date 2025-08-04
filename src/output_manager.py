import asyncio
from threading import Lock
import logging
import time
import unicodedata
import json
import ast
import re
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
from src.llm.function_client import FunctionClient
from src.tts.ttsable import TTSable
from src.tts.synthesization_options import SynthesizationOptions

class ChatManager:
    def __init__(self, config: ConfigLoader, tts: TTSable, client: AIClient, function_client: FunctionClient):
        self.loglevel = 28
        self.__config: ConfigLoader = config
        self.__tts: TTSable = tts
        self.__client: AIClient = client
        self.__function_client: FunctionClient = function_client
        self.__is_generating: bool = False
        self.__stop_generation = asyncio.Event()
        self.__tts_access_lock = Lock()
        self.__is_first_sentence: bool = False
        self.__end_of_sentence_chars = ['.', '?', '!', ';', '。', '？', '！', '；']
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in self.__end_of_sentence_chars]
        self.__generated_function_results_lock = Lock()
        self.__generated_function_results = None

    @property
    def is_generating(self):
        return self.__is_generating

    @property
    def generated_function_results(self):
        with self.__generated_function_results_lock:
            return self.__generated_function_results

    @generated_function_results.setter
    def generated_function_results(self, value):
        with self.__generated_function_results_lock:
            self.__generated_function_results = value

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
            while retries < max_retries:
                try:
                    start_time = time.time()
                    async for content in self.__client.streaming_call(messages=messages, is_multi_npc=is_multi_npc):
                        if self.__stop_generation.is_set():
                            break
                        if not content:
                            continue

                        if first_token:
                            logging.log(self.loglevel, f"Roleplay LLM took {round(time.time() - start_time, 2)} seconds to respond")
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
                                    blocking_queue.put(new_sentence)
                                    parsed_sentence = None
                        if settings.stop_generation:
                            break
                        if settings.interrupting_action:
                            # If there is an interrupting action, stop the generation after the next sentence
                            settings.stop_generation = True
                    break #if the streaming_call() completed without exception, break the while loop
                            
                    # TODO: Incorporate veto logic into new sentence parser
                    # # --- Add this block to handle the <veto> tag ---
                    # has_veto = False
                    # if current_sentence.strip().startswith('<veto>'):
                    #     logging.log(28, f"Detected <veto> tag in sentence: {current_sentence}")
                    #     # Remove the <veto> tag
                    #     current_sentence = current_sentence.strip()[len('<veto>'):].lstrip()
                    #     has_veto = True
                        
                    # # --- Set the has_veto attribute ---
                    # new_sentence.has_veto = has_veto
                    # is_first_line_of_response = False
                    
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

    def generate_simple_response_from_message_thread(self, messages, response_type: str, tools_list: list[str] = None):
        # Generates a response for a single message without characters or actions.
        self.__is_generating = True
        if response_type.lower() == "function":
            llm_response = self.__function_client.request_call(messages, tools_list)
            if llm_response:
                # Check if the response is a string and convert it to JSON if necessary
                if isinstance(llm_response, str):
                    try:
                        llm_response = json.loads(llm_response)
                    except json.JSONDecodeError as e:
                        logging.error("Failed to decode JSON from LLM response: %s", e)
                        return

                # Check if 'choices' exists and is not empty
                if 'choices' in llm_response and llm_response['choices']:
                    for choice in llm_response['choices']:
                        # Safely access 'message' and 'tool_calls'
                        tool_calls = choice.get('message', {}).get('tool_calls')
                        content = (choice.get('message', {}).get('content') or '').strip()
                        if tool_calls and isinstance(tool_calls, list) and tool_calls:
                            first_tool_call = tool_calls[0]
                            self.generated_function_results = self.process_tool_call(first_tool_call)
                        elif "<tool_call>" in choice.get('message', {}).get('content', '') :
                            self.generated_function_results = self.process_pseudo_tool_call(choice.get('message', {}).get('content', ''))
                            return
                        elif content.startswith('```'):
                            content = content.replace('```json', '').strip()
                            content = content.replace('```', '').strip()
                            self.generated_function_results = self.process_unlabeled_function_content(content)
                            return
                        elif content.startswith('{') and '}' in content:
                            # Attempt to parse the content as a function call
                            self.generated_function_results = self.process_unlabeled_function_content(content)
                            return
                        else:
                            logging.debug("No tool calls found in Function LLM response or tool_calls is not a list. Aborting function call.")
                else:
                    logging.debug("No choices found in Function LLM response. Aborting function call.")
            else:
                logging.debug("No valid response received from LLM")
        else:
            logging.debug("Unsupported response type for direct calls")
        self.__is_generating = False

    def process_tool_call(self,tool_call):
        # Check if 'function' and required fields are in tool_call
        if 'function' in tool_call and 'name' in tool_call['function'] and 'arguments' in tool_call['function']:
            function_name = tool_call['function']['name']
            arguments = json.loads(tool_call['function']['arguments'])
            # Safely get 'type' from tool_call or default to 'unknown'
            call_type = tool_call.get('type', 'unknown') if isinstance(tool_call, dict) else 'unknown'
            return call_type, function_name, arguments
            # Optional: Store values in variables if further processing is needed
            # function_name_var = function_name
            # call_type_var = call_type
            # arguments_var = arguments
        else:
            logging.debug("Missing function details in tool call")

    def process_pseudo_tool_call(self, tool_call_string):
        logging.debug("Processing pseudo tool call")
        # Find the first occurrence of <tool_call> and remove everything before it
        start_index = tool_call_string.find('<tool_call>')
        if start_index == -1:
            logging.debug("Error in pseudo tool call: <tool_call> substring not found in the output.")
            return None

        content = tool_call_string[start_index + len('<tool_call>'):].strip()

        # Patterns to match different possible formats, including self-closing tags
        patterns = [
            # Pattern for <FunctionCall ...> ... </FunctionCall> or self-closing tags
            r'<FunctionCall\s+name=["\']([^"\']+)["\']\s+arguments=(\{.*?\})\s*(?:/?>|>\s*</FunctionCall>)',
            # Pattern for JSON content
            r'(\{.*\})'
        ]

        function_name = None
        arguments = None

        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                if 'FunctionCall' in pattern:
                    # Extract function name and arguments
                    function_name = match.group(1)
                    arguments_str = match.group(2)
                    arguments = self._try_parse_json(arguments_str)
                else:
                    # Try to parse the entire content as JSON
                    json_like_str = match.group(1)
                    data = self._try_parse_json(json_like_str)
                    if data:
                        # First attempt: check top-level
                        function_name = data.get('name')
                        arguments = data.get('arguments')

                        # If not found at top-level, try inside 'properties'
                        if not function_name or not arguments:
                            properties = data.get('properties', {})
                            if 'name' in properties and 'arguments' in properties:
                                function_name = properties['name']
                                arguments = properties['arguments']
                break  # Exit the loop since we've found a match

        if function_name and arguments is not None:
            return 'function', function_name, arguments
        else:
            logging.error("Error in pseudo tool call :Failed to parse the tool call string.")
            return None

    def _try_parse_json(self, json_like_str):
        """Attempt to parse a string as JSON. If that fails because of single quotes,
        use ast.literal_eval to convert it to a Python object and then back to JSON."""
        try:
            # Try parsing as valid JSON
            return json.loads(json_like_str)
        except json.JSONDecodeError:
            try:
                # Try to reformat the JSON string
                return json.loads(self._fix_json_string(json_like_str))
            except Exception as e:
                try:
                    python_obj = ast.literal_eval(json_like_str)
                    # Convert Python object to JSON string
                    json_str = json.dumps(python_obj)
                    return json.loads(json_str)
                except Exception as e:
                    logging.error(f"Function LLM : JSON error. Failed to parse {json_like_str}: {e}")
                    return None

    def _fix_json_string(self, json_str):
        """Convert Python-style string to valid JSON"""
        # Replace single quotes with double quotes
        json_str = json_str.replace("'", '"')
        # Replace Python booleans with JSON booleans
        json_str = json_str.replace("True", "true").replace("False", "false")
        return json_str

    def process_unlabeled_function_content(self, content):
        logging.debug("Attempting to process unlabeled function content")
        call_type = 'function'  # As specified, call_type is always 'function'

        # Find the first '{' character
        start_idx = content.find('{')
        if start_idx == -1:
            logging.debug("Error while processing unlabeled function content from Function LLM : No JSON object found in content.")
            return None

        # Initialize brace count and find the matching '}'
        brace_count = 0
        end_idx = -1
        for idx in range(start_idx, len(content)):
            char = content[idx]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = idx + 1  # Include the closing brace
                    break

        if end_idx == -1:
            logging.debug("Error while processing unlabeled function content from Function LLM : No matching closing brace found for JSON object.")
            return None

        # Extract the JSON string
        json_str = content[start_idx:end_idx]

        # Attempt to parse the JSON string
        try:
            data = self._try_parse_json(json_str)
        except Exception as e:
            logging.error(f"Error while processing unlabeled function content from Function LLM : Failed to parse content as JSON {json_str}: {e}")
            return None

        # Try top-level extraction first
        function_name = data.get('name')
        arguments = data.get('arguments')

        # If not found at the top-level, try fallback under 'properties'
        if function_name is None or arguments is None:
            properties = data.get('properties', {})
            function_name = function_name or properties.get('name')
            arguments = arguments or properties.get('arguments')

        if function_name and arguments is not None:
            return call_type, function_name, arguments
        else:
            logging.error(f"Error while processing unlabeled function content from Function LLM : Function name or arguments missing in content {json_str}.")
            return None


    
        
