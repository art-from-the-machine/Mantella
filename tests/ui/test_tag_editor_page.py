"""Builds the Tag Editor tab and drives its handlers the way the UI would (docs/tag_editor.md)."""
import os

import gradio as gr
import pandas as pd
import pytest

from src.config.config_loader import ConfigLoader
from src.ui import settings_ui_constructor
from src.ui.tag_editor_page import build_tag_editor_page


class _Page:
    """The built tab: its handlers by name, and the components they read and write"""

    def __init__(self, config: ConfigLoader):
        with gr.Blocks() as self.blocks:
            build_tag_editor_page(config)
        self.handlers = {}
        for block_fn in self.blocks.fns:
            self.handlers[block_fn.fn.__name__] = block_fn
        save = self.handlers["on_save"]
        self.fields = save.inputs[1:]  # text, events, 10 outcome boxes, announce, notes
        self.dropdown = self.handlers["on_pick"].inputs[0]
        self.message = save.outputs[-1]
        self.snapshot_component = save.inputs[0]

    def call(self, name: str, *args):
        return self.handlers[name].fn(*args)


def _fields(text="", events=None, outcomes=None, announce=True, notes=""):
    table = pd.DataFrame(events or [], columns=["Date", "Event"])
    return (text, table, *(outcomes or [""] * 10), announce, notes)


@pytest.fixture
def page(tmp_path, default_config: ConfigLoader, monkeypatch):
    monkeypatch.setattr(settings_ui_constructor, "_game_manager_ref", None)
    default_config.save_folder = str(tmp_path)
    default_config.mod_path_base = str(tmp_path)
    return _Page(default_config)


def _snapshot(page: _Page, update: dict) -> dict:
    return update[page.snapshot_component]


def test_create_save_and_reload_a_new_tag(page, tmp_path):
    created = page.call("on_create", "tag_editor_page_test", {}, *_fields())
    snapshot = _snapshot(page, created)
    assert snapshot["tag"] == "tag_editor_page_test" and snapshot["is_new"]

    saved = page.call("on_save", snapshot, *_fields(text="Shared knowledge.", events=[["2026-11-06 14:30", "Something\nhappened"]], notes="mine"))

    path = os.path.join(str(tmp_path), "data", "Skyrim", "bio_templates", "tag_editor.csv")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    row = df[df["tag"] == "tag_editor_page_test"].iloc[0]
    assert row["description"].startswith("Shared knowledge.\n- ")
    assert row["description"].endswith(": Something happened")
    assert row["notes"] == "mine"
    assert "Saved" in saved[page.message]
    assert "hasn't connected to the game yet" in saved[page.message]

    reloaded = _snapshot(page, saved)
    assert reloaded["text"] == "Shared knowledge."
    assert reloaded["events"][0][1] == "Something happened"
    assert not reloaded["is_new"]


def test_nothing_to_save_when_nothing_changed(page):
    snapshot = _snapshot(page, page.call("on_create", "tag_editor_page_test", {}, *_fields()))
    page.call("on_save", snapshot, *_fields(text="Text."))
    snapshot = _snapshot(page, page.call("on_pick", "tag_editor_page_test", {}, *_fields()))

    result = page.call("on_save", snapshot, *_fields(text="Text."))

    assert result[page.message] == "Nothing to save."


def test_unsaved_changes_keep_the_current_tag(page):
    snapshot = _snapshot(page, page.call("on_create", "tag_editor_page_test", {}, *_fields()))
    page.call("on_save", snapshot, *_fields(text="Text."))
    snapshot = _snapshot(page, page.call("on_pick", "tag_editor_page_test", {}, *_fields()))

    result = page.call("on_pick", "warrior", snapshot, *_fields(text="Edited but not saved."))

    assert "unsaved changes to `tag_editor_page_test`" in result[page.message]
    assert page.snapshot_component not in result


def test_create_rejects_commas_and_existing_names(page):
    assert "commas" in page.call("on_create", "a,b", {}, *_fields())[page.message]
    snapshot = _snapshot(page, page.call("on_create", "tag_editor_page_test", {}, *_fields()))
    page.call("on_save", snapshot, *_fields(text="Text."))

    assert "already exists" in page.call("on_create", "tag_editor_page_test", {}, *_fields())[page.message]


def test_delete_needs_a_second_click_and_removes_only_personal_rows(page, tmp_path):
    snapshot = _snapshot(page, page.call("on_create", "tag_editor_page_test", {}, *_fields()))
    snapshot = _snapshot(page, page.call("on_save", snapshot, *_fields(text="Text.")))

    asked = page.call("on_delete", snapshot)
    assert "Confirm delete" in asked[page.message]
    path = os.path.join(str(tmp_path), "data", "Skyrim", "bio_templates", "tag_editor.csv")
    assert "tag_editor_page_test" in pd.read_csv(path, dtype=str)["tag"].tolist()

    deleted = page.call("on_confirm_delete", snapshot)

    assert "Deleted `tag_editor_page_test`" in deleted[page.message]
    assert "tag_editor_page_test" not in pd.read_csv(path, dtype=str, keep_default_na=False)["tag"].tolist()
    assert os.path.exists(path + ".bak")


@pytest.fixture
def page_with_mod_tag(tmp_path, default_config: ConfigLoader, monkeypatch):
    mod_folder = tmp_path / "SKSE" / "Plugins" / "MantellaSoftware" / "data" / "Skyrim" / "bio_templates"
    mod_folder.mkdir(parents=True)
    (mod_folder / "mod.csv").write_text("tag,description,notes\ntag_editor_mod_test,Mod text.,Mod note.\n", encoding="utf-8")
    monkeypatch.setattr(settings_ui_constructor, "_game_manager_ref", None)
    default_config.save_folder = str(tmp_path)
    default_config.mod_path_base = str(tmp_path)
    return _Page(default_config)


def test_override_then_back_to_original(page_with_mod_tag, tmp_path):
    page = page_with_mod_tag
    snapshot = _snapshot(page, page.call("on_pick", "tag_editor_mod_test", {}, *_fields()))
    assert snapshot["text"] == "Mod text."

    saved = page.call("on_save", snapshot, *_fields(text="My text.", notes="Mod note."))
    snapshot = _snapshot(page, saved)
    assert snapshot["text"] == "My text."
    mod_file = tmp_path / "SKSE" / "Plugins" / "MantellaSoftware" / "data" / "Skyrim" / "bio_templates" / "mod.csv"
    assert "Mod text." in mod_file.read_text(encoding="utf-8")

    assert "Confirm" in page.call("on_back", snapshot)[page.message]
    restored = page.call("on_confirm_back", snapshot)

    assert _snapshot(page, restored)["text"] == "Mod text."
    assert "back to the original" in restored[page.message]


def test_clearing_brings_back_the_mod_value_or_says_it_cant_be_blanked(page_with_mod_tag):
    page = page_with_mod_tag
    snapshot = _snapshot(page, page.call("on_pick", "tag_editor_mod_test", {}, *_fields()))
    snapshot = _snapshot(page, page.call("on_save", snapshot, *_fields(text="My text.", notes="Mod note.")))

    cleared = page.call("on_save", snapshot, *_fields(text="", notes=""))

    assert "the Mod value comes back" in cleared[page.message]
    assert "Notes comes from a Mod file and can't be blanked" in cleared[page.message]
    assert _snapshot(page, cleared)["text"] == "Mod text."


class _FakeGame:
    def __init__(self, folder: str, versions: tuple[str, str]):
        self.conversation_folder_path = folder
        self.character_df = pd.DataFrame([{"name": "Lydia", "base_id": "0A2C94", "tags": "tag_editor_page_test", "tags_overwrite": ""}])
        self.versions = versions
        self.refreshed_with = None

    def reload_bio_templates(self):
        return self.versions

    def refresh_characters_with_tag(self, characters, tag, tag_outcomes=None):
        self.refreshed_with = (characters, tag)
        return ["Lydia"]


class _FakeGameManager:
    def __init__(self, game, talk):
        self.game = game
        self.active_conversation = talk


class _FakeTalk:
    class context:
        world_id = "Player1"

        class npcs_in_conversation:
            @staticmethod
            def get_all_characters():
                return ["lydia character"]


@pytest.mark.parametrize("versions, paused", [(("v1", "v2"), True), (("v1", "v1"), False)])
def test_save_during_a_conversation_refreshes_npcs_and_warns_when_checks_pause(page, tmp_path, monkeypatch, versions, paused):
    game = _FakeGame(str(tmp_path), versions)
    monkeypatch.setattr(settings_ui_constructor, "_game_manager_ref", _FakeGameManager(game, _FakeTalk()))
    snapshot = _snapshot(page, page.call("on_create", "tag_editor_page_test", {}, *_fields()))

    saved = page.call("on_save", snapshot, *_fields(text="Text."))

    assert game.refreshed_with == (["lydia character"], "tag_editor_page_test")
    assert "Lydia, in the current conversation, use the new version from their next reply." in saved[page.message]
    assert ("quest progress won't be checked until the next conversation starts" in saved[page.message]) is paused
    npc_list = [component for component in page.handlers["on_save"].outputs if getattr(component, "label", "") == "NPCs with this tag"][0]
    assert saved[npc_list] == "Lydia (0A2C94)"


def test_delete_sees_files_edited_by_hand_after_the_tab_loaded(page, tmp_path):
    snapshot = _snapshot(page, page.call("on_create", "tag_editor_page_test", {}, *_fields()))
    snapshot = _snapshot(page, page.call("on_save", snapshot, *_fields(text="Text.")))
    by_hand = tmp_path / "data" / "Skyrim" / "bio_templates" / "by_hand.csv"
    by_hand.write_text("tag,description\ntag_editor_page_test,Also here.\n", encoding="utf-8")

    asked = page.call("on_delete", snapshot)
    assert "`by_hand.csv`" in asked[page.message]
    page.call("on_confirm_delete", snapshot)

    assert "tag_editor_page_test" not in pd.read_csv(by_hand, dtype=str, keep_default_na=False)["tag"].tolist()


def test_picking_a_tag_shows_files_edited_by_hand_and_clears_a_half_typed_event(page, tmp_path):
    personal = tmp_path / "data" / "Skyrim" / "bio_templates"
    personal.mkdir(parents=True, exist_ok=True)
    (personal / "by_hand.csv").write_text("tag,description\ntag_editor_by_hand,Written by hand.\n", encoding="utf-8")

    picked = page.call("on_pick", "tag_editor_by_hand", {}, *_fields())

    assert _snapshot(page, picked)["text"] == "Written by hand."
    new_event_text = page.handlers["on_add_event"].inputs[1]
    assert picked[new_event_text] == ""


def test_an_event_line_with_a_timestamp_windows_cant_show_still_opens(page, tmp_path):
    personal = tmp_path / "data" / "Skyrim" / "bio_templates"
    personal.mkdir(parents=True, exist_ok=True)
    (personal / "odd.csv").write_text("tag,description\ntag_editor_odd,\"Text.\n- 99999999999: Far future\"\n", encoding="utf-8")

    picked = page.call("on_pick", "tag_editor_odd", {}, *_fields())

    assert _snapshot(page, picked)["events"] == [["99999999999", "Far future"]]


def test_clearing_several_fields_in_another_personal_file_keeps_its_backup_intact(page, tmp_path):
    personal = tmp_path / "data" / "Skyrim" / "bio_templates"
    personal.mkdir(parents=True, exist_ok=True)
    original = "tag,description,potential_paste_1,notes\ntag_editor_two_files,,Outcome text.,A note.\n"
    (personal / "a.csv").write_text(original, encoding="utf-8")
    (personal / "b.csv").write_text("tag,description\ntag_editor_two_files,Text from b.\n", encoding="utf-8")
    snapshot = _snapshot(page, page.call("on_pick", "tag_editor_two_files", {}, *_fields()))
    outcomes = [""] * 10

    page.call("on_save", snapshot, *_fields(text="Text from b.", outcomes=outcomes, notes=""))

    assert (personal / "a.csv.bak").read_text(encoding="utf-8") == original
    assert pd.read_csv(personal / "a.csv", dtype=str, keep_default_na=False).to_dict("records") == [
        {"tag": "tag_editor_two_files", "description": "", "potential_paste_1": "", "notes": ""}
    ]


def test_saving_keeps_the_exact_timestamp_of_an_untouched_event(page, tmp_path):
    personal = tmp_path / "data" / "Skyrim" / "bio_templates"
    personal.mkdir(parents=True, exist_ok=True)
    # 01:30 local time in the hour repeated when clocks go back; its shown date maps back to a different moment
    timestamp = 1793518200
    (personal / "dst.csv").write_text(f"tag,description\ntag_editor_dst,\"Old.\n- {timestamp}: Event\"\n", encoding="utf-8")
    snapshot = _snapshot(page, page.call("on_pick", "tag_editor_dst", {}, *_fields()))

    page.call("on_save", snapshot, *_fields(text="New.", events=snapshot["events"]))

    description = pd.read_csv(personal / "dst.csv", dtype=str, keep_default_na=False)["description"][0]
    assert description == f"New.\n- {timestamp}: Event"


class _Selected:
    def __init__(self, row: int):
        self.index = [row, 2]


def test_search_then_click_a_result_opens_the_tag(page, tmp_path):
    personal = tmp_path / "data" / "Skyrim" / "bio_templates"
    personal.mkdir(parents=True, exist_ok=True)
    (personal / "mine.csv").write_text("tag,description,notes\ntag_editor_search_a,Knows about the Zebra Cult.,\ntag_editor_search_b,,zebra notes\n", encoding="utf-8")
    search = page.handlers["on_search"]
    results_table, result_tags, summary = search.outputs

    found = page.call("on_search", "ZEBRA")

    assert found[result_tags] == ["tag_editor_search_a", "tag_editor_search_b"]
    assert found[results_table].values.tolist() == [
        ["tag_editor_search_a", "Tag text", "Knows about the Zebra Cult.", "Personal, mine.csv"],
        ["tag_editor_search_b", "Notes", "zebra notes", "Personal, mine.csv"],
    ]
    assert "2 matches in 2 tags" in found[summary]

    clicked = page.call("on_result_select", found[result_tags], _Selected(1))
    assert clicked == "tag_editor_search_b"
    opened = page.call("on_open_result", clicked, {}, *_fields())
    assert _snapshot(page, opened)["tag"] == "tag_editor_search_b"
    assert page.call("on_open_result", None, {}, *_fields()) == {}


def test_search_with_nothing_found(page):
    search = page.handlers["on_search"]
    found = page.call("on_search", "no tag says this 12345")
    assert "Nothing found" in found[search.outputs[2]]


def test_bad_event_date_is_reported_not_raised(page):
    result = page.call("on_add_event", pd.DataFrame(columns=["Date", "Event"]), "Something", "someday")

    assert "isn't a date" in result[page.message]
