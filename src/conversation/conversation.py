# from src.game_manager import GameStateManager
from src.remember.remembering import remembering
from src.output_manager import ChatManager
from src.llm.messages import assistant_message, system_message, user_message
from src.conversation.context import context
from src.llm.message_thread import message_thread
from src.conversation.conversation_type import conversation_type, multi_npc, pc_to_npc, radiant
from src.config_loader import ConfigLoader
from src.character_manager import Character
from src.stt import Transcriber


class conversation:
    def __init__(self, config: ConfigLoader, stt :Transcriber, output_manager: ChatManager, rememberer: remembering, is_radiant: bool, initial_character: Character, language: str, initial_location = "Skyrim", intial_ingame_time: int = 12, context_length: int = 4096) -> None:
        if is_radiant:
            self.__conversation_type: conversation_type = radiant(config.multi_npc_prompt)
        else:
            self.__conversation_type: conversation_type = pc_to_npc(config.prompt)
        self.__context: context = context(config, initial_character, language, initial_location, intial_ingame_time)
        self.__messages: message_thread = message_thread(self.__conversation_type.generate_prompt(self.__context))
        self.__stt = stt
        # self.__game_manager: GameStateManager = game_manager
        self.__output_manager: ChatManager = output_manager
        self.__rememberer: remembering = rememberer
        self.__context_length: int = context_length
        self.__token_limit_percent: float = 0.45
        self.__latest_character = initial_character
        self.__has_ended: bool = False

    def add_character(self, new_character: Character):
        self.__context.npcs_in_conversation.add(new_character)
        self.__latest_character = new_character

        #switch to multi-npc dialog
        if not isinstance(self.__conversation_type, multi_npc) and len(self.__context.npcs_in_conversation) > 1:
            self.__conversation_type = multi_npc(self.__context.prompt_multinpc)
            self.__messages.turn_into_multi_npc_conversation(self.__conversation_type.generate_prompt(self.__context))
            
    async def proceed(self) -> bool:
        if self.__has_ended:
            return False
        last_message = message_thread.get_last_message
        if isinstance(last_message, assistant_message) or isinstance(last_message, system_message):
            self.__add_user_message()
        else:
            await self.__add_assistant_message()
            if self.__output_manager.num_tokens(self.__messages.get_talk_only()) > (round(self.__context_length*self.__token_limit_percent,0)):
                self.__reload_conversation()
        return True

    def end(self):
        config = self.__context.config
        # say goodbyes
        for character in self.__context.npcs_in_conversation:
            self.__output_manager.play_sentence_ingame(config.goodbye_npc_response, character)

        self.__messages.add_message(user_message(config.end_conversation_keyword+'.', config.player_name, is_system_generated_message=True))
        self.__messages.add_message(assistant_message(config.end_conversation_keyword+'.', self.__context.get_character_names(), is_system_generated_message=True))

        self.__rememberer.save_conversation_state(self.__messages, self.__context.npcs_in_conversation)
        self.__has_ended = True

    async def __add_assistant_message(self):
        await self.__output_manager.get_response(self.__messages, self.__context.npcs_in_conversation, self.__conversation_type.is_radiant())

    def __add_user_message(self):
        new_message = self.__conversation_type.get_user_text(self.__stt, self.__messages)

    def __reload_conversation(self):
        #Play gather thoughts
        collecting_thoughts_text = self.__context.config.collecting_thoughts_npc_response
        self.__output_manager.play_sentence_ingame(collecting_thoughts_text, self.__latest_character)
        #Add gather thought messages to thread
        self.__messages.add_message(user_message(self.__latest_character.name +'?', self.__context.config.player_name, is_system_generated_message=True))
        if len(self.__context.npcs_in_conversation) > 1:
            collecting_thoughts_response = self.__latest_character.name +': '+ collecting_thoughts_text +'.'
        else:
            collecting_thoughts_response = collecting_thoughts_text+'.'
        self.__messages.add_message(assistant_message(collecting_thoughts_response, self.__context.get_character_names(), is_system_generated_message=True))
        #Save conversation state
        self.__rememberer.save_conversation_state(self.__messages, self.__context.npcs_in_conversation)
        #Reload
        new_prompt = self.__conversation_type.generate_prompt(self.__context)
        self.__messages.reload_message_thread(new_prompt, 8)
    
