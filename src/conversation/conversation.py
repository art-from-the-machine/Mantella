from src.llm.messages import assistant_message
from src.conversation.context import context
from src.llm.message_thread import message_thread
from src.conversation.conversation_type import conversation_type, multi_npc, pc_to_npc, radiant
from src.config_loader import ConfigLoader
from src.character_manager import Character
from src.stt import Transcriber


class conversation:
    def __init__(self, config: ConfigLoader, stt :Transcriber, is_radiant: bool, initial_character: Character, language: str, initial_location = "Skyrim", intial_ingame_time: int = 12) -> None:
        if is_radiant:
            self.__conversation_type: conversation_type = radiant(config.radiant_dialogue_prompt)
        else:
            self.__conversation_type: conversation_type = pc_to_npc(config.prompt)
        self.__context: context = context(config, initial_character, language, initial_location, intial_ingame_time)
        self.__messages: message_thread = message_thread(self.__conversation_type.generate_prompt(self.__context))
        self.__stt = stt

    def add_character(self, new_character: Character):
        self.__context.npcs_in_conversation.add(new_character)

        #switch to multi-npc dialog
        if not isinstance(self.__conversation_type, multi_npc) and len(self.__context.npcs_in_conversation) > 1:
            self.__conversation_type = multi_npc(self.__context.prompt_multinpc)
            self.__messages.turn_into_multi_npc_conversation(self.__conversation_type.generate_prompt(self.__context))
            
    def proceed(self):
        pass

    def end(self):
        pass

    def __generate_assistant_message(self) -> assistant_message:

    
