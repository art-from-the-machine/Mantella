import json
import logging
import re
import threading
import time
from copy import deepcopy
from typing import Any, Callable, cast
import requests
from src.character_manager import Character
from src.config.config_loader import ConfigLoader
from src.config.definitions.prompt_definitions import PromptDefinitions
from src.conversation.context import context as Context
from src.conversation.bystanders import AnswerDue, EventPerson, ShoutState, TurnAnswers
from src.config.definitions.conversation_definitions import DIRECTOR, GROUP, MAX_NPC_TURNS_KINDS, AtReplyLimitEnum, max_npc_turns_identifier
from src.conversation.answer_rules import AnswerOrder, TurnRules, turn_rules
from src.conversation.conversation_type import multi_npc_game_master, shout
from src.conversation.npc_event import NpcEvent, wind_down_text
from src.llm.ai_client import AIClient
from src.llm.client_base import ClientBase
from src.llm.image_client import VisionCapture
from src.llm.message_thread import message_thread
from src.llm.messages import AssistantMessage, join_message, leave_message, Message, UserMessage
from src.llm.sentence import Sentence
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum
from src.llm.sentence_queue import SentenceQueue
from src.prompt_profile_manager import PromptSectionError


def read_decision(text: str | None) -> tuple[str, str] | None:
    """The choice and reason in the Game Master's JSON reply, e.g. {"next": "Lydia", "reason": "..."}. None if it is not valid"""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return str(data.get("next", "")), str(data.get("reason", "")).strip()


def parse_decision(text: str | None, npcs: list[Character], player_name: str, allow_player: bool) -> tuple[bool, Character | None, str]:
    """Reads the Game Master's JSON reply, e.g. {"next": "Lydia", "reason": "..."}

    Returns:
        tuple[bool, Character | None, str]: (is the choice valid, the chosen NPC or None for the player, the reason)
    """
    decision = read_decision(text)
    if not decision:
        return False, None, ""
    choice, reason = decision
    is_valid, speaker = match_speaker(choice, npcs, player_name, allow_player)
    return is_valid, speaker, reason


def match_nearby(choice: str, nearby: list[EventPerson]) -> EventPerson | None:
    """NPC Events: the nearby person the Game Master chose, by their exact label"""
    choice = choice.strip().lower()
    for person in nearby:
        if person.name.lower() == choice:
            return person
    return None


def match_speaker(choice: str, npcs: list[Character], player_name: str, allow_player: bool) -> tuple[bool, Character | None]:
    """Matches the Game Master's choice to an NPC or the player

    Returns:
        tuple[bool, Character | None]: (is the choice valid, the chosen NPC or None for the player)
    """
    choice = choice.strip().lower()
    if not choice:
        return False, None
    if choice == "player" or (player_name and choice == player_name.lower()):
        return allow_player, None
    for npc in npcs:
        if npc.name.lower() == choice:
            return True, npc
    for npc in npcs:
        if choice in [part.lower() for part in npc.name.split()]:
            return True, npc
    return False, None


DECISIONS_URLS = {
    "OpenRouter": "https://openrouter.ai/api/alpha/decisions",
    "NanoGPT": "https://nano-gpt.com/api/v1/decisions",
}
DECISION_QUESTION = "next_speaker"
TOKEN_MARGIN = 0.9 # The token count is only an estimate, so part of the limit is kept free


def post_decision_with_retry(url: str, headers: dict[str, str], body: dict[str, Any], timeout: int,
                             should_retry: Callable[[], bool] = lambda: True) -> requests.Response:
    """Posts to the Decisions API, and posts once more if the connection breaks or the server fails (5xx) and should_retry() allows it"""
    try:
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
        if response.status_code < 500 or not should_retry():
            return response
        logging.warning(f"Game Master decision call failed with status {response.status_code}. Retrying once...")
    except requests.ConnectionError as e:
        if not should_retry():
            raise
        logging.warning(f"Game Master decision call failed: {e}. Retrying once...")
    return requests.post(url, headers=headers, json=body, timeout=timeout)


ADDRESSED_QUESTION = "addressed_" # Followed by the person's number, as their label can be anything
ADDRESSED_INSTRUCTIONS = "Was {speaker}'s latest line addressed to {name}?"
EVENT_PART_INSTRUCTIONS = "Is {name} part of what just happened (the last line, in brackets)?"
DIRECTION_PART_INSTRUCTIONS = "Is {name} part of what just happened (the latest scene direction, the last line without a speaker)?"
ADDRESSED_CRITERIA = "skyrim_shout_decision_addressed_criteria"
NOT_ADDRESSED_CRITERIA = "skyrim_shout_decision_not_addressed_criteria"
EVENT_PART_CRITERIA = "skyrim_shout_decision_event_part_criteria"
EVENT_NOT_PART_CRITERIA = "skyrim_shout_decision_event_not_part_criteria"
GROUP_ANSWER_NOTE = "skyrim_shout_group_answer_note"
REJECTED_STATUS_CODES = (400, 404, 422) # The service does not take the request as it is
NAME_WORDS_IGNORED = ("the", "of", "and")
services_without_yes_no_questions: set[str] = set() # Decisions API urls that rejected the yes/no questions. They are left out until Mantella restarts


def read_also(text: str | None) -> list[str]:
    """The other names in the Game Master's JSON reply, e.g. {"next": "Jake", "also": ["Emily"], "reason": "..."}. Empty if there are none"""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    also = data.get("also") if isinstance(data, dict) else None
    return [str(name) for name in also] if isinstance(also, list) else []


def is_named_in(name: str, line: str) -> bool:
    """The line has the person's name or a part of it as a word, e.g. 'Carlotta' for Carlotta Valentia"""
    words = set(re.findall(r"[^\W_]+", line.lower()))
    return any(part in words for part in re.findall(r"[^\W_]+", name.lower()) if len(part) > 2 and part not in NAME_WORDS_IGNORED)


def cap_answering(flagged: list[Any], line: str, max_answering: int, free_places: int, nearby_first: bool = False) -> list[Any]:
    """Who of the people a line was aimed at answers it. People the line names always do. Of the others (a line to a group, like 'hello guys'),
    as many as People Who Must Answer a Group Line leaves room for. Of the people nearby, only as many as Most People in Conversation lets in

    Args:
        flagged (list[Any]): the people the line was aimed at: those in the conversation first, then those nearby, nearest first
        free_places (int): how many more people Most People in Conversation lets in
        nearby_first (bool): after a Nearby or Random Event, the people nearby keep their places in the group before those in the conversation,
            as the event is about them. The order of the result does not change
    """
    named = [person for person in flagged if is_named_in(person.name, line)]
    group = [person for person in flagged if not any(person is n for n in named)]
    if nearby_first:
        group = [person for person in group if isinstance(person, EventPerson)] + [person for person in group if not isinstance(person, EventPerson)]
    kept = named + group[:max(0, max_answering - len(named))]
    nearby = [person for person in kept if isinstance(person, EventPerson)][:max(0, free_places)] # Named people first
    return [person for person in flagged if any(person is k for k in kept) and (not isinstance(person, EventPerson) or any(person is n for n in nearby))]


def latest_line(history: list[Message], after_event: bool) -> tuple[str, str]:
    """Who said the latest line, and its text without thoughts. No speaker for an event (the last message), for a direction
    the player gave in Director Mode (nobody in the scene said it), or if nothing was said yet"""
    if after_event:
        return "", history_text(history[-1:], False).strip()
    for message in reversed(history):
        if not is_spoken_message(message):
            continue
        if isinstance(message, AssistantMessage):
            turns = [turn for turn in message.get_formatted_turns(include_thoughts=False) if turn.strip()]
            return message.last_speaker_name(), turns[-1].strip() if turns else ""
        if is_direction(message):
            return "", history_text([message], False).strip()
        return str(getattr(message, "player_character_name", "") or ""), history_text([message], False).strip()
    return "", ""


def is_latest_line_a_direction(history: list[Message]) -> bool:
    """The latest line is a direction the player gave in Director Mode, not something someone in the scene said"""
    for message in reversed(history):
        if is_spoken_message(message):
            return is_direction(message)
    return False


DECISION_INSTRUCTIONS = "skyrim_game_master_decision_instructions"
DECISION_NPC_CRITERIA = "skyrim_game_master_decision_npc_criteria"
DECISION_PLAYER_CRITERIA = "skyrim_game_master_decision_player_criteria"
SHOUT_NOBODY_CRITERIA = "skyrim_shout_decision_nobody_criteria"
NOBODY_ANSWERS = "Nobody" # Just saying something: the Game Master's choice when nobody nearby answers the player


def resolve_decision_prompts(config: ConfigLoader, after_event: bool = False) -> dict[str, str]:
    """The decision prompts by prompt type, with an active prompt profile's shared sections expanded and their conditional blocks applied

    Args:
        after_event (bool): the first choice after a Conversation, Nearby or Random Event: {if after_event} is true, so the question
            and the player criteria are about who reacts to the event first

    Raises:
        PromptSectionError: an active profile has a variable that is not allowed, or the conditional blocks are broken
    """
    manager = config.prompt_profile_manager
    conditions = {"after_event"} if after_event else set()
    def resolve(prompt_type: str, text: str) -> str:
        return PromptDefinitions.apply_prompt_conditions(prompt_type, manager.resolve_prompt(prompt_type, text), conditions)
    return {
        DECISION_INSTRUCTIONS: resolve(DECISION_INSTRUCTIONS, config.game_master_decision_instructions),
        DECISION_NPC_CRITERIA: resolve(DECISION_NPC_CRITERIA, config.game_master_decision_npc_criteria),
        DECISION_PLAYER_CRITERIA: resolve(DECISION_PLAYER_CRITERIA, config.game_master_decision_player_criteria),
    }


def fill_prompt_variables(prompt: str, values: dict[str, str]) -> str:
    """Fills {variables} with str.replace, so other braces in the text are left alone"""
    for name, value in values.items():
        prompt = prompt.replace("{" + name + "}", value)
    return prompt


def drop_oldest_lines(lines: list[str], budget: int, count_line_tokens: Callable[[str], int]) -> list[str] | None:
    """Drops the oldest lines until the rest fit the token budget. None if the budget is used up even without any lines"""
    line_tokens = [count_line_tokens(line) for line in lines]
    first_line = 0
    while sum(line_tokens[first_line:]) > budget:
        if first_line >= len(lines):
            return None
        first_line += 1
    return lines[first_line:]


def build_decision_request(prompts: dict[str, str], model: str, scene: str, history_lines: list[str], npc_names: list[str],
                           player_name: str, allow_player: bool, count_tokens: Callable[[str], int], token_limit: int,
                           extra_criteria: dict[str, str] | None = None, extra_questions: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Builds the Decisions API request that asks a decision model who speaks next.
    The oldest conversation lines are dropped until the request fits the model's token limit.

    Args:
        prompts (dict[str, str]): the decision prompts by prompt type (see resolve_decision_prompts)
        extra_criteria (dict[str, str] | None): more options and their criteria, e.g. the people near an NPC Event
        extra_questions (dict[str, Any] | None): more questions answered with the same request, e.g. who the latest line was spoken to

    Returns:
        dict[str, Any] | None: the request body. None if it does not fit even without any conversation lines
    """
    player_label = player_name or "Player"
    criteria = {name: fill_prompt_variables(prompts[DECISION_NPC_CRITERIA], {"name": name, "player_name": player_label}) for name in npc_names}
    if allow_player:
        criteria[player_label] = fill_prompt_variables(prompts[DECISION_PLAYER_CRITERIA], {"player_name": player_label})
    criteria.update(extra_criteria or {})
    question = {
        "type": "choice",
        "instructions": fill_prompt_variables(prompts[DECISION_INSTRUCTIONS], {"player_name": player_label, "names": ", ".join(npc_names)}),
        "criteria": criteria,
    }

    questions = {DECISION_QUESTION: question, **(extra_questions or {})}
    budget = (int(token_limit * TOKEN_MARGIN) - count_tokens(json.dumps(questions, ensure_ascii=False))
              - count_tokens(json.dumps({"scene": scene, "conversation": []}, ensure_ascii=False)))
    kept_lines = drop_oldest_lines(history_lines, budget, lambda line: count_tokens(json.dumps(line, ensure_ascii=False)) + 1)
    if kept_lines is None:
        return None
    state = {"scene": scene, "conversation": kept_lines}
    return {"model": model, "state": state, "questions": questions}


def format_decision_request(body: dict[str, Any]) -> str:
    """The Decisions API request as readable text for the log, with the prompts' line breaks kept"""
    state = body["state"]
    lines = [f"Model: {body['model']}", "", "===== Scene =====", state["scene"], "",
             f"===== Conversation ({len(state['conversation'])} lines) ====="]
    lines += state["conversation"]
    for name, question in body["questions"].items():
        lines += ["", f"===== Question: {name} ({question['type']}) =====", question["instructions"], "", "Criteria:"]
        lines += [f"  - {choice}: {criterion}" for choice, criterion in question["criteria"].items()]
    return "\n".join(lines)


def format_response_text(text: str) -> str:
    """A JSON response indented for the log. Anything else is returned unchanged"""
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except (ValueError, TypeError):
        return text


def format_confidence(answer: dict[str, Any]) -> str:
    """The decision's confidence and probabilities for the log. Values that are not numbers are shown as they are"""
    try:
        probabilities = answer.get("probabilities") or {}
        details = ", ".join(f"{name} {probability:.2f}" for name, probability in sorted(probabilities.items(), key=lambda item: -item[1]))
        return f"confidence {answer.get('confidence', 0):.2f}: {details}"
    except (TypeError, ValueError, AttributeError):
        return f"confidence {answer.get('confidence')}, probabilities {answer.get('probabilities')}"


def log_request_time(started_at: float):
    logging.log(26, f"Game Master request took {time.time() - started_at:.2f} seconds")


def should_log_prompt(logged_prompts: set[str], key: str) -> bool:
    """True the first time a key is seen. Used to log each prompt once, and again when the participants change"""
    if key in logged_prompts:
        return False
    logged_prompts.add(key)
    return True


def messages_heard_by(history: list[Message], npc: Character) -> list[Message]:
    """Keeps only the messages from while the NPC was in the conversation, the same way summaries do.
    The NPCs who start the conversation have no join message, and a long conversation's reload can drop one.
    So an NPC counts as present from the start if its first join/leave message is a leave message, or if it has none.
    """
    markers = [m for m in history if isinstance(m, (join_message, leave_message)) and m.character.name == npc.name]
    if not markers:
        return history
    result: list[Message] = []
    is_present = isinstance(markers[0], leave_message)
    for message in history:
        if isinstance(message, join_message) and message.character.name == npc.name:
            is_present = True
        if is_present:
            result.append(message)
        if isinstance(message, leave_message) and message.character.name == npc.name:
            is_present = False
    return result


def history_text(history: list[Message], include_thoughts: bool) -> str:
    """The conversation as text with each line labelled by speaker, one line per NPC turn. Turn thoughts are left out unless include_thoughts is set"""
    result = ""
    for message in history:
        was_multi_npc_message = message.is_multi_npc_message
        message.is_multi_npc_message = True
        if isinstance(message, AssistantMessage):
            result += "".join(f"{turn}\n" for turn in message.get_formatted_turns(include_thoughts=include_thoughts))
        else:
            result += f"{message.get_formatted_content()}\n"
        message.is_multi_npc_message = was_multi_npc_message
    return result


def game_master_history_lines(history: list[Message], config: ConfigLoader) -> list[str]:
    """The conversation lines the Game Master sees: only the last lines if a message limit is set, and turn thoughts only if enabled.
    Each line is one message: a player line, one NPC's reply, or a join/leave note.
    Only lines where someone says something count toward the limit (see is_spoken_message): join/leave notes, lines with only
    in-game events and Mantella's own narration do not, so people coming or going and things happening do not push out what was said.
    Those between the kept lines are kept, the ones before the oldest kept line are not"""
    lines: list[tuple[str, bool]] = [] # (line, counts toward the limit)
    for message in history:
        counts = is_spoken_message(message)
        lines.extend((line, counts) for line in history_text([message], config.game_master_include_turn_thoughts).split("\n") if line.strip())
    message_count = config.game_master_history_message_count
    if message_count <= 0:
        return [line for line, _ in lines]
    kept: list[str] = []
    spoken = 0
    for line, counts in reversed(lines):
        if spoken >= message_count:
            break
        kept.append(line)
        if counts:
            spoken += 1
    kept.reverse()
    return kept


def is_spoken_message(message: Message) -> bool:
    """Someone says or directs something: an NPC reply, a player line with text, or a direction the player typed in director mode.
    Not a join/leave note, a line with only in-game events, or narration Mantella adds itself (an NPC Event's scene,
    the NPC Initiative opener, "The scene continues.")"""
    if isinstance(message, AssistantMessage):
        return True
    if not isinstance(message, UserMessage) or not message.text.strip():
        return False
    if message.is_director_message:
        return bool(message.player_character_name) and not message.is_system_generated_message
    return True


def is_direction(message: Message) -> bool:
    """A direction the player typed in Director Mode: narration that becomes true in the scene, not a line anyone in the scene said"""
    return (isinstance(message, UserMessage) and message.is_director_message and bool(message.player_character_name)
            and not message.is_system_generated_message and bool(message.text.strip()))


def is_player_line(message: Message) -> bool:
    """Something the player said or directed. Not narration Mantella adds itself, nor a line with only in-game events"""
    return isinstance(message, UserMessage) and not message.is_system_generated_message and is_spoken_message(message)


def add_reply_to_history(history: list[Message], sentences: list[Sentence], config: ConfigLoader, is_multi_npc: bool):
    """Adds a reply's sentences to the history the same way the conversation does when they are played:
    to the last assistant message, or to a new one if the last message is not an assistant message"""
    if not sentences:
        return
    if history and isinstance(history[-1], AssistantMessage):
        message = history[-1]
    else:
        message = AssistantMessage(config)
        message.is_multi_npc_message = is_multi_npc
        message.thoughts_in_place = True
        history.append(message)
    for sentence in sentences:
        message.add_sentence(sentence)


def thread_for_lorebook(config: ConfigLoader, history: list[Message]) -> message_thread:
    """A message thread with the given history, for the lorebook"""
    thread = message_thread(config, None)
    thread.add_non_system_messages(history)
    return thread


def is_watched_scene(context_for_conversation: Context) -> bool:
    """An NPC Event the player only watches"""
    event = context_for_conversation.npc_event
    return bool(event and not event.player_joined)


def rules_for(context_for_conversation: Context, conversation_type: Any, event_kind: str = "") -> TurnRules:
    """The talk settings, Most Replies per Person and People Who Must Answer a Group Line of a turn (see answer_rules.turn_rules)"""
    shout_state = context_for_conversation.shout if isinstance(context_for_conversation.shout, ShoutState) else None
    return turn_rules(context_for_conversation.config, conversation_type, shout, is_watched_scene(context_for_conversation), event_kind,
                      shout_state.max_answering if shout_state else None)


class GameMaster:
    """Asks the Game Master LLM who speaks next in a multi-NPC Game Master Mode conversation"""
    def __init__(self, context_for_conversation: Context, conversation_type: multi_npc_game_master, client: AIClient | None, logged_prompts: set[str] | None = None,
                 rules: TurnRules | None = None, answers: TurnAnswers | None = None, unavailable: set[str] | None = None) -> None:
        """
        Args:
            rules (TurnRules | None): the rules of the turn. None for the conversation's own (no event)
            answers (TurnAnswers | None): who still has to answer. None for Shout's, or none at all without Shout
            unavailable (set[str] | None): the ref ids of the NPCs who have reached Most Replies per Person: they are not picked
        """
        self.__context = context_for_conversation
        self.__conversation_type = conversation_type
        self.__client = client
        self.__logged_prompts: set[str] = logged_prompts if logged_prompts is not None else set()
        self.__rules: TurnRules = rules or rules_for(context_for_conversation, conversation_type)
        shout_state = context_for_conversation.shout if isinstance(context_for_conversation.shout, ShoutState) else None
        self.__answers: TurnAnswers = answers or shout_state or TurnAnswers()
        self.__unavailable: set[str] = unavailable or set()
        self.picked_player: bool = False # The last choice handed the turn to the player. choose_next_speaker returns None for that and for no valid choice
        # Shout: what the last choice found out about the latest line
        self.aimed_at: list[Character | EventPerson] = [] # Everyone it was spoken to (or who is part of the event), whoever speaks first at the front. Empty if nobody, or not asked
        self.scores: dict[str, float] = {} # How likely each person speaks next, by name. Only from a decision model
        self.line_speaker: str = "" # Who said it. Empty for an event or a direction (Director Mode)
        self.is_line_protected: bool = False # The player said or directed it, or it is an event: the people it is aimed at answer even past the limit of NPC replies in a row
        self.__is_direction: bool = False # The latest line is a direction the player gave in Director Mode
        self.__is_director: bool = False # Director Mode: the player is not part of the scene, so they take no place in the conversation
        self.__lone_npc_spoke_last: Character | None = None # Director Mode with one NPC, who said the latest line: not picked again
        self.__line: tuple[int, str] = (0, "") # The latest line: how many messages there are, and its text
        self.__free_places: int = 0
        self.__usual_free_places: int = 0 # What Most People in Conversation lets in without the exception for an event
        self.__is_past_limit_allowed: bool = False # Reacting to a Nearby or Random Event: its people join past Most People in Conversation

    def choose_next_speaker(self, live_messages: message_thread, history: list[Message], allow_player: bool, allow_nearby: bool = False,
                            always_ask: bool = False, after_event: bool = False) -> Character | EventPerson | None:
        """Asks the Game Master who speaks next

        Args:
            live_messages (message_thread): the message thread used for the lorebook
            history (list[Message]): the conversation history to show the Game Master
            allow_player (bool): whether the Game Master may hand the turn to the player
            allow_nearby (bool): Shout only (NPC Events run in Shout too). The Game Master may also pick someone nearby, who has to be added in game
                before they can speak. Only when Shout's limits allow someone to join right now, or the player watching an NPC Event can be noticed
            always_ask (bool): ask even when Shout has only one NPC and nobody nearby to offer, e.g. who reacts first to an event: the NPC or the player
            after_event (bool): the first choice after a Conversation, Nearby or Random Event: the decision model is asked who reacts to it first

        Returns:
            Character | EventPerson | None: the NPC to speak next, or the person nearby who joins first. None if the player should speak (see picked_player)
                or no valid choice was made
        """
        self.picked_player = False
        self.aimed_at, self.scores, self.line_speaker, self.is_line_protected = [], {}, "", False
        self.__is_direction = False
        self.__is_past_limit_allowed = False
        self.__lone_npc_spoke_last = None
        if not self.__client:
            return None
        config = self.__context.config
        npcs = self.__context.get_characters_excluding_player().get_all_characters()
        # The NPCs who may be picked: not those who have reached Most Replies per Person
        pickable = [npc for npc in npcs if npc.ref_id not in self.__unavailable]
        player = self.__context.npcs_in_conversation.get_player_character()
        player_name = player.name if player else ""
        allow_player = allow_player and player is not None # A bystander of an NPC Event can only be drawn in as someone nearby
        is_director = self.__conversation_type.is_director_mode()
        self.__is_director = is_director
        # A direction (Director Mode) is asked about like an event: who is part of it, not who it was spoken to. The people it is about join past Most People
        self.__is_direction = not after_event and is_latest_line_a_direction(history)
        event = self.__context.npc_event
        shout_state = self.__context.shout if isinstance(self.__context.shout, ShoutState) else None
        participant_names = [npc.name for npc in npcs] + ([player_name] if player_name else [])
        nearby: list[EventPerson] = []
        if allow_nearby:
            if shout_state:
                nearby = shout_state.nearby_choices(config, participant_names, len(npcs), has_player=player is not None and not is_director,
                                                    after_event=after_event, is_direction=self.__is_direction)
            noticed_player = event.noticed_player(config, participant_names) if event else None
            if noticed_player:
                nearby = nearby + [noticed_player] # Outside Shout's limits: the scene can always draw in the player watching it
        is_said_to_room = isinstance(self.__conversation_type, shout) and shout_state is not None and not npcs
        if is_said_to_room and not nearby:
            logging.log(26, "Game Master: nobody nearby can answer")
            return None
        if (isinstance(self.__conversation_type, shout) or is_director) and not nearby and len(npcs) == 1 and not always_ask:
            # One NPC and nobody nearby offered: like a one-on-one conversation, the NPC answers and then the player speaks.
            # Director Mode: the NPC answers the direction once (the first speaker falls back to them), then the player directs again
            return None if allow_player or is_director or not pickable else npcs[0]
        if npcs and not pickable and not nearby:
            logging.log(26, f"Game Master: everyone has reached Most Replies per Person ({self.__rules.most_replies}), so nobody else speaks")
            return None
        if is_director and len(npcs) == 1 and latest_line(history, after_event)[0] == npcs[0].name:
            # Director Mode with one NPC, who just answered: someone nearby may still join, but the NPC doesn't talk on alone
            self.__lone_npc_spoke_last = npcs[0]
        should_log = should_log_prompt(self.__logged_prompts, "game master|" + self.__context.get_character_names_as_text(True))
        if should_log:
            logging.log(26, "===== Game Master prompt =====")
        if shout_state:
            shout_state.game_master_offer = nearby # {nearby} in the prompt names only who may be picked this time
        try:
            prompt = self.__conversation_type.generate_game_master_prompt(self.__context, live_messages, should_log)
        except PromptSectionError as e:
            logging.error(str(e))
            logging.error("Game Master could not decide who speaks next. Fix the active Game Master prompt profile.")
            return None
        finally:
            if shout_state:
                shout_state.game_master_offer = None
        wind_down = wind_down_text(event, config, self.__context.get_character_names_as_text(False))
        if wind_down:
            prompt += "\n\n" + wind_down
        candidates = self.__aimed_at_candidates(shout_state, history, after_event, npcs, pickable, nearby, player_name)
        if config.game_master_use_decision_model:
            return self.__choose_with_decision_model(prompt, history, allow_player, pickable, player_name, nearby, is_said_to_room, after_event, candidates)

        choices = [npc.name for npc in pickable] + [person.name for person in nearby]
        if is_said_to_room:
            choices.append(NOBODY_ANSWERS)
        elif allow_player and player_name:
            choices.append(player_name)
        history_lines = game_master_history_lines(history, config)
        header ="The conversation so far:\n"
        also_rule = self.__also_rule(candidates, after_event)
        if also_rule:
            footer = (f"\nWho speaks next? Choose one of: {', '.join(choices)}.\n"
                      f'In "also", list everyone else of {", ".join(person.name for person in candidates)} for whom this is true: {also_rule}\n'
                      'Leave "also" empty if there is nobody else.\n'
                      'Reply only with JSON in this format: {"next": "<name>", "also": ["<name>"], "reason": "<a few words>"}')
        else:
            candidates = []
            footer = (f"\nWho speaks next? Choose one of: {', '.join(choices)}.\n"
                      'Reply only with JSON in this format: {"next": "<name>", "reason": "<a few words>"}')
        # The conversation is only reloaded when it gets too long for the NPC model, so the oldest lines are dropped to fit the Game Master model
        client = cast(ClientBase, self.__client)
        budget = int(client.token_limit * TOKEN_MARGIN) - client.get_count_tokens(prompt) - client.get_count_tokens(header + footer)
        kept_lines = drop_oldest_lines(history_lines, budget, lambda line: client.get_count_tokens(line) + 1)
        if kept_lines is None:
            logging.error(f"Game Master prompt is too long for the Game Master model {client.model_name} ({client.token_limit} tokens). Shorten the Skyrim Game Master Prompt.")
            return None
        request_text = header + "".join(line + "\n" for line in kept_lines) + footer
        request = message_thread(config, prompt) # Never with the decensor bypass: its roleplay commitment can make the Game Master write dialogue
        request.add_message(UserMessage(config, request_text, "", True))

        started_at = time.time()
        try:
            reply = self.__client.request_call(request)
        except Exception as e:
            logging.error(f"Game Master LLM call failed: {e}")
            return None
        finally:
            log_request_time(started_at)
        decision = read_decision(reply)
        # The people it listed, the one who speaks next first. None if it was not asked
        also = read_also(reply)
        listed = [person for name in ([decision[0]] if decision else []) + also for person in candidates if person.name.lower() == name.strip().lower()]
        # Only the next speaker and nobody in "also": the line was aimed at nobody in particular. The next speaker can be the player, who is not listed
        flagged = None if not candidates else [person for person in candidates if any(person is l for l in listed)] if also else []
        if decision and (person := match_nearby(decision[0], nearby)):
            return self.__with_aimed_at(self.__request_join(person, decision[1]), flagged, listed)
        if is_said_to_room:
            return self.__nobody_answers(decision[0] if decision else "", decision[1] if decision else "", reply)
        is_valid, speaker, reason = parse_decision(reply, pickable, player_name, allow_player)
        if not is_valid:
            logging.warning(f"Game Master gave no valid choice: {reply}")
            return self.__with_aimed_at(None, flagged, listed)
        logging.log(26, f"Game Master: {speaker.name if speaker else player_name} speaks next ({reason})")
        self.picked_player = speaker is None
        return self.__with_aimed_at(speaker, flagged, listed)

    def __aimed_at_candidates(self, shout_state: ShoutState | None, history: list[Message], after_event: bool, npcs: list[Character], pickable: list[Character],
                              nearby: list[EventPerson], player_name: str) -> list[Character | EventPerson]:
        """The people the latest line can be aimed at: everyone in the conversation who may still speak except whoever said it, then (Shout)
        the people nearby who may join, nearest first. Empty if there is nothing to ask: nothing was said, the line was asked about already,
        only one person could be meant (except an NPC's line when who it was for makes a difference: that one person then has to answer it,
        or answers first), or who it was for makes no difference and nobody nearby could join"""
        self.line_speaker, text = latest_line(history, after_event)
        self.is_line_protected = after_event or self.__is_direction or (bool(player_name) and self.line_speaker == player_name)
        self.__line = (len(history), text)
        if shout_state:
            has_player = bool(player_name) and not self.__is_director
            self.__free_places = shout_state.free_places(len(npcs), has_player, after_event, self.__is_direction)
            self.__usual_free_places = shout_state.free_places(len(npcs), has_player)
            self.__is_past_limit_allowed = shout_state.is_past_limit_allowed(after_event, self.__is_direction)
        if not self.__rules.uses_who_a_line_is_for(self.is_line_protected) and not nearby:
            return [] # Nobody has to answer, nobody answers first, and nobody can join together
        if not text or (not after_event and not self.__is_direction and not self.line_speaker) or self.__answers.analysed_line == self.__line:
            return []
        candidates: list[Character | EventPerson] = [npc for npc in pickable if npc.name != self.line_speaker] + list(nearby)
        if len(candidates) == 1 and not self.is_line_protected and self.__rules.uses_who_a_line_is_for(False):
            # Only one person could be meant, but whether the NPC spoke to them decides if they have to answer, or answer first, e.g. with two NPCs
            return candidates
        return candidates if len(candidates) > 1 else []

    def __also_rule(self, candidates: list[Character | EventPerson], after_event: bool) -> str:
        """For a Game Master LLM: when someone else also counts as aimed at by the latest line. Empty if it is not asked"""
        if not candidates:
            return ""
        config = self.__context.config
        try:
            if after_event or self.__is_direction:
                rule = config.prompt_profile_manager.resolve_prompt(EVENT_PART_CRITERIA, config.shout_decision_event_part_criteria)
            else:
                rule = config.prompt_profile_manager.resolve_prompt(ADDRESSED_CRITERIA, config.shout_decision_addressed_criteria)
        except PromptSectionError as e:
            logging.error(str(e))
            logging.error("Game Master is not asked who else the latest line was spoken to. Fix the active prompt profile.")
            return ""
        return fill_prompt_variables(rule, {"name": "that person", "speaker": self.line_speaker}).strip()

    def __yes_no_questions(self, candidates: list[Character | EventPerson], after_event: bool) -> dict[str, Any]:
        """For a decision model: one yes/no question for each person, answered with the same request: was the latest line spoken to them,
        or after an event, are they part of what happened

        Raises:
            PromptSectionError: an active profile has a variable that is not allowed
        """
        config = self.__context.config
        manager = config.prompt_profile_manager
        if after_event or self.__is_direction:
            instructions = DIRECTION_PART_INSTRUCTIONS if self.__is_direction else EVENT_PART_INSTRUCTIONS
            yes = manager.resolve_prompt(EVENT_PART_CRITERIA, config.shout_decision_event_part_criteria)
            no = manager.resolve_prompt(EVENT_NOT_PART_CRITERIA, config.shout_decision_event_not_part_criteria)
        else:
            instructions = ADDRESSED_INSTRUCTIONS
            yes = manager.resolve_prompt(ADDRESSED_CRITERIA, config.shout_decision_addressed_criteria)
            no = manager.resolve_prompt(NOT_ADDRESSED_CRITERIA, config.shout_decision_not_addressed_criteria)
        questions: dict[str, Any] = {}
        for number, person in enumerate(candidates, 1):
            values = {"name": person.name, "speaker": self.line_speaker}
            questions[f"{ADDRESSED_QUESTION}{number}"] = {"type": "noul", "instructions": fill_prompt_variables(instructions, values),
                                                          "criteria": {"true": fill_prompt_variables(yes, values), "false": fill_prompt_variables(no, values)}}
        return questions

    def __read_yes_no_answers(self, answers: Any, candidates: list[Character | EventPerson]) -> list[Character | EventPerson] | None:
        """The people the decision model is sure enough about (Game Master Spoken To Threshold). None if any answer is missing or can't be read"""
        threshold = float(self.__context.config.game_master_addressed_threshold)
        try:
            values = [float(answers[f"{ADDRESSED_QUESTION}{number}"]["noul"]) for number in range(1, len(candidates) + 1)]
        except Exception:
            logging.warning("Game Master: who the latest line was spoken to could not be read. Only the next speaker is used.")
            return None
        details = ", ".join(f"{person.name} {value:.2f}" for value, person in sorted(zip(values, candidates), key=lambda pair: -pair[0])[:8])
        logging.log(26, f"Game Master: spoken to (yes at {threshold:.2f} or more), highest scores: {details}")
        return [person for value, person in zip(values, candidates) if value >= threshold]

    def __with_aimed_at(self, usual: Character | EventPerson | None, flagged: list[Character | EventPerson] | None,
                        listed: list[Character | EventPerson] | None = None) -> Character | EventPerson | None:
        """Shout: applies who the latest line was aimed at to the Game Master's own choice of who speaks next (see __apply_aimed_at)"""
        speaker = self.__apply_aimed_at(usual, flagged, listed)
        if speaker is not None and speaker is self.__lone_npc_spoke_last:
            logging.log(26, f"Game Master: {speaker.name} already answered the direction and is the only NPC, so the player directs again")
            return None
        self.__log_past_limit(speaker)
        return speaker

    def __log_past_limit(self, speaker: Character | EventPerson | None):
        """Logs when the people a Nearby or Random Event is about join past Most People in Conversation. Only then, not each time it is allowed"""
        if not self.__is_past_limit_allowed:
            return
        joining = [person for person in self.aimed_at if isinstance(person, EventPerson)]
        if isinstance(speaker, EventPerson) and not any(person is speaker for person in joining):
            joining.append(speaker)
        if len(joining) > self.__usual_free_places:
            shout_state = cast(ShoutState, self.__context.shout)
            logging.log(26, f"Game Master: {', '.join(person.name for person in joining)} join past Most People in Conversation "
                            f"({shout_state.max_people}), as the {'direction' if self.__is_direction else 'event'} is about them")

    def __apply_aimed_at(self, usual: Character | EventPerson | None, flagged: list[Character | EventPerson] | None,
                         listed: list[Character | EventPerson] | None = None) -> Character | EventPerson | None:
        """Shout and every group conversation: finds out who the latest line was aimed at (aimed_at), capped by People Who Must Answer a Group Line
        and, for people nearby, Most People in Conversation. The Game Master's own choice is returned unchanged: what follows from who it was
        aimed at (who has to speak, who answers first, who joins) is up to the talk settings (see GameMasterTurns)

        Args:
            usual (Character | EventPerson | None): the Game Master's own choice. None for the player, or no valid choice
            flagged (list[Character | EventPerson] | None): the people the line was aimed at. None if that was not asked, or the answer could not be read
            listed (list[Character | EventPerson] | None): a Game Master LLM's order of them. It gives no scores
        """
        if flagged is None:
            return usual
        self.__answers.analysed_line = self.__line # Asked once for each line
        rules = self.__rules
        nearby_first = self.__is_past_limit_allowed
        is_shouting = isinstance(self.__context.shout, ShoutState)
        free_places = self.__free_places if is_shouting else len(flagged) # Without Shout, nobody joins: everyone flagged is in the conversation
        aimed = cap_answering(flagged, self.__line[1], rules.max_answering, free_places, nearby_first)
        if len(aimed) < len(flagged):
            capped = cap_answering(flagged, self.__line[1], rules.max_answering, len(flagged), nearby_first) # Without the room limit
            too_many = [person.name for person in flagged if not any(person is c for c in capped)]
            no_room = [person.name for person in capped if not any(person is a for a in aimed)]
            if too_many:
                logging.log(26, f"Game Master: these people don't have to answer, as more than People Who Must Answer a Group Line ({rules.max_answering}) were spoken to: {', '.join(too_many)}")
            if no_room:
                logging.log(26, f"Game Master: not joining, as Most People in Conversation leaves no room for them: {', '.join(no_room)}")
        if not aimed:
            return usual
        if listed:
            aimed.sort(key=lambda person: next((i for i, l in enumerate(listed) if l is person), len(listed)))
        # The Game Master's own choice first, if it is one of them
        self.aimed_at = [person for person in aimed if person is usual] + [person for person in aimed if person is not usual]
        logging.log(26, f"Game Master: the latest line was spoken to {', '.join(person.name for person in self.aimed_at)}")
        return usual

    def __nearby_criteria_source(self) -> NpcEvent | ShoutState | None:
        """Whose decision model criteria are used for the people nearby: the NPC Event's while the player watches it, otherwise Shout's"""
        event = self.__context.npc_event
        if event and not event.player_joined:
            return event
        return self.__context.shout if isinstance(self.__context.shout, ShoutState) else None

    def __request_join(self, person: EventPerson, reason: str) -> EventPerson:
        """NPC Events and Shout: the person nearby joins the conversation before they speak"""
        logging.log(26, f"Game Master: {person.name} joins the conversation and speaks next ({reason})")
        return person

    def __nobody_answers(self, choice: str, reason: str, reply: str | None) -> None:
        """Just saying something: the Game Master picked nobody nearby. Anything else it answered also means nobody"""
        if choice.strip().lower() == NOBODY_ANSWERS.lower():
            logging.log(26, f"Game Master: nobody answers ({reason})")
        else:
            logging.warning(f"Game Master gave no valid choice, so nobody answers: {reply}")
        return None

    def __choose_with_decision_model(self, prompt: str, history: list[Message], allow_player: bool,
                                     npcs: list[Character], player_name: str, nearby: list[EventPerson],
                                     is_said_to_room: bool = False, after_event: bool = False,
                                     candidates: list[Character | EventPerson] | None = None) -> Character | EventPerson | None:
        """Asks a decision model (e.g. typesafe/jev-1.13) who speaks next through the OpenRouter or NanoGPT Decisions API.
        With candidates, it is also asked about each of them whether the latest line was aimed at them, with the same request"""
        config = self.__context.config
        client = cast(ClientBase, self.__client)
        url = DECISIONS_URLS.get(client.service_name)
        if not url:
            logging.error(f"Game Master decision models only work through OpenRouter or NanoGPT, not {client.service_name}.")
            return None
        history_lines = game_master_history_lines(history, config)
        candidates = candidates if candidates and url not in services_without_yes_no_questions else []
        try:
            prompts = resolve_decision_prompts(config, after_event)
            extra_questions = self.__yes_no_questions(candidates, after_event) if candidates else {}
            nearby_criteria = {}
            criteria_source = self.__nearby_criteria_source()
            if nearby and criteria_source:
                event = self.__context.npc_event
                event_player_name = player_name or (event.player.name if event and event.player else "")
                criteria_type, criteria_text, conditions = criteria_source.nearby_criteria(config, is_said_to_room)
                criteria = PromptDefinitions.apply_prompt_conditions(criteria_type, config.prompt_profile_manager.resolve_prompt(criteria_type, criteria_text), conditions)
                nearby_criteria = {p.name: fill_prompt_variables(criteria, {"name": p.name, "player_name": event_player_name}) for p in nearby}
            if is_said_to_room:
                nobody_criteria = PromptDefinitions.apply_prompt_conditions(SHOUT_NOBODY_CRITERIA,
                    config.prompt_profile_manager.resolve_prompt(SHOUT_NOBODY_CRITERIA, config.shout_decision_nobody_criteria),
                    {"director"} if self.__conversation_type.is_director_mode() else set())
                nearby_criteria[NOBODY_ANSWERS] = fill_prompt_variables(nobody_criteria, {"player_name": player_name or "Player"})
        except PromptSectionError as e:
            logging.error(str(e))
            logging.error("Game Master could not decide who speaks next. Fix the active Game Master Decision prompt profile.")
            return None
        body = build_decision_request(prompts, client.model_name, prompt, history_lines, [npc.name for npc in npcs],
                                      player_name, allow_player, client.get_count_tokens, client.token_limit, nearby_criteria, extra_questions)
        if not body:
            logging.error(f"Game Master prompt is too long for the decision model {client.model_name} ({client.token_limit} tokens). Shorten the Skyrim Game Master Prompt.")
            return None
        logging.log(15, "Game Master decision request:\n" + format_decision_request(body))

        headers = {
            "Authorization": f"Bearer {client.api_key}",
            "HTTP-Referer": "https://art-from-the-machine.github.io/Mantella/",
            "X-Title": "Mantella",
        }
        logging.info(f"Game Master Request Parameters: model='{client.model_name}', url='{url}'")
        started_at = time.time()
        try:
            response = post_decision_with_retry(url, headers, body, config.llm_response_timeout)
            if extra_questions and response.status_code in REJECTED_STATUS_CODES:
                # Most likely the service does not know yes/no questions. Without them, one person answers, as before
                logging.warning(f"Game Master decision call failed with status {response.status_code}. Asking again without the questions about who the latest line "
                                f"was spoken to: {response.text[:300]}")
                for name in extra_questions:
                    body["questions"].pop(name, None)
                candidates = []
                response = post_decision_with_retry(url, headers, body, config.llm_response_timeout)
                if response.status_code == 200:
                    # Only now is it clear the questions were the problem. If it failed again, something else was
                    services_without_yes_no_questions.add(url)
                    logging.warning("Game Master: the questions about who the latest line was spoken to are left out until Mantella restarts.")
        except Exception as e:
            logging.error(f"Game Master decision call failed: {e}")
            return None
        finally:
            log_request_time(started_at)
        if response.status_code != 200:
            try:
                message = response.json()["error"]["message"]
            except Exception:
                message = response.text
            logging.error(f"Game Master decision call failed with status {response.status_code}: {message}")
            logging.log(23, f"Game Master decision response:\n{format_response_text(response.text)}")
            return None
        try:
            answers = response.json()["answers"]
            answer = answers[DECISION_QUESTION]
            choice = str(answer["choice"])
        except Exception:
            logging.warning(f"Game Master gave no valid choice:\n{format_response_text(response.text)}")
            return None
        try:
            self.scores = {str(name): float(probability) for name, probability in (answer.get("probabilities") or {}).items()}
        except (TypeError, ValueError, AttributeError):
            self.scores = {}
        flagged = self.__read_yes_no_answers(answers, candidates) if candidates else None

        person = match_nearby(choice, nearby)
        if person:
            return self.__with_aimed_at(self.__request_join(person, format_confidence(answer)), flagged)
        if is_said_to_room:
            return self.__nobody_answers(choice, format_confidence(answer), choice)
        is_valid, speaker = match_speaker(choice, npcs, player_name, allow_player)
        if not is_valid:
            logging.warning(f"Game Master gave no valid choice: {choice}")
            return self.__with_aimed_at(None, flagged)
        logging.log(26, f"Game Master: {speaker.name if speaker else player_name} speaks next ({format_confidence(answer)})")
        self.picked_player = speaker is None
        return self.__with_aimed_at(speaker, flagged)


class ReplyQueue:
    """The sentences of one NPC reply. A released reply passes its sentences on to the conversation's SentenceQueue.
    A held reply keeps them until it is released, so it can be generated while the reply before it is still being played.
    """
    def __init__(self, queue: SentenceQueue, is_released: bool) -> None:
        self.__queue = queue
        self.__lock: threading.Lock = threading.Lock()
        self.__held: list[Sentence] = []
        self.__is_more_to_come: bool = True
        self.__is_released: bool = is_released
        self.__is_discarded: bool = False
        self.sentences: list[Sentence] = [] # The sentences the conversation adds to its history when they are played
        self.next_reply: ReplyQueue | None = None # The reply that follows this one. None if the player gets the turn
        self.next_ready: threading.Event = threading.Event() # Set once next_reply is decided

    @property
    def is_released(self) -> bool:
        return self.__is_released

    @property
    def is_more_to_come(self) -> bool:
        return self.__is_more_to_come

    @is_more_to_come.setter
    def is_more_to_come(self, value: bool):
        with self.__lock:
            self.__is_more_to_come = value
            if self.__is_released and not self.__is_discarded:
                self.__queue.is_more_to_come = value

    def put(self, new_sentence: Sentence):
        with self.__lock:
            if self.__is_discarded:
                return
            if not new_sentence.is_system_generated_sentence and not new_sentence.speaker.is_player_character:
                self.sentences.append(new_sentence)
            if self.__is_released:
                self.__queue.put(new_sentence)
            else:
                self.__held.append(new_sentence)

    def release(self) -> bool:
        """Passes the held sentences on and lets the rest of the reply through. False if the reply was thrown away"""
        with self.__lock:
            if self.__is_discarded:
                return False
            for sentence in self.__held:
                self.__queue.put(sentence)
            self.__held.clear()
            self.__queue.is_more_to_come = self.__is_more_to_come
            self.__is_released = True
            return True

    def discard(self):
        """Throws the reply away. Nothing more is passed on"""
        with self.__lock:
            self.__is_discarded = True
            self.__held.clear()

    def end(self, speaker: Character | None):
        """Sends the end-of-reply sentence if the reply has not sent one yet"""
        if self.is_more_to_come:
            self.is_more_to_come = False
            self.put(Sentence(SentenceContent(speaker, "", SentenceTypeEnum.SPEECH, True), "", 0))


class GameMasterTurns:
    """Turn state of a multi-NPC Game Master Mode conversation.
    After each NPC reply, the next speaker is decided and their reply is generated while the reply before it is still being played in game.
    Generation stays at most one reply ahead of the reply being played.
    """
    def __init__(self, context_for_conversation: Context, sentences: SentenceQueue) -> None:
        self.__context = context_for_conversation
        self.__sentences = sentences
        self.__npc_turns_since_player: int = 0
        self.__turn_id: int = 0 # Bumped when the turn is thrown away, so work from it is thrown away too
        self.__playing: ReplyQueue | None = None # The reply being played. None until an NPC turn starts after the last player input
        self.__replies: list[ReplyQueue] = [] # The replies of the running turn
        self.__logged_prompts: set[str] = set()
        self.__lock: threading.Lock = threading.Lock() # Keeps the turn id check and the update that follows it together
        self.__output_manager = None # The ChatManager the latest reply was generated with. After a settings change, it is not the conversation's ChatManager
        self.__allow_player_first: bool = False # See start_turn
        self.__answers_without_shout: TurnAnswers = TurnAnswers() # Who still has to answer while Shout is off (Shout keeps its own)
        self.__event_kind: str = "" # "conversation", "nearby" or "random" while the NPCs react to a Conversation Wheel event
        self.__replies_by_npc: dict[str, int] = {} # By ref id: how often each NPC has replied since the player's last line (Most Replies per Person)
        self.__everyone_added: set[str] = set() # Everyone in the conversation: the ref ids already added to who still has to answer since the player's last line
        self.__order: AnswerOrder = AnswerOrder() # Who is due to give the next replies ("When you talk to someone", "When an NPC talks to someone")
        self.__past_limit: bool = False # The NPCs have reached the reply limit since the player's last line: the extra rounds run
        self.__rounds_done: int = 0 # Extra rounds started since the reply limit
        self.__free_picks_left: int = 0 # Replies in between left in the running round

    def on_player_input(self, event_kind: str = ""):
        """The player spoke, or an event happened: the NPCs' replies are counted from here

        Args:
            event_kind (str): "conversation", "nearby" or "random" for a Conversation Wheel event. Empty for a player line
        """
        with self.__lock:
            self.__npc_turns_since_player = 0
            self.__replies_by_npc = {}
            self.__event_kind = event_kind
            self.__everyone_added = set()
            self.__answers_without_shout = TurnAnswers()
            self.__order = AnswerOrder()
            self.__past_limit, self.__rounds_done, self.__free_picks_left = False, 0, 0
            self.__discard_turn()

    def nobody_left_to_speak(self, conversation_type: Any) -> bool:
        """Every NPC in the conversation has reached Most Replies per Person, e.g. a watched NPC Event has nobody left to go on with"""
        with self.__lock: # The NPCs' turn may still be counting replies
            unavailable = self.__unavailable(self.__rules(conversation_type))
        npcs = list(self.__context.get_characters_excluding_player().get_all_characters())
        return bool(npcs) and all(npc.ref_id in unavailable for npc in npcs)

    def __rules(self, conversation_type: Any) -> TurnRules:
        return rules_for(self.__context, conversation_type, self.__event_kind)

    def __unavailable(self, rules: TurnRules) -> set[str]:
        """The ref ids of the NPCs who have reached Most Replies per Person"""
        return {ref_id for ref_id, count in self.__replies_by_npc.items() if count >= rules.most_replies}

    def __answers(self) -> TurnAnswers:
        """Who still has to answer: Shout's while Shout is on (NPC Events run in Shout too)"""
        shout_state = self.__context.shout
        return shout_state if isinstance(shout_state, ShoutState) else self.__answers_without_shout

    def __add_everyone(self, turn_id: int, conversation_type: Any):
        """Everyone in the conversation: at the start of the NPCs' turn after the player's line or an event (or a watched scene's start),
        everyone in the conversation has to say something. Also anyone who joins during the turn: the turn starts again for them.
        Not after the reply limit: nobody new has to speak then"""
        with self.__lock:
            if turn_id != self.__turn_id:
                return
            rules = self.__rules(conversation_type)
            if not rules.everyone_speaks or self.__past_limit:
                return
            unavailable = self.__unavailable(rules)
            answers = self.__answers()
            npcs = [npc for npc in self.__context.get_characters_excluding_player().get_all_characters()
                    if npc.ref_id not in unavailable and npc.ref_id not in self.__everyone_added]
            self.__everyone_added.update(npc.ref_id for npc in npcs)
            for npc in npcs:
                due = answers.still_to_answer.get(npc.ref_id)
                if due:
                    # Already has to answer: keeps that line (and its Group Answer Note), but can no longer be dropped, e.g. when it was an NPC's line
                    due.is_protected = True
            npcs = [npc for npc in npcs if npc.ref_id not in answers.still_to_answer]
            for npc in npcs:
                answers.add_still_to_answer([(npc.ref_id, npc.name)], "", True) # One at a time, so nobody gets the Group Answer Note for it
            if npcs:
                logging.log(26, f"Game Master: everyone gets to speak: {', '.join(npc.name for npc in npcs)}")

    def cancel(self):
        """Throws away the running NPC turn and its replies, so the player gets the next turn.
        Call before stopping generation, so the turn sees it was discarded as soon as its reply stops."""
        with self.__lock:
            self.__discard_turn()
        # A discarded turn never sends its end-of-reply sentence. Without one, a request waiting for the next
        # sentence would wait forever while holding the queue's lock, so clearing the queue would never finish
        self.__end_reply()

    def drop_lookahead(self) -> bool:
        """Throws away the replies that have not started playing, so the player gets the turn after the reply being played.

        Returns:
            bool: True if a reply that was thrown away may still be generating
        """
        with self.__lock:
            return self.__drop_lookahead()

    def log_prompts_again(self):
        """Logs each prompt again the next time it is used, e.g. after a settings change that can change the prompts"""
        self.__logged_prompts.clear()

    def stop_generation(self):
        """Stops generation on the ChatManager the latest reply was generated with.
        A reply started before a settings change keeps generating on the old ChatManager"""
        output_manager = self.__output_manager
        if output_manager:
            output_manager.stop_generation()

    def __drop_lookahead(self) -> bool:
        """drop_lookahead for a caller that holds the lock"""
        playing = self.__playing
        if not playing:
            return False
        self.__turn_id += 1
        for reply in self.__replies:
            if reply is not playing:
                reply.discard()
        self.__replies = [playing]
        playing.next_reply = None
        playing.next_ready.set()
        # Once the reply being played is fully generated, any generation still running is for a reply that was thrown away
        return not playing.is_more_to_come

    def __discard_turn(self):
        self.__turn_id += 1
        for reply in self.__replies:
            reply.discard()
        self.__replies = []
        self.__playing = None

    def start_turn(self, allow_player_first: bool = False) -> int:
        """Call before starting the thread for run_turn. Returns the id to pass to run_turn

        Args:
            allow_player_first (bool): the Game Master may give the player the turn right away, e.g. who reacts first to an event
        """
        with self.__lock:
            first_reply = ReplyQueue(self.__sentences, True)
            self.__replies = [first_reply]
            self.__playing = first_reply
            self.__allow_player_first = allow_player_first
            return self.__turn_id

    def play_next_reply(self, timeout: float, is_interrupted: Callable[[], bool] = lambda: False) -> bool:
        """Starts playing the reply that follows the one that has just been played

        Args:
            timeout (float): seconds to wait for the decision
            is_interrupted (Callable[[], bool]): stops the wait early when it returns True, e.g. when the player has spoken

        Returns:
            bool: True if an NPC reply follows. False if the player gets the turn
        """
        with self.__lock:
            playing = self.__playing
            turn_id = self.__turn_id
        if not playing:
            # No NPC turn is running (e.g. the conversation just switched to Game Master Mode, or an NPC was dismissed)
            return False
        deadline = time.time() + timeout
        while not playing.next_ready.wait(0.05):
            if is_interrupted() or turn_id != self.__turn_id:
                return False
            if time.time() >= deadline:
                logging.warning("Game Master did not decide in time. The player gets the turn.")
                with self.__lock:
                    if turn_id == self.__turn_id:
                        # Stops the turn, so a late decision does not generate a reply that is never played.
                        # The decision is still being made, so no reply is generating
                        self.__drop_lookahead()
                return False
        with self.__lock:
            next_reply = playing.next_reply
            if turn_id != self.__turn_id or not next_reply or not next_reply.release():
                return False
            self.__playing = next_reply
            return True

    def run_turn(self, turn_id: int, get_conversation_type: Callable[[], Any], get_output_manager: Callable[[], Any], live_messages: message_thread):
        """Generates NPC replies one after another, each with a prompt that only contains that NPC, until the player gets the turn.
        Each reply after the first is generated while the one before it is being played, and is held until that one has been played.
        Runs in the generation thread.

        Args:
            turn_id (int): the id returned by start_turn
            get_conversation_type (Callable[[], Any]): returns the conversation's current conversation type, which builds the prompts
            get_output_manager (Callable[[], Any]): returns the conversation's current ChatManager, which generates the replies and holds the Game Master client
                Both are read again for each request, so a settings change applies from the next request on
            live_messages (message_thread): the conversation's message thread
        """
        with self.__lock:
            if turn_id != self.__turn_id or not self.__playing:
                return
            reply: ReplyQueue | None = self.__playing
            allow_player_first = self.__allow_player_first
        # The history as it will be once the replies generated so far have been played
        history = live_messages.get_persistent_messages()
        # One screenshot per turn: every reply of the turn sees the game as it was when the turn started
        vision_capture = VisionCapture()
        speaker: Character | None = None
        while reply:
            try:
                conversation_type = get_conversation_type()
                if not isinstance(conversation_type, multi_npc_game_master):
                    # A settings change turned Game Master Mode off
                    self.__end_turn_early(turn_id, reply)
                    return
                if not speaker:
                    # The first speaker of the turn, after the player has spoken or an event happened
                    self.__add_everyone(turn_id, conversation_type)
                    first: Character | EventPerson | None = self.__take_forced_speaker()
                    joins: list[EventPerson] = []
                    if not first:
                        first, joins = self.__choose_first_speaker(turn_id, conversation_type, get_output_manager(), history, allow_player_first)
                    if isinstance(first, EventPerson) or joins:
                        # Shout: people nearby answer the player. The game adds them first, all in one step, then the first of them speaks
                        if self.__request_add(turn_id, first, joins, is_answer=True):
                            self.__end_turn_early(turn_id, reply, mark_failed=False)
                        return
                    speaker = first
                if not speaker:
                    # With allow_player_first, the Game Master may have given the player the turn
                    self.__end_turn_early(turn_id, reply, mark_failed=not allow_player_first)
                    return
                speaker, reply = self.__run_reply(speaker, reply, turn_id, history, conversation_type, get_conversation_type, get_output_manager, vision_capture)
            except Exception as e:
                logging.error(f"Game Master turn failed: {e}")
                self.__end_turn_early(turn_id, reply)
                return

    def __game_master(self, conversation_type: multi_npc_game_master, output_manager, rules: TurnRules) -> GameMaster:
        return GameMaster(self.__context, conversation_type, output_manager.game_master_client, self.__logged_prompts, rules, self.__answers(), self.__unavailable(rules))

    def __shout(self, conversation_type: Any) -> ShoutState | None:
        """The Shout state while the conversation is a Shout conversation"""
        if isinstance(conversation_type, shout) and isinstance(self.__context.shout, ShoutState):
            return self.__context.shout
        return None

    def __bystanders(self) -> ShoutState | None:
        """The people nearby the Game Master may draw in: Shout's, whenever Shout is on. NPC Events run in Shout too"""
        return self.__context.shout if isinstance(self.__context.shout, ShoutState) else None

    def __take_forced_speaker(self) -> Character | None:
        """Shout: the person who has just joined speaks first, without asking the Game Master. If the line was also aimed at someone
        already in the conversation, whom the Game Master had picked to speak first, they do. The people who joined answer after them"""
        bystanders = self.__bystanders()
        if not bystanders or not (bystanders.answer_first_ref_id or bystanders.forced_speaker_ref_id):
            return None
        ref_id = bystanders.answer_first_ref_id or bystanders.forced_speaker_ref_id
        bystanders.answer_first_ref_id, bystanders.forced_speaker_ref_id = "", ""
        for npc in self.__context.get_characters_excluding_player().get_all_characters():
            if npc.ref_id == ref_id:
                return npc
        return None

    def __request_add(self, turn_id: int, first: Character | EventPerson | None, joins: list[EventPerson], is_answer: bool) -> bool:
        """Asks the game to add the people nearby the Game Master picked. Only while the turn is current,
        so a turn thrown away meanwhile (e.g. the player stepped in) can't add anyone

        Args:
            first (Character | EventPerson | None): who speaks first, once they are added
            joins (list[EventPerson]): the people nearby the line was aimed at
            is_answer (bool): Shout: they answer the player's line, so the turn starts again if they can't be added

        Returns:
            bool: False if the turn was thrown away
        """
        with self.__lock:
            if turn_id != self.__turn_id:
                return False
            self.__set_pending_adds(first, joins, is_answer)
            return True

    def __set_pending_adds(self, first: Character | EventPerson | None, joins: list[EventPerson], is_answer: bool):
        """The player watching an NPC Event is added by the event, anyone else by Shout, all in one step. Call while holding the lock

        Args:
            first (Character | EventPerson | None): who speaks first. If they are in the conversation already, they speak once the others have been added
            joins (list[EventPerson]): the people nearby the line was aimed at, with or without the first speaker
        """
        people = ([first] if isinstance(first, EventPerson) else []) + [person for person in joins if person is not first]
        event = self.__context.npc_event
        if event and any(person is event.player for person in people):
            event.pending_add = event.player
            people = [person for person in people if person is not event.player]
        bystanders = self.__bystanders()
        if bystanders and people:
            bystanders.request_adds(people)
            bystanders.answering_pick = is_answer
            bystanders.answer_first_ref_id = first.ref_id if first and not isinstance(first, EventPerson) else ""

    def __apply_decision(self, game_master: GameMaster, speaker: Character | EventPerson | None, rules: TurnRules) -> tuple[Character | EventPerson | None, list[EventPerson]]:
        """What follows from who the latest line was aimed at, by the talk settings:
        - Who must speak before your turn: the people it was aimed at go on the list of who still has to speak (not after the reply limit).
        - When you talk to someone / When an NPC talks to someone: they are due to give the next replies, so one of them speaks next
          instead of the Game Master's own choice, also when it gives the player the turn.
        If the Game Master gives the player the turn while someone still has to speak, they speak instead (after the reply limit, the caller
        starts the next round instead). Those who are only nearby (Shout) have to be added first. Call while holding the lock

        Returns:
            tuple[Character | EventPerson | None, list[EventPerson]]: who speaks next (None: the player's turn), and the people nearby to add
        """
        answers = self.__answers()
        aimed = game_master.aimed_at
        from_you = game_master.is_line_protected
        is_scene = is_watched_scene(self.__context)
        added = False
        if aimed and rules.must_answer(from_you) and not self.__past_limit:
            answers.add_still_to_answer([(person.ref_id, person.name) for person in aimed], game_master.line_speaker, from_you)
            added = True
        if aimed and not self.__order.add([(person.ref_id, person.name) for person in aimed], from_you, rules.answers_first(from_you)):
            logging.log(26, f"Game Master: {', '.join(person.name for person in aimed)} don't answer {game_master.line_speaker} next, "
                            f"as {', '.join(name for group in self.__order.names() for name in group)} are still waiting their turn")
        joining = [person for person in aimed if isinstance(person, EventPerson)] # People nearby the line was spoken to, who join if anyone speaks
        joining_ids = {person.ref_id for person in joining}
        wants_player = speaker is None and game_master.picked_player
        self.__due_to_speak(answers, rules, joining_ids)
        due = self.__due_speaker(speaker, game_master.scores, rules, aimed)
        if wants_player and due is None and (self.__past_limit or not answers.still_to_answer):
            # Nobody is due to answer: the player gets the turn (after the reply limit: unless the caller starts another round). Nobody joins to speak then
            return None, []
        if due is not None and due is not speaker:
            logging.log(26, f"Game Master: {due.name} speaks next, as they are due to answer")
            speaker = due
        if speaker is None and not self.__past_limit:
            speaker = (self.__next_still_to_answer(answers, game_master.scores, rules, joining_ids)
                       or next((person for person in joining if person.ref_id in answers.still_to_answer), None))
            if speaker:
                logging.log(26, f"Game Master: {speaker.name} has not answered yet, so they speak before {'the scene goes on' if is_scene else 'the player gets the turn'}")
        return speaker, joining if speaker is not None or added else []

    def __due_speaker(self, pick: Character | EventPerson | None, scores: dict[str, float], rules: TurnRules,
                      aimed: list[Character | EventPerson]) -> Character | EventPerson | None:
        """Who of the people due to give the next reply speaks: the Game Master's own choice if it is one of them, otherwise the one it rates most
        likely to speak, otherwise the first of them. None if nobody is due. Call while holding the lock"""
        npcs = {npc.ref_id: npc for npc in self.__context.get_characters_excluding_player().get_all_characters()}
        joining = {person.ref_id: person for person in aimed if isinstance(person, EventPerson)}
        self.__order.drop(self.__unavailable(rules))
        while self.__order.due():
            people: list[Character | EventPerson] = [npcs.get(ref_id) or joining[ref_id] for ref_id, _name in self.__order.due() if ref_id in npcs or ref_id in joining]
            if not people:
                self.__order.drop({ref_id for ref_id, _name in self.__order.due()}) # They left, or could not be added
                continue
            if pick is not None and any(person.ref_id == pick.ref_id for person in people):
                return pick
            return max(people, key=lambda person: scores.get(person.name, 0.0))
        return None

    def __due_to_speak(self, answers: TurnAnswers, rules: TurnRules, joining_ids: set[str] = set()) -> list[Character]:
        """The people in the conversation who still have to speak before the player's turn. Drops those who have reached Most Replies per Person,
        or left. People nearby still waiting to be added, or joining now (joining_ids), stay. Call while holding the lock"""
        capped = answers.drop_answers(self.__unavailable(rules))
        if capped:
            logging.log(26, f"Game Master: no longer answering, as they have reached Most Replies per Person ({rules.most_replies}): {', '.join(capped)}")
        npcs = {npc.ref_id: npc for npc in self.__context.get_characters_excluding_player().get_all_characters()}
        bystanders = self.__bystanders()
        waiting = ({person.ref_id for person in bystanders.pending_adds()} if bystanders else set()) | joining_ids
        due: list[Character] = []
        for ref_id in list(answers.still_to_answer):
            if ref_id in npcs:
                due.append(npcs[ref_id])
            elif ref_id not in waiting:
                answers.still_to_answer.pop(ref_id, None) # They left, or could not be added
        return due

    def __next_still_to_answer(self, answers: TurnAnswers, scores: dict[str, float], rules: TurnRules, joining_ids: set[str] = set()) -> Character | None:
        """Who of the people in the conversation that still have to answer speaks now: the one the Game Master thinks most likely to
        speak next, otherwise whoever has waited longest. None if nobody has to. Call while holding the lock"""
        due = self.__due_to_speak(answers, rules, joining_ids)
        return max(due, key=lambda npc: scores.get(npc.name, 0.0)) if due else None

    def __at_reply_limit(self, rules: TurnRules, reply_limit: int) -> Character | None:
        """The NPCs have reached the reply limit (a watched NPC Event: its line limit). The answer order is cleared, "who still speaks" drops people
        from who still has to speak, and the first extra round starts. Call while holding the lock"""
        self.__past_limit = True
        self.__order.clear()
        answers = self.__answers()
        if rules.at_reply_limit == AtReplyLimitEnum.NOT_ANSWERED_YOU:
            dropped = answers.drop_unprotected_answers()
        elif rules.at_reply_limit == AtReplyLimitEnum.NOBODY:
            dropped = [due.name for due in answers.still_to_answer.values()]
            answers.still_to_answer.clear()
        else:
            dropped = []
        if dropped:
            logging.log(26, f"Game Master: no longer answering, as the NPCs have reached the reply limit ({rules.at_reply_limit.display_name}): {', '.join(dropped)}")
        return self.__start_round(rules, reply_limit)

    def __start_round(self, rules: TurnRules, reply_limit: int) -> Character | None:
        """After the reply limit: the next extra round. One person who still has to speak speaks, then up to Replies in between free picks of the Game Master.
        None once nobody still has to speak, or the extra rounds have run out: then everyone left is dropped. Call while holding the lock"""
        answers = self.__answers()
        speaker = self.__next_still_to_answer(answers, {}, rules) if self.__rounds_done < rules.extra_rounds else None
        self.__order.clear() # The answer order never lasts past a round's free picks
        if speaker:
            self.__rounds_done += 1
            self.__free_picks_left = rules.free_picks(reply_limit)
            logging.log(26, f"Game Master: extra round {self.__rounds_done} of {rules.extra_rounds} after the reply limit: {speaker.name} has not answered yet, "
                            f"then up to {self.__free_picks_left} replies in between")
            return speaker
        self.__free_picks_left = 0
        dropped = [due.name for due in answers.still_to_answer.values()]
        answers.still_to_answer.clear()
        if dropped:
            logging.log(26, f"Game Master: no longer answering, as the extra rounds ({rules.extra_rounds}) have run out: {', '.join(dropped)}")
        return None

    def __group_answer_note(self, speaker: Character, due: AnswerDue | None) -> str:
        """The note for someone who answers a line that was aimed at several people (Skyrim Shout Group Answer Note), Shout or not.
        Empty if the line was only aimed at them, or the note is empty

        Args:
            due (AnswerDue | None): the line they answer. None if they did not have to answer one
        """
        if not due or not due.others:
            return ""
        config = self.__context.config
        try:
            note = config.prompt_profile_manager.resolve_prompt(GROUP_ANSWER_NOTE, config.shout_group_answer_note)
        except PromptSectionError as e:
            logging.error(str(e))
            logging.error("The Skyrim Shout Group Answer Note was left out. Fix the active prompt profile.")
            return ""
        return fill_prompt_variables(note, {"name": speaker.name, "names": ", ".join(due.others), "speaker": due.speaker}).strip()

    def __choose_first_speaker(self, turn_id: int, conversation_type: multi_npc_game_master, output_manager, history: list[Message],
                               allow_player: bool = False) -> tuple[Character | EventPerson | None, list[EventPerson]]:
        """Who speaks first in the turn, and the people nearby the latest line was aimed at, who have to be added first.
        If the Game Master gives no valid choice, the NPC who joined last

        Args:
            allow_player (bool): the Game Master may give the player the turn right away (not in director mode). None then.
                Only set after a Conversation, Nearby or Random Event, so the Game Master is asked who reacts to it first
        """
        with self.__lock:
            rules = self.__rules(conversation_type)
            game_master = self.__game_master(conversation_type, output_manager, rules)
        live_messages = thread_for_lorebook(self.__context.config, history)
        after_event = allow_player
        allow_player = allow_player and not conversation_type.is_director_mode()
        shout_state = self.__shout(conversation_type)
        if shout_state:
            # Someone nearby may answer the player, unless the last person picked to answer could not be added
            allow_nearby = not shout_state.answer_again
            shout_state.answer_again = False
            speaker = game_master.choose_next_speaker(live_messages, history, allow_player=allow_player, allow_nearby=allow_nearby, always_ask=allow_player,
                                                      after_event=after_event)
        else:
            speaker = game_master.choose_next_speaker(live_messages, history, allow_player=allow_player, after_event=after_event)
        with self.__lock:
            if turn_id != self.__turn_id:
                return None, []
            speaker, joins = self.__apply_decision(game_master, speaker, rules)
            unavailable = self.__unavailable(rules)
        if speaker:
            return speaker, joins
        if allow_player and game_master.picked_player:
            return None, joins
        characters = self.__context.npcs_in_conversation
        npcs = [npc for npc in self.__context.get_characters_excluding_player().get_all_characters() if npc.ref_id not in unavailable]
        last_added = characters.last_added_character
        if last_added and not last_added.is_player_character and last_added.ref_id not in unavailable:
            return last_added, joins
        if npcs:
            return npcs[-1], joins
        return None, joins

    def __run_reply(self, speaker: Character, reply: ReplyQueue, turn_id: int, history: list[Message], conversation_type: multi_npc_game_master,
                    get_conversation_type: Callable[[], Any], get_output_manager: Callable[[], Any], vision_capture: VisionCapture) -> tuple[Character | None, ReplyQueue | None]:
        """Generates one reply, decides who speaks next and waits until the reply is being played

        Returns:
            tuple[Character | None, ReplyQueue | None]: the next speaker and their reply. (None, None) if this turn is over
        """
        config = self.__context.config
        characters = self.__context.npcs_in_conversation
        if turn_id != self.__turn_id:
            return None, None
        output_manager = get_output_manager()

        should_log = should_log_prompt(self.__logged_prompts, f"{speaker.ref_id}|{self.__context.get_character_names_as_text(True)}")
        if should_log:
            logging.log(26, f"===== Game Master Mode prompt for {speaker.name} =====")
        try:
            prompt = conversation_type.generate_npc_prompt(self.__context, speaker, thread_for_lorebook(config, history), should_log)
        except PromptSectionError as e:
            logging.error(str(e))
            logging.error("NPC reply was not generated. Fix the active Game Master NPC prompt profile, or end the conversation.")
            self.__end_turn_early(turn_id, reply)
            return None, None
        with self.__lock:
            if turn_id != self.__turn_id:
                return None, None
            due = self.__answers().take_still_to_answer(speaker.ref_id) # They speak now, so they no longer have to answer
            self.__order.spoke(speaker.ref_id)
            group_answer_note = self.__group_answer_note(speaker, due)
        if group_answer_note:
            prompt += "\n\n" + group_answer_note # Only sent with this request. Never added to the conversation itself
        event = self.__context.npc_event
        is_bystander_scene = bool(event and not event.player_joined)
        # A separate copy, so only what this NPC heard and only its own thoughts are sent. The Game Master sees the whole conversation (see game_master_history_lines).
        # While the player watches an NPC Event, people who join later were nearby and overheard the whole scene
        npc_history = deepcopy(history) if is_bystander_scene else messages_heard_by(deepcopy(history), speaker)
        for message in npc_history:
            if isinstance(message, AssistantMessage):
                message.thoughts_only_of_ref_id = speaker.ref_id
        npc_request = message_thread(config, prompt, include_decensor_bypass=True)
        npc_request.vision_capture = vision_capture
        npc_request.add_non_system_messages(npc_history)
        if len(npc_history) == 0 or not isinstance(npc_history[-1], UserMessage):
            # Only sent with this request so the NPC has something to reply to. Never added to the conversation itself
            wind_down = wind_down_text(event, config, self.__context.get_character_names_as_text(False))
            npc_request.add_message(UserMessage(config, f"({speaker.name} speaks next.) {wind_down}".strip(), "", True))

        with self.__lock:
            if turn_id != self.__turn_id:
                return None, None
            self.__output_manager = output_manager
        output_manager.generate_response(npc_request, characters, reply, config.actions, single_speaker=speaker)
        add_reply_to_history(history, reply.sentences, config, characters.contains_multiple_npcs())
        with self.__lock:
            if turn_id != self.__turn_id:
                return None, None
            self.__npc_turns_since_player += 1
            npc_turns = self.__npc_turns_since_player
            self.__replies_by_npc[speaker.ref_id] = self.__replies_by_npc.get(speaker.ref_id, 0) + 1
            if event and is_bystander_scene:
                event.npc_lines += 1
        next_speaker: Character | EventPerson | None = None
        game_master: GameMaster | None = None
        is_at_reply_limit = False
        is_free_pick = False # After the reply limit: one of the Replies in between of the running round
        start_next_round = False # After the reply limit: the round's free picks are used up
        reply_limit = 0
        # Read again, so a settings change made while the reply was generating applies to the decision
        conversation_type = get_conversation_type()
        if isinstance(conversation_type, multi_npc_game_master): # Otherwise a settings change turned Game Master Mode off, and the player gets the turn
            # Director mode: the player is not part of the conversation, so they only get the turn back once the run ends
            is_director = conversation_type.is_director_mode()
            with self.__lock:
                rules = self.__rules(conversation_type)
                past_limit, free_picks_left = self.__past_limit, self.__free_picks_left
            max_npc_turns = self.__max_npc_turns(rules)
            # A bystander player never gets the turn, so only the scene's line limit applies
            reply_limit = config.npc_event_max_lines_without_player if event and is_bystander_scene else max_npc_turns
            has_reached_limit = event.has_reached_limit(config) if event and is_bystander_scene else npc_turns >= max_npc_turns
            if has_reached_limit and not past_limit:
                logging.log(26, f"Game Master: {npc_turns} NPC replies in a row, the reply limit is reached")
                is_at_reply_limit = True
            elif not past_limit or free_picks_left > 0:
                is_free_pick = past_limit
                with self.__lock:
                    game_master = self.__game_master(conversation_type, get_output_manager(), rules)
                allow_nearby = is_bystander_scene or self.__bystanders() is not None
                next_speaker = game_master.choose_next_speaker(thread_for_lorebook(config, history), history, allow_player=not is_director, allow_nearby=allow_nearby)
            else:
                start_next_round = True
        with self.__lock:
            if turn_id != self.__turn_id:
                return None, None
            joins: list[EventPerson] = []
            if game_master:
                if is_free_pick:
                    self.__free_picks_left -= 1
                next_speaker, joins = self.__apply_decision(game_master, next_speaker, rules)
                if is_free_pick and next_speaker is None:
                    # The Game Master gives the player the turn: the round's free picks end. The next round starts, if anyone still has to speak
                    next_speaker = self.__start_round(rules, reply_limit)
            elif is_at_reply_limit:
                next_speaker = self.__at_reply_limit(rules, reply_limit)
            elif start_next_round:
                next_speaker = self.__start_round(rules, reply_limit)
            if self.__past_limit and not next_speaker and not joins:
                if is_bystander_scene and event:
                    logging.log(26, f"NPC Event: {event.npc_lines} lines without the player. The scene ends.")
                elif not self.__has_pending_adds():
                    logging.log(26, "Game Master: nobody still has to answer. The player gets the turn.")
            if isinstance(conversation_type, multi_npc_game_master):
                self.__log_turn_state(speaker, next_speaker, joins, rules, reply_limit)
            if isinstance(next_speaker, EventPerson) or joins:
                # Set only while the turn is current, so a turn thrown away meanwhile (e.g. the player stepped in) can't add anyone.
                # The turn ends after this reply. Whoever was picked speaks once the game has added the people nearby
                self.__set_pending_adds(next_speaker, joins, is_answer=False)
                next_speaker = None
            next_reply = ReplyQueue(self.__sentences, False) if next_speaker else None
            if next_reply:
                self.__replies.append(next_reply)
            reply.next_reply = next_reply
            reply.next_ready.set()
        if not next_reply:
            return None, None
        # Generation stays one reply ahead: the next reply is only generated once this one is being played
        while not reply.is_released:
            if turn_id != self.__turn_id:
                return None, None
            time.sleep(0.05)
        return next_speaker, next_reply

    def __log_turn_state(self, speaker: Character, next_speaker: Character | EventPerson | None, joins: list[EventPerson], rules: TurnRules, reply_limit: int):
        """One line after each reply, read by the in-game test (tests/ingame/talk_settings): who spoke, who speaks next, whose talk settings apply,
        who still has to speak, who is due to answer first, and the extra rounds after the reply limit. Call while holding the lock"""
        state = {
            "spoke": speaker.name,
            "next": next_speaker.name if next_speaker else ("joining" if joins else "nobody"),
            "situation": rules.situation,
            "settings": rules.settings_from or "shared",
            "still_to_speak": [due.name for due in self.__answers().still_to_answer.values()],
            "answer_order": self.__order.names(),
            "past_limit": self.__past_limit,
            "round": self.__rounds_done,
            "extra_rounds": rules.extra_rounds,
            "free_picks_left": self.__free_picks_left,
            "replies_in_between": rules.free_picks(reply_limit),
            "reply_limit": reply_limit,
        }
        logging.log(26, "Turn state: " + json.dumps(state, default=str))

    def __has_pending_adds(self) -> bool:
        """Shout: people nearby are still waiting to be added. Call while holding the lock"""
        bystanders = self.__bystanders()
        return bool(bystanders and bystanders.pending_adds())

    def __max_npc_turns(self, rules: TurnRules) -> int:
        """The limit of NPC replies in a row before the player gets the turn: the Max NPC Turns per Player Turn of the kind of conversation
        (an event's own, also in Director Mode), or Max NPC Turns per Direction in Director Mode"""
        config = self.__context.config
        if rules.situation in MAX_NPC_TURNS_KINDS:
            return getattr(config, max_npc_turns_identifier(rules.situation))
        if rules.situation == DIRECTOR:
            return config.multi_npc_game_master_director_max_npc_turns
        return getattr(config, max_npc_turns_identifier(GROUP)) # A watched NPC Event: only its line limit applies, see the caller

    def __end_turn_early(self, turn_id: int, reply: ReplyQueue | None, mark_failed: bool = True):
        """Hands the turn to the player after the reply when it could not be generated

        Args:
            mark_failed (bool): False when the turn ends on purpose, e.g. to add the person nearby who answers the player
        """
        with self.__lock:
            if reply and turn_id == self.__turn_id:
                reply.next_reply = None
                reply.next_ready.set()
                event = self.__context.npc_event
                if event and not reply.sentences and mark_failed:
                    event.has_failed = True # Starting another turn would most likely fail the same way
                if mark_failed:
                    # Otherwise another turn starts for whoever still has to answer, and most likely fails the same way, again and again
                    self.__answers().still_to_answer.clear()
        if reply:
            reply.end(self.__context.npcs_in_conversation.last_added_character)

    def __end_reply(self):
        """Sends the end-of-reply sentence if a reply is still expected. Unblocks the game if it is already waiting for the next sentence"""
        if self.__sentences.is_more_to_come:
            self.__sentences.is_more_to_come = False
            self.__sentences.put(Sentence(SentenceContent(self.__context.npcs_in_conversation.last_added_character, "", SentenceTypeEnum.SPEECH, True), "", 0))
