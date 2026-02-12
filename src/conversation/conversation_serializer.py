"""
Lossless JSON serialization and deserialization for conversation message threads.
Used by the live conversation editor in the Bio Editor tab.
"""
import json
import logging
from src.config.config_loader import ConfigLoader
from src.llm.messages import UserMessage, AssistantMessage, join_message, leave_message, Message
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum
from src.llm.sentence import Sentence
from src.character_manager import Character
from src.games.equipment import Equipment


def _character_to_dict(c: Character) -> dict:
    """Serialize Character to a minimal dict for round-trip."""
    return {
        "ref_id": c.ref_id,
        "name": c.name,
        "base_id": c.base_id,
    }


def _character_from_dict(d: dict, character_resolver) -> Character:
    """
    Resolve Character from dict. Uses character_resolver(ref_id, name, base_id) to get
    full Character, or creates a stub if not found.
    """
    ref_id = str(d.get("ref_id", ""))
    name = str(d.get("name", ""))
    base_id = str(d.get("base_id", ref_id))
    if character_resolver:
        ch = character_resolver(ref_id, name, base_id)
        if ch is not None:
            return ch
    return _create_stub_character(ref_id, name, base_id)


def _create_stub_character(ref_id: str, name: str, base_id: str) -> Character:
    """Create a minimal Character for deserialization when the character is not in the active conversation."""
    return Character(
        base_id=base_id or ref_id,
        ref_id=ref_id,
        name=name or "Unknown",
        gender=0,
        race="",
        is_player_character=False,
        bio="",
        is_in_combat=False,
        is_enemy=False,
        relationship_rank=0,
        is_generic_npc=True,
        ingame_voice_model="",
        tts_voice_model="",
        csv_in_game_voice_model="",
        advanced_voice_model="",
        voice_accent="",
        equipment=Equipment({}),
        custom_character_values={},
        tts_service="",
        llm_service="",
        llm_model="",
    )


def serialize_persistent_messages(messages: list[Message], config: ConfigLoader) -> str:
    """
    Serialize persistent messages to a lossless JSON string.
    Preserves all fields for UserMessage, AssistantMessage, join_message, leave_message.
    """
    result = []
    for m in messages:
        if isinstance(m, UserMessage):
            time_val = None
            if hasattr(m, "_UserMessage__time") and m._UserMessage__time:
                time_val = list(m._UserMessage__time)
            events = []
            if hasattr(m, "_UserMessage__ingame_events"):
                events = list(m._UserMessage__ingame_events) if m._UserMessage__ingame_events else []
            result.append({
                "type": "user",
                "text": m.text,
                "player_character_name": m.player_character_name,
                "ingame_events": events,
                "time": time_val,
                "is_system_generated": m.is_system_generated_message,
                "is_multi_npc": m.is_multi_npc_message,
            })
        elif isinstance(m, AssistantMessage):
            sentences_data = []
            if hasattr(m, "_AssistantMessage__sentences"):
                for s in m._AssistantMessage__sentences:
                    sentences_data.append({
                        "speaker_ref_id": s.speaker.ref_id,
                        "speaker_name": s.speaker.name,
                        "speaker_base_id": s.speaker.base_id,
                        "text": s.text,
                        "sentence_type": s.sentence_type.name if hasattr(s.sentence_type, "name") else str(s.sentence_type),
                        "is_system_generated": getattr(s, "is_system_generated_sentence", False),
                        "actions": list(s.actions) if s.actions else [],
                    })
            result.append({
                "type": "assistant",
                "is_multi_npc": m.is_multi_npc_message,
                "is_system_generated": m.is_system_generated_message,
                "sentences": sentences_data,
            })
        elif isinstance(m, join_message):
            result.append({
                "type": "join",
                "character": _character_to_dict(m.character),
                "content": m.text,
            })
        elif isinstance(m, leave_message):
            result.append({
                "type": "leave",
                "character": _character_to_dict(m.character),
                "content": m.text,
            })
        else:
            logging.warning(f"conversation_serializer: skipping unknown message type {type(m)}")
    return json.dumps(result, indent=2, ensure_ascii=False)


def deserialize_persistent_messages(
    json_str: str,
    config: ConfigLoader,
    character_resolver=None,
) -> list[Message]:
    """
    Deserialize JSON string back to a list of Message objects.
    character_resolver: callable(ref_id, name, base_id) -> Character | None
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of messages")

    result = []
    for item in data:
        if not isinstance(item, dict) or "type" not in item:
            logging.warning(f"conversation_serializer: skipping invalid message item: {item}")
            continue
        msg_type = item.get("type", "")
        if msg_type == "user":
            msg = UserMessage(
                config,
                text=str(item.get("text", "")),
                player_character_name=str(item.get("player_character_name", "")),
                is_system_generated_message=bool(item.get("is_system_generated", False)),
            )
            msg.is_multi_npc_message = bool(item.get("is_multi_npc", False))
            for ev in item.get("ingame_events", []):
                msg.add_event([str(ev)])
            if item.get("time"):
                t = item["time"]
                if isinstance(t, (list, tuple)) and len(t) >= 2:
                    msg.set_ingame_time(str(t[0]), str(t[1]))
            result.append(msg)
        elif msg_type == "assistant":
            msg = AssistantMessage(
                config,
                is_system_generated_message=bool(item.get("is_system_generated", False)),
            )
            msg.is_multi_npc_message = bool(item.get("is_multi_npc", False))
            for sdata in item.get("sentences", []):
                ref_id = str(sdata.get("speaker_ref_id", ""))
                name = str(sdata.get("speaker_name", ""))
                base_id = str(sdata.get("speaker_base_id", ref_id))
                speaker = _character_from_dict(
                    {"ref_id": ref_id, "name": name, "base_id": base_id},
                    character_resolver,
                )
                stype_str = sdata.get("sentence_type", "SPEECH").upper()
                stype = SentenceTypeEnum.SPEECH if stype_str != "NARRATION" else SentenceTypeEnum.NARRATION
                actions = list(sdata.get("actions", [])) if sdata.get("actions") else []
                content = SentenceContent(
                    speaker=speaker,
                    text=str(sdata.get("text", "")),
                    sentence_type=stype,
                    is_system_generated_sentence=bool(sdata.get("is_system_generated", False)),
                    actions=actions,
                )
                sentence = Sentence(content, "", 0.0)
                msg.add_sentence(sentence)
            result.append(msg)
        elif msg_type == "join":
            ch_d = item.get("character", {})
            character = _character_from_dict(ch_d, character_resolver)
            msg = join_message(character, config)
            if item.get("content"):
                msg.text = str(item["content"])
            result.append(msg)
        elif msg_type == "leave":
            ch_d = item.get("character", {})
            character = _character_from_dict(ch_d, character_resolver)
            msg = leave_message(character, config)
            if item.get("content"):
                msg.text = str(item["content"])
            result.append(msg)
        else:
            logging.warning(f"conversation_serializer: skipping unknown type '{msg_type}'")
    return result
