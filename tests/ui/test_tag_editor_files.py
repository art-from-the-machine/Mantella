"""Tests for the Tag Editor's file handling (docs/tag_editor.md, "Where your changes are saved")."""
import os
from datetime import datetime

import pandas as pd
import pytest

from src.bio_template_manager import LAYER_BASE, LAYER_MOD, LAYER_PERSONAL, _split_static_and_dynamic
from src.ui.tag_editor_files import (
    TAG_EDITOR_FILE,
    changed_cells,
    choose_target_file,
    clean_event_text,
    current_source,
    event_timestamps,
    format_event_date,
    has_base_or_mod_rows,
    join_description,
    npcs_by_tag,
    parse_event_date,
    personal_files,
    personal_files_with_value,
    remove_tag_rows,
    search_tags,
    source_underneath,
    split_description,
    write_cells,
)


def _read_raw(path) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def _read(path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


# --- Description and events ---

def test_split_and_join_round_trip():
    description = "Knows the Dragonborn.\nLikes mead.\n- 2000: {player_name} defeated Alduin\n- 1000: {player_name} became Thane"
    text, events = split_description(description)

    assert text == "Knows the Dragonborn.\nLikes mead."
    joined = join_description(text, events)
    assert joined == "Knows the Dragonborn.\nLikes mead.\n- 1000: {player_name} became Thane\n- 2000: {player_name} defeated Alduin"
    assert _split_static_and_dynamic(joined) == (text, sorted(events))


def test_join_drops_empty_events_and_puts_events_on_one_line():
    joined = join_description("", [(5, "first\nline"), (6, "   ")])

    assert joined == "- 5: first line"
    assert clean_event_text("a\r\n  b") == "a b"


def test_event_dates_round_trip_to_the_second():
    timestamp = 1739270421
    assert parse_event_date(format_event_date(timestamp)) == timestamp


def test_dates_windows_cant_handle_give_a_readable_error_or_stay_a_number():
    with pytest.raises(ValueError, match="from 1970 on"):
        parse_event_date("1960-01-01")
    assert format_event_date(99999999999) == "99999999999"
    assert parse_event_date("99999999999") == 99999999999


def test_a_year_or_short_number_is_not_taken_as_seconds():
    for text in ("2026", "20261106", "²"):
        with pytest.raises(ValueError, match="isn't a date"):
            parse_event_date(text)
    assert parse_event_date("1739270400") == 1739270400


def test_untouched_events_keep_their_exact_timestamp():
    # Two different moments can show as the same local time (the hour repeated when clocks go back)
    loaded = [("2026-11-01 01:30:00", "first", 1793514600), ("2026-11-01 01:30:00", "second", 1793518200)]
    rows = [["2026-11-01 01:30:00", "second"], ["2026-11-01 01:30:00", "first"]]

    assert event_timestamps(rows, loaded) == [(1793518200, "second"), (1793514600, "first")]


def test_edited_event_text_keeps_its_timestamp_and_a_new_date_is_read():
    loaded = [("2026-11-01 01:30:00", "old text", 1793518200)]
    rows = [["2026-11-01 01:30:00", "new text"], ["2026-11-06 14:30", "added"]]

    assert event_timestamps(rows, loaded) == [
        (1793518200, "new text"),
        (int(datetime(2026, 11, 6, 14, 30).timestamp()), "added"),
    ]


def test_event_dates_accept_minutes_or_a_bare_date():
    assert parse_event_date("2026-11-06 14:30") == int(datetime(2026, 11, 6, 14, 30).timestamp())
    assert parse_event_date("2026-11-06") == int(datetime(2026, 11, 6).timestamp())
    with pytest.raises(ValueError):
        parse_event_date("next tuesday")


# --- Where values come from ---

SOURCES = {
    "whiterun_hold": {
        "description": [(LAYER_BASE, "base.csv", "Base."), (LAYER_MOD, "mod.csv", "Mod."), (LAYER_PERSONAL, "a.csv", "Mine.")],
        "notes": [(LAYER_PERSONAL, "a.csv", "x"), (LAYER_PERSONAL, "b.csv", "y")],
    }
}
FILES = {
    "whiterun_hold": [(LAYER_BASE, "base.csv"), (LAYER_MOD, "mod.csv"), (LAYER_PERSONAL, "a.csv"), (LAYER_PERSONAL, "b.csv")],
    "mine_only": [(LAYER_PERSONAL, "a.csv")],
}


def test_current_source_and_what_is_underneath():
    assert current_source(SOURCES, "whiterun_hold", "description") == (LAYER_PERSONAL, "a.csv", "Mine.")
    assert source_underneath(SOURCES, "whiterun_hold", "description") == (LAYER_MOD, "mod.csv", "Mod.")
    assert source_underneath(SOURCES, "whiterun_hold", "notes") is None
    assert current_source(SOURCES, "whiterun_hold", "code_1") is None


def test_personal_files_and_layers():
    assert personal_files(FILES, "whiterun_hold") == ["a.csv", "b.csv"]
    assert has_base_or_mod_rows(FILES, "whiterun_hold") is True
    assert has_base_or_mod_rows(FILES, "mine_only") is False
    assert personal_files_with_value(SOURCES, "whiterun_hold", "notes") == ["a.csv", "b.csv"]
    assert personal_files_with_value(SOURCES, "whiterun_hold", "code_1") == []


def test_target_is_the_last_personal_file_with_the_tag(tmp_path):
    assert choose_target_file(FILES, "whiterun_hold", str(tmp_path)) == "b.csv"


def test_target_is_tag_editor_csv_when_no_personal_file_has_the_tag(tmp_path):
    files = {"base_only": [(LAYER_BASE, "base.csv")]}
    assert choose_target_file(files, "base_only", str(tmp_path)) == os.path.join(str(tmp_path), TAG_EDITOR_FILE)
    assert choose_target_file(files, "brand_new", str(tmp_path)) == os.path.join(str(tmp_path), TAG_EDITOR_FILE)


def test_changed_cells_ignores_unchanged_and_end_spaces():
    before = {"description": "Same.", "notes": "", "code_1": "old"}
    after = {"description": "Same.  ", "notes": "new note", "code_1": ""}
    assert changed_cells(before, after) == {"notes": "new note", "code_1": ""}


# --- Writing ---

def test_write_cells_creates_tag_editor_csv(tmp_path):
    path = str(tmp_path / "bio_templates" / TAG_EDITOR_FILE)

    write_cells(path, "new_tag", {"notes": "hello"})

    df = _read(path)
    assert list(df.columns[:2]) == ["tag", "description"]
    assert df.to_dict("records") == [{"tag": "new_tag", "description": "", "notes": "hello"}]
    assert not os.path.exists(path + ".bak")


def test_write_cells_changes_only_the_given_cells_and_keeps_the_rest(tmp_path):
    path = str(tmp_path / "my_tags.csv")
    with open(path, "w", encoding="utf-8", newline="") as file:
        file.write("tag,description,code_1,my_column\nwhiterun_hold,Old text.,1,keep me\nother,NA,,\n")

    write_cells(path, "whiterun_hold", {"description": "New text.", "announce": "no"})

    df = _read(path)
    assert df.to_dict("records") == [
        {"tag": "whiterun_hold", "description": "New text.", "code_1": "1", "my_column": "keep me", "announce": "no"},
        {"tag": "other", "description": "NA", "code_1": "", "my_column": "", "announce": ""},
    ]


def test_write_cells_keeps_a_backup_of_the_file_before_the_change(tmp_path):
    path = str(tmp_path / "my_tags.csv")
    original = "tag,description\nwhiterun_hold,Old text.\n"
    with open(path, "w", encoding="utf-8", newline="") as file:
        file.write(original)

    write_cells(path, "whiterun_hold", {"description": "New text."})

    assert _read_raw(path + ".bak") == original


def test_write_cells_reads_the_file_fresh(tmp_path):
    path = str(tmp_path / "my_tags.csv")
    write_cells(path, "a", {"description": "A."})
    with open(path, "a", encoding="utf-8") as file:
        file.write("added_by_hand,By hand.\n")

    write_cells(path, "a", {"description": "A2."})

    assert _read(path)["tag"].tolist() == ["a", "added_by_hand"]


def test_write_cells_updates_the_last_row_with_the_tag_and_matches_curly_apostrophes(tmp_path):
    path = str(tmp_path / "my_tags.csv")
    with open(path, "w", encoding="utf-8", newline="") as file:
        file.write("tag,description\nrisaad's_caravan,First.\nrisaad’s_caravan,Second.\n")

    write_cells(path, "risaad's_caravan", {"description": "Changed."})

    assert _read(path)["description"].tolist() == ["First.", "Changed."]


def test_write_cells_turns_an_ascii_file_into_utf8_for_new_characters(tmp_path):
    path = str(tmp_path / "my_tags.csv")
    with open(path, "w", encoding="ascii", newline="") as file:
        file.write("tag,description\nwhiterun_hold,Old.\n")

    write_cells(path, "whiterun_hold", {"description": "Café ’quoted’."})

    assert _read(path)["description"].tolist() == ["Café ’quoted’."]


def test_a_valid_utf8_file_stays_utf8_whatever_the_guess(tmp_path, monkeypatch):
    path = str(tmp_path / "my_tags.csv")
    with open(path, "w", encoding="utf-8", newline="") as file:
        file.write("tag,description\nother,Café.\nwhiterun_hold,Old.\n")
    monkeypatch.setattr("src.utils.get_file_encoding", lambda _: "Windows-1252")

    write_cells(path, "whiterun_hold", {"description": "’quoted’ 中"})

    with open(path, "r", encoding="utf-8") as file:
        df = pd.read_csv(file, dtype=str, keep_default_na=False)
    assert df["description"].tolist() == ["Café.", "’quoted’ 中"]


def test_clearing_a_cell_clears_it_on_every_row_with_the_tag(tmp_path):
    path = str(tmp_path / "my_tags.csv")
    with open(path, "w", encoding="utf-8", newline="") as file:
        file.write("tag,description,notes\nt,First.,a\nother,Keep.,b\nt,Second.,c\n")

    write_cells(path, "t", {"description": "", "notes": "new"})

    assert _read(path).to_dict("records") == [
        {"tag": "t", "description": "", "notes": "a"},
        {"tag": "other", "description": "Keep.", "notes": "b"},
        {"tag": "t", "description": "", "notes": "new"},
    ]


def test_write_cells_keeps_multi_line_descriptions(tmp_path):
    path = str(tmp_path / "my_tags.csv")
    description = join_description("Line one.\nLine two.", [(100, "event, with comma")])

    write_cells(path, "t", {"description": description})

    assert _read(path)["description"].tolist() == [description]


def test_remove_tag_rows_only_touches_the_given_files(tmp_path):
    first = str(tmp_path / "a.csv")
    second = str(tmp_path / "b.csv")
    untouched = str(tmp_path / "c.csv")
    for path in (first, second, untouched):
        with open(path, "w", encoding="utf-8", newline="") as file:
            file.write("tag,description\ngone,Bye.\nstays,Hi.\n")

    changed = remove_tag_rows([first, second, first], "gone")

    assert changed == [first, second]
    assert _read(first)["tag"].tolist() == ["stays"]
    assert _read(second)["tag"].tolist() == ["stays"]
    assert _read(untouched)["tag"].tolist() == ["gone", "stays"]
    assert os.path.exists(first + ".bak")
    assert not os.path.exists(untouched + ".bak")


# --- Search ---

SEARCH_SOURCES = {
    "whiterun_hold": {
        "description": [(LAYER_BASE, "base.csv", "Old thane text."), (LAYER_PERSONAL, "mine.csv", "Knows the Dragonborn.\n- 1739270400: {player_name} became Thane of Whiterun")],
        "code_2": [(LAYER_MOD, "mod.csv", "getstagedone Favor250 20=1")],
        "notes": [(LAYER_PERSONAL, "mine.csv", "check the THANE quests")],
    },
    "thane_of_riften": {
        "potential_paste_1": [(LAYER_MOD, "mod.csv", "The player is now a Thane.")],
    },
}
SEARCH_FILES = {
    "whiterun_hold": [(LAYER_BASE, "base.csv"), (LAYER_MOD, "mod.csv"), (LAYER_PERSONAL, "mine.csv")],
    "thane_of_riften": [(LAYER_MOD, "mod.csv")],
}


def test_search_finds_every_field_ignoring_case():
    results = search_tags(SEARCH_SOURCES, SEARCH_FILES, "thane")

    found = [(result["tag"], result["where"]) for result in results]
    assert found == [
        ("thane_of_riften", "Tag name"),
        ("thane_of_riften", "Outcome 1 text"),
        ("whiterun_hold", f"Event {format_event_date(1739270400)}"),
        ("whiterun_hold", "Notes"),
    ]
    riften_text = results[1]
    assert riften_text["snippet"] == "The player is now a Thane."
    assert (riften_text["layer"], riften_text["file"]) == (LAYER_MOD, "mod.csv")


def test_search_only_looks_at_current_values():
    # "Old thane text." is overridden by the personal description, so the game never uses it
    assert all(result["where"] != "Tag text" for result in search_tags(SEARCH_SOURCES, SEARCH_FILES, "old thane"))


def test_search_finds_conditions_and_trims_long_text():
    assert [r["where"] for r in search_tags(SEARCH_SOURCES, SEARCH_FILES, "favor250")] == ["Condition 2"]
    long_sources = {"long": {"description": [(LAYER_BASE, "b.csv", "a" * 100 + " needle " + "b" * 100)]}}
    snippet = search_tags(long_sources, {"long": [(LAYER_BASE, "b.csv")]}, "NEEDLE")[0]["snippet"]
    assert snippet.startswith("…") and snippet.endswith("…") and "needle" in snippet and len(snippet) < 100


def test_empty_search_finds_nothing():
    assert search_tags(SEARCH_SOURCES, SEARCH_FILES, "   ") == []


# --- NPCs with a tag ---

def test_npcs_by_tag_uses_tags_overwrite_when_set():
    df = pd.DataFrame([
        {"name": "Lydia", "base_id": "A2C94", "tags": "whiterun_hold,housecarl", "tags_overwrite": ""},
        {"name": "Mjoll", "base_id": "1336A", "tags": "riften_hold", "tags_overwrite": "  "},
        {"name": "Aela", "base_id": "1A696", "tags": "whiterun_hold", "tags_overwrite": "companion"},
        {"name": "Saadia", "base_id": "13BA4", "tags": "risaad’s_caravan", "tags_overwrite": float("nan")},
        {"name": "Nobody", "base_id": "1", "tags": float("nan"), "tags_overwrite": float("nan")},
    ])

    result = npcs_by_tag(df)

    assert result["whiterun_hold"] == ["Lydia (A2C94)"]
    assert result["companion"] == ["Aela (1A696)"]
    assert result["riften_hold"] == ["Mjoll (1336A)"]
    assert result["risaad's_caravan"] == ["Saadia (13BA4)"]
    assert npcs_by_tag(None) == {}
