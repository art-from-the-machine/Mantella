from abc import ABC, abstractmethod
from openai.types.chat import ChatCompletionMessageParam
from src.config.definitions.llm_definitions import NarrationIndicatorsEnum
from src.config.config_loader import ConfigLoader
from src.llm.sentence_content import SentenceTypeEnum, SentenceContent
from src.character_manager import Character

from src.llm.sentence import Sentence
from src import utils
import logging

class Message(ABC):
    """Base class for messages 
    """
    def __init__(self, text: str, config: ConfigLoader, is_system_generated_message: bool = False):
        self.__text: str = text
        self.__is_multi_npc_message: bool = False
        self.__is_system_generated_message = is_system_generated_message
        if config.narration_indicators == NarrationIndicatorsEnum.BRACKETS:
            self.__narration_start: str = "["
            self.__narration_end: str = "]"
        elif config.narration_indicators == NarrationIndicatorsEnum.ASTERISKS:
            self.__narration_start: str = "*"
            self.__narration_end: str = "*"
        else:
            self.__narration_start: str = "("
            self.__narration_end: str = ")"

    @property
    def text(self) -> str:
        return self.__text
    
    @text.setter
    def text(self, text: str):
        self.__text = text

    @property
    def narration_start(self) -> str:
        return self.__narration_start
    
    @property
    def narration_end(self) -> str:
        return self.__narration_end

    @property
    def is_multi_npc_message(self) -> bool:
        return self.__is_multi_npc_message
    
    @is_multi_npc_message.setter
    def is_multi_npc_message(self, is_multi_npc_message: bool):
        self.__is_multi_npc_message = is_multi_npc_message

    @property
    def is_system_generated_message(self) -> bool:
        return self.__is_system_generated_message
    
    @is_system_generated_message.setter
    def is_system_generated_message(self, is_system_generated_message: bool):
        self.__is_system_generated_message = is_system_generated_message

    @abstractmethod
    def get_openai_message(self) -> ChatCompletionMessageParam:
        """Returns the message in form of an appropriately formatted openai.types.chat.ChatCompletionMessageParam

        Returns:
            ChatCompletionMessageParam: The message ready to be passed to an openai chat.completions call
        """
        pass

    @abstractmethod
    def get_formatted_content(self) -> str:
        pass
    
    @abstractmethod
    def get_dict_formatted_string(self) -> str:
        pass

    @utils.time_it
    def hot_swap_settings(self, config: ConfigLoader) -> bool:
        """Attempts to hot-swap settings without ending the conversation.
        
        Args:
            config: Updated config loader instance
            
        Returns:
            bool: True if hot-swap was successful, False otherwise
        """
        try:
            # Update narration indicators
            if config.narration_indicators == NarrationIndicatorsEnum.BRACKETS:
                self.__narration_start = "["
                self.__narration_end = "]"
            elif config.narration_indicators == NarrationIndicatorsEnum.ASTERISKS:
                self.__narration_start = "*"
                self.__narration_end = "*"
            else:
                self.__narration_start = "("
                self.__narration_end = ")"
            
            return True
            
        except Exception as e:
            logging.error(f"Message hot-swap failed: {e}")
            return False

class join_message(Message):
    """ A internal message logging that a certain actor has joined the conversation this point (for system use only) """
    def __init__(self, character: Character, config: ConfigLoader):
        super().__init__(f"*{character.name} has joined the conversation*", config, False)
        self.character = character

    def get_formatted_content(self) -> str:
        return self.text

    def get_openai_message(self) -> ChatCompletionMessageParam:
        return {"role":"system", "content": self.get_formatted_content(),}
    
    def get_dict_formatted_string(self) -> str:
        dictionary = {"role":"system", "content": self.get_formatted_content(),}
        return f"{dictionary}"
    
class leave_message(Message):
    """  A internal message logging that a certain actor has left the conversation this point (for system use only) """
    def __init__(self, character: Character, config: ConfigLoader):
        super().__init__(f"*{character.name} is no longer part of the conversation*", config, False)
        self.character = character

    def get_formatted_content(self) -> str:
        return self.text

    def get_openai_message(self) -> ChatCompletionMessageParam:
        return {"role":"system", "content": self.get_formatted_content(),}
    
    def get_dict_formatted_string(self) -> str:
        dictionary = {"role":"system", "content": self.get_formatted_content(),}
        return f"{dictionary}"
    

class SystemMessage(Message):
    """A message with the role 'system'. Usually used as the initial main prompt of an exchange with the LLM
    """

    def __init__(self, prompt: str, config: ConfigLoader):
        super().__init__(prompt, config, True)

    def get_formatted_content(self) -> str:
        return self.text

    def get_openai_message(self) -> ChatCompletionMessageParam:
        return {"role":"system", "content": self.get_formatted_content(),}
    
    def get_dict_formatted_string(self) -> str:
        dictionary = {"role":"system", "content": self.get_formatted_content(),}
        return f"{dictionary}"
        
class AssistantMessage(Message):
    """An assistant message containing the response of an LLM to a request.
    Automatically appends the character name in front of the text if provided and if there is only one active_assistant_character
    """
    def __init__(self, config: ConfigLoader, is_system_generated_message: bool = False):
        super().__init__("", config, is_system_generated_message)
        self.__sentences: list[SentenceContent] = []
        self.thoughts_only_of_ref_id: str | None = None # If set, the thoughts of other NPCs are left out
        # Game Master Mode: each NPC turn is its own LLM reply, so each thought is shown right after the turn it was written in.
        # Otherwise one LLM reply holds every NPC's lines and all thoughts are shown at the end
        self.thoughts_in_place: bool = False

    def add_sentence(self, new_sentence: Sentence):
        self.__sentences.append(new_sentence.content)

    def get_formatted_content(self, include_thoughts: bool = True) -> str:
        if len(self.__sentences) < 1:
            return ""

        result = ""
        lastActor: Character | None = None
        was_last_sentence_narration: bool = False
        spoken_ref_ids = self.__spoken_ref_ids()
        thought_ref_id: str | None = None # The speaker of the thought block that was just written, if any
        thought_text: str = ""
        for sentence in self.__sentences:
            if sentence.sentence_type == SentenceTypeEnum.THOUGHT:
                if include_thoughts and self.thoughts_in_place and self.__is_kept_thought(sentence, spoken_ref_ids):
                    text = sentence.text.strip()
                    if thought_ref_id == sentence.speaker.ref_id:
                        # A continuation sentence of the same thought block
                        if text not in thought_text:
                            result += " " + text
                            thought_text += " " + text
                    else:
                        result += f"\n<<thought {sentence.speaker.name}>> {text}"
                        thought_ref_id, thought_text = sentence.speaker.ref_id, text
                        # The next line starts a new turn, so it gets its speaker's name again
                        lastActor = None
                        was_last_sentence_narration = False
                continue
            thought_ref_id = None
            if self.is_multi_npc_message and lastActor != sentence.speaker:
                lastActor = sentence.speaker
                was_last_sentence_narration = False
                result += "\n" + lastActor.name +':'
            if not was_last_sentence_narration and sentence.sentence_type == SentenceTypeEnum.NARRATION:
                result += " " + self.narration_start
            elif was_last_sentence_narration and sentence.sentence_type == SentenceTypeEnum.SPEECH:
                result += self.narration_end + " "
            else:
                result += " "
            was_last_sentence_narration = sentence.sentence_type == SentenceTypeEnum.NARRATION
            result += sentence.text.strip()
        if include_thoughts and not self.thoughts_in_place:
            for speaker_name, kept_thought_text in self.__kept_thoughts(spoken_ref_ids):
                result += f"\n<<thought {speaker_name}>> {kept_thought_text}"
        result = utils.remove_extra_whitespace(result)
        return result

    def __spoken_ref_ids(self) -> set[str]:
        """The NPCs who actually spoke in this reply"""
        return {
            sentence.speaker.ref_id
            for sentence in self.__sentences
            if sentence.sentence_type != SentenceTypeEnum.THOUGHT and sentence.text.strip()
        }

    def __is_kept_thought(self, sentence: SentenceContent, spoken_ref_ids: set[str]) -> bool:
        ref_id = sentence.speaker.ref_id
        if ref_id not in spoken_ref_ids or not sentence.text.strip():
            return False
        return self.thoughts_only_of_ref_id is None or ref_id == self.thoughts_only_of_ref_id

    def __kept_thoughts(self, spoken_ref_ids: set[str]) -> list[tuple[str, str]]:
        """One thought per NPC who actually spoke in this reply. Later duplicates are ignored."""
        merged: dict[str, str] = {}
        order: list[str] = []
        names: dict[str, str] = {}
        for sentence in self.__sentences:
            if sentence.sentence_type != SentenceTypeEnum.THOUGHT:
                continue
            if not self.__is_kept_thought(sentence, spoken_ref_ids):
                continue
            ref_id = sentence.speaker.ref_id
            if ref_id not in merged:
                merged[ref_id] = sentence.text.strip()
                order.append(ref_id)
                names[ref_id] = sentence.speaker.name
            # A second thought block is a separate sentence only when the parser
            # suppressed it. Continuation sentences of the first block are appended
            # when they were still queued. Queued continuations share the speaker
            # and are joined here.
            elif sentence.text.strip() not in merged[ref_id]:
                merged[ref_id] = f"{merged[ref_id]} {sentence.text.strip()}"
        return [(names[ref_id], merged[ref_id]) for ref_id in order]

    def get_openai_message(self, include_thoughts: bool = True) -> ChatCompletionMessageParam:
        return {"role":"assistant", "content": self.get_formatted_content(include_thoughts),}
    
    def get_dict_formatted_string(self) -> str:
        dictionary = {"role":"assistant", "content": self.get_formatted_content(),}
        return f"{dictionary}"

class UserMessage(Message):
    """A user message sent to the LLM. Contains the text from the player and optionally it's name.
    Ingame Events can be added as a list[str]. Each ingame event will be placed before the text of the player in asterisks 
    """
    def __init__(self, config: ConfigLoader, text: str, player_character_name: str = "", is_system_generated_message: bool = False):
        super().__init__(text, config, is_system_generated_message)
        self.__player_character_name: str = player_character_name
        self.__ingame_events: list[str] = []
        self.__time: tuple[str,str] | None = None
        self.is_director_message: bool = False # Director mode: the text is a scene direction, shown as narration without the player's name
        

    @property
    def player_character_name(self) -> str:
        return self.__player_character_name

    def get_formatted_content(self) -> str:
        result = ""
        result += self.get_ingame_events_text()
        if self.__time:
            result += f"{self.narration_start}The time is {self.__time[0]} {self.__time[1]}.{self.narration_end}\n"
        if self.is_director_message:
            if self.text:
                result += f"{self.narration_start}{self.text}{self.narration_end}"
        else:
            if self.is_multi_npc_message:
                result += f"{self.__player_character_name}: "
            result += f"{self.text}"
        # if self.is_multi_npc_message:
        #     result += f"\n[Please respond with replies for as many of your characters as possible.]"
        result = utils.remove_extra_whitespace(result)
        return result
    
    def get_openai_message(self) -> ChatCompletionMessageParam:
        return {"role":"user", "content": self.get_formatted_content(),}
    
    def get_dict_formatted_string(self) -> str:
        dictionary = {"role":"user", "content": self.get_formatted_content(),}
        return f"{dictionary}"

    def add_event(self, events: list[str]):
        for event in events:
            if len(event) > 0:
                self.__ingame_events.append(event)
    
    def count_ingame_events(self) -> int:
        return len(self.__ingame_events)
    
    def get_ingame_events_text(self) -> str:
        result = ""
        for event in self.__ingame_events:
            result += f"{self.narration_start}{event}{self.narration_end}\n"
        return result
    
    def set_ingame_time(self, time: str, time_group: str):
        self.__time = time, time_group


class ImageMessage(Message):
    """A image message sent to the LLM. Contains the a base64 encode image and accompanying description text.
    """
    def __init__(self, config: ConfigLoader, encoded_image: str, text: str = "", resolution: str = "auto", is_system_generated_message: bool = False):
        super().__init__(text, config, is_system_generated_message)
        self.encoded_image = encoded_image
        self.text_content = text
        self.resolution = resolution

    def get_formatted_content(self):
        return f"[Image: {self.encoded_image}] {self.text_content}"

    def get_dict_formatted_string(self):
        return f"Image: {self.encoded_image}, Content: {self.text_content}"

    def get_openai_message(self):
        # Implement the method to return the appropriate format for OpenAI API
        return {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": self.text_content
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{self.encoded_image}",
                        "detail": self.resolution
                    }
                }
            ]
        }
    
class ImageDescriptionMessage(Message):
    """An image description message, similar to a user message but interacted with by the conversation object"""
    def __init__(self, config: ConfigLoader, text: str = "", is_system_generated_message: bool = False):
        super().__init__(text, config, is_system_generated_message)
        self.text_content = text

    def get_formatted_content(self):
        return self.Text

    def get_dict_formatted_string(self):
        dictionary = {"role":"user", "content": self.get_formatted_content(),}
        return f"{dictionary}"

    def get_openai_message(self):
        # Implement the method to return the appropriate format for OpenAI API
        return {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"This is description of the scene is only to give context to the conversation and is from the point of view of the player: {self.text_content}"
                }
            ]
        }
