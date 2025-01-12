import asyncio
from threading import Lock
import wave
import logging
import time
import re
import unicodedata
import json
import ast
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
from src.llm.openai_client import openai_client, function_client
from src.tts.ttsable import ttsable
from src.tts.synthesization_options import SynthesizationOptions

class ChatManager:
    @utils.time_it
    def __init__(self, game: gameable, config: ConfigLoader, tts: ttsable, client: openai_client, function_client_instance: function_client):
        self.loglevel = 28
        self.__game: gameable = game
        self.__config: ConfigLoader = config
        # self.max_response_sentences = config.max_response_sentences
        # self.language = config.language
        # self.wait_time_buffer = config.wait_time_buffer
        self.__tts: ttsable = tts
        self.__client: openai_client = client
        self.__function_client: function_client = function_client_instance 
        self.__is_generating: bool = False
        self.__stop_generation = asyncio.Event()
        self.__tts_access_lock = Lock()
        # self.__number_words_tts: int = config.number_words_tts
        self.__end_of_sentence_chars = ['.', '?', '!', ':', ';', '。', '？', '！', '；', '：']
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in self.__end_of_sentence_chars]
        self.__generated_function_results_lock = Lock()
        self.__generated_function_results = None
        self.__has_character_switch_occurred = None

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
    def tts(self) -> ttsable:
        return self.__tts
    
    @property
    def has_character_switch_occurred(self):
        return self.__has_character_switch_occurred

    @utils.time_it
    def generate_sentence(self, text: str, character_to_talk: Character, is_first_line_of_response: bool = False, is_system_generated_sentence: bool = False) -> mantella_sentence:
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
                synth_options = SynthesizationOptions(character_to_talk.is_in_combat, is_first_line_of_response)
                audio_file = self.__tts.synthesize(character_to_talk.tts_voice_model, text, character_to_talk.in_game_voice_model, character_to_talk.csv_in_game_voice_model, character_to_talk.voice_accent, synth_options, character_to_talk.advanced_voice_model)
            except Exception as e:
                error_text = f"Text-to-Speech Error: {e}"
                logging.log(29, error_text)
                return mantella_sentence(character_to_talk, text, "", 0, True, error_text)
            return mantella_sentence(character_to_talk, text, audio_file, self.get_audio_duration(audio_file), is_system_generated_sentence)

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

    @utils.time_it
    def __matching_action_keyword(self, keyword: str, actions: list[action]) -> action | None:
        for a in actions:
            if keyword.lower() == a.keyword.lower():
                return a
        return None
    
    @utils.time_it
    def __character_switched_to(self, extracted_keyword: str, charaters_in_conversation: Characters) -> Character | None:
        for actor in charaters_in_conversation.get_all_characters():
            actor_name = actor.name.lower()
            if actor_name.startswith(extracted_keyword.lower()):
                return actor
        return None

    @utils.time_it
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
            first_token = True
            is_first_line_of_response = True
            self.__has_character_switch_occurred = False
            while True:
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
                            # --- Add this block to handle the <veto> tag ---
                            has_veto = False
                            if current_sentence.strip().startswith('<veto>'):
                                logging.log(28, f"Detected <veto> tag in sentence: {current_sentence}")
                                # Remove the <veto> tag
                                current_sentence = current_sentence.strip()[len('<veto>'):].lstrip()
                                has_veto = True

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
                                        self.__has_character_switch_occurred=True
                                        if character_switched_to.is_player_character:
                                            logging.log(28, f"Stopped LLM from speaking on behalf of the player")
                                            break
                                        else:
                                            logging.log(28, f"Switched to {character_switched_to.name}")
                                            active_character = character_switched_to
                                            full_reply += f"{keyword_extraction}: "
                                            self.__tts.change_voice(active_character.tts_voice_model, active_character.in_game_voice_model, active_character.csv_in_game_voice_model, active_character.advanced_voice_model, voice_accent=active_character.voice_accent)
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
                                
                                if self.__stop_generation.is_set():
                                    break
                                new_sentence = self.generate_sentence(' ' + sentence + ' ', active_character, is_first_line_of_response)
                                # --- Set the has_veto attribute ---
                                new_sentence.has_veto = has_veto
                                is_first_line_of_response = False
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

            if not self.__stop_generation.is_set():
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
                        elif content.startswith('{') and '}' in content:
                            # Attempt to parse the content as a function call
                            self.generated_function_results = self.process_unlabeled_function_content(content)
                            return
                        else:
                            print("No tool calls found in response or tool_calls is not a list")
                else:
                    print("No choices found in response")
            else:
                logging.error("No valid response received from LLM")
        else:
            logging.error("Unsupported response type for direct calls")
        self.__is_generating = False

    def process_tool_call(self,tool_call):
        # Check if 'function' and required fields are in tool_call
        if 'function' in tool_call and 'name' in tool_call['function'] and 'arguments' in tool_call['function']:
            function_name = tool_call['function']['name']
            arguments = json.loads(tool_call['function']['arguments'])
            # Safely get 'type' from tool_call or default to 'unknown'
            call_type = tool_call.get('type', 'unknown') if isinstance(tool_call, dict) else 'unknown'
        

            print("Function Name:", function_name)
            print("Call Type:", call_type)
            print("Arguments:", arguments)
            return call_type, function_name, arguments
            # Optional: Store values in variables if further processing is needed
            # function_name_var = function_name
            # call_type_var = call_type
            # arguments_var = arguments
        else:
            print("Missing function details in tool call")

    def process_pseudo_tool_call(self, tool_call_string):
        print("Processing pseudo tool call")
        # Find the first occurrence of <tool_call> and remove everything before it
        start_index = tool_call_string.find('<tool_call>')
        if start_index == -1:
            print("Error: <tool_call> substring not found in the output.")
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
            print("Failed to parse the tool call string.")
            return None

    def _try_parse_json(self, json_like_str):
        """Attempt to parse a string as JSON. If that fails because of single quotes,
        use ast.literal_eval to convert it to a Python object and then back to JSON."""
        try:
            # Try parsing as valid JSON
            return json.loads(json_like_str)
        except json.JSONDecodeError:
            # Try using literal_eval to handle single quotes
            try:
                python_obj = ast.literal_eval(json_like_str)
                # Convert Python object to JSON string
                json_str = json.dumps(python_obj)
                return json.loads(json_str)
            except Exception as e:
                print("Failed to parse using literal_eval:", e)
                return None
        
    def process_unlabeled_function_content(self, content):
        print("Attempting to process unlabeled function content")
        call_type = 'function'  # As specified, call_type is always 'function'

        # Find the first '{' character
        start_idx = content.find('{')
        if start_idx == -1:
            print("No JSON object found in content.")
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
            print("No matching closing brace found for JSON object.")
            return None

        # Extract the JSON string
        json_str = content[start_idx:end_idx]

        # Attempt to parse the JSON string
        try:
            # Replace single quotes with double quotes
            json_str = json_str.replace("'", '"')
            # Replace Python booleans with JSON booleans
            json_str = json_str.replace("True", "true").replace("False", "false")

            data = json.loads(json_str)

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
                print("Function name or arguments missing in content.")
                return None

        except json.JSONDecodeError as e:
            print("Failed to parse content as JSON:", e)
            return None


    
        
