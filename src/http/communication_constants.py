
class communication_constants: 
    PREFIX: str = "mantella_"    
    KEY_REQUESTTYPE: str = PREFIX + "request_type"
    KEY_REPLYTYPE: str = PREFIX + "reply_type"

    KEY_REQUESTTYPE_INIT: str = PREFIX + "initialize"
    KEY_REQUESTTYPE_STARTCONVERSATION: str = PREFIX + "start_conversation"
    KEY_REQUESTTYPE_CONTINUECONVERSATION: str = PREFIX + "continue_conversation"
    KEY_REQUESTTYPE_PLAYERINPUT: str = PREFIX + "player_input"
    KEY_REQUESTTYPE_ENDCONVERSATION: str = PREFIX + "end_conversation"
    KEY_REQUESTTYPE_INTERRUPT: str = PREFIX + "interrupt"

    KEY_REPLYTTYPE_INITCOMPLETED: str = PREFIX + "init_completed"
    KEY_REPLYTTYPE_STARTCONVERSATIONCOMPLETED: str = PREFIX + "start_conversation_completed"

    KEY_REQUEST_EXTRA_ACTIONS: str = PREFIX + "extra_actions"
    
    KEY_REPLYTYPE_NPCTALK: str = PREFIX + "npc_talk"
    KEY_REPLYTYPE_NPCACTION: str  = PREFIX + "npc_action"
    KEY_REPLYTYPE_PLAYERTALK: str  = PREFIX + "player_talk"
    KEY_REPLYTYPE_ENDCONVERSATION: str  = PREFIX + "end_conversation"
    KEY_REPLYTYPE_INTERRUPTRECEIVED: str  = PREFIX + "interrupt_received"

    KEY_REQUESTTYPE_NPCINITIATIVE: str = PREFIX + "npc_initiative_check"
    KEY_REPLYTYPE_NPCINITIATIVE: str = PREFIX + "npc_initiative_result"
    KEY_STARTCONVERSATION_NPCINITIATIVE: str = PREFIX + "npc_initiative"
    KEY_NPCINITIATIVE_CHOSEN_REFID: str = PREFIX + "npc_initiative_chosen_refid"
    KEY_NPCINITIATIVE_SKIPTHRESHOLD: str = PREFIX + "npc_initiative_skip_threshold"

    KEY_REQUESTTYPE_NPCEVENT: str = PREFIX + "npc_event_check"
    KEY_REPLYTYPE_NPCEVENT: str = PREFIX + "npc_event_result"
    KEY_REPLYTYPE_NPCEVENT_ADDACTOR: str = PREFIX + "npc_event_add_actor"
    KEY_NPCEVENT_ID: str = PREFIX + "npc_event_id" # In the result, and in the start request of the conversation that acts the event out
    KEY_NPCEVENT_PARTICIPANT_REFIDS: str = PREFIX + "npc_event_participant_refids"
    KEY_NPCEVENT_ADDACTOR_REFID: str = PREFIX + "npc_event_add_actor_refid" # Only the player watching: anyone else joins by Shout
    # In the check: everyone nearby, nearest first. Only the nearest are also in the actors, in full
    KEY_NPCEVENT_NEARBY_REFIDS: str = PREFIX + "npc_event_nearby_refids"
    KEY_NPCEVENT_NEARBY_NAMES: str = PREFIX + "npc_event_nearby_names" # In the same order as the refids
    KEY_EVENT_HINT: str = PREFIX + "event_hint" # What the player would like to happen (Ask for a Hint). Only for the event generator

    # Conversation, Nearby and Random Events (Conversation Wheel). Sent during the player's turn, queued like player input
    KEY_REQUESTTYPE_CONVERSATIONEVENT: str = PREFIX + "conversation_event"
    KEY_REPLYTYPE_CONVERSATIONEVENT: str = PREFIX + "conversation_event_result"
    KEY_EVENT_KIND: str = PREFIX + "event_kind" # "conversation", "nearby" or "random". In an interrupt request: an event was picked, so a wait for the player to speak ends
    KEY_EVENT_SENDHISTORY: str = PREFIX + "event_send_history" # Send the Conversation So Far
    KEY_EVENT_INCLUDEPLAYER: str = PREFIX + "event_include_player" # Include Me
    KEY_EVENT_NEARBY_REFIDS: str = PREFIX + "event_nearby_refids" # Nearby and Random: who the event can be about, nearest first. Random: the NPCs in the conversation too
    KEY_EVENT_NEARBY_NAMES: str = PREFIX + "event_nearby_names" # In the same order as the refids
    KEY_EVENT_NEARBY_ACTORS: str = PREFIX + "event_nearby_actors" # Full actor settings of the nearest who are not in the conversation (Most People Described)
    KEY_EVENT_MAXDESCRIBED: str = PREFIX + "event_max_described" # Most People Described
    KEY_EVENT_RESULT: str = PREFIX + "event_result" # In the reply: True if something happened
    KEY_EVENT_CANCEL: str = PREFIX + "event_cancel" # In an interrupt request: the player ended the conversation while the event was being generated
    KEY_GAMEMASTERMODE: str = PREFIX + "game_master_mode" # In the start, continue and event replies: whether Game Master Mode is on

    # Shout: sent with every continue and player input request. The rest only while the player shouts
    KEY_SHOUT_ENABLED: str = PREFIX + "shout_enabled"
    KEY_SHOUT_NEARBY_REFIDS: str = PREFIX + "shout_nearby_refids"
    KEY_SHOUT_NEARBY_NAMES: str = PREFIX + "shout_nearby_names" # In the same order as the refids
    KEY_SHOUT_NEARBY_ACTORS: str = PREFIX + "shout_nearby_actors" # Full actor settings, sent once for each person who is new to the list
    KEY_SHOUT_LINESBETWEENJOINS: str = PREFIX + "shout_lines_between_joins"
    KEY_SHOUT_MAXDESCRIBED: str = PREFIX + "shout_max_described" # How many of the nearest people the Game Master gets the bios and memories of
    KEY_SHOUT_MAXPEOPLE: str = PREFIX + "shout_max_people"
    KEY_SHOUT_NEWCOMERSREMEMBER: str = PREFIX + "shout_newcomers_remember" # What someone who joins by shouting heard before: 0 since shouting, 1 the player's last line, 2 everything
    KEY_SHOUT_ADDFAILED_REFID: str = PREFIX + "shout_add_failed_refid"
    KEY_SHOUT_ADDFAILED_REASON: str = PREFIX + "shout_add_failed_reason" # Why the game could not add them, e.g. "in a scene". Only logged
    KEY_REPLYTYPE_SHOUT_ADDACTOR: str = PREFIX + "shout_add_actor"
    KEY_SHOUT_ADDACTOR_REFID: str = PREFIX + "shout_add_actor_refid"
    KEY_SHOUT_UNAVAILABLE: str = PREFIX + "shout_unavailable" # In the reply: Shout can't be used, as no Game Master model is set up

    # Quest tags: the game answers the checks of the quest tag conditions
    KEY_REQUESTTYPE_QUESTCHECKLIST: str = PREFIX + "quest_check_list_request" # Sent once when a save loads
    KEY_REPLYTYPE_QUESTCHECKLIST: str = PREFIX + "quest_check_list_result"
    KEY_QUESTCHECKS_LIST: str = PREFIX + "quest_check_list" # In the list reply, and in the start reply when the game's list is out of date
    KEY_QUESTCHECKS_FUNCTIONS: str = PREFIX + "quest_check_functions"
    KEY_QUESTCHECKS_REFERENCES: str = PREFIX + "quest_check_references" # What each check runs on; empty: the player
    KEY_QUESTCHECKS_PARAMS1: str = PREFIX + "quest_check_params1"
    KEY_QUESTCHECKS_PARAMS2: str = PREFIX + "quest_check_params2"
    KEY_QUESTCHECKS_VERSION: str = PREFIX + "quest_check_version" # In the list, and with every set of answers
    KEY_QUESTCHECKS_RESULTS: str = PREFIX + "quest_check_results" # In the context (start, player input), or top-level on the catch-up continue request
    KEY_NPCEVENT_PLAYERNOTICEABLE: str = PREFIX + "npc_event_player_noticeable"

    KEY_STARTCONVERSATION_WORLDID: str = PREFIX + "worldid"
    KEY_STARTCONVERSATION_USENARRATOR: str = PREFIX + "use_narrator"
    KEY_CONTINUECONVERSATION_TOPICINFOFILE: str = PREFIX + "topicinfofile"
    KEY_INPUTTYPE: str = PREFIX + "input_type"
    KEY_INPUTTYPE_MIC: str = PREFIX + "mic_input"
    KEY_INPUTTYPE_TEXT: str = PREFIX + "text_input"
    KEY_INPUTTYPE_PTT: str = PREFIX + "push_to_talk"

    KEY_REQUESTTYPE_TTS: str = PREFIX + "tts"
    KEY_INPUT_NAMESINCONVERSATION: str = PREFIX + "names_in_conversation"
    KEY_TRANSCRIBE: str = PREFIX + "transcribe"

    #Actors
    KEY_ACTORS: str = PREFIX + "actors"
    KEY_ACTOR_BASEID: str = PREFIX + "actor_baseid"
    KEY_ACTOR_REFID: str = PREFIX + "actor_refid"
    KEY_ACTOR_NAME: str = PREFIX + "actor_name"
    KEY_ACTOR_GENDER: str = PREFIX + "actor_gender"
    KEY_ACTOR_RACE: str = PREFIX + "actor_race"
    KEY_ACTOR_ISPLAYER: str = PREFIX + "actor_is_player"
    KEY_ACTOR_RELATIONSHIPRANK: str = PREFIX + "actor_relationshiprank"
    KEY_ACTOR_VOICETYPE: str = PREFIX + "actor_voicetype"
    KEY_ACTOR_ISINCOMBAT: str = PREFIX + "actor_is_in_combat"
    KEY_ACTOR_ISENEMY: str = PREFIX + "actor_is_enemy"
    KEY_ACTOR_CUSTOMVALUES: str = PREFIX + "actor_custom_values"
    KEY_ACTOR_EQUIPMENT: str = PREFIX + "equipment"

    KEY_ACTOR_SPEAKER: str = PREFIX + "actor_speaker"
    KEY_ACTOR_LINETOSPEAK: str = PREFIX + "actor_line_to_speak"
    KEY_ACTOR_ISNARRATION: str = PREFIX + "is_narration"
    KEY_ACTOR_VOICEFILE: str = PREFIX + "actor_voice_file"
    KEY_ACTOR_DURATION: str = PREFIX + "actor_line_duration"
    KEY_ACTOR_ACTIONS: str = PREFIX + "actor_actions"

    KEY_ACTOR_PC_DESCRIPTION = PREFIX + "pc_description"
    KEY_ACTOR_PC_VOICEPLAYERINPUT = PREFIX + "pc_voiceplayerinput"
    KEY_ACTOR_PC_VOICEMODEL = PREFIX + "pc_voicemodel"

    #context
    KEY_CONTEXT: str = PREFIX + "context"
    KEY_CONTEXT_LOCATION: str = PREFIX + "location"
    KEY_CONTEXT_WEATHER = PREFIX + "weather"
    KEY_CONTEXT_TIME: str = PREFIX + "time"
    KEY_CONTEXT_INGAMEEVENTS: str = PREFIX + "ingame_events"
    KEY_CONTEXT_CUSTOMVALUES: str = PREFIX + "custom_context_values"
    KEY_CONTEXT_CUSTOMVALUES_VISION_HINTSNAMEARRAY: str = PREFIX + "vision_hints_names"
    KEY_CONTEXT_CUSTOMVALUES_VISION_HINTSDISTANCEARRAY: str = PREFIX + "vision_hints_distance"

    # Actions
    ACTION_RELOADCONVERSATION: str = PREFIX + "reload_conversation"
    ACTION_ENDCONVERSATION: str = PREFIX + "end_conversation"
    ACTION_REMOVECHARACTER: str = PREFIX + "remove_character"

    ACTION_NPC_OFFENDED: str = PREFIX + "npc_offended"
    ACTION_NPC_FORGIVEN: str = PREFIX + "npc_forgiven"
    ACTION_NPC_FOLLOW: str = PREFIX + "npc_follow"
    ACTION_NPC_INVENTORY: str = PREFIX + "npc_inventory"