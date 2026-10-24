"""Tests for the record of quest tag outcomes (docs/quest_tags_1_user_edits.md, Part 1, "Updating the record")."""
import json
from src.quest_tags import history
from src.quest_tags.history import OutcomeChange, apply_outcomes


def _record(**tags):
    return {tag: {"current": current, "seen": {str(k): v for k, v in seen.items()}} for tag, (current, seen) in tags.items()}


class TestApplyOutcomes:
    def test_first_check_records_everything_as_background(self):
        tags, changes = apply_outcomes(None, {"dragon": 1, "battle": 0}, now=500)
        assert tags == _record(dragon=(1, {1: 0}), battle=(0, {}))
        assert changes == [OutcomeChange("dragon", None, 1), OutcomeChange("battle", None, 0)]

    def test_unknown_writes_nothing(self):
        record = _record(saadia=(1, {1: 300}))
        tags, changes = apply_outcomes(record, {"saadia": None, "new_tag": None}, now=500)
        assert tags == record
        assert changes == []

    def test_tag_added_later_is_background(self):
        tags, changes = apply_outcomes(_record(battle=(0, {})), {"battle": 0, "new_tag": 2}, now=500)
        assert tags["new_tag"] == {"current": 2, "seen": {"2": 0}}
        assert changes == [OutcomeChange("new_tag", None, 2)]

    def test_same_writes_nothing(self):
        record = _record(battle=(2, {2: 300}))
        tags, changes = apply_outcomes(record, {"battle": 2}, now=500)
        assert tags == record
        assert changes == []

    def test_higher_is_timed_now(self):
        tags, changes = apply_outcomes(_record(battle=(0, {})), {"battle": 2}, now=500)
        assert tags["battle"] == {"current": 2, "seen": {"2": 500}}
        assert changes == [OutcomeChange("battle", 0, 2)]

    def test_lower_forgets_higher_times_and_keeps_its_own(self):
        tags, _ = apply_outcomes(_record(quest=(2, {1: 100, 2: 300})), {"quest": 1}, now=500)
        assert tags["quest"] == {"current": 1, "seen": {"1": 100}}

    def test_lower_without_a_time_is_timed_now(self):
        tags, _ = apply_outcomes(_record(quest=(2, {2: 300})), {"quest": 1}, now=500)
        assert tags["quest"] == {"current": 1, "seen": {"1": 500}}

    def test_back_to_zero_forgets_all_times(self):
        tags, changes = apply_outcomes(_record(battle=(2, {2: 300})), {"battle": 0}, now=500)
        assert tags["battle"] == {"current": 0, "seen": {}}
        assert changes == [OutcomeChange("battle", 2, 0)]

    def test_reaching_a_forgotten_outcome_again_is_news(self):
        tags, _ = apply_outcomes(_record(quest=(2, {1: 100, 2: 300})), {"quest": 1}, now=500)
        tags, _ = apply_outcomes(tags, {"quest": 2}, now=900)
        assert tags["quest"] == {"current": 2, "seen": {"1": 100, "2": 900}}

    def test_input_is_not_modified(self):
        record = _record(battle=(0, {}))
        apply_outcomes(record, {"battle": 2}, now=500)
        assert record == _record(battle=(0, {}))


class TestFile:
    def test_update_writes_and_reads_back(self, tmp_path):
        path = history.record_path(str(tmp_path), "Player1")
        _, _, is_first = history.update(path, {"dragon": 1}, now=500)
        assert is_first
        with open(path, encoding="utf-8") as f:
            assert json.load(f) == {"tags": {"dragon": {"current": 1, "seen": {"1": 0}}}}
        _, changes, is_first = history.update(path, {"dragon": 2}, now=600)
        assert not is_first
        assert changes == [OutcomeChange("dragon", 1, 2)]
        assert history.current_outcomes(history.load(path)) == {"dragon": (2, 600)}

    def test_first_check_without_usable_answers_writes_nothing(self, tmp_path):
        path = history.record_path(str(tmp_path), "Player1")
        history.update(path, {"dragon": None}, now=500)
        assert history.load(path) is None

    def test_no_temporary_files_are_left(self, tmp_path):
        path = history.record_path(str(tmp_path), "Player1")
        history.update(path, {"dragon": 1}, now=500)
        assert [p.name for p in (tmp_path / "Player1").iterdir()] == [history.FILE_NAME]

    def test_current_outcomes_skips_zero(self):
        assert history.current_outcomes(_record(battle=(0, {}), dragon=(1, {1: 0}))) == {"dragon": (1, 0)}
