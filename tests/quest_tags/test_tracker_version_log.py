"""Answers to an older check list are ignored and logged once (docs/tag_editor.md, "Conditions")."""
import logging

from src.http.communication_constants import communication_constants as comm_consts
from src.quest_tags.conditions import CheckList
from src.quest_tags.tracker import QuestTagTracker


class _FakeGame:
    def __init__(self, folder: str):
        self.conversation_folder_path = folder
        self.quest_check_list = CheckList({"battle": {2: "getstagedone CWObj 100=1"}})


def _old_report() -> dict:
    return {comm_consts.KEY_QUESTCHECKS_VERSION: "oldlist1", comm_consts.KEY_QUESTCHECKS_RESULTS: [1.0]}


def test_answers_to_an_older_list_change_nothing_and_are_logged_once(tmp_path, caplog):
    game = _FakeGame(str(tmp_path))
    tracker = QuestTagTracker()

    with caplog.at_level(logging.INFO):
        for _ in range(3):
            changes, announced = tracker.apply_report(game, "Player1", _old_report(), QuestTagTracker.MOMENT_PLAYER_INPUT)
            assert (changes, announced) == ([], [])

    messages = [record.getMessage() for record in caplog.records if "answered list version oldlist1" in record.getMessage()]
    assert len(messages) == 1
    assert game.quest_check_list.version in messages[0]
    assert tracker.get_outcomes(game, "Player1") == {}
