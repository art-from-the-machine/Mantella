"""Connects the game's answers to the record of quest tag outcomes, and decides what is announced.

See docs/quest_tags_1_user_edits.md, Parts 1, 3, 4 and 7.
"""
import logging
import time
from typing import Any

from src.games.gameable import Gameable
from src.http.communication_constants import communication_constants as comm_consts
from src.quest_tags import history
from src.quest_tags.conditions import ANSWER_MISSING, ANSWER_NOT_LOADED, CheckList
import src.utils as utils


class QuestTagTracker:
    """Applies reports (the answers the game sends) to the playthrough's record. Holds no game state of its own"""

    MOMENT_START = "found at conversation start"
    MOMENT_CATCHUP = "found in catch-up"
    MOMENT_PLAYER_INPUT = "player input"

    def __init__(self):
        self.__logged_once: set[str] = set()  # Messages that are only logged once per session

    def get_outcomes(self, game: Gameable, world_id: str) -> dict[str, tuple[int, int]]:
        """Tag -> (current outcome, time first seen) in this playthrough, for what NPCs are told"""
        return history.current_outcomes(history.load(history.record_path(game.conversation_folder_path, world_id)))

    def get_check_list_payload(self, game: Gameable) -> dict[str, Any]:
        """The check list as the game receives it: a version and three parallel arrays"""
        check_list = game.quest_check_list
        return {
            comm_consts.KEY_QUESTCHECKS_VERSION: check_list.version,
            comm_consts.KEY_QUESTCHECKS_FUNCTIONS: [c.function for c in check_list.checks],
            comm_consts.KEY_QUESTCHECKS_SUBJECTS: [c.subject for c in check_list.checks],
            comm_consts.KEY_QUESTCHECKS_ARGUMENTS: [c.argument for c in check_list.checks],
        }

    def is_game_list_out_of_date(self, game: Gameable, start_context: dict[str, Any]) -> bool:
        """Whether the start reply has to carry the check list.

        The game only sends a version when the check plugin is loaded; an empty one means it holds no list yet.
        Without a version (no plugin, or an old Mantella-Spell) the list is never sent.
        """
        if comm_consts.KEY_QUESTCHECKS_VERSION not in start_context:
            if game.quest_check_list.tags:
                self.__log_once("no_results", logging.INFO, "Quest tags: the game sent no results. Update Mantella-Spell, and check that MantellaQuestChecks.dll loaded (see SKSE's log).")
            return False
        game_version = str(start_context[comm_consts.KEY_QUESTCHECKS_VERSION] or "")
        if game_version != game.quest_check_list.version:
            logging.debug(f"Quest tags: the game has list version {game_version or '(none)'}, sending {game.quest_check_list.version} with the start reply")
            return True
        return False

    def apply_report(self, game: Gameable, world_id: str, report: dict[str, Any] | None, moment: str) -> tuple[list[history.OutcomeChange], list[history.OutcomeChange]]:
        """Update the record from one report. Returns every change, and the changes to announce.

        Args:
            report: the dictionary holding the version and the results, or None when the request carried none
            moment: when the report was sent, for the log; only MOMENT_PLAYER_INPUT changes can be announced
        """
        # A quest tag problem never stops a conversation: the record stays as it is, and the next report tries again
        try:
            return self.__apply_report(game, world_id, report, moment)
        except Exception as e:
            logging.warning(f"Quest tags: could not apply the game's answers, keeping the record as it is. Error: {e}")
            return [], []

    def __apply_report(self, game: Gameable, world_id: str, report: dict[str, Any] | None, moment: str) -> tuple[list[history.OutcomeChange], list[history.OutcomeChange]]:
        if not report or comm_consts.KEY_QUESTCHECKS_VERSION not in report:
            return [], []
        check_list = game.quest_check_list
        if not check_list.tags:
            return [], []
        if str(report[comm_consts.KEY_QUESTCHECKS_VERSION] or "") != check_list.version:
            return [], []  # Answers to another list: unknown. The catch-up brings answers to this one
        answers = [float(a) for a in (report.get(comm_consts.KEY_QUESTCHECKS_RESULTS) or [])]
        if len(answers) != len(check_list.checks):
            logging.warning(f"Quest tags: the game sent {len(answers)} results for {len(check_list.checks)} checks - ignoring them")
            return [], []
        self.__log_unanswered(check_list, answers)

        outcomes = check_list.evaluate(answers)
        for tag, outcome in outcomes.items():
            if outcome is None:
                logging.debug(f"Quest tag {tag}: outcome unknown (a check is about something not loaded right now)")
        path = history.record_path(game.conversation_folder_path, world_id)
        _, changes, is_first_check = history.update(path, outcomes, int(time.time()))
        if is_first_check:
            already_true = sum(1 for c in changes if c.new)
            logging.info(f"Quest tags: first check for {world_id}: {already_true} outcomes already true, recorded as background")
            return changes, []

        announceable: list[history.OutcomeChange] = []
        for change in changes:
            if change.old is None:
                logging.info(f"Quest tag {change.tag}: new tag, outcome {change.new} recorded as background")
            elif change.new < change.old:
                logging.info(f"Quest tag {change.tag}: outcome {change.old} -> {change.new} (no longer true)")
            elif moment != self.MOMENT_PLAYER_INPUT:
                logging.info(f"Quest tag {change.tag}: outcome {change.old} -> {change.new} ({moment})")
            elif not game.is_quest_tag_announced(change.tag):
                logging.info(f"Quest tag {change.tag}: outcome {change.old} -> {change.new} (announce = no)")
            elif change.new in check_list.tags[change.tag].death_only:
                logging.info(f"Quest tag {change.tag}: outcome {change.old} -> {change.new} (death, not announced)")
            else:
                logging.info(f"Quest tag {change.tag}: outcome {change.old} -> {change.new} (announced)")
                announceable.append(change)
        return changes, announceable

    def get_announcements(self, game: Gameable, changes: list[history.OutcomeChange], player_name: str | None) -> list[str]:
        """The narration lines for announced changes, as the CSVs word them now"""
        texts: list[str] = []
        for change in changes:
            text = game.get_quest_outcome_text(change.tag, change.new)
            if text:
                texts.append(utils.resolve_player_name_placeholder(text, player_name))
        return texts

    def __log_unanswered(self, check_list: CheckList, answers: list[float]):
        """Checks the game couldn't answer, once per session each (Part 7)"""
        for check, answer in zip(check_list.checks, answers):
            if answer == ANSWER_MISSING:
                if check.function in ("getstagedone", "getquestcompleted", "getstage"):
                    self.__log_once(f"missing:{check}", logging.DEBUG, f"Quest tags: quest {check.subject} not found (mod not installed, or a typo)")
                elif check.function == "getdeadcount":
                    self.__log_once(f"missing:{check}", logging.WARNING, f"Quest tags: NPC {check.subject} from Skyrim/DLCs not found for a death count (check base_id in the characters CSV)")
                else:
                    self.__log_once(f"missing:{check}", logging.WARNING, f"Quest tags: a form in {check.function} {check.subject} {check.argument} was not found or is the wrong kind (typo?)")
            elif answer == ANSWER_NOT_LOADED:
                self.__log_once(f"notloaded:{check}", logging.DEBUG, f"Quest tags: {check.function} {check.subject} {check.argument}: not loaded (not nearby, or a typo)")

    def __log_once(self, key: str, level: int, message: str):
        if key not in self.__logged_once:
            self.__logged_once.add(key)
            logging.log(level, message)
