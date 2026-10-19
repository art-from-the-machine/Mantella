import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable
from src.config.config_loader import ConfigLoader
from src.llm.ai_client import AIClient
from src.llm.message_thread import message_thread
from src.llm.messages import UserMessage
from src.prompt_profile_manager import PromptSectionError
from src.utils import get_time_group

GENERATOR_PROMPT = "skyrim_npc_event_generator_prompt"
WIND_DOWN_PROMPT = "skyrim_npc_event_wind_down_prompt"
NEARBY_CRITERIA = "skyrim_npc_event_decision_nearby_criteria"
MIN_PARTICIPANTS = 2
NOBODY_NEARBY = "nobody"


@dataclass
class EventPerson:
    """Someone near the scene: a nearby NPC who is not part of it yet, or the player"""
    name: str # The label shown to the LLMs. People with the same name get 'Name (2)', 'Name (3)', ...
    refid: int # As sent by the game, so it can be sent back unchanged
    ref_id: str # Character.ref_id, to recognise them when they join the conversation


@dataclass
class NpcEvent:
    """A scene the event generator invented, acted out by its participants while the player is a bystander.
    Once the player joins, by stepping in or by being pulled in, it becomes a normal conversation"""
    id: int
    text: str
    player: EventPerson | None
    nearby: list[EventPerson] # The candidates from the check who are not part of the scene
    present_refids: set[int] | None = None # The nearby people the game still sees near the scene. None until the game first reports them
    player_noticeable: bool = False # The player is close enough, in sight and not sneaking
    player_joined: bool = False
    npc_lines: int = 0 # NPC lines written while the player was a bystander
    pending_add: EventPerson | None = None # Picked by the Game Master. Can only speak once the game has added them
    forced_speaker_ref_id: str = "" # Has just joined, so speaks next without asking the Game Master
    has_failed: bool = False # An NPC turn produced nothing, so the scene ends instead of trying again forever
    logged_nearby: list[str] = field(default_factory=list)

    def nearby_people(self, config: ConfigLoader, participant_names: list[str]) -> list[EventPerson]:
        """The nearby NPCs who are still near the scene, and the player once they can be noticed.
        Someone with the same name as a participant is left out, as the LLMs could not tell the two apart
        (e.g. the scene's 'Whiterun Guard' was labelled 'Whiterun Guard (2)' in the check, so the other guard nearby is 'Whiterun Guard' too)

        Args:
            participant_names (list[str]): the names of everyone in the conversation, as in game
        """
        taken_names = {name.lower() for name in participant_names}
        people = [p for p in self.nearby if self.present_refids is None or p.refid in self.present_refids]
        if self.can_notice_player(config) and self.player:
            people.append(self.player)
        return [p for p in people if p.name.lower() not in taken_names]

    def nearby_choices(self, config: ConfigLoader, participant_names: list[str], npc_count: int) -> list[EventPerson]:
        """The nearby people the Game Master may draw into the scene. Nearby NPCs only while the scene is below Max Scene Size"""
        is_full = npc_count >= config.npc_event_max_scene_size
        return [p for p in self.nearby_people(config, participant_names) if not is_full or p is self.player]

    def nearby_text(self, config: ConfigLoader, participant_names: list[str]) -> str:
        """The {nearby} prompt variable"""
        names = [p.name for p in self.nearby_people(config, participant_names)]
        if names != self.logged_nearby:
            self.logged_nearby = names
            logging.log(26, f"NPC Event: nearby now: {', '.join(names) or NOBODY_NEARBY}")
        return ", ".join(names) or NOBODY_NEARBY

    def can_notice_player(self, config: ConfigLoader) -> bool:
        """The scene has gone on long enough for the participants to notice the bystander player, and the player can be noticed now"""
        return not self.player_joined and self.player_noticeable and self.npc_lines >= config.npc_event_player_notice_delay

    def has_reached_limit(self, config: ConfigLoader) -> bool:
        return not self.player_joined and self.npc_lines >= config.npc_event_max_lines_without_player

    def is_winding_down(self, config: ConfigLoader) -> bool:
        """The next line is one of the last lines before the limit"""
        wind_down_lines = config.npc_event_wind_down_lines
        return not self.player_joined and wind_down_lines > 0 and self.npc_lines >= config.npc_event_max_lines_without_player - wind_down_lines

    def apply_game_update(self, present_refids: list[int] | None, player_noticeable: bool | None, add_failed_refid: int):
        """What the game reports with each continue request of the event"""
        if present_refids is not None:
            self.present_refids = {int(refid) for refid in present_refids}
        if player_noticeable is not None:
            self.player_noticeable = bool(player_noticeable)
        if add_failed_refid and self.pending_add and self.pending_add.refid == add_failed_refid:
            logging.log(26, f"NPC Event: {self.pending_add.name} could not be added to the scene")
            self.nearby = [p for p in self.nearby if p.refid != add_failed_refid]
            self.pending_add = None

    def on_joined(self, ref_id: str, is_player: bool):
        """Someone joined the conversation: the person the Game Master picked, or anyone the player added"""
        if is_player:
            self.player_joined = True
            self.pending_add = None # The player gets the turn first
        else:
            self.nearby = [p for p in self.nearby if p.ref_id != ref_id]
        if self.pending_add and self.pending_add.ref_id == ref_id:
            self.pending_add = None
            if not is_player:
                self.forced_speaker_ref_id = ref_id


def wind_down_text(event: NpcEvent | None, config: ConfigLoader, names: str) -> str:
    """The Event Wind-Down Prompt during the last lines before the limit, otherwise empty"""
    if not event or not event.is_winding_down(config):
        return ""
    try:
        text = config.prompt_profile_manager.resolve_prompt(WIND_DOWN_PROMPT, config.npc_event_wind_down_prompt)
    except PromptSectionError as e:
        logging.error(str(e))
        logging.error("NPC Event wind-down was skipped. Fix the active Skyrim NPC Event Wind-Down Prompt profile.")
        return ""
    return text.replace("{names}", names).strip()


def generate_event(config: ConfigLoader, client: AIClient | None, candidates: list[EventPerson], player_name: str, location: str,
                   hour: int, weather: str, bios_and_summaries: str, is_cancelled: Callable[[], bool] = lambda: False) -> tuple[list[EventPerson], str] | None:
    """Asks the event generator to invent a scene between some of the candidates

    Args:
        candidates (list[EventPerson]): the nearby NPCs, with unique labels as names
        bios_and_summaries (str): the candidates' bios and memories, as in the Skyrim Multi-NPC Prompt
        is_cancelled (Callable[[], bool]): True once the event is no longer needed (a conversation started)

    Returns:
        tuple[list[EventPerson], str] | None: the participants and the event text. None for no event, or if anything goes wrong
    """
    from src.conversation.game_master import fill_prompt_variables
    if not client or len(candidates) < MIN_PARTICIPANTS:
        return None
    player_name = player_name or "the player"
    try:
        prompt = config.prompt_profile_manager.resolve_prompt(GENERATOR_PROMPT, config.npc_event_generator_prompt)
        # The bios are filled last, so text in them that looks like a variable is left alone
        prompt = fill_prompt_variables(prompt, {
            "player_name": player_name,
            "names": ", ".join(c.name for c in candidates),
            "location": location or "Skyrim",
            "time": str(hour - 12 if hour > 12 else hour),
            "time_group": get_time_group(hour),
            "weather": weather,
            "max_participants": str(config.npc_event_max_participants),
            "bios_and_summaries": bios_and_summaries,
        }).strip()
        request_text = ('Reply only with JSON in this format: {"participants": ["<name>", "<name>"], "event": "<the event>"}\n'
                        'For no event, reply: {"participants": []}')
        request = message_thread(config, prompt)
        request.add_message(UserMessage(config, request_text, "", True))
        if is_cancelled():
            return None
        logging.log(15, f"NPC Event generator prompt:\n{prompt}")
        started_at = time.time()
        try:
            reply = client.request_call(request)
        finally:
            logging.log(26, f"NPC Event generator request took {time.time() - started_at:.2f} seconds")
        if is_cancelled():
            return None
        return parse_event(reply, candidates, config.npc_event_max_participants)
    except Exception as e:
        logging.error(f"NPC Event generation failed: {e}")
        return None


def parse_event(text: str | None, candidates: list[EventPerson], max_participants: int) -> tuple[list[EventPerson], str] | None:
    """Reads the generator's JSON reply, e.g. {"participants": ["Hulda", "Mikael"], "event": "..."}.
    Unknown names are dropped and the list is cut to max_participants. None for no event, or if the reply is not valid"""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        logging.warning(f"NPC Event generator gave no valid JSON: {text}")
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        logging.warning(f"NPC Event generator gave no valid JSON: {text}")
        return None
    if not isinstance(data, dict) or not isinstance(data.get("participants"), list):
        logging.warning(f"NPC Event generator gave no valid participants: {text}")
        return None
    by_label = {c.name.lower(): c for c in candidates}
    participants: list[EventPerson] = []
    for name in data["participants"]:
        person = by_label.get(str(name).strip().lower())
        if not person:
            logging.log(26, f"NPC Event: '{name}' is not one of the candidates and was dropped")
        elif person not in participants:
            participants.append(person)
    participants = participants[:max_participants]
    event_text = str(data.get("event", "")).strip()
    if len(participants) < MIN_PARTICIPANTS or not event_text:
        logging.log(26, "NPC Event: no event this time")
        return None
    logging.log(26, f"NPC Event: {', '.join(p.name for p in participants)}: {event_text}")
    return participants, event_text
