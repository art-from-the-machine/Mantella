import logging
from typing import Any, Hashable
import regex
from src.config.definitions.llm_definitions import NarrationHandlingEnum
from src.games.equipment import Equipment, EquipmentItem
from src.games.external_character_info import external_character_info
from src.games.gameable import gameable
from src.conversation.action import action
from src.llm.sentence import sentence
from src.output_manager import ChatManager
from src.remember.remembering import remembering
from src.remember.summaries import summaries
from src.config.config_loader import ConfigLoader
from src.llm.llm_client import LLMClient
from src.conversation.conversation import conversation
from src.conversation.context import context
from src.character_manager import Character
import src.utils as utils
from src.http.communication_constants import communication_constants as comm_consts
from src.stt import Transcriber

class CharacterDoesNotExist(Exception):
    """Exception raised when NPC name cannot be found in skyrim_characters.csv/fallout4_characters.csv"""
    pass


class GameStateManager:
    TOKEN_LIMIT_PERCENT: float = 0.45 # not used?
    WORLD_ID_CLEANSE_REGEX: regex.Pattern = regex.compile('[^A-Za-z0-9]+')

    @utils.time_it
    def __init__(self, game: gameable, chat_manager: ChatManager, config: ConfigLoader, language_info: dict[Hashable, str], client: LLMClient, stt_api_file: str, api_file: str):        
        self.__game: gameable = game
        self.__config: ConfigLoader = config
        self.__language_info: dict[Hashable, str] = language_info 
        self.__client: LLMClient = client
        self.__chat_manager: ChatManager = chat_manager
        self.__rememberer: remembering = summaries(game, config, client, language_info['language'])
        self.__talk: conversation | None = None
        self.__mic_input: bool = False
        self.__mic_ptt: bool = False # push-to-talk
        self.__stt_api_file: str = stt_api_file
        self.__api_file: str = api_file
        self.__stt: Transcriber | None = None
        self.__first_line: bool = True
        self.__automatic_greeting: bool = config.automatic_greeting
        self.__conv_has_narrator: bool = config.narration_handling == NarrationHandlingEnum.USE_NARRATOR

    ###### react to calls from the game #######
    @utils.time_it
    def start_conversation(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if self.__talk: #This should only happen if game and server are out of sync due to some previous error -> close conversation and start a new one
            self.__talk.end()
            self.__talk = None
        world_id = "default"
        if input_json.__contains__(comm_consts.KEY_STARTCONVERSATION_WORLDID):
            world_id = input_json[comm_consts.KEY_STARTCONVERSATION_WORLDID]
            world_id = self.WORLD_ID_CLEANSE_REGEX.sub("", world_id)
        if input_json.__contains__(comm_consts.KEY_INPUTTYPE):
            if input_json[comm_consts.KEY_INPUTTYPE] in (comm_consts.KEY_INPUTTYPE_MIC, comm_consts.KEY_INPUTTYPE_PTT):
                self.__mic_input = True
                # only init Transcriber if mic input is enabled
                self.__stt = Transcriber(self.__config, self.__stt_api_file, self.__api_file)
                if input_json[comm_consts.KEY_INPUTTYPE] == comm_consts.KEY_INPUTTYPE_PTT:
                    self.__mic_ptt = True
                
        context_for_conversation = context(world_id, self.__config, self.__client, self.__rememberer, self.__language_info)
        self.__talk = conversation(context_for_conversation, self.__chat_manager, self.__rememberer, self.__client, self.__stt, self.__mic_input, self.__mic_ptt)
        self.__update_context(input_json)
        self.__try_preload_voice_model()
        self.__talk.start_conversation()
            
        return {
            comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTTYPE_STARTCONVERSATIONCOMPLETED,
            comm_consts.KEY_STARTCONVERSATION_USENARRATOR: self.__conv_has_narrator}
        
    
    @utils.time_it
    def continue_conversation(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if(not self.__talk ):
            return self.error_message("No running conversation.")
        
        if input_json.__contains__(comm_consts.KEY_REQUEST_EXTRA_ACTIONS):
            extra_actions: list[str] = input_json[comm_consts.KEY_REQUEST_EXTRA_ACTIONS]
            if extra_actions.__contains__(comm_consts.ACTION_RELOADCONVERSATION):
                self.__talk.reload_conversation()

        topicInfoID: int = int(input_json.get(comm_consts.KEY_CONTINUECONVERSATION_TOPICINFOFILE,1))

        self.__update_context(input_json)

        while True:
            replyType, sentence_to_play = self.__talk.continue_conversation()
            if replyType == comm_consts.KEY_REQUESTTYPE_TTS:
                # if player input is detected mid-response, immediately process the player input
                reply = self.player_input({"mantella_context": {}, "mantella_player_input": "", "mantella_request_type": "mantella_player_input"})
                self.__first_line = False # since the NPC is already speaking in-game, setting this to True would just cause two voicelines to play at once
                continue # continue conversation with new player input (ie call self.__talk.continue_conversation() again)
            else:
                reply: dict[str, Any] = {comm_consts.KEY_REPLYTYPE: replyType}
                break

        if sentence_to_play:
            if not sentence_to_play.error_message:
                self.__game.prepare_sentence_for_game(sentence_to_play, self.__talk.context, self.__config, topicInfoID, self.__first_line)            
                reply[comm_consts.KEY_REPLYTYPE_NPCTALK] = self.sentence_to_json(sentence_to_play, topicInfoID)
                self.__first_line = False
            else:
                self.__talk.end()
                return self.error_message(sentence_to_play.error_message)
        return reply

    @utils.time_it
    def player_input(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if(not self.__talk ):
            return self.error_message("No running conversation.")
        
        self.__first_line = True
        
        player_text: str = input_json.get(comm_consts.KEY_REQUESTTYPE_PLAYERINPUT, '')
        self.__update_context(input_json)
        updated_player_text, update_events, player_spoken_sentence = self.__talk.process_player_input(player_text)
        if update_events:
            return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REQUESTTYPE_TTS, comm_consts.KEY_TRANSCRIBE: updated_player_text}

        cleaned_player_text = utils.clean_text(updated_player_text)
        npcs_in_conversation = self.__talk.context.npcs_in_conversation
        if not npcs_in_conversation.contains_multiple_npcs(): # actions are only enabled in 1-1 conversations
            for action in self.__config.actions:
                # if the player response is just the name of an action, force the action to trigger
                if action.keyword.lower() == cleaned_player_text.lower() and npcs_in_conversation.last_added_character:
                    return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_NPCACTION,
                            comm_consts.KEY_REPLYTYPE_NPCACTION: {
                                'mantella_actor_speaker': npcs_in_conversation.last_added_character.name,
                                'mantella_actor_actions': [action.identifier],
                                }
                            }
        
        # if the player response is not an action command, return a regular player reply type
        if player_spoken_sentence:
            topicInfoID: int = int(input_json.get(comm_consts.KEY_CONTINUECONVERSATION_TOPICINFOFILE,1))
            self.__game.prepare_sentence_for_game(player_spoken_sentence, self.__talk.context, self.__config, topicInfoID, self.__first_line)
            self.__first_line = False
            return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_NPCTALK, comm_consts.KEY_REPLYTYPE_NPCTALK: self.sentence_to_json(player_spoken_sentence, topicInfoID)}
        else:
            return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_NPCTALK}

    @utils.time_it
    def end_conversation(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if(self.__talk):
            self.__talk.end()
            self.__talk = None

        logging.log(24, '\nConversations not starting when you select an NPC? See here:')
        logging.log(25, 'https://art-from-the-machine.github.io/Mantella/pages/issues_qna')
        logging.log(24, '\nWaiting for player to select an NPC...')
        return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_ENDCONVERSATION}

    ####### JSON constructions #########

    @utils.time_it
    def character_to_json(self, character_to_jsonfy: Character) -> dict[str, Any]:
        return {
            comm_consts.KEY_ACTOR_BASEID: character_to_jsonfy.base_id,
            comm_consts.KEY_ACTOR_NAME: character_to_jsonfy.name,
        }
    
    @utils.time_it
    def sentence_to_json(self, sentence_to_prepare: sentence, topicID: int) -> dict[str, Any]:
        return {
            comm_consts.KEY_ACTOR_SPEAKER: sentence_to_prepare.speaker.name,
            comm_consts.KEY_ACTOR_LINETOSPEAK: self.__abbreviate_text(sentence_to_prepare.text.strip()),
            comm_consts.KEY_ACTOR_ISNARRATION: sentence_to_prepare.is_narration,
            comm_consts.KEY_ACTOR_VOICEFILE: sentence_to_prepare.voice_file,
            comm_consts.KEY_ACTOR_DURATION: sentence_to_prepare.voice_line_duration,
            comm_consts.KEY_ACTOR_ACTIONS: sentence_to_prepare.actions,
            comm_consts.KEY_CONTINUECONVERSATION_TOPICINFOFILE: topicID
        }
    
    def __abbreviate_text(self, text_to_abbreviate: str) -> str:
        return self.__game.modify_sentence_text_for_game(text_to_abbreviate)

    ##### utils #######

    @utils.time_it
    def __update_context(self,  json: dict[str, Any]):
        if self.__talk:
            if json.__contains__(comm_consts.KEY_ACTORS):
                actors_in_json: list[Character] = []
                for actorJson in json[comm_consts.KEY_ACTORS]:
                    if comm_consts.KEY_ACTOR_BASEID in actorJson:
                        actor: Character | None = self.load_character(actorJson)                
                        if actor:
                            actors_in_json.append(actor)
                self.__talk.add_or_update_character(actors_in_json)
            
            location = None
            time = None
            ingame_events = None
            weather = ""
            custom_context_values: dict[str, Any] = {}
            if json.__contains__(comm_consts.KEY_CONTEXT):
                if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_LOCATION):
                    location: str = json[comm_consts.KEY_CONTEXT].get(comm_consts.KEY_CONTEXT_LOCATION, None)
                
                if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_TIME):
                    time: int = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_TIME]

                if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_INGAMEEVENTS):
                    ingame_events: list[str] = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_INGAMEEVENTS]
                
                if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_WEATHER):
                    weather = self.__game.get_weather_description(json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_WEATHER])

                if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_CUSTOMVALUES):
                    custom_context_values = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_CUSTOMVALUES]
            self.__talk.update_context(location, time, ingame_events, weather, custom_context_values)
    
    @utils.time_it
    def load_character(self, json: dict[str, Any]) -> Character | None:
        try:
            base_id: str = utils.convert_to_skyrim_hex_format(str(json[comm_consts.KEY_ACTOR_BASEID]))
            ref_id: str = utils.convert_to_skyrim_hex_format(str(json[comm_consts.KEY_ACTOR_REFID]))

            # ignore plugin ID at the start of the ref ID as this can vary by load order
            if ref_id.startswith('FE'):             #Item from lite mod, statically placed in CK, has 'FEXXX' prefix. 
                ref_id = ref_id[-3:].rjust(6,"0")   #Mask off prefix, pad w/'0'
            else:
                ref_id = ref_id[-6:]
            if base_id.startswith('FE'):
                base_id = base_id[-3:].rjust(6,"0")
            else:
                base_id = base_id[-6:]

            character_name: str = str(json[comm_consts.KEY_ACTOR_NAME])
            gender: int = int(json[comm_consts.KEY_ACTOR_GENDER])
            race: str = str(json[comm_consts.KEY_ACTOR_RACE])
            actor_voice_model: str = str(json[comm_consts.KEY_ACTOR_VOICETYPE])
            ingame_voice_model: str = actor_voice_model.split('<')[1].split(' ')[0]
            is_in_combat: bool = bool(json[comm_consts.KEY_ACTOR_ISINCOMBAT])
            is_outside_talking_range: bool = bool(json[comm_consts.KEY_ACTOR_ISOUTSIDETALKINGRANGE])
            is_enemy: bool = bool(json[comm_consts.KEY_ACTOR_ISENEMY])
            relationship_rank: int = int(json[comm_consts.KEY_ACTOR_RELATIONSHIPRANK])
            custom_values: dict[str, Any] = {}
            if json.__contains__(comm_consts.KEY_ACTOR_CUSTOMVALUES):
                custom_values = json[comm_consts.KEY_ACTOR_CUSTOMVALUES]
                if not custom_values:
                    custom_values: dict[str, Any] = {}
            equipment = Equipment({})
            if json.__contains__(comm_consts.KEY_ACTOR_EQUIPMENT):
                equipment = Equipment(self.__convert_to_equipment_item_dictionary(json[comm_consts.KEY_ACTOR_EQUIPMENT]))
            is_generic_npc: bool = False
            bio: str = ""
            tts_voice_model: str = ""
            csv_in_game_voice_model: str = ""
            advanced_voice_model: str = ""
            voice_accent: str = ""
            is_player_character: bool = bool(json[comm_consts.KEY_ACTOR_ISPLAYER])
            if self.__talk and self.__talk.contains_character(ref_id):
                already_loaded_character: Character | None = self.__talk.get_character(ref_id)
                if already_loaded_character:
                    bio = already_loaded_character.bio
                    tts_voice_model = already_loaded_character.tts_voice_model
                    csv_in_game_voice_model = already_loaded_character.csv_in_game_voice_model
                    advanced_voice_model = already_loaded_character.advanced_voice_model
                    voice_accent = already_loaded_character.voice_accent
                    is_generic_npc = already_loaded_character.is_generic_npc
            elif self.__talk and not is_player_character :#If this is not the player and the character has not already been loaded
                external_info: external_character_info = self.__game.load_external_character_info(base_id, character_name, race, gender, actor_voice_model)
                
                bio = external_info.bio
                tts_voice_model = external_info.tts_voice_model
                csv_in_game_voice_model = external_info.csv_in_game_voice_model
                advanced_voice_model = external_info.advanced_voice_model
                voice_accent = external_info.voice_accent
                is_generic_npc = external_info.is_generic_npc
                if is_generic_npc:
                    character_name = external_info.name
                    ingame_voice_model = external_info.ingame_voice_model
            elif self.__talk and is_player_character and self.__config.voice_player_input:
                if custom_values.__contains__(comm_consts.KEY_ACTOR_PC_VOICEMODEL):
                    tts_voice_model = self.__get_player_voice_model(str(custom_values[comm_consts.KEY_ACTOR_PC_VOICEMODEL]))
                else:
                    tts_voice_model = self.__get_player_voice_model(None)

            return Character(base_id,
                            ref_id,
                            character_name,
                            gender,
                            race,
                            is_player_character,
                            bio,
                            is_in_combat,
                            is_outside_talking_range,
                            is_enemy,
                            relationship_rank,
                            is_generic_npc,
                            ingame_voice_model,
                            tts_voice_model,
                            csv_in_game_voice_model,
                            advanced_voice_model,
                            voice_accent,
                            equipment,
                            custom_values)
        except CharacterDoesNotExist:                 
            logging.log(23, 'Restarting...')
            return None 
        
    def error_message(self, message: str) -> dict[str, Any]:
        return {
                comm_consts.KEY_REPLYTYPE: "error",
                "mantella_message": message
            }
    
    @utils.time_it
    def __get_player_voice_model(self, game_value: str | None) -> str:
        if game_value == None:
            return self.__config.player_voice_model
        return game_value
    
    @utils.time_it
    def __convert_to_equipment_item_dictionary(self, input_dict: dict[str, Any]) -> dict[str, EquipmentItem]:
        result: dict[str, EquipmentItem] = {}
        if input_dict:
            for slot, itemname in input_dict.items():
                result[slot] = EquipmentItem(itemname)
        return result

    @utils.time_it
    def __try_preload_voice_model(self):
        '''
        If the conversation has the following conditions:

        1. Single NPC (ie only one possible voice model to load)
        2. The player is not the first to speak (ie there is no player voice model)
        3. The conversation does not have a narrator (ie their is no narrator voice model)

        Then pre-load the NPC's voice model
        '''
        is_npc_speaking_first: bool = self.__automatic_greeting

        if not self.__talk.context.npcs_in_conversation.contains_multiple_npcs() and is_npc_speaking_first and not self.__conv_has_narrator:
            character_to_talk = self.__talk.context.npcs_in_conversation.last_added_character
            if character_to_talk:
                self.__talk.output_manager.tts.change_voice(
                    character_to_talk.tts_voice_model, 
                    character_to_talk.in_game_voice_model, 
                    character_to_talk.csv_in_game_voice_model, 
                    character_to_talk.advanced_voice_model, 
                    character_to_talk.voice_accent, 
                    voice_gender=character_to_talk.gender, 
                    voice_race=character_to_talk.race
                )
            else:
                return self.error_message("Could not load initial character to talk to. Please try again.")