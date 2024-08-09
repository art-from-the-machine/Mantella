from copy import deepcopy
from typing import Callable
from src.llm.messages import message, system_message, user_message, assistant_message
from openai.types.chat import ChatCompletionMessageParam

class message_thread():
    """A thread of messages consisting of system-, user- and assistant-messages.
    Central place for adding new messages to the thread and manipulating the existing ones
    """
    def __init__(self, initial_system_message: str | system_message | None) -> None:
        self.__messages: list[message] = []
        if not initial_system_message:
            return
        if isinstance(initial_system_message, str):
            initial_system_message = system_message(initial_system_message)        
        self.__messages.append(initial_system_message)
    
    def __len__(self) -> int:
        return self.__messages.__len__()

    @staticmethod
    def transform_to_openai_messages(messages: list[message]) -> list[ChatCompletionMessageParam]:
        result = []
        for m in messages:
            result.append(m.get_openai_message())
        return result
    
    @staticmethod
    def transform_to_text(messages: list[message]) -> str:
        result = ""
        for m in messages:
            original_is_multi = m.is_multi_npc_message
            m.is_multi_npc_message = True
            result += f"{m.get_formatted_content()}\n"
            m.is_multi_npc_message = original_is_multi
        return result
    
    @staticmethod
    def transform_to_dict_representation(messages: list[message]) -> str:
        result = ""
        for m in messages:
            # original_is_multi = m.is_multi_npc_message
            # m.is_multi_npc_message = True
            result += m.get_dict_formatted_string()
            # m.is_multi_npc_message = original_is_multi
        return result

    def get_openai_messages(self) -> list[ChatCompletionMessageParam]:
        return message_thread.transform_to_openai_messages(self.__messages)

    def add_message(self, new_message: user_message | assistant_message):
        self.__messages.append(new_message)

    def add_non_system_messages(self, new_messages: list[message]):
        """Adds a list of messages to this message_thread. Omits system_messages 

        Args:
            new_messages (list[message]): a list of messages to add
        """
        for new_message in new_messages:
            if not isinstance(message, system_message):
                self.__messages.append(new_message)
    
    def reload_message_thread(self, new_prompt: str, text_measurer: Callable[[str], int], max_tokens: int):
        """Reloads this message_thread with a new system_message prompt and drops all but the last X messages

        Args:
            new_prompt (str): the new prompt for the system_message
            last_messages_to_keep (int): how many of the last messages to keep
        """
        result: list[message] = []
        result.append(system_message(new_prompt))
        messages_to_keep: list[message]  = []
        used_tokens = 0
        for talk_message in reversed(self.get_talk_only()):
            used_tokens += text_measurer(talk_message.get_formatted_content())
            if used_tokens < max_tokens:
                messages_to_keep.append(talk_message)
            else:
                break
        messages_to_keep.reverse()
        result.extend(messages_to_keep)
        self.__messages = result

    def get_talk_only(self, include_system_generated_messages: bool = False) -> list[message]:
        """Returns a deepcopy of the messages in the conversation thread without the system_message

        Args:
            include_system_generated_messages (bool): if true, does not include user- and assistant_messages that are flagged as system messages

        Returns:
            list[message]: the selection of messages in question
        """
        result = []
        for message in self.__messages:
            if isinstance(message, (assistant_message, user_message)):
                if include_system_generated_messages:
                    result.append(deepcopy(message)) # TODO: Once assistant_message uses Character instead of str, this needs to be improved, don't want deepcopies of Character
                elif not message.is_system_generated_message:
                    result.append(deepcopy(message))
        return result
    
    def get_last_message(self) -> message:
        return self.__messages[len(self.__messages) -1]

    def get_last_assistant_message(self) -> assistant_message | None:
        for message in reversed(self.__messages):
            if isinstance(message, assistant_message):
                return message
        return None
    
    def append_text_to_last_assistant_message(self, text_to_append: str):
        """Appends a text to the last assistant message. 

        Args:
            text_to_append (str): the text to append to the end of last assitant message
        """
        last_assistant_message = self.get_last_assistant_message()
        if last_assistant_message:
            last_assistant_message.text += text_to_append

    def modify_messages(self, new_prompt: str, multi_npc_conversation: bool, remove_system_flagged_messages: bool = False):
        if len(self.__messages) > 0 and isinstance(self.__messages[0], system_message):
            messages_to_remove: list[message] = []
            self.__messages[0].text = new_prompt
            for m in self.__messages:
                if m.is_system_generated_message and remove_system_flagged_messages and not isinstance(m, system_message):
                    messages_to_remove.append(m)
                m.is_multi_npc_message = multi_npc_conversation
            for m in messages_to_remove:
                self.__messages.remove(m)