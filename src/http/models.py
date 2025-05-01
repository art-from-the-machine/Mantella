from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union, Literal
from .communication_constants import communication_constants as comm_consts
# pyright: reportInvalidTypeForm=false

class Equipment(BaseModel):
    body: Optional[str] = None
    feet: Optional[str] = None
    hands: Optional[str] = None
    head: Optional[str] = None
    righthand: Optional[str] = None

class ActorCustomValues(BaseModel):
    description: str = Field('', alias=comm_consts.KEY_ACTOR_PC_DESCRIPTION)
    voice_player_input: bool = Field(False, alias=comm_consts.KEY_ACTOR_PC_VOICEPLAYERINPUT)

class Actor(BaseModel):
    base_id: int = Field(..., alias=comm_consts.KEY_ACTOR_BASEID)
    custom_values: Optional[ActorCustomValues] = Field(None, alias=comm_consts.KEY_ACTOR_CUSTOMVALUES)
    gender: int = Field(..., alias=comm_consts.KEY_ACTOR_GENDER)
    is_enemy: bool = Field(..., alias=comm_consts.KEY_ACTOR_ISENEMY)
    is_in_combat: bool = Field(..., alias=comm_consts.KEY_ACTOR_ISINCOMBAT)
    is_player: bool = Field(..., alias=comm_consts.KEY_ACTOR_ISPLAYER)
    name: str = Field(..., alias=comm_consts.KEY_ACTOR_NAME)
    race: str = Field(..., alias=comm_consts.KEY_ACTOR_RACE)
    ref_id: int = Field(..., alias=comm_consts.KEY_ACTOR_REFID)
    relationship_rank: int = Field(..., alias=comm_consts.KEY_ACTOR_RELATIONSHIPRANK)
    voice_type: str = Field(..., alias=comm_consts.KEY_ACTOR_VOICETYPE)
    equipment: Equipment = Field(..., alias=comm_consts.KEY_ACTOR_EQUIPMENT)

class Context(BaseModel):
    location: str = Field(..., alias=comm_consts.KEY_CONTEXT_LOCATION)
    time: int = Field(..., alias=comm_consts.KEY_CONTEXT_TIME)
    ingame_events: List[str] = Field([], alias=comm_consts.KEY_CONTEXT_INGAMEEVENTS)
    weather: Optional[str] = Field(None, alias=comm_consts.KEY_CONTEXT_WEATHER)
    custom_values: Optional[Dict[str, Any]] = Field(None, alias=comm_consts.KEY_CONTEXT_CUSTOMVALUES)

class ActorTalk(BaseModel):
    speaker: str = Field(..., alias=comm_consts.KEY_ACTOR_SPEAKER)
    line_to_speak: str = Field(..., alias=comm_consts.KEY_ACTOR_LINETOSPEAK)
    is_narration: bool = Field(..., alias=comm_consts.KEY_ACTOR_ISNARRATION)
    voice_file: str = Field(..., alias=comm_consts.KEY_ACTOR_VOICEFILE)
    line_duration: float = Field(..., alias=comm_consts.KEY_ACTOR_DURATION)
    actions: List[str] = Field([], alias=comm_consts.KEY_ACTOR_ACTIONS)
    topic_info_file: int = Field(..., alias=comm_consts.KEY_CONTINUECONVERSATION_TOPICINFOFILE)


class BaseRequest(BaseModel):
    request_type: str = Field(..., alias=comm_consts.KEY_REQUESTTYPE)

class InitRequest(BaseRequest):
    request_type: Literal[comm_consts.KEY_REQUESTTYPE_INIT] = Field(
        comm_consts.KEY_REQUESTTYPE_INIT, alias=comm_consts.KEY_REQUESTTYPE
    )

class StartConversationRequest(BaseRequest):
    request_type: Literal[comm_consts.KEY_REQUESTTYPE_STARTCONVERSATION] = Field(
        comm_consts.KEY_REQUESTTYPE_STARTCONVERSATION, alias=comm_consts.KEY_REQUESTTYPE
    )
    actors: List[Actor] = Field(..., alias=comm_consts.KEY_ACTORS)
    context: Context = Field(..., alias=comm_consts.KEY_CONTEXT)
    input_type: str = Field(..., alias=comm_consts.KEY_INPUTTYPE)
    world_id: str = Field(..., alias=comm_consts.KEY_STARTCONVERSATION_WORLDID)
    use_narrator: Optional[bool] = Field(None, alias=comm_consts.KEY_STARTCONVERSATION_USENARRATOR)

class ContinueConversationRequest(BaseRequest):
    request_type: Literal[comm_consts.KEY_REQUESTTYPE_CONTINUECONVERSATION] = Field(
        comm_consts.KEY_REQUESTTYPE_CONTINUECONVERSATION, alias=comm_consts.KEY_REQUESTTYPE
    )
    topicinfo_file: int = Field(..., alias=comm_consts.KEY_CONTINUECONVERSATION_TOPICINFOFILE)

class PlayerInputRequest(BaseRequest):
    request_type: Literal[comm_consts.KEY_REQUESTTYPE_PLAYERINPUT] = Field(
        comm_consts.KEY_REQUESTTYPE_PLAYERINPUT, alias=comm_consts.KEY_REQUESTTYPE
    )
    actors: Optional[List[Actor]] = Field(None, alias=comm_consts.KEY_ACTORS)
    context: Optional[Context] = Field(None, alias=comm_consts.KEY_CONTEXT)
    player_input: str = Field(..., alias=comm_consts.KEY_REQUESTTYPE_PLAYERINPUT)

class EndConversationRequest(BaseRequest):
    request_type: Literal[comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION] = Field(
        comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION, alias=comm_consts.KEY_REQUESTTYPE
    )


class BaseResponse(BaseModel):
    reply_type: str = Field(..., alias=comm_consts.KEY_REPLYTYPE)

class InitResponse(BaseResponse):
    reply_type: Literal[comm_consts.KEY_REPLYTTYPE_INITCOMPLETED] = Field(
        comm_consts.KEY_REPLYTTYPE_INITCOMPLETED, alias=comm_consts.KEY_REPLYTYPE
    )

class StartConversationResponse(BaseResponse):
    reply_type: Literal[comm_consts.KEY_REPLYTTYPE_STARTCONVERSATIONCOMPLETED] = Field(
        comm_consts.KEY_REPLYTTYPE_STARTCONVERSATIONCOMPLETED, alias=comm_consts.KEY_REPLYTYPE
    )

class NpcTalkResponse(BaseResponse):
    reply_type: Literal[comm_consts.KEY_REPLYTYPE_NPCTALK] = Field(
        comm_consts.KEY_REPLYTYPE_NPCTALK, alias=comm_consts.KEY_REPLYTYPE
    )
    actor_talk: Optional[ActorTalk] = Field(None, alias=comm_consts.KEY_REPLYTYPE_NPCTALK)

class PlayerTalkResponse(BaseResponse):
    reply_type: Literal[comm_consts.KEY_REPLYTYPE_PLAYERTALK] = Field(
        comm_consts.KEY_REPLYTYPE_PLAYERTALK, alias=comm_consts.KEY_REPLYTYPE
    )

class EndConversationResponse(BaseResponse):
    reply_type: Literal[comm_consts.KEY_REPLYTYPE_ENDCONVERSATION] = Field(
        comm_consts.KEY_REPLYTYPE_ENDCONVERSATION, alias=comm_consts.KEY_REPLYTYPE
    )