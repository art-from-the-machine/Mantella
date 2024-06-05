from abc import ABC, abstractmethod
from openai.types.chat import ChatCompletionMessageParam
from src.character_manager import Character

from src.llm.sentence import sentence

class message(ABC):
    """Base class for messages 
    """
    def __init__(self, text: str, is_system_generated_message: bool = False):
        self.__text: str = text
        self.__is_multi_npc_message: bool = False
        self.__is_system_generated_message = is_system_generated_message

    @property
    def text(self) -> str:
        return self.__text
    
    @text.setter
    def text(self, text: str):
        self.__text = text

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
        self.__sentences: list[sentence] = []
    
    def add_sentence(self, new_sentence: sentence):
        self.__sentences.append(new_sentence)

    def get_formatted_content(self) -> str:
        if len(self.__sentences) < 1:
            return ""
        
        result = ""
        lastActor: Character | None = None
        for sentence in self.__sentences: 
            if self.is_multi_npc_message and lastActor != sentence.speaker:
                lastActor = sentence.speaker
                result += "\n" + lastActor.name +': '+ sentence.sentence
            else:
                result += sentence.sentence
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
            result += f"*The time is {self.__time[0]} {self.__time[1]}.*\n"
        if self.is_multi_npc_message:
            result += f"{self.__player_character_name}: "
        result += f"{self.text}"
        return result
    
    def get_openai_message(self) -> ChatCompletionMessageParam:
        return {"role":"user", "content": self.get_formatted_content(),}
    
    def get_dict_formatted_string(self) -> str:
        dictionary = {"role":"user", "content": self.get_formatted_content(),}
        return f"{dictionary}"

    def add_event(self, events: list[str]):
        for event in events:
            self.__ingame_events.append(event)
    
    def count_ingame_events(self) -> int:
        return len(self.__ingame_events)
    
    def get_ingame_events_text(self) -> str:
        result = ""
        for event in self.__ingame_events:
            result += f"*{event}*\n"
        return result
    
    def set_ingame_time(self, time: str, time_group: str):
        self.__time = time, time_group
