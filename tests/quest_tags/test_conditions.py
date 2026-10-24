"""Tests for reading quest tag conditions and evaluating the game's answers. Conditions are copied from the community bio templates CSV."""
import pandas as pd
import pytest
from src.quest_tags.conditions import (
    ANSWER_MISSING, ANSWER_NOT_LOADED, Check, CheckList, build_ref_to_base_map, normalize_local_id,
)


def _answers(check_list: CheckList, values: dict[Check, float], default: float = 0.0) -> list[float]:
    return [values.get(check, default) for check in check_list.checks]


STAGE_100 = Check("getstagedone", "CWObj", "100")
SAADIA_DEAD = Check("getdead", "Skyrim.esm|0D7505")
SAADIA_GONE = Check("getstagedone", "MS08", "201")


class TestReading:
    def test_multi_line_condition_with_and(self):
        check_list = CheckList({"battle": {2: "getstagedone CWObj 100=1\nAND\ngetquestcompleted MQ104=1"}})
        assert check_list.checks == [STAGE_100, Check("getquestcompleted", "MQ104")]
        assert check_list.unreadable == []

    def test_brackets_and_or(self):
        code = 'getstagedone T01 60=0\nAND\n("1E766".ishostiletoactor player=1\nOR\n"1E766".getdead=1)'
        check_list = CheckList({"dibella": {2: code}})
        assert check_list.checks == [
            Check("getstagedone", "T01", "60"),
            Check("ishostiletoactor", "Skyrim.esm|01E766", "player"),
            Check("getdead", "Skyrim.esm|01E766"),
        ]

    def test_missing_comparison_means_equals_one(self):
        check_list = CheckList({"letter": {1: "getstagedone FreeformRiverwood01 240"}})
        check = Check("getstagedone", "FreeformRiverwood01", "240")
        assert check_list.evaluate(_answers(check_list, {check: 1})) == {"letter": 1}
        assert check_list.evaluate(_answers(check_list, {check: 0})) == {"letter": 0}

    def test_forms_and_player(self):
        check_list = CheckList({
            "trainer": {1: '"14".getav archery>=100'},
            "spell": {1: '"14".hasspell 0201462A=0'},
            "faction": {1: "getinfaction 28186=1"},
            "liked": {1: '"01A66A".getrelationshiprank 14>=1'},
        })
        assert check_list.checks == [
            Check("getav", "player", "Marksman"),
            Check("hasspell", "player", "Dawnguard.esm|01462A"),
            Check("getinfaction", "player", "Skyrim.esm|028186"),
            Check("getrelationshiprank", "Skyrim.esm|01A66A", "player"),
        ]

    def test_shared_checks_are_listed_once(self):
        check_list = CheckList({"a": {1: "getstagedone CWObj 100=1"}, "b": {1: "getstagedone CWObj 100=1 AND getstage MQ101>=10"}})
        assert check_list.checks == [STAGE_100, Check("getstage", "MQ101")]

    @pytest.mark.parametrize("code", [
        "getstagecompleted DA08=50",                # misspelled command
        '"\'065AB3".getdead=1',                     # stray quote
        '"01B08E\t".getdead=1',                     # tab inside the number
        "getstagedone Favor 256 25=1",              # space in the quest name
        "getstage DLC2TT1b 100=1",                  # getstage with a step number
        "GetKeywordDataForLocation 16772 CWOwner=2",  # keyword by name
        "show PlayerIsVampire=1",                   # global by name
        '"Mod.esp|00ABCD".getdead=1',               # mod forms aren't supported yet
    ])
    def test_unreadable_conditions_never_happen(self, code):
        check_list = CheckList({"tag": {1: code}})
        assert [u.slot for u in check_list.unreadable] == [1]
        assert check_list.checks == []
        assert check_list.tags == {}

    def test_unreadable_outcome_leaves_others(self):
        check_list = CheckList({"whiterun": {1: "GetKeywordDataForLocation 16772 CWOwner=2", 2: "getstagedone CWObj 100=1"}})
        assert check_list.checks == [STAGE_100]
        assert list(check_list.tags["whiterun"].outcomes) == [2]

    def test_version_changes_only_with_the_checks(self):
        first = CheckList({"a": {1: "getstagedone CWObj 100=1"}})
        reworded = CheckList({"b": {2: "getstagedone CWObj 100=1"}})
        changed = CheckList({"a": {1: "getstagedone CWObj 110=1"}})
        assert first.version == reworded.version
        assert first.version != changed.version


class TestDeathCount:
    def test_getdead_uses_the_base_npc(self):
        ref_to_base = build_ref_to_base_map(pd.DataFrame({"ref_id": ["0D7505"], "base_id": ["0D7503"]}))
        check_list = CheckList({"saadia_status": {1: '"0D7505".getdead=1'}}, ref_to_base)
        assert check_list.checks == [Check("getdeadcount", "Skyrim.esm|0D7503")]
        assert check_list.tags["saadia_status"].death_only == {1}

    @pytest.mark.parametrize("count, expected", [(0, 0), (1, 1), (3, 1)])
    def test_death_count_reads_as_dead_or_not(self, count, expected):
        ref_to_base = build_ref_to_base_map(pd.DataFrame({"ref_id": ["0D7505"], "base_id": ["0D7503"]}))
        check_list = CheckList({"saadia_status": {1: '"0D7505".getdead=1'}}, ref_to_base)
        assert check_list.evaluate([float(count)]) == {"saadia_status": expected}

    def test_reference_with_several_bases_is_checked_directly(self):
        ref_to_base = build_ref_to_base_map(pd.DataFrame({"ref_id": ["0D7505", "0D7505"], "base_id": ["0D7503", "0D7504"]}))
        check_list = CheckList({"saadia_status": {1: '"0D7505".getdead=1'}}, ref_to_base)
        assert check_list.checks == [SAADIA_DEAD]

    def test_death_only_outcomes(self):
        check_list = CheckList({"saadia_status": {1: '"0D7505".getdead=1', 2: "getstagedone MS08 201=1"}})
        assert check_list.tags["saadia_status"].death_only == {1}

    @pytest.mark.parametrize("value, expected", [("0D7505", 0x0D7505), (87750, 0x087750), ("FE001ABC", 0xABC), (float("nan"), None), ("", None)])
    def test_normalize_local_id(self, value, expected):
        assert normalize_local_id(value) == expected


class TestEvaluating:
    def setup_method(self):
        self.check_list = CheckList({"saadia_status": {1: '"0D7505".getdead=1', 2: "getstagedone MS08 201=1"}})

    def test_highest_true_outcome_wins(self):
        answers = _answers(self.check_list, {SAADIA_DEAD: 1, SAADIA_GONE: 1})
        assert self.check_list.evaluate(answers) == {"saadia_status": 2}

    def test_none_true_is_outcome_zero(self):
        assert self.check_list.evaluate(_answers(self.check_list, {})) == {"saadia_status": 0}

    def test_missing_is_not_true(self):
        answers = _answers(self.check_list, {SAADIA_DEAD: ANSWER_MISSING, SAADIA_GONE: 0})
        assert self.check_list.evaluate(answers) == {"saadia_status": 0}

    def test_not_loaded_below_a_true_outcome_doesnt_matter(self):
        answers = _answers(self.check_list, {SAADIA_DEAD: ANSWER_NOT_LOADED, SAADIA_GONE: 1})
        assert self.check_list.evaluate(answers) == {"saadia_status": 2}

    def test_not_loaded_with_nothing_higher_true_is_unknown(self):
        answers = _answers(self.check_list, {SAADIA_DEAD: ANSWER_NOT_LOADED, SAADIA_GONE: 0})
        assert self.check_list.evaluate(answers) == {"saadia_status": None}

    def test_answers_to_another_list_are_unknown(self):
        assert self.check_list.evaluate([1.0]) == {"saadia_status": None}

    @pytest.mark.parametrize("hostile, dead, expected", [
        (1, 0, 2), (0, 1, 2), (0, 0, 0),
        (ANSWER_NOT_LOADED, 1, 2),        # OR: true if any part is true
        (ANSWER_NOT_LOADED, 0, None),     # OR: otherwise unknown if any part is unknown
    ])
    def test_and_or(self, hostile, dead, expected):
        check_list = CheckList({"dibella": {2: 'getstagedone T01 60=0 AND ("1E766".ishostiletoactor player=1 OR "1E766".getdead=1)'}})
        values = {Check("ishostiletoactor", "Skyrim.esm|01E766", "player"): hostile, Check("getdead", "Skyrim.esm|01E766"): dead}
        assert check_list.evaluate(_answers(check_list, values)) == {"dibella": expected}

    def test_and_with_a_false_part_is_false_even_if_another_is_unknown(self):
        check_list = CheckList({"battle": {1: 'getstagedone CWObj 100=1 AND "0D7505".getdead=1'}})
        answers = _answers(check_list, {STAGE_100: 0, SAADIA_DEAD: ANSWER_NOT_LOADED})
        assert check_list.evaluate(answers) == {"battle": 0}
