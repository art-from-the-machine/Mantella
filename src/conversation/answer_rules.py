"""Who has to speak before the player's turn, and who answers first: the talk settings, Most Replies per Person and People Who Must Answer a Group Line
that apply to a turn of NPC replies, by what started it (see the Conversation page)"""
from dataclasses import dataclass
from typing import Any
from src.config.definitions.conversation_definitions import (AT_REPLY_LIMIT, DEFAULT_MAX_ANSWERING, DEFAULT_MOST_REPLIES, DIRECTOR, EVENT_KINDS, EXTRA_ROUNDS,
                                                             GROUP, NPC_EVENT, REPLIES_IN_BETWEEN, SHARED, SHOUT, WHEN_NPC_TALKS, WHEN_YOU_TALK,
                                                             WHO_MUST_SPEAK, AtReplyLimitEnum, WhoAnswersFirstEnum, WhoMustSpeakEnum, default_talk_settings,
                                                             default_uses_own_settings, most_replies_identifier, must_speak_problem, talk_key, use_own_key)


@dataclass(frozen=True)
class TurnRules:
    situation: str # The kind of conversation the turn belongs to: group_conversation, shout, director, an event kind, or npc_event
    settings_from: str # Whose talk settings apply: the kind itself (its "Use its own settings" switch is on), or SHARED (the All Conversations section)
    must_speak: frozenset[WhoMustSpeakEnum] # Who must speak before the player's turn
    after_you: WhoAnswersFirstEnum # Who answers first when the player (or an event or direction) talks to someone
    after_npc: WhoAnswersFirstEnum # Who answers first when an NPC talks to someone
    at_reply_limit: AtReplyLimitEnum # Who of the people who still have to speak still does at the reply limit
    replies_in_between: int # Free picks of the Game Master in each round after the reply limit, before the reply limit minus 1 caps it
    extra_rounds: int # The most rounds after the reply limit
    most_replies: int # Most Replies per Person
    max_answering: int # People Who Must Answer a Group Line

    @property
    def everyone_speaks(self) -> bool:
        """Everyone in the conversation has to say something"""
        return WhoMustSpeakEnum.EVERYONE in self.must_speak

    def must_answer(self, from_you: bool) -> bool:
        """Whoever a line is spoken to has to speak before the player's turn: a line the player said (or an event or direction), or an NPC's"""
        return (WhoMustSpeakEnum.YOU_TALK_TO if from_you else WhoMustSpeakEnum.NPC_TALKS_TO) in self.must_speak

    def answers_first(self, from_you: bool) -> WhoAnswersFirstEnum:
        return self.after_you if from_you else self.after_npc

    def uses_who_a_line_is_for(self, from_you: bool) -> bool:
        """Who a line was spoken to makes a difference: they have to speak, or they answer first"""
        return self.must_answer(from_you) or self.answers_first(from_you) != WhoAnswersFirstEnum.GAME_MASTER

    def free_picks(self, reply_limit: int) -> int:
        """Replies in between, never more than the reply limit minus 1, so a round is never longer than the reply limit"""
        return max(0, min(self.replies_in_between, reply_limit - 1))


def conversation_situation(conversation_type: Any, shout_type: type) -> str:
    """Group Conversation, Shout or Director Mode, from the conversation type. Directing wins"""
    if conversation_type.is_director_mode():
        return DIRECTOR
    if isinstance(conversation_type, shout_type):
        return SHOUT
    return GROUP


def _number(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _setting(config: Any, kind: str, setting: str, expected: type) -> Any:
    """A talk setting of the set, or its default if it is missing or not what it should be (e.g. a test config)"""
    value = getattr(config, talk_key(kind, setting), None)
    default = default_talk_settings(kind)[setting]
    if setting == WHO_MUST_SPEAK:
        ticked = frozenset(value) if isinstance(value, (set, frozenset, list, tuple)) and all(isinstance(v, WhoMustSpeakEnum) for v in value) else None
        return ticked if ticked and not must_speak_problem(list(ticked)) else frozenset(default) # type: ignore
    if expected is int:
        return max(0, _number(value, default)) # type: ignore
    return value if isinstance(value, expected) else default


def uses_own_settings(config: Any, kind: str) -> bool:
    value = getattr(config, use_own_key(kind), None)
    return value if isinstance(value, bool) else default_uses_own_settings(kind)


def turn_rules(config: Any, conversation_type: Any, shout_type: type, is_watched_scene: bool, event_kind: str = "", shout_max_answering: int | None = None) -> TurnRules:
    """The rules of a turn of NPC replies

    Args:
        conversation_type: the conversation's current type
        shout_type (type): the Shout conversation type (passed in, so this module needs no conversation types)
        is_watched_scene (bool): an NPC Event the player only watches
        event_kind (str): "conversation", "nearby" or "random" if a Conversation Wheel event started the turn. Empty otherwise
        shout_max_answering (int | None): Shout's People Who Must Answer a Group Line while Shout is on. None without Shout
    """
    if is_watched_scene:
        situation = NPC_EVENT
        most_replies_situation = NPC_EVENT
    else:
        conversation = conversation_situation(conversation_type, shout_type)
        situation = EVENT_KINDS.get(event_kind, conversation)
        most_replies_situation = conversation # Events use the number of the conversation they happen in
    settings_from = situation if uses_own_settings(config, situation) else SHARED
    after_you = WhoAnswersFirstEnum.GAME_MASTER if settings_from == NPC_EVENT else _setting(config, settings_from, WHEN_YOU_TALK, WhoAnswersFirstEnum)
    most_replies = max(1, _number(getattr(config, most_replies_identifier(most_replies_situation), None), DEFAULT_MOST_REPLIES))
    if shout_max_answering is not None:
        max_answering = shout_max_answering
    else:
        max_answering = _number(getattr(config, "group_conversation_max_answering", None), DEFAULT_MAX_ANSWERING)
    return TurnRules(situation, settings_from,
                     _setting(config, settings_from, WHO_MUST_SPEAK, frozenset),
                     after_you,
                     _setting(config, settings_from, WHEN_NPC_TALKS, WhoAnswersFirstEnum),
                     _setting(config, settings_from, AT_REPLY_LIMIT, AtReplyLimitEnum),
                     _setting(config, settings_from, REPLIES_IN_BETWEEN, int),
                     _setting(config, settings_from, EXTRA_ROUNDS, int),
                     most_replies, max(1, max_answering))


@dataclass
class AnswerGroup:
    """The people one line was spoken to, who answer first ("When you talk to someone" / "When an NPC talks to someone")"""
    people: list[tuple[str, str]] # (ref id, name) of each who hasn't answered yet, the Game Master's choice first
    from_you: bool # The player said the line, or it is an event or a direction
    each_in_turn: bool # Each answers in turn: one reply each. Otherwise They answer next: one reply from any of them


class AnswerOrder:
    """Who is due to give the next replies, as "When you talk to someone" and "When an NPC talks to someone" set it: groups of people,
    the oldest group first. Unlike who still has to speak (TurnAnswers), it only sets the order: it is cleared at the reply limit"""
    def __init__(self) -> None:
        self.groups: list[AnswerGroup] = []

    def add(self, people: list[tuple[str, str]], from_you: bool, answers_first: WhoAnswersFirstEnum) -> bool:
        """The line was spoken to these people

        Returns:
            bool: False if an NPC's "They answer next" was forgotten, as people are still waiting their turn: they go first
        """
        if not people or answers_first == WhoAnswersFirstEnum.GAME_MASTER:
            return True
        if answers_first == WhoAnswersFirstEnum.ANSWER_NEXT and not from_you and self.groups:
            return False
        self.groups.append(AnswerGroup(list(people), from_you, answers_first == WhoAnswersFirstEnum.EACH_IN_TURN))
        return True

    def due(self) -> list[tuple[str, str]]:
        """The people one of whom gives the next reply. Empty if nobody is due"""
        return list(self.groups[0].people) if self.groups else []

    def spoke(self, ref_id: str):
        """They replied: that one reply covers every line they were due to answer. A "They answer next" group first in line is used up by the reply,
        whoever gave it"""
        if self.groups and not self.groups[0].each_in_turn:
            self.groups.pop(0)
        self.drop({ref_id})

    def drop(self, ref_ids: set[str]):
        """These people are no longer due, e.g. they have reached Most Replies per Person or left"""
        for group in self.groups:
            group.people = [person for person in group.people if person[0] not in ref_ids]
        self.groups = [group for group in self.groups if group.people]

    def clear(self):
        self.groups = []

    def names(self) -> list[list[str]]:
        return [[name for _ref_id, name in group.people] for group in self.groups]
