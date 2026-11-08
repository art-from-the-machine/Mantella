"""Tests for BioTemplateManager remembering which file each tag value came from (docs/tag_editor.md)."""
import os
from types import SimpleNamespace

import pandas as pd

from src.bio_template_manager import LAYER_BASE, LAYER_MOD, LAYER_PERSONAL, BioTemplateManager


def _write_csv(folder: str, filename: str, rows: list[dict]) -> str:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    pd.DataFrame(rows).to_csv(path, index=False, encoding='utf-8')
    return path


def _make_manager(tmp_path) -> tuple[BioTemplateManager, dict[str, str]]:
    base = str(tmp_path / "base")
    mod = str(tmp_path / "mods" / "SKSE" / "Plugins" / "MantellaSoftware" / "data" / "Skyrim" / "bio_templates")
    personal = str(tmp_path / "save" / "data" / "Skyrim" / "bio_templates")
    paths = {
        "base": _write_csv(base, "bio_templates.csv", [
            {"tag": "whiterun_hold", "description": "Base text.", "code_1": "getdead 0D7505=1", "notes": "base note"},
            {"tag": "base_only", "description": "Only in base."},
        ]),
        "mod": _write_csv(mod, "mod.csv", [
            {"tag": "whiterun_hold", "description": "Mod text.", "potential_paste_1": "Mod outcome."},
        ]),
        "personal": _write_csv(personal, "my_tags.csv", [
            {"tag": "whiterun_hold", "description": "My text.", "announce": "no"},
            {"tag": "personal_only", "description": "Only mine."},
        ]),
    }
    config = SimpleNamespace(mod_path_base=str(tmp_path / "mods"), save_folder=str(tmp_path / "save"), enable_character_tag_reading=True)
    return BioTemplateManager(base, config, "Skyrim"), paths


def test_last_value_wins_and_every_source_is_kept(tmp_path):
    manager, paths = _make_manager(tmp_path)

    description = manager.sources["whiterun_hold"]["description"]
    assert description == [
        (LAYER_BASE, paths["base"], "Base text."),
        (LAYER_MOD, paths["mod"], "Mod text."),
        (LAYER_PERSONAL, paths["personal"], "My text."),
    ]
    assert manager.templates["whiterun_hold"] == description[-1][2]


def test_cells_come_from_the_file_that_filled_them(tmp_path):
    manager, paths = _make_manager(tmp_path)

    sources = manager.sources["whiterun_hold"]
    assert sources["code_1"] == [(LAYER_BASE, paths["base"], "getdead 0D7505=1")]
    assert sources["potential_paste_1"] == [(LAYER_MOD, paths["mod"], "Mod outcome.")]
    assert sources["announce"] == [(LAYER_PERSONAL, paths["personal"], "no")]
    assert "potential_paste_2" not in sources


def test_notes_are_loaded(tmp_path):
    manager, paths = _make_manager(tmp_path)

    assert manager.sources["whiterun_hold"]["notes"] == [(LAYER_BASE, paths["base"], "base note")]


def test_files_with_tag_lists_every_file_with_a_row(tmp_path):
    manager, paths = _make_manager(tmp_path)

    assert manager.files_with_tag["whiterun_hold"] == [
        (LAYER_BASE, paths["base"]),
        (LAYER_MOD, paths["mod"]),
        (LAYER_PERSONAL, paths["personal"]),
    ]
    assert manager.files_with_tag["base_only"] == [(LAYER_BASE, paths["base"])]
    assert manager.files_with_tag["personal_only"] == [(LAYER_PERSONAL, paths["personal"])]


def test_a_row_with_no_cells_still_counts_as_a_file_with_the_tag(tmp_path):
    manager, paths = _make_manager(tmp_path)
    personal = os.path.dirname(paths["personal"])
    empty_row = _write_csv(personal, "tag_editor.csv", [{"tag": "new_tag", "description": ""}])

    manager.reload_templates()

    assert manager.files_with_tag["new_tag"] == [(LAYER_PERSONAL, empty_row)]
    assert "new_tag" not in manager.sources


def test_a_valid_utf8_file_is_read_as_utf8_whatever_the_guess(tmp_path, monkeypatch):
    base = tmp_path / "base"
    base.mkdir()
    (base / "bio_templates.csv").write_text("tag,description\ncafe,Café ’quoted’.\n", encoding="utf-8")
    monkeypatch.setattr("src.utils.get_file_encoding", lambda _: "Windows-1252")

    manager = BioTemplateManager(str(base), None, "Skyrim")

    assert manager.templates["cafe"] == "Café ’quoted’."


def test_reload_starts_over(tmp_path):
    manager, paths = _make_manager(tmp_path)
    os.remove(paths["personal"])

    manager.reload_templates()

    assert "personal_only" not in manager.files_with_tag
    assert manager.sources["whiterun_hold"]["description"][-1] == (LAYER_MOD, paths["mod"], "Mod text.")
