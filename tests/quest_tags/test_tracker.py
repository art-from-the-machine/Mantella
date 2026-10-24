"""Tests for applying the game's answers to the record, and what gets announced (docs/quest_tags_1_user_edits.md, Parts 3 and 4)."""
import pytest
from src.http.communication_constants import communication_constants as comm_consts
from src.quest_tags import history
from src.quest_tags.conditions import ANSWER_NOT_LOADED, Check, CheckList
from src.quest_tags.history import OutcomeChange
from src.quest_tags.tracker import QuestTagTracker

BATTLE_DONE = Check("getstagedone", "CWObj", "100")
SAADIA_DEAD = Check("getdead", "Skyrim.esm|0D7505")


class _FakeGame:
    def __init__(self, folder: str, no_announce: set[str] | None = None):
        self.conversation_folder_path = folder
        self.quest_check_list = CheckList({
            "battle": {2: "getstagedone CWObj 100=1"},
            "saadia_status": {1: '"0D7505".getdead=1'},
            "trainer": {1: "getstagedone CWObj 100=1"},
        })
        self.__no_announce = no_announce or set()

    def get_quest_outcome_text(self, tag: str, slot: int) -> str | None:
        return {("battle", 2): "{player_name} won the battle.", ("saadia_status", 1): "Saadia has died.", ("trainer", 1): "Aware."}.get((tag, slot))

    def is_quest_tag_announced(self, tag: str) -> bool:
        return tag not in self.__no_announce


def _report(game: _FakeGame, values: dict[Check, float]) -> dict:
    return {
        comm_consts.KEY_QUESTCHECKS_VERSION: game.quest_check_list.version,
        comm_consts.KEY_QUESTCHECKS_RESULTS: [values.get(c, 0.0) for c in game.quest_check_list.checks],
    }


@pytest.fixture
def game(tmp_path):
    return _FakeGame(str(tmp_path), no_announce={"trainer"})


@pytest.fixture
def tracker():
    return QuestTagTracker()


def _first_check(tracker, game):
    tracker.apply_report(game, "Player1", _report(game, {}), QuestTagTracker.MOMENT_START)


class TestApplyReport:
    def test_first_check_is_background(self, tracker, game):
        changes, announced = tracker.apply_report(game, "Player1", _report(game, {BATTLE_DONE: 1}), QuestTagTracker.MOMENT_PLAYER_INPUT)
        assert announced == []
        assert OutcomeChange("battle", None, 2) in changes
        assert tracker.get_outcomes(game, "Player1") == {"battle": (2, 0), "trainer": (1, 0)}

    def test_change_on_player_input_is_announced(self, tracker, game):
        _first_check(tracker, game)
        _, announced = tracker.apply_report(game, "Player1", _report(game, {BATTLE_DONE: 1}), QuestTagTracker.MOMENT_PLAYER_INPUT)
        assert announced == [OutcomeChange("battle", 0, 2)]  # trainer has announce = no
        assert tracker.get_announcements(game, announced, "Dovahkiin") == ["Dovahkiin won the battle."]

    def test_reapplying_the_same_report_announces_nothing(self, tracker, game):
        _first_check(tracker, game)
        tracker.apply_report(game, "Player1", _report(game, {BATTLE_DONE: 1}), QuestTagTracker.MOMENT_PLAYER_INPUT)
        _, announced = tracker.apply_report(game, "Player1", _report(game, {BATTLE_DONE: 1}), QuestTagTracker.MOMENT_PLAYER_INPUT)
        assert announced == []

    @pytest.mark.parametrize("moment", [QuestTagTracker.MOMENT_START, QuestTagTracker.MOMENT_CATCHUP])
    def test_change_at_start_or_catch_up_is_recorded_not_announced(self, tracker, game, moment):
        _first_check(tracker, game)
        changes, announced = tracker.apply_report(game, "Player1", _report(game, {BATTLE_DONE: 1}), moment)
        assert OutcomeChange("battle", 0, 2) in changes
        assert announced == []

    def test_death_is_never_announced(self, tracker, game):
        _first_check(tracker, game)
        changes, announced = tracker.apply_report(game, "Player1", _report(game, {SAADIA_DEAD: 1}), QuestTagTracker.MOMENT_PLAYER_INPUT)
        assert changes == [OutcomeChange("saadia_status", 0, 1)]
        assert announced == []

    def test_not_loaded_keeps_the_record(self, tracker, game):
        _first_check(tracker, game)
        tracker.apply_report(game, "Player1", _report(game, {SAADIA_DEAD: 1}), QuestTagTracker.MOMENT_START)
        changes, _ = tracker.apply_report(game, "Player1", _report(game, {SAADIA_DEAD: ANSWER_NOT_LOADED}), QuestTagTracker.MOMENT_START)
        assert changes == []
        assert tracker.get_outcomes(game, "Player1")["saadia_status"][0] == 1

    def test_answers_to_another_list_version_are_ignored(self, tracker, game):
        report = _report(game, {BATTLE_DONE: 1})
        report[comm_consts.KEY_QUESTCHECKS_VERSION] = "oldlist"
        assert tracker.apply_report(game, "Player1", report, QuestTagTracker.MOMENT_START) == ([], [])
        assert history.load(history.record_path(game.conversation_folder_path, "Player1")) is None

    def test_request_without_a_report_changes_nothing(self, tracker, game):
        assert tracker.apply_report(game, "Player1", {}, QuestTagTracker.MOMENT_PLAYER_INPUT) == ([], [])


class TestCheckListDelivery:
    def test_list_sent_when_the_game_holds_another_or_none(self, tracker, game):
        assert tracker.is_game_list_out_of_date(game, {comm_consts.KEY_QUESTCHECKS_VERSION: ""})
        assert tracker.is_game_list_out_of_date(game, {comm_consts.KEY_QUESTCHECKS_VERSION: "oldlist"})

    def test_list_not_sent_when_up_to_date(self, tracker, game):
        assert not tracker.is_game_list_out_of_date(game, {comm_consts.KEY_QUESTCHECKS_VERSION: game.quest_check_list.version})

    def test_list_never_sent_without_the_check_plugin(self, tracker, game):
        assert not tracker.is_game_list_out_of_date(game, {})

    def test_payload_is_parallel_arrays(self, tracker, game):
        payload = tracker.get_check_list_payload(game)
        assert payload[comm_consts.KEY_QUESTCHECKS_VERSION] == game.quest_check_list.version
        assert payload[comm_consts.KEY_QUESTCHECKS_FUNCTIONS] == ["getstagedone", "getdead"]
        assert payload[comm_consts.KEY_QUESTCHECKS_SUBJECTS] == ["CWObj", "Skyrim.esm|0D7505"]
        assert payload[comm_consts.KEY_QUESTCHECKS_ARGUMENTS] == ["100", ""]
