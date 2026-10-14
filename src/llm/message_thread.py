from copy import deepcopy
from src.config.config_loader import ConfigLoader
from src.config.definitions.llm_definitions import DecensorPlacementEnum
from src.llm.messages import join_message, leave_message, Message, SystemMessage, UserMessage, AssistantMessage, ImageMessage, ImageDescriptionMessage
from src.prompt_profile_manager import PromptSectionError
from typing import Callable, TYPE_CHECKING
from openai.types.chat import ChatCompletionMessageParam
from src import utils
import json
import logging

if TYPE_CHECKING:
    from src.llm.image_client import VisionCapture

def decensor_placement(config) -> DecensorPlacementEnum:
    placement = getattr(config, "decensor_assistant_placement", DecensorPlacementEnum.AFTER_SYSTEM_PROMPT)
    return placement if isinstance(placement, DecensorPlacementEnum) else DecensorPlacementEnum.AFTER_SYSTEM_PROMPT

def _decensor_text(config, prompt_type: str) -> str:
    text = str(getattr(config, prompt_type, "") or "")
    manager = getattr(config, "prompt_profile_manager", None)
    resolve = getattr(manager, "resolve_prompt", None) if manager is not None else None
    if callable(resolve):
        text = resolve(prompt_type, text)
    return text.strip() if isinstance(text, str) else ""

def decensor_bypass_messages(config) -> list[ChatCompletionMessageParam]:
    """Return the decensor messages to send, in order, for the chosen placement.

    After the system prompt: the user handshake, then the assistant commitment.
    At the end of the request: only the commitment, in the chosen role, because the latest player input already comes before it.
    Empty when the toggle is off or a text the placement needs is empty or does not resolve to text.
    Raises PromptSectionError when an active profile references a broken shared section.
    """
    if getattr(config, "enable_decensor_bypass", False) is not True:
        return []
    placement = decensor_placement(config)
    if placement == DecensorPlacementEnum.AFTER_SYSTEM_PROMPT:
        handshake = _decensor_text(config, "decensor_handshake_prompt")
        commitment = _decensor_text(config, "decensor_assistant_prompt")
        if not handshake or not commitment:
            return []
        return [
            {"role": "user", "content": handshake},
            {"role": "assistant", "content": commitment},
        ]
    commitment = _decensor_text(config, "decensor_assistant_prompt")
    if not commitment:
        return []
    role = "system" if placement == DecensorPlacementEnum.END_AS_SYSTEM else "assistant"
    return [{"role": role, "content": commitment}]

def format_decensor_bypass_preview(config) -> str:
    """Read-only JSON of the decensor messages, or empty text when they are not sent."""
    try:
        bypass = decensor_bypass_messages(config)
    except PromptSectionError as e:
        return str(e)
    if not bypass:
        return ""
    return json.dumps(bypass, indent=2, ensure_ascii=False)

class message_thread():
    """A thread of messages consisting of system-, user- and assistant-messages.
    Central place for adding new messages to the thread and manipulating the existing ones
    """
    def __init__(self, config: ConfigLoader, initial_system_message: str | SystemMessage | None, include_decensor_bypass: bool = False) -> None:
        self.__messages: list[Message] = []
        self.__config = config
        self.__include_decensor_bypass = include_decensor_bypass
        self.__logged_skipped_decensor = False
        self.vision_capture: "VisionCapture | None" = None # When set, requests with this thread reuse its screenshot instead of taking a new one
        if not initial_system_message:
            return
        if isinstance(initial_system_message, str):
            initial_system_message = SystemMessage(initial_system_message, config)
        self.__messages.append(initial_system_message)
    
    def __len__(self) -> int:
        return self.__messages.__len__()

    @staticmethod
    @utils.time_it
    def transform_to_openai_messages(
        messages: list[Message],
        last_turn_thoughts_only: bool = False,
        thoughts_on_last_assistant_turns: int | None = None,
    ) -> list[ChatCompletionMessageParam]:
        """Build OpenAI messages.

        thoughts_on_last_assistant_turns limits turn thoughts to that many recent assistant replies.
        last_turn_thoughts_only is the same limit with a count of 1. Omit both to keep every thought.
        """
        if thoughts_on_last_assistant_turns is not None:
            keep_count = max(0, thoughts_on_last_assistant_turns)
        elif last_turn_thoughts_only:
            keep_count = 1
        else:
            keep_count = None
        kept_assistant_ids: set[int] | None = None
        if keep_count is not None:
            assistants = [message for message in messages if isinstance(message, AssistantMessage)]
            kept_assistant_ids = {id(message) for message in assistants[-keep_count:]} if keep_count else set()
        result = []
        for m in messages:
            if isinstance(m, AssistantMessage):
                include_thoughts = kept_assistant_ids is None or id(m) in kept_assistant_ids
                result.append(m.get_openai_message(include_thoughts=include_thoughts))
            else:
                result.append(m.get_openai_message())
        return result
    
    @staticmethod
    @utils.time_it
    def transform_to_text(messages: list[Message]) -> str:
        result = ""
        for m in messages:
            original_is_multi = m.is_multi_npc_message
            m.is_multi_npc_message = True
            result += f"{m.get_formatted_content()}\n"
            m.is_multi_npc_message = original_is_multi
        return result
    
    @staticmethod
    @utils.time_it
    def transform_to_dict_representation(messages: list[Message]) -> str:
        result = ""
        for m in messages:
            # original_is_multi = m.is_multi_npc_message
            # m.is_multi_npc_message = True
            result += m.get_dict_formatted_string()
            # m.is_multi_npc_message = original_is_multi
        return result

    def get_openai_messages(self) -> list[ChatCompletionMessageParam]:
        """Live chat keeps turn thoughts on the last N assistant replies.

        Other requests, including summaries and inner thoughts, keep thoughts only on the latest assistant reply.
        """
        if self.__include_decensor_bypass:
            openai_messages = message_thread.transform_to_openai_messages(
                self.__messages,
                thoughts_on_last_assistant_turns=self.__turn_thoughts_to_keep(),
            )
        else:
            openai_messages = message_thread.transform_to_openai_messages(self.__messages, last_turn_thoughts_only=True)
        return self.__insert_decensor_bypass(openai_messages)

    def __turn_thoughts_to_keep(self) -> int:
        raw = getattr(self.__config, "turn_thoughts_to_keep", 1)
        try:
            count = int(raw)
        except (TypeError, ValueError):
            return 1
        return max(0, count)

    def __insert_decensor_bypass(self, openai_messages: list[ChatCompletionMessageParam]) -> list[ChatCompletionMessageParam]:
        """Place a user handshake and assistant commitment directly after the system prompt, when that is the chosen placement.

        Only the live conversation thread opts in. The decensor messages are not stored in history, so they are
        not summarized and they are rebuilt from the current prompt text on every request.
        """
        if not self.__include_decensor_bypass or decensor_placement(self.__config) != DecensorPlacementEnum.AFTER_SYSTEM_PROMPT:
            return openai_messages
        if not openai_messages or openai_messages[0].get("role") != "system":
            return openai_messages
        bypass = self.__decensor_bypass_messages()
        if not bypass:
            return openai_messages
        return [openai_messages[0], *bypass, *openai_messages[1:]]

    def append_decensor_commitment(self, openai_messages: list[ChatCompletionMessageParam]) -> list[ChatCompletionMessageParam]:
        """Append the commitment as the last message, when an end of request placement is chosen.

        Call this on the final request messages, after the image and the cache breakpoints were added,
        because both expect the latest player input to be the last message.
        """
        if not self.__include_decensor_bypass or decensor_placement(self.__config) == DecensorPlacementEnum.AFTER_SYSTEM_PROMPT:
            return openai_messages
        bypass = self.__decensor_bypass_messages()
        if not bypass:
            return openai_messages
        return [*openai_messages, *bypass]

    def __decensor_bypass_messages(self) -> list[ChatCompletionMessageParam]:
        try:
            bypass = decensor_bypass_messages(self.__config)
        except PromptSectionError as e:
            logging.error(str(e))
            logging.error("Decensor bypass was not added. Fix the active prompt profile.")
            return []
        if not bypass:
            if getattr(self.__config, "enable_decensor_bypass", False) is True and not self.__logged_skipped_decensor:
                logging.warning("Decensor bypass is enabled, but a decensor prompt its placement needs is empty. Nothing was sent.")
                self.__logged_skipped_decensor = True
            return []
        self.__logged_skipped_decensor = False
        return bypass

    def add_message(self, new_message: UserMessage | AssistantMessage | ImageMessage | ImageDescriptionMessage | join_message | leave_message):
        self.__messages.append(new_message)

    @utils.time_it
    def add_non_system_messages(self, new_messages: list[Message]):
        """Adds a list of messages to this message_thread. Omits system_messages 

        Args:
            new_messages (list[Message]): a list of messages to add
        """
        for new_message in new_messages:
            if not isinstance(Message, SystemMessage):
                self.__messages.append(new_message)
    
    @utils.time_it
    def reload_message_thread(self, new_prompt: str, is_too_long: Callable[[list[Message], float], bool], percent_modifier: float):
        """Reloads this message_thread with a new system_message prompt and drops all but the last X persistent messages.
        Returns the persistent messages that were removed.

        Args:
            new_prompt (str): The new prompt for the system_message.
            is_too_long (Callable): Function to determine if the list of messages is too long.
            percent_modifier01 (float): A percentage modifier (clamped between 0 and 1).
        """
        result: list[Message] = []
        result.append(SystemMessage(new_prompt, self.__config))
        messages_to_keep: list[Message] = []
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
        removed_messages: list[Message] = persistent_messages if kept_count == 0 else persistent_messages[:len(persistent_messages) - kept_count]
        return removed_messages

    @utils.time_it
    def get_talk_only(self, include_system_generated_messages: bool = False) -> list[Message]:
        """Returns a deepcopy of the messages in the conversation thread without the system_message

        Args:
            include_system_generated_messages (bool): if true, does not include user- and assistant_messages that are flagged as system messages

        Returns:
            list[Message]: the selection of messages in question
        """
        result = []
        for message in self.__messages:
            if isinstance(message, (AssistantMessage, UserMessage)):
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
            if isinstance(message, (AssistantMessage, UserMessage, join_message, leave_message)):
                result.append(deepcopy(message))
        return result
    
    @utils.time_it
    def get_messages_of_type(self, typesTuple):
        result = []
        for message in self.__messages:
            if isinstance(message, typesTuple):
                result.append(deepcopy(message))
        return result
    
    def insert_after_system_messages(self, new_message: UserMessage | AssistantMessage | ImageMessage | ImageDescriptionMessage | join_message | leave_message):
        # find the index of the first message that is not a system_message and has is_system_generated_message == false
        index = 0
        for i, message in enumerate(self.__messages):
            if not isinstance(message, SystemMessage) and not message.is_system_generated_message:
                index = i
                break
        self.__messages.insert(index, new_message)
        
    
    
    @utils.time_it
    def get_persistent_messages(self):
        """ Returns a deepcopy of all the messages we want to persist over multiple turns. """
        result = []
        for message in self.__messages:
            if isinstance(message, (AssistantMessage, UserMessage, join_message, leave_message)):
                result.append(deepcopy(message))
        return result

    @utils.time_it
    def replace_persistent_messages(self, new_persistent_messages: list[Message]):
        """Replaces all persistent messages (user, assistant, join, leave) with the provided list.
        Keeps system messages at the start of the thread.
        """
        system_messages = [m for m in self.__messages if isinstance(m, SystemMessage)]
        self.__messages = system_messages + list(new_persistent_messages)
    
    def insert_after_system_messages(self, new_message: UserMessage | AssistantMessage | ImageMessage | ImageDescriptionMessage | join_message | leave_message):
        # find the index of the first message that is not a system_message and has is_system_generated_message == false
        index = 0
        for i, message in enumerate(self.__messages):
            if not isinstance(message, SystemMessage) and not message.is_system_generated_message:
                index = i
                break
        self.__messages.insert(index, new_message)
            
    @utils.time_it
    def get_last_message(self) -> Message:
        return self.__messages[len(self.__messages) -1]

    @utils.time_it
    def get_last_assistant_message(self) -> AssistantMessage | None:
        for message in reversed(self.__messages):
            if isinstance(message, AssistantMessage):
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
        if len(self.__messages) > 0 and isinstance(self.__messages[0], SystemMessage):
            messages_to_remove: list[Message] = []
            self.__messages[0].text = new_prompt
            for m in self.__messages:
                if m.is_system_generated_message and remove_system_flagged_messages and not isinstance(m, SystemMessage):
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

    def replace_message_type(self, new_message: Message, message_type: type):
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
    
    @utils.time_it
    def hot_swap_settings(self, config: ConfigLoader) -> bool:
        """Attempts to hot-swap settings without ending the conversation.
        
        Args:
            config: Updated config loader instance
            
        Returns:
            bool: True if hot-swap was successful, False otherwise
        """
        try:
            # Update config reference
            self.__config = config
            
            # Update all messages with new config for narration indicators
            for message in self.__messages:
                if hasattr(message, 'hot_swap_settings'):
                    message.hot_swap_settings(config)
            
            logging.info("message_thread hot-swap completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"message_thread hot-swap failed: {e}")
            return False