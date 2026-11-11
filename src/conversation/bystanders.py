import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar
from src.config.config_loader import ConfigLoader

if TYPE_CHECKING:
    from src.character_manager import Character

NOBODY_NEARBY = "nobody"
SHOUT_NEARBY_CRITERIA = "skyrim_shout_decision_nearby_criteria"

# Newcomers Remember (Shout Mode MCM page): what someone who joins by shouting heard before they joined. The values the game sends
NEWCOMERS_REMEMBER_SINCE_SHOUT = 0 # Everything since the player started shouting
NEWCOMERS_REMEMBER_LAST_LINE = 1 # Only the player's last line and what was said after it
NEWCOMERS_REMEMBER_EVERYTHING = 2 # The whole conversation
NEWCOMERS_REMEMBER_CHOICES = (NEWCOMERS_REMEMBER_SINCE_SHOUT, NEWCOMERS_REMEMBER_LAST_LINE, NEWCOMERS_REMEMBER_EVERYTHING)


@dataclass
class EventPerson:
    """Someone near the conversation who is not part of it yet: a nearby NPC, or the bystander player of an NPC Event"""
    name: str # The label shown to the LLMs. People with the same name get 'Name (2)', 'Name (3)', ...
    refid: int # As sent by the game, so it can be sent back unchanged
    ref_id: str # Character.ref_id, to recognise them when they join the conversation


@dataclass
class AnswerDue:
    """Someone a line was spoken to, or who is part of an event, and who has not answered it yet"""
    name: str
    speaker: str # Who said the line. Empty for an event
    is_protected: bool # Spoken to by the player, or part of an event: they still answer once the NPCs have reached their limit of replies in a row
    others: list[str] = field(default_factory=list) # The others the same line was aimed at. Empty unless it was aimed at several people


@dataclass(kw_only=True)
class Bystanders:
    """The people near a conversation who are not part of it, any of whom the Game Master may draw in.
    The Game Master picks who a line is aimed at, the game adds them in one step, and the first of them speaks next"""
    LOG_PREFIX: ClassVar[str] = "Nearby"
    nearby: list[EventPerson] = field(default_factory=list)
    pending_add: EventPerson | None = None # Picked by the Game Master. Can only speak once the game has added them. None: nobody waits to be added
    pending_others: list[EventPerson] = field(default_factory=list) # The others the same line was aimed at, added in the same step as pending_add
    join_order: list[str] = field(default_factory=list) # The ref ids of the last people asked for, the first speaker first
    forced_speaker_ref_id: str = "" # Has just joined, so speaks next without asking the Game Master
    logged_nearby: list[str] | None = None # None until first logged, so "nobody" is logged too

    def pending_adds(self) -> list[EventPerson]:
        """Everyone who waits to be added by the game, the one who speaks first at the front"""
        return ([self.pending_add] if self.pending_add else []) + self.pending_others

    def request_adds(self, people: list[EventPerson]):
        """The game is asked to add these people in one step. The first of them who joins speaks next"""
        self.pending_add = people[0] if people else None
        self.pending_others = list(people[1:])
        self.join_order = [p.ref_id for p in people]

    def _drop_pending(self, person: EventPerson):
        """They no longer wait to be added. The next one waiting moves up, so pending_add is only None when nobody waits"""
        if self.pending_add is person:
            self.pending_add = self.pending_others.pop(0) if self.pending_others else None
        else:
            self.pending_others = [p for p in self.pending_others if p is not person]

    def _join_rank(self, ref_id: str) -> int:
        return self.join_order.index(ref_id) if ref_id in self.join_order else len(self.join_order)

    def present_nearby(self) -> list[EventPerson]:
        """The nearby people who are still near the conversation"""
        return list(self.nearby)

    def nearby_people(self, config: ConfigLoader, participant_names: list[str]) -> list[EventPerson]:
        """The nearby people, without anyone named like someone in the conversation, as the LLMs could not tell the two apart
        (e.g. the scene's 'Whiterun Guard' was labelled 'Whiterun Guard (2)' in the check, so the other guard nearby is 'Whiterun Guard' too)

        Args:
            participant_names (list[str]): the names of everyone in the conversation, as in game
        """
        taken_names = {name.lower() for name in participant_names}
        return [p for p in self.present_nearby() if p.name.lower() not in taken_names]

    def nearby_choices(self, config: ConfigLoader, participant_names: list[str], npc_count: int, has_player: bool = True) -> list[EventPerson]:
        """The nearby people the Game Master may draw in right now

        Args:
            has_player (bool): the player is in the conversation (not while they watch an NPC Event)
        """
        return self.nearby_people(config, participant_names)

    def nearby_text(self, config: ConfigLoader, participant_names: list[str], extra: list[EventPerson] | None = None) -> str:
        """The {nearby} prompt variable

        Args:
            extra (list[EventPerson] | None): named after the people nearby, e.g. the player watching an NPC Event once the scene's people can notice them
        """
        names = [p.name for p in self.nearby_people(config, participant_names) + (extra or [])]
        if sorted(names) != self.logged_nearby: # Logged when someone comes or goes, not each time people move and the order changes
            self.logged_nearby = sorted(names)
            logging.log(26, f"{self.LOG_PREFIX}: nearby now: {', '.join(names) or NOBODY_NEARBY}")
        return ", ".join(names) or NOBODY_NEARBY

    def nearby_criteria(self, config: ConfigLoader) -> tuple[str, str]:
        """The decision model's criteria for choosing someone nearby: (prompt type, text)"""
        raise NotImplementedError

    def apply_add_failed(self, refid: int, reason: str = "") -> bool:
        """The game could not add the person picked

        Args:
            reason (str): why, as the game sent it (e.g. "in a scene"). Only logged

        Returns:
            bool: True if they were waiting to be added
        """
        person = next((p for p in self.pending_adds() if p.refid == refid), None) if refid else None
        if not person:
            return False
        because = f": {reason}" if reason else ""
        logging.log(26, f"{self.LOG_PREFIX}: {person.name} could not be added to the conversation{because}")
        self.nearby = [p for p in self.nearby if p.refid != refid]
        self._drop_pending(person)
        return True

    def on_npc_joined(self, ref_id: str) -> bool:
        """An NPC joined the conversation: the person the Game Master picked, or anyone the player added

        Returns:
            bool: True if they were waiting to be added. The first of the people asked for who joins speaks next
        """
        self.nearby = [p for p in self.nearby if p.ref_id != ref_id]
        person = next((p for p in self.pending_adds() if p.ref_id == ref_id), None)
        if not person:
            return False
        self._drop_pending(person)
        if not self.forced_speaker_ref_id or self._join_rank(ref_id) < self._join_rank(self.forced_speaker_ref_id):
            self.forced_speaker_ref_id = ref_id
        return True


@dataclass(kw_only=True)
class ShoutState(Bystanders):
    """Shout: anyone near the player can answer them or join in. The game sends who is nearby with each request,
    and the limits below decide when the Game Master may draw one of them in.
    NPC Events run in Shout from the start, so it is also who can join a scene the player watches (the game finds them with the NPC Event's rules)"""
    LOG_PREFIX: ClassVar[str] = "Shout"
    max_people: int = 6 # Nobody new joins once the conversation has this many people, the player included
    start_marker: int | None = None # The token marking the last message before Shout was turned on. Newcomers hear everything after it. None if nothing was said
    answering_pick: bool = False # The pending pick answers the player's line
    answer_again: bool = False # The person picked to answer the player could not be added: the turn starts again without anyone nearby
    failed_refids: set[int] = field(default_factory=set) # Could not be added. Left out until they drop off the game's nearby list
    game_master_offer: list[EventPerson] | None = field(default=None, repr=False) # While the Game Master's prompt is built: who it may pick this time
    characters: dict[int, "Character"] = field(default_factory=dict, repr=False) # The nearby people the game sent in full, by refid. Kept while Shout is on
    max_described: int = 6 # Most People Described: how many of the nearest people the Game Master gets the bios and memories of
    max_answering: int = 5 # Most People Answering at Once: how many answer a line aimed at a group. People the line names always answer
    still_to_answer: dict[str, AnswerDue] = field(default_factory=dict) # By ref id: who a line was aimed at and has not answered it yet
    answer_first_ref_id: str = "" # Someone in the conversation who speaks first once the others the line was aimed at have been added
    analysed_line: tuple[int, str] | None = field(default=None, repr=False) # The last line the Game Master was asked about (who it was aimed at), so it is asked once
    newcomers_remember: int = NEWCOMERS_REMEMBER_SINCE_SHOUT # What someone who joins by shouting heard before they joined
    logged_described: list[str] | None = field(default=None, repr=False) # Whose bios the Game Master used, as last logged
    event_ignores_max_people: bool = False # The latest event was a Nearby or Random Event: the people nearby who react to it first join even past Most People in Conversation. Set by each event

    def apply_settings(self, settings: dict[str, Any] | None):
        """The Shout Mode settings from the MCM, sent with each request. Keys: max_people, max_described, newcomers_remember, max_answering"""
        if not settings:
            return
        if settings.get("max_answering") is not None:
            self.max_answering = max(1, int(settings["max_answering"]))
        if settings.get("max_people") is not None:
            self.max_people = int(settings["max_people"])
        if settings.get("max_described") is not None:
            self.max_described = max(0, int(settings["max_described"]))
        if settings.get("newcomers_remember") is not None:
            choice = int(settings["newcomers_remember"])
            self.newcomers_remember = choice if choice in NEWCOMERS_REMEMBER_CHOICES else NEWCOMERS_REMEMBER_SINCE_SHOUT

    def update_nearby(self, people: list[EventPerson]):
        """The people the game sees near the player now, nearest first. Replaces the list from the last request"""
        present = {p.refid for p in people}
        self.failed_refids &= present
        self.nearby = [p for p in people if p.refid not in self.failed_refids]

    def apply_add_failed(self, refid: int, reason: str = "") -> bool:
        was_answering = self.answering_pick
        person = next((p for p in self.pending_adds() if p.refid == refid), None) if refid else None
        if not super().apply_add_failed(refid, reason):
            return False
        self.failed_refids.add(refid)
        if person:
            self.still_to_answer.pop(person.ref_id, None) # They can no longer answer
        if not self.pending_add: # Nobody else waits to be added
            self.answering_pick = False
            # Unless someone else the line was aimed at has joined, or someone in the conversation answers first
            self.answer_again = was_answering and not self.forced_speaker_ref_id and not self.answer_first_ref_id
        return True

    def on_npc_joined(self, ref_id: str) -> bool:
        if not super().on_npc_joined(ref_id):
            return False
        if not self.pending_add:
            self.answering_pick = False
        self.answer_again = False # Someone the line was aimed at has joined, so they answer
        return True

    def clear_pick(self):
        """Forgets the pending picks, a pending retry and who still has to answer, e.g. when the player speaks again and the turn is thrown away"""
        self.pending_add = None
        self.pending_others = []
        self.answering_pick = False
        self.answer_again = False
        self.answer_first_ref_id = ""
        self.still_to_answer.clear()

    def is_past_limit_allowed(self, after_event: bool) -> bool:
        """The reaction to a Nearby or Random Event: the people it is about join even past Most People in Conversation"""
        return after_event and self.event_ignores_max_people

    def free_places(self, npc_count: int, has_player: bool = True, after_event: bool = False) -> int:
        """How many more people Most People in Conversation lets in. The player counts while in the conversation.
        Everyone nearby while reacting to a Nearby or Random Event"""
        if self.is_past_limit_allowed(after_event):
            return len(self.nearby)
        return max(0, self.max_people - npc_count - (1 if has_player else 0))

    def add_still_to_answer(self, people: list[tuple[str, str]], speaker: str, is_protected: bool):
        """A line was aimed at these people. Each of them answers before the player gets the turn

        Args:
            people (list[tuple[str, str]]): the (ref id, name) of each
            speaker (str): who said the line. Empty for an event
            is_protected (bool): the player said it, or it is an event: they answer even once the NPCs have reached their limit of replies in a row
        """
        names = [name for _ref_id, name in people]
        for ref_id, name in people:
            known = self.still_to_answer.get(ref_id)
            others = [n for n in names if n != name]
            self.still_to_answer[ref_id] = AnswerDue(name, speaker, is_protected or bool(known and known.is_protected), others)

    def take_still_to_answer(self, ref_id: str) -> AnswerDue | None:
        """They speak now, so they no longer have to answer. None if they did not have to"""
        return self.still_to_answer.pop(ref_id, None)

    def drop_unprotected_answers(self) -> list[str]:
        """The NPCs have reached their limit of replies in a row: only the people the player spoke to, or who are part of an event, still answer

        Returns:
            list[str]: the names of the people who no longer have to answer
        """
        dropped = [ref_id for ref_id, due in self.still_to_answer.items() if not due.is_protected]
        return [self.still_to_answer.pop(ref_id).name for ref_id in dropped]

    def nearby_choices(self, config: ConfigLoader, participant_names: list[str], npc_count: int, has_player: bool = True,
                       after_event: bool = False) -> list[EventPerson]:
        """The nearby people the Game Master may draw in right now. Nobody unless every limit allows it.
        Reacting to a Nearby or Random Event, Most People in Conversation does not apply: the event is about them"""
        people = self.nearby_people(config, participant_names)
        if not people or self.pending_add:
            return []
        if self.free_places(npc_count, has_player, after_event) == 0:
            return []
        return people

    def nearby_text(self, config: ConfigLoader, participant_names: list[str], extra: list[EventPerson] | None = None) -> str:
        """The {nearby} prompt variable. In the Game Master's prompt, only the people it may pick this time,
        so it is not told about someone the limits keep out"""
        offer = self.game_master_offer
        if offer is not None:
            return ", ".join(p.name for p in offer) or NOBODY_NEARBY
        return super().nearby_text(config, participant_names, extra)

    def nearby_criteria(self, config: ConfigLoader) -> tuple[str, str]:
        return SHOUT_NEARBY_CRITERIA, config.shout_decision_nearby_criteria

    def characters_for_game_master(self, config: ConfigLoader, participant_names: list[str]) -> list["Character"]:
        """The characters whose bios and memories go into the Game Master's prompt ({nearby_bios}): of the people it may pick this time
        (everyone nearby when no decision is being made, e.g. the prompt kept in the conversation to measure its size), the nearest
        Most People Described. It knows the others by name only"""
        people = self.game_master_offer if self.game_master_offer is not None else self.nearby_people(config, participant_names)
        described = {p.refid for p in self.nearby[:self.max_described]} # The game lists the nearest first
        characters = [self.characters[p.refid] for p in people if p.refid in described and p.refid in self.characters]
        if self.game_master_offer and characters:
            self.__log_described(characters, len(people))
        return characters

    def __log_described(self, characters: list["Character"], offered: int):
        """Logs whose bios and memories the Game Master uses to decide, when that changes. Most of them may have been sent earlier"""
        names = [c.name for c in characters]
        if sorted(names) == self.logged_described:
            return
        self.logged_described = sorted(names)
        others = offered - len(names)
        nearest = "the nearest person" if len(names) == 1 else f"the {len(names)} nearest people"
        by_name = ""
        if others == 1:
            by_name = " The 1 other person nearby is known by name only."
        elif others > 1:
            by_name = f" The {others} other people nearby are known by name only."
        logging.log(26, f"{self.LOG_PREFIX}: the Game Master is using the bios and memories of {nearest}: {', '.join(names)}.{by_name}")
