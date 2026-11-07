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


def test_bad_event_date_is_reported_not_raised(page):
    result = page.call("on_add_event", pd.DataFrame(columns=["Date", "Event"]), "Something", "someday")

    assert "isn't a date" in result[page.message]
