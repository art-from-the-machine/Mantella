from abc import ABC, abstractmethod
from openai.types.chat import ChatCompletionMessageParam
from src.llm.sentence_content import SentenceTypeEnum, sentence_content
from src.character_manager import Character

from src.llm.sentence import sentence
from src import utils

class message(ABC):
    """Base class for messages 
    """
    def __init__(self, text: str, is_system_generated_message: bool = False):
        self.__text: str = text
        self.__is_multi_npc_message: bool = False
        self.__is_system_generated_message = is_system_generated_message
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

class join_message(message):
    """ A internal message logging that a certain actor has joined the conversation this point (for system use only) """
    def __init__(self, character: Character):
        super().__init__(f"*{character.name} has joined the conversation*", False)
        self.character = character

    def get_formatted_content(self) -> str:
        return self.text

    def get_openai_message(self) -> ChatCompletionMessageParam:
        return {"role":"system", "content": self.get_formatted_content(),}
    
    def get_dict_formatted_string(self) -> str:
        dictionary = {"role":"system", "content": self.get_formatted_content(),}
        return f"{dictionary}"
    
class leave_message(message):
    """  A internal message logging that a certain actor has left the conversation this point (for system use only) """
    def __init__(self, character: Character):
        super().__init__(f"*{character.name} is no longer part of the conversation*", False)
        self.character = character

    def get_formatted_content(self) -> str:
        return self.text

    def get_openai_message(self) -> ChatCompletionMessageParam:
        return {"role":"system", "content": self.get_formatted_content(),}
    
    def get_dict_formatted_string(self) -> str:
        dictionary = {"role":"system", "content": self.get_formatted_content(),}
        return f"{dictionary}"
    

class system_message(message):
    """A message with the role 'system'. Usually used as the initial main prompt of an exchange with the LLM
    """

    def __init__(self, prompt: str):
        super().__init__(prompt, True)

    def get_formatted_content(self) -> str:
        return self.text

    def get_openai_message(self) -> ChatCompletionMessageParam:
        return {"role":"system", "content": self.get_formatted_content(),}
    
    def get_dict_formatted_string(self) -> str:
        dictionary = {"role":"system", "content": self.get_formatted_content(),}
        return f"{dictionary}"
        
class assistant_message(message):
    """An assistant message containing the response of an LLM to a request.
    Automatically appends the character name in front of the text if provided and if there is only one active_assistant_character
    """
    def __init__(self, is_system_generated_message: bool = False):
        super().__init__("", is_system_generated_message)
        self.__sentences: list[sentence_content] = []
    
    def add_sentence(self, new_sentence: sentence):
        self.__sentences.append(new_sentence.content)

    def get_formatted_content(self) -> str:
        if len(self.__sentences) < 1:
            return ""
        
        result = ""
        lastActor: Character | None = None
        was_last_sentence_narration: bool = False
        for sentence in self.__sentences:
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
        result = utils.remove_extra_whitespace(result)
        return result

    def get_openai_message(self) -> ChatCompletionMessageParam:
        return {"role":"assistant", "content": self.get_formatted_content(),}
    
    def get_dict_formatted_string(self) -> str:
        dictionary = {"role":"assistant", "content": self.get_formatted_content(),}
        return f"{dictionary}"

class user_message(message):
    """A user message sent to the LLM. Contains the text from the player and optionally it's name.
    Ingame Events can be added as a list[str]. Each ingame event will be placed before the text of the player in asterisks 
    """
    def __init__(self, text: str, player_character_name: str = "", is_system_generated_message: bool = False):
        super().__init__(text, is_system_generated_message)
        self.__player_character_name: str = player_character_name
        self.__ingame_events: list[str] = []
        self.__time: tuple[str,str] | None = None
        

    def get_formatted_content(self) -> str:
        result = ""
        result += self.get_ingame_events_text()
        if self.__time:
            result += f"{self.narration_start}The time is {self.__time[0]} {self.__time[1]}.{self.narration_end}\n"
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


class image_message(message):
    """A image message sent to the LLM. Contains the a base64 encode image and accompanying description text.
    """
    def __init__(self, encoded_image: str, text: str = "", resolution: str = "auto", is_system_generated_message: bool = False):
        super().__init__(text, is_system_generated_message)
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
    
class image_description_message(message):
    """An image description message, similar to a user message but interacted with by the conversation object"""
    def __init__(self, text: str = "", is_system_generated_message: bool = False):
        super().__init__(text, is_system_generated_message)
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
