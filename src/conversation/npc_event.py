import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Callable
from src.config.config_loader import ConfigLoader
from src.config.definitions.prompt_definitions import PromptDefinitions
from src.conversation.bystanders import EventPerson
from src.llm.ai_client import AIClient
from src.llm.message_thread import message_thread
from src.llm.messages import UserMessage
from src.prompt_profile_manager import PromptSectionError
from src.utils import get_time_group

GENERATOR_PROMPT = "skyrim_npc_event_generator_prompt"
WIND_DOWN_PROMPT = "skyrim_npc_event_wind_down_prompt"
NEARBY_CRITERIA = "skyrim_shout_decision_nearby_criteria" # The Decision Nearby Criteria, shared with Shout
MIN_PARTICIPANTS = 2


@dataclass(kw_only=True)
class NpcEvent:
    """A scene the event generator invented, acted out by its participants while the player is a bystander.
    Once the player joins, by stepping in or by being pulled in, it becomes a normal Shout conversation.
    The scene runs in Shout from the start, so the people nearby who can join are Shout's (see ShoutState).
    This keeps the scene's own state, and the bystander player, whom the Game Master may draw in once they can be noticed"""
    id: int
    text: str
    player: EventPerson | None
    pending_add: EventPerson | None = None # The bystander player, picked by the Game Master. Can only speak once the game has added them
    player_noticeable: bool = False # The player is close enough, in sight and not sneaking
    player_joined: bool = False
    npc_lines: int = 0 # NPC lines written while the player was a bystander
    has_failed: bool = False # An NPC turn produced nothing, so the scene ends instead of trying again forever

    def noticed_player(self, config: ConfigLoader, participant_names: list[str]) -> EventPerson | None:
        """The bystander player, while the people in the scene can notice them and nobody waits to be added.
        Left out if someone in the scene has the same name, as the LLMs could not tell the two apart"""
        if not self.player or self.pending_add or not self.can_notice_player(config):
            return None
        if self.player.name.lower() in {name.lower() for name in participant_names}:
            return None
        return self.player

    def nearby_criteria(self, config: ConfigLoader, is_said_to_room: bool = False) -> tuple[str, str, set[str]]:
        """The decision model's criteria for choosing someone nearby while the player watches: (prompt type, text, the conditions that are true)"""
        return NEARBY_CRITERIA, config.shout_decision_nearby_criteria, {"npc_event"}

    def can_notice_player(self, config: ConfigLoader) -> bool:
        """The scene has gone on long enough for the participants to notice the bystander player, and the player can be noticed now.
        Never with Director Mode on: the player is not part of the scene, also while watching it"""
        from src.conversation.conversation_type import multi_npc # Here, as conversation_type imports context, which knows NPC Events
        if multi_npc.is_director_enabled(config):
            return False
        return not self.player_joined and self.player_noticeable and self.npc_lines >= config.npc_event_player_notice_delay

    def has_reached_limit(self, config: ConfigLoader) -> bool:
        return not self.player_joined and self.npc_lines >= config.npc_event_max_lines_without_player

    def is_winding_down(self, config: ConfigLoader) -> bool:
        """The next line is one of the last lines before the limit"""
        wind_down_lines = config.npc_event_wind_down_lines
        return not self.player_joined and wind_down_lines > 0 and self.npc_lines >= config.npc_event_max_lines_without_player - wind_down_lines

    def apply_game_update(self, player_noticeable: bool | None):
        """What the game reports with each continue request of the event"""
        if player_noticeable is not None:
            self.player_noticeable = bool(player_noticeable)

    def on_player_joined(self):
        """The player joined: picked by the Game Master, or they stepped in"""
        self.player_joined = True
        self.pending_add = None # The player gets the turn first


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


EVENT_REPLY_FORMAT = ('Reply only with JSON in this format: {"participants": ["<name>", "<name>"], "event": "<the event>"}\n'
                      'For no event, reply: {"participants": []}')

# Conversation, Nearby and Random Events share one prompt, the Talk/Nearby/Random Event Generator Prompt. Its conditional blocks tell the kinds apart
EVENT_GENERATOR_PROMPT = "skyrim_conversation_event_generator_prompt"
CONVERSATION_EVENT_KINDS: dict[str, tuple[str, str]] = { # kind, as the game sends it: (condition, name in the log)
    "conversation": ("talk_event", "Conversation Event"),
    "nearby": ("nearby_event", "Nearby Event"),
    "random": ("random_event", "Random Event"),
}


def generate_event(config: ConfigLoader, client: AIClient | None, candidates: list[EventPerson], player_name: str, location: str,
                   hour: int, weather: str, bios_and_summaries: str, is_cancelled: Callable[[], bool] = lambda: False,
                   hint: str = "") -> tuple[list[EventPerson], str] | None:
    """Asks the event generator to invent a scene between some of the candidates

    Args:
        candidates (list[EventPerson]): the nearby NPCs, with unique labels as names
        bios_and_summaries (str): the bios and memories of the nearest candidates (Most People Described), as in the Skyrim Multi-NPC Prompt
        is_cancelled (Callable[[], bool]): True once the event is no longer needed (a conversation started)
        hint (str): what the player would like to happen, as they typed it. Empty for a surprise

    Returns:
        tuple[list[EventPerson], str] | None: the participants and the event text. None for no event, or if anything goes wrong
    """
    if not client or len(candidates) < MIN_PARTICIPANTS:
        return None
    values = event_prompt_values(config, player_name, [c.name for c in candidates], location, hour, weather, hint)
    reply = request_event(config, client, GENERATOR_PROMPT, config.npc_event_generator_prompt, values, bios_and_summaries, [], "NPC Event", is_cancelled)
    return parse_event(reply, candidates, config.npc_event_max_participants) if reply is not None else None


def generate_conversation_event(config: ConfigLoader, client: AIClient | None, kind: str, names: list[str], player_name: str, player_description: str,
                                location: str, hour: int, weather: str, bios_and_summaries: str, hint: str, history_lines: list[str],
                                is_cancelled: Callable[[], bool] = lambda: False, hides_player: bool = False) -> str | None:
    """Conversation, Nearby and Random Events: asks the event generator what happens now. It has only that one job: who reacts is up to
    the Game Master, so the participants in the reply are ignored and there is no minimum number of people

    Args:
        kind (str): "conversation", "nearby" or "random"
        names (list[str]): who the event can be about, with unique labels. The player too with Include Me on
        bios_and_summaries (str): the bios and memories of the people described (see the Events page)
        hint (str): what the player would like to happen, as they typed it. Empty for a surprise
        history_lines (list[str]): the recent lines of the conversation (Send the Conversation So Far), added after the prompt. Empty to send none
        is_cancelled (Callable[[], bool]): True once the event is no longer needed (the player ended the conversation)
        hides_player (bool): Director Mode: the player is not part of the scene. The prompt's {if director} parts are used

    Returns:
        str | None: the event. None for no event, or if anything goes wrong
    """
    if not client or kind not in CONVERSATION_EVENT_KINDS:
        return None
    condition, log_name = CONVERSATION_EVENT_KINDS[kind]
    values = event_prompt_values(config, player_name, names, location, hour, weather, hint)
    values["player_description"] = player_description
    reply = request_event(config, client, EVENT_GENERATOR_PROMPT, config.conversation_event_generator_prompt, values, bios_and_summaries, history_lines,
                          log_name, is_cancelled, conditions={condition, "director"} if hides_player else {condition})
    if reply is None:
        return None
    data = read_event_json(reply, log_name)
    event_text = str(data.get("event", "")).strip() if data else ""
    logging.log(26, f"{log_name}: {event_text}" if event_text else f"{log_name}: no event this time")
    return event_text or None


def event_prompt_values(config: ConfigLoader, player_name: str, names: list[str], location: str, hour: int, weather: str, hint: str) -> dict[str, str]:
    """The variables every event generator prompt has, except {bios_and_summaries}"""
    return {
        "player_name": player_name or "the player",
        "names": ", ".join(names),
        "location": location or "Skyrim",
        "time": str(hour - 12 if hour > 12 else hour),
        "time_group": get_time_group(hour),
        "weather": weather,
        "max_participants": str(config.npc_event_max_participants),
        "hint": hint,
    }


def request_event(config: ConfigLoader, client: AIClient, prompt_type: str, prompt_text: str, values: dict[str, str], bios_and_summaries: str,
                  history_lines: list[str], log_name: str, is_cancelled: Callable[[], bool], conditions: set[str] | None = None) -> str | None:
    """Fills the event generator prompt and asks for the event as JSON (EVENT_REPLY_FORMAT), after the conversation lines if there are any.
    The oldest lines are dropped until the request fits the model. None if cancelled, or if anything goes wrong

    Args:
        conditions (set[str] | None): for the Talk/Nearby/Random Event Generator Prompt, the kind of event ({if talk_event}, ...)
    """
    from src.conversation.game_master import drop_oldest_lines, fill_prompt_variables, TOKEN_MARGIN
    try:
        prompt = config.prompt_profile_manager.resolve_prompt(prompt_type, prompt_text)
        prompt = PromptDefinitions.apply_prompt_conditions(prompt_type, prompt, conditions)
        # The bios are filled last, so text in them that looks like a variable is left alone
        prompt = fill_prompt_variables(fill_prompt_variables(prompt, values), {"bios_and_summaries": bios_and_summaries}).strip()
        request_text = EVENT_REPLY_FORMAT
        if history_lines:
            header = "The conversation so far:\n"
            token_limit = getattr(client, "token_limit", None)
            count_tokens = getattr(client, "get_count_tokens", None)
            if isinstance(token_limit, int) and callable(count_tokens):
                budget = int(token_limit * TOKEN_MARGIN) - count_tokens(prompt) - count_tokens(header + "\n" + EVENT_REPLY_FORMAT)
                history_lines = drop_oldest_lines(history_lines, budget, lambda line: count_tokens(line) + 1) or []
            if history_lines:
                request_text = header + "".join(line + "\n" for line in history_lines) + "\n" + EVENT_REPLY_FORMAT
        request = message_thread(config, prompt)
        request.add_message(UserMessage(config, request_text, "", True))
        if is_cancelled():
            return None
        logging.log(15, f"{log_name} generator prompt:\n{prompt}\n\n{request_text}")
        started_at = time.time()
        try:
            reply = client.request_call(request)
        finally:
            logging.log(26, f"{log_name} generator request took {time.time() - started_at:.2f} seconds")
        if is_cancelled():
            return None
        return reply or ""
    except Exception as e:
        logging.error(f"{log_name} generation failed: {e}")
        return None


def read_event_json(text: str | None, log_name: str) -> dict | None:
    """The JSON object in the generator's reply. None if there is none"""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        logging.warning(f"{log_name} generator gave no valid JSON: {text}")
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        logging.warning(f"{log_name} generator gave no valid JSON: {text}")
        return None
    return data if isinstance(data, dict) else None


def parse_event(text: str | None, candidates: list[EventPerson], max_participants: int) -> tuple[list[EventPerson], str] | None:
    """Reads the generator's JSON reply, e.g. {"participants": ["Hulda", "Mikael"], "event": "..."}.
    Unknown names are dropped and the list is cut to max_participants. None for no event, or if the reply is not valid"""
    data = read_event_json(text, "NPC Event")
    if data is None:
        return None
    if not isinstance(data.get("participants"), list):
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
