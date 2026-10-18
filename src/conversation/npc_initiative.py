import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, cast
from src.config.config_loader import ConfigLoader
from src.conversation.game_master import (DECISIONS_URLS, fill_prompt_variables, format_confidence, format_decision_request,
                                          format_response_text, post_decision_with_retry)
from src.llm.ai_client import AIClient
from src.llm.client_base import ClientBase
from src.llm.message_thread import message_thread
from src.llm.messages import UserMessage
from src.utils import get_time_group

NOBODY = "Nobody"
DECISION_QUESTION = "npc_initiative"
NPC_INITIATIVE_TIMEOUT = 10 # Seconds. Requests are handled one at a time, so a slow check would hold up a conversation the player starts meanwhile

INSTRUCTIONS = "skyrim_npc_initiative_decision_instructions"
NPC_CRITERIA = "skyrim_npc_initiative_decision_npc_criteria"
NOBODY_CRITERIA = "skyrim_npc_initiative_decision_nobody_criteria"


@dataclass
class InitiativeCandidate:
    """A nearby NPC who might walk up to the player"""
    name: str
    refid: int # As sent by the game, so it can be sent back unchanged


def label_candidates(candidates: list[InitiativeCandidate]) -> dict[str, InitiativeCandidate]:
    """One answer option per candidate. Candidates with the same name get 'Name (2)', 'Name (3)', ..."""
    labelled: dict[str, InitiativeCandidate] = {}
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.name] = counts.get(candidate.name, 0) + 1
        label = candidate.name if counts[candidate.name] == 1 else f"{candidate.name} ({counts[candidate.name]})"
        labelled[label] = candidate
    return labelled


def build_question(config: ConfigLoader, labels: list[str], player_name: str, location: str, hour: int, bios_and_summaries: str) -> dict[str, Any]:
    """The choice question with one option per candidate plus Nobody. Its instructions also carry the scene

    Args:
        bios_and_summaries (str): each candidate's bio and memories, as in the Skyrim Multi-NPC Prompt

    Raises:
        PromptSectionError: an active profile has a variable that is not allowed
    """
    manager = config.prompt_profile_manager
    instructions = manager.resolve_prompt(INSTRUCTIONS, config.npc_initiative_decision_instructions)
    npc_criteria = manager.resolve_prompt(NPC_CRITERIA, config.npc_initiative_decision_npc_criteria)
    nobody_criteria = manager.resolve_prompt(NOBODY_CRITERIA, config.npc_initiative_decision_nobody_criteria)
    criteria = {label: fill_prompt_variables(npc_criteria, {"name": label, "player_name": player_name}) for label in labels}
    criteria[NOBODY] = fill_prompt_variables(nobody_criteria, {"player_name": player_name})
    return {
        "type": "choice",
        # The bios are filled last, so text in them that looks like a variable is left alone
        "instructions": fill_prompt_variables(instructions, {
            "player_name": player_name,
            "names": ", ".join(labels),
            "location": location,
            "time": str(hour - 12 if hour > 12 else hour),
            "time_group": get_time_group(hour),
            "bios_and_summaries": bios_and_summaries,
        }).strip(),
        "criteria": criteria,
    }


def choose_initiator(config: ConfigLoader, client: AIClient | None, candidates: list[InitiativeCandidate], player_name: str,
                     location: str, hour: int, bios_and_summaries: str, is_cancelled: Callable[[], bool] = lambda: False,
                     skip_threshold: bool = False) -> InitiativeCandidate | None:
    """Asks the Game Master's decision model (or LLM) whether one of the candidates has to walk up to the player

    Args:
        bios_and_summaries (str): the candidates' bios and memories, as in the Skyrim Multi-NPC Prompt
        is_cancelled (Callable[[], bool]): True once the check is no longer needed (the player started a conversation).
            The request already sent can not be stopped, but nothing more is sent after it
        skip_threshold (bool): the top candidate approaches however likely the decision model thinks it is

    Returns:
        InitiativeCandidate | None: the candidate who approaches the player. None for nobody, or if anything goes wrong
    """
    if not client or not candidates:
        return None
    player_name = player_name or "the player"
    try:
        labelled = label_candidates(candidates)
        question = build_question(config, list(labelled), player_name, location or "Skyrim", hour, bios_and_summaries)
        if is_cancelled():
            return None
        if config.game_master_use_decision_model:
            chosen = _choose_with_decision_model(config, cast(ClientBase, client), labelled, question, is_cancelled, skip_threshold)
        else:
            chosen = _choose_with_llm(config, client, labelled, question)
        return None if is_cancelled() else chosen
    except Exception as e:
        logging.error(f"NPC Initiative check failed: {e}")
        return None


def _choose_with_decision_model(config: ConfigLoader, client: ClientBase, labelled: dict[str, InitiativeCandidate],
                                 question: dict[str, Any], is_cancelled: Callable[[], bool],
                                 skip_threshold: bool = False) -> InitiativeCandidate | None:
    url = DECISIONS_URLS.get(client.service_name)
    if not url:
        logging.error(f"NPC Initiative decision models only work through OpenRouter or NanoGPT, not {client.service_name}.")
        return None
    # The scene is in the question's instructions. The empty scene keeps the request in the Game Master's shape
    body = {"model": client.model_name, "state": {"scene": "", "conversation": []}, "questions": {DECISION_QUESTION: question}}
    logging.log(15, "NPC Initiative decision request:\n" + format_decision_request(body))
    headers = {
        "Authorization": f"Bearer {client.api_key}",
        "HTTP-Referer": "https://art-from-the-machine.github.io/Mantella/",
        "X-Title": "Mantella",
    }
    started_at = time.time()
    try:
        response = post_decision_with_retry(url, headers, body, min(config.llm_response_timeout, NPC_INITIATIVE_TIMEOUT),
                                            should_retry=lambda: not is_cancelled())
    finally:
        logging.log(26, f"NPC Initiative request took {time.time() - started_at:.2f} seconds")
    if response.status_code != 200:
        logging.error(f"NPC Initiative decision call failed with status {response.status_code}:\n{format_response_text(response.text)}")
        return None
    answer = response.json()["answers"][DECISION_QUESTION]
    probabilities: dict[str, float] = answer.get("probabilities") or {}
    if probabilities:
        top = max(probabilities, key=lambda label: probabilities[label])
        probability = float(probabilities[top])
    else:
        top = str(answer["choice"])
        probability = float(answer.get("confidence", 0))
    logging.log(26, f"NPC Initiative: {format_confidence(answer)}")
    if top == NOBODY or top not in labelled:
        return None
    if probability < config.npc_initiative_threshold and not skip_threshold:
        logging.log(26, f"NPC Initiative: {top} ({probability:.2f}) is below the threshold of {config.npc_initiative_threshold:.2f}")
        return None
    logging.log(26, f"NPC Initiative: {top} approaches the player")
    return labelled[top]


def _choose_with_llm(config: ConfigLoader, client: AIClient, labelled: dict[str, InitiativeCandidate],
                      question: dict[str, Any]) -> InitiativeCandidate | None:
    options = "\n".join(f"- {label}: {criterion}" for label, criterion in question["criteria"].items())
    prompt = f"{question['instructions']}\n\nThe options are:\n{options}"
    request_text = (f"Choose one of: {', '.join(question['criteria'])}.\n"
                    'Reply only with JSON in this format: {"next": "<option>", "reason": "<a few words>"}')
    request = message_thread(config, prompt)
    request.add_message(UserMessage(config, request_text, "", True))
    started_at = time.time()
    try:
        reply = client.request_call(request)
    finally:
        logging.log(26, f"NPC Initiative request took {time.time() - started_at:.2f} seconds")
    choice, reason = parse_choice(reply)
    candidate = match_label(choice, labelled)
    logging.log(26, f"NPC Initiative: {candidate.name if candidate else NOBODY} ({reason or reply})")
    return candidate


def parse_choice(text: str | None) -> tuple[str, str]:
    """Reads the LLM's JSON reply, e.g. {"next": "Hulda", "reason": "..."}. Empty strings if it is not valid"""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return "", ""
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    return str(data.get("next", "")).strip(), str(data.get("reason", "")).strip()


def match_label(choice: str, labelled: dict[str, InitiativeCandidate]) -> InitiativeCandidate | None:
    choice = choice.strip().lower()
    for label, candidate in labelled.items():
        if label.lower() == choice:
            return candidate
    return None
