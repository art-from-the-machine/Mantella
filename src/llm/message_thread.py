from copy import deepcopy
from src.llm.messages import join_message, leave_message, message, system_message, user_message, assistant_message, image_message, image_description_message
from typing import Callable
from openai.types.chat import ChatCompletionMessageParam
from src import utils

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
    @utils.time_it
    def transform_to_openai_messages(messages: list[message]) -> list[ChatCompletionMessageParam]:
        result = []
        for m in messages:
            result.append(m.get_openai_message())
        return result
    
    @staticmethod
    @utils.time_it
    def transform_to_text(messages: list[message]) -> str:
        result = ""
        for m in messages:
            original_is_multi = m.is_multi_npc_message
            m.is_multi_npc_message = True
            result += f"{m.get_formatted_content()}\n"
            m.is_multi_npc_message = original_is_multi
        return result
    
    @staticmethod
    @utils.time_it
    def transform_to_dict_representation(messages: list[message]) -> str:
        result = ""
        for m in messages:
            # original_is_multi = m.is_multi_npc_message
            # m.is_multi_npc_message = True
            result += m.get_dict_formatted_string()
            # m.is_multi_npc_message = original_is_multi
        return result

    @utils.time_it
    def get_openai_messages(self) -> list[ChatCompletionMessageParam]:
        return message_thread.transform_to_openai_messages(self.__messages)

    def add_message(self, new_message: user_message | assistant_message | image_message | image_description_message | join_message | leave_message):
        self.__messages.append(new_message)

    @utils.time_it
    def add_non_system_messages(self, new_messages: list[message]):
        """Adds a list of messages to this message_thread. Omits system_messages 

        Args:
            new_messages (list[message]): a list of messages to add
        """
        for new_message in new_messages:
            if not isinstance(message, system_message):
                self.__messages.append(new_message)
    
    @utils.time_it
    def reload_message_thread(self, new_prompt: str, is_too_long: Callable[[list[message], float], bool], percent_modifier: float):
        """Reloads this message_thread with a new system_message prompt and drops all but the last X persistent messages.
        Returns the persistent messages that were removed.

        Args:
            new_prompt (str): The new prompt for the system_message.
            is_too_long (Callable): Function to determine if the list of messages is too long.
            percent_modifier01 (float): A percentage modifier (clamped between 0 and 1).
        """
        result: list[message] = []
        result.append(system_message(new_prompt))
        messages_to_keep: list[message] = []
        persistent_messages = self.get_persistent_messages()
        
        for talk_message in reversed(persistent_messages):
            messages_to_keep.append(talk_message)
            if is_too_long(messages_to_keep, percent_modifier):
                messages_to_keep = messages_to_keep[:-1]
                break

        messages_to_keep.reverse()
        result.extend(messages_to_keep)
        self.__messages = result
        
        kept_count = len(messages_to_keep)
        # Compute removed persistent messages: all persistent messages except the kept ones.
        removed_messages: list[message] = persistent_messages if kept_count == 0 else persistent_messages[:len(persistent_messages) - kept_count]
        return removed_messages

    @utils.time_it
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
    
    @utils.time_it
    def get_persistent_messages(self):
        """ Returns a deepcopy of all the messages we want to persist over multiple turns. """
        result = []
        for message in self.__messages:
            if isinstance(message, (assistant_message, user_message, join_message, leave_message)):
                result.append(deepcopy(message))
        return result
    
    @utils.time_it
    def get_messages_of_type(self, typesTuple):
        result = []
        for message in self.__messages:
            if isinstance(message, typesTuple):
                result.append(deepcopy(message))
        return result
    
    def insert_after_system_messages(self, new_message: user_message | assistant_message | image_message | image_description_message | join_message | leave_message):
        # find the index of the first message that is not a system_message and has is_system_generated_message == false
        index = 0
        for i, message in enumerate(self.__messages):
            if not isinstance(message, system_message) and not message.is_system_generated_message:
                index = i
                break
        self.__messages.insert(index, new_message)
        
    
    
    @utils.time_it
    def get_last_message(self) -> message:
        return self.__messages[len(self.__messages) -1]

    @utils.time_it
    def get_last_assistant_message(self) -> assistant_message | None:
        for message in reversed(self.__messages):
            if isinstance(message, assistant_message):
                return message
        return None
    
    @utils.time_it
    def append_text_to_last_assistant_message(self, text_to_append: str):
        """Appends a text to the last assistant message. 

        Args:
            text_to_append (str): the text to append to the end of last assitant message
        """
        last_assistant_message = self.get_last_assistant_message()
        if last_assistant_message:
            last_assistant_message.text += text_to_append

    @utils.time_it
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
    
    def has_message_type(self, message_type: type) -> bool:
        """Checks if there is any message of the specified type in the messages.

        Args:
            message_type (type): The type of message to check for.

        Returns:
            bool: True if there is a message of the specified type, False otherwise.
        """
        return any(isinstance(message, message_type) for message in self.__messages)

    def replace_message_type(self, new_message: message, message_type: type):
        """Replaces the first found message of the specified type in the messages with the provided new_message.

        Args:
            new_message (message): The new message to replace the old one.
            message_type (type): The type of message to replace.
        """
        for idx, msg in enumerate(self.__messages):
            if isinstance(msg, message_type):
                self.__messages[idx] = new_message
                # Move the new message to the end of the list
                self.__messages.append(self.__messages.pop(idx))
                break
            
    def delete_all_message_type(self, message_type: type):
        """Deletes all messages of the specified type from the messages.

        Args:
            message_type (type): The type of messages to delete.
        """
        self.__messages = [msg for msg in self.__messages if not isinstance(msg, message_type)]

    def replace_or_add_message(self, message_instance, message_type: type):
        if self.has_message_type(message_type):
            self.replace_message_type(message_instance,message_type)
        else:
            self.add_message(message_instance)