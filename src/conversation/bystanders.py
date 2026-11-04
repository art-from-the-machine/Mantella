import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar
from src.config.config_loader import ConfigLoader

if TYPE_CHECKING:
    from src.character_manager import Character

NOBODY_NEARBY = "nobody"
SHOUT_NEARBY_CRITERIA = "skyrim_shout_decision_nearby_criteria"


@dataclass
class EventPerson:
    """Someone near the conversation who is not part of it yet: a nearby NPC, or the bystander player of an NPC Event"""
    name: str # The label shown to the LLMs. People with the same name get 'Name (2)', 'Name (3)', ...
    refid: int # As sent by the game, so it can be sent back unchanged
    ref_id: str # Character.ref_id, to recognise them when they join the conversation


@dataclass(kw_only=True)
class Bystanders:
    """The people near a conversation who are not part of it, any of whom the Game Master may draw in.
    Shared by NPC Events and Shout. The Game Master picks one, the game adds them, and they speak next"""
    LOG_PREFIX: ClassVar[str] = "Nearby"
    nearby: list[EventPerson] = field(default_factory=list)
    pending_add: EventPerson | None = None # Picked by the Game Master. Can only speak once the game has added them
    forced_speaker_ref_id: str = "" # Has just joined, so speaks next without asking the Game Master
    logged_nearby: list[str] | None = None # None until first logged, so "nobody" is logged too

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

    def nearby_choices(self, config: ConfigLoader, participant_names: list[str], npc_count: int) -> list[EventPerson]:
        """The nearby people the Game Master may draw in right now"""
        return self.nearby_people(config, participant_names)

    def nearby_text(self, config: ConfigLoader, participant_names: list[str]) -> str:
        """The {nearby} prompt variable"""
        names = [p.name for p in self.nearby_people(config, participant_names)]
        if sorted(names) != self.logged_nearby: # Logged when someone comes or goes, not each time people move and the order changes
            self.logged_nearby = sorted(names)
            logging.log(26, f"{self.LOG_PREFIX}: nearby now: {', '.join(names) or NOBODY_NEARBY}")
        return ", ".join(names) or NOBODY_NEARBY

    def nearby_criteria(self, config: ConfigLoader) -> tuple[str, str]:
        """The decision model's criteria for choosing someone nearby: (prompt type, text)"""
        raise NotImplementedError

    def apply_add_failed(self, refid: int) -> bool:
        """The game could not add the person picked

        Returns:
            bool: True if it was the pending pick
        """
        if not refid or not self.pending_add or self.pending_add.refid != refid:
            return False
        logging.log(26, f"{self.LOG_PREFIX}: {self.pending_add.name} could not be added to the conversation")
        self.nearby = [p for p in self.nearby if p.refid != refid]
        self.pending_add = None
        return True

    def on_npc_joined(self, ref_id: str) -> bool:
        """An NPC joined the conversation: the person the Game Master picked, or anyone the player added

        Returns:
            bool: True if it was the pending pick, who then speaks next
        """
        self.nearby = [p for p in self.nearby if p.ref_id != ref_id]
        if self.pending_add and self.pending_add.ref_id == ref_id:
            self.pending_add = None
            self.forced_speaker_ref_id = ref_id
            return True
        return False


@dataclass(kw_only=True)
class ShoutState(Bystanders):
    """Shout: anyone near the player can answer them or join in. The game sends who is nearby with each request,
    and the limits below decide when the Game Master may draw one of them in"""
    LOG_PREFIX: ClassVar[str] = "Shout"
    lines_between_joins: int = 3 # Lines spoken after someone joined before the next person can join
    max_people: int = 6 # Nobody new joins once the conversation has this many people, the player included
    start_marker: int | None = None # The token marking the last message before Shout was turned on. Newcomers hear everything after it. None if nothing was said
    lines_since_join: int = 0
    has_joined: bool = False # Someone joined by shouting, so Lines Between Joins applies
    answering_pick: bool = False # The pending pick answers the player's line
    answer_again: bool = False # The person picked to answer the player could not be added: the turn starts again without anyone nearby
    failed_refids: set[int] = field(default_factory=set) # Could not be added. Left out until they drop off the game's nearby list
    game_master_offer: list[EventPerson] | None = field(default=None, repr=False) # While the Game Master's prompt is built: who it may pick this time
    characters: dict[int, "Character"] = field(default_factory=dict, repr=False) # The nearby people the game sent in full, by refid. Kept while Shout is on
    max_described: int = 6 # Most People Described: how many of the nearest people the Game Master gets the bios and memories of

    def apply_settings(self, settings: dict[str, Any] | None):
        """The Shout Mode settings from the MCM, sent with each request. Keys: lines_between_joins, max_people, max_described"""
        if not settings:
            return
        if settings.get("lines_between_joins") is not None:
            self.lines_between_joins = int(settings["lines_between_joins"])
        if settings.get("max_people") is not None:
            self.max_people = int(settings["max_people"])
        if settings.get("max_described") is not None:
            self.max_described = max(0, int(settings["max_described"]))

    def update_nearby(self, people: list[EventPerson]):
        """The people the game sees near the player now, nearest first. Replaces the list from the last request"""
        present = {p.refid for p in people}
        self.failed_refids &= present
        self.nearby = [p for p in people if p.refid not in self.failed_refids]

    def apply_add_failed(self, refid: int) -> bool:
        was_answering = self.answering_pick
        if not super().apply_add_failed(refid):
            return False
        self.failed_refids.add(refid)
        self.answering_pick = False
        self.answer_again = was_answering
        return True

    def on_npc_joined(self, ref_id: str) -> bool:
        if not super().on_npc_joined(ref_id):
            return False
        self.has_joined = True
        self.lines_since_join = 0
        self.answering_pick = False
        return True

    def count_line(self):
        self.lines_since_join += 1

    def clear_pick(self):
        """Forgets the pending pick and a pending retry, e.g. when the player speaks again and the turn is thrown away"""
        self.pending_add = None
        self.answering_pick = False
        self.answer_again = False

    def nearby_choices(self, config: ConfigLoader, participant_names: list[str], npc_count: int) -> list[EventPerson]:
        """The nearby people the Game Master may draw in right now. Nobody unless every limit allows it"""
        people = self.nearby_people(config, participant_names)
        if not people or self.pending_add:
            return []
        if npc_count + 1 >= self.max_people: # The player counts
            return []
        if self.has_joined and self.lines_since_join < self.lines_between_joins:
            return []
        return people

    def nearby_text(self, config: ConfigLoader, participant_names: list[str]) -> str:
        """The {nearby} prompt variable. In the Game Master's prompt, only the people it may pick this time,
        so it is not told about someone the limits keep out"""
        offer = self.game_master_offer
        if offer is not None:
            return ", ".join(p.name for p in offer) or NOBODY_NEARBY
        return super().nearby_text(config, participant_names)

    def nearby_criteria(self, config: ConfigLoader) -> tuple[str, str]:
        return SHOUT_NEARBY_CRITERIA, config.shout_decision_nearby_criteria

    def characters_for_game_master(self, config: ConfigLoader, participant_names: list[str]) -> list["Character"]:
        """The characters whose bios and memories go into the Game Master's prompt ({nearby_bios}): of the people it may pick this time
        (everyone nearby when no decision is being made, e.g. the prompt kept in the conversation to measure its size), the nearest
        Most People Described. It knows the others by name only"""
        people = self.game_master_offer if self.game_master_offer is not None else self.nearby_people(config, participant_names)
        described = {p.refid for p in self.nearby[:self.max_described]} # The game lists the nearest first
        return [self.characters[p.refid] for p in people if p.refid in described and p.refid in self.characters]
