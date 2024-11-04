
class communication_constants: 
    PREFIX: str = "mantella_"    
    KEY_REQUESTTYPE: str = PREFIX + "request_type"
    KEY_REPLYTYPE: str = PREFIX + "reply_type"

    KEY_REQUESTTYPE_STARTCONVERSATION: str = PREFIX + "start_conversation"
    KEY_REQUESTTYPE_CONTINUECONVERSATION: str = PREFIX + "continue_conversation"
    KEY_REQUESTTYPE_PLAYERINPUT: str = PREFIX + "player_input"
    KEY_REQUESTTYPE_ENDCONVERSATION: str = PREFIX + "end_conversation"

    KEY_REPLYTTYPE_STARTCONVERSATIONCOMPLETED: str = PREFIX + "start_conversation_completed"

    KEY_REQUEST_EXTRA_ACTIONS: str = PREFIX + "extra_actions"
    
    KEY_REPLYTYPE_NPCTALK: str = PREFIX + "npc_talk"
    KEY_REPLYTYPE_PLAYERTALK: str  = PREFIX + "player_talk"
    KEY_REPLYTYPE_ENDCONVERSATION: str  = PREFIX + "end_conversation"

    #Actors
    KEY_ACTORS: str = PREFIX + "actors"
    KEY_ACTOR_ID: str = PREFIX + "actor_baseid"
    KEY_ACTOR_NAME: str = PREFIX + "actor_name"
    KEY_ACTOR_GENDER: str = PREFIX + "actor_gender"
    KEY_ACTOR_RACE: str = PREFIX + "actor_race"
    KEY_ACTOR_ISPLAYER: str = PREFIX + "actor_is_player"
    KEY_ACTOR_RELATIONSHIPRANK: str = PREFIX + "actor_relationshiprank"
    KEY_ACTOR_VOICETYPE: str = PREFIX + "actor_voicetype"
    KEY_ACTOR_ISINCOMBAT: str = PREFIX + "actor_is_in_combat"
    KEY_ACTOR_ISENEMY: str = PREFIX + "actor_is_enemy"
    KEY_ACTOR_CUSTOMVALUES: str = PREFIX + "actor_custom_values"

    KEY_ACTOR_SPEAKER: str = PREFIX + "actor_speaker"
    KEY_ACTOR_LINETOSPEAK: str = PREFIX + "actor_line_to_speak"
    KEY_ACTOR_VOICEFILE: str = PREFIX + "actor_voice_file"
    KEY_ACTOR_DURATION: str = PREFIX + "actor_line_duration"
    KEY_ACTOR_ACTIONS: str = PREFIX + "actor_actions"

    #context
    KEY_CONTEXT: str = PREFIX + "context"
    KEY_CONTEXT_LOCATION: str = PREFIX + "location"
    KEY_CONTEXT_TIME: str = PREFIX + "time"
    KEY_CONTEXT_INGAMEEVENTS: str = PREFIX + "ingame_events"
    KEY_CONTEXT_CUSTOMVALUES: str = PREFIX + "custom_context_values"

    # Actions
    ACTION_RELOADCONVERSATION: str = PREFIX + "reload_conversation"
    ACTION_ENDCONVERSATION: str = PREFIX + "end_conversation"
    ACTION_REMOVECHARACTER: str = PREFIX + "remove_character"

    ACTION_NPC_OFFENDED: str = PREFIX + "npc_offended"
    ACTION_NPC_FORGIVEN: str = PREFIX + "npc_forgiven"
    ACTION_NPC_FOLLOW: str = PREFIX + "npc_follow"