"""Tests for re-reading tag files without ending a conversation (the Tag Editor's Save, docs/tag_editor.md)."""
import pytest

from src.character_manager import Character
from src.config.config_loader import ConfigLoader
from src.config.definitions.llm_definitions import AutoQuestTagOutcomesEnum
from src.games.skyrim import Skyrim

TAG = "tag_editor_test_tag"
QUEST_TAG = "tag_editor_test_quest_tag"


def _write(path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _character(name: str, base_id: str, is_player: bool = False, bio: str = "Loaded bio.") -> Character:
    return Character(
        base_id=base_id,
        ref_id=base_id,
        name=name,
        gender=0,
        race='[Race <NordRace (00013746)>]',
        is_player_character=is_player,
        bio=bio,
        is_in_combat=False,
        is_enemy=False,
        relationship_rank=0,
        is_generic_npc=False,
        ingame_voice_model='MaleNord',
        tts_voice_model='MaleNord',
        csv_in_game_voice_model='MaleNord',
        advanced_voice_model='',
        voice_accent='en',
        equipment=None,
        custom_character_values={},
    )


@pytest.fixture
def setup(tmp_path, default_config: ConfigLoader):
    default_config.mod_path_base = str(tmp_path)
    default_config.save_folder = str(tmp_path)
    default_config.auto_quest_tag_outcomes = AutoQuestTagOutcomesEnum.STATIC
    _write(
        tmp_path / "SKSE" / "Plugins" / "MantellaSoftware" / "data" / "skyrim" / "character_overrides" / "npcs.csv",
        "name,base_id,race,bio,voice_model,skyrim_voice_folder,advanced_voice_model,voice_accent,tags\n"
        f"Tag Tester,0ABC01,Nord,Raw bio.,MaleNord,MaleNord,,en,{TAG}\n"
        "Other Npc,0ABC02,Nord,Other raw bio.,MaleNord,MaleNord,,en,some_unrelated_test_tag\n",
    )
    templates = tmp_path / "data" / "Skyrim" / "bio_templates" / "my_tags.csv"
    _write(templates, f"tag,description,code_1\n{TAG},Old text.,\n{QUEST_TAG},,getstagedone TagEditorQuest 10=1 AND getstagedone TagEditorQuest 20=1\n")
    return Skyrim(default_config), templates, default_config


def test_reload_picks_up_changed_files(setup):
    skyrim, templates, _ = setup
    assert "Old text." in skyrim.expand_bio_with_tags("Raw bio.", TAG)

    _write(templates, f"tag,description\n{TAG},New text.\n")
    skyrim.reload_bio_templates()

    assert "New text." in skyrim.expand_bio_with_tags("Raw bio.", TAG)


def test_version_changes_only_when_the_checks_change(setup):
    skyrim, templates, _ = setup

    _write(templates, f"tag,description,code_1\n{QUEST_TAG},,getstagedone TagEditorQuest 10=1 OR getstagedone TagEditorQuest 20=1\n")
    old_version, new_version = skyrim.reload_bio_templates()
    assert old_version == new_version  # AND -> OR: the same questions, Mantella does the comparing

    _write(templates, f"tag,description,code_1\n{QUEST_TAG},,getstagedone TagEditorQuest 30=1\n")
    old_version, new_version = skyrim.reload_bio_templates()
    assert old_version != new_version
    assert new_version == skyrim.quest_check_list.version


def test_version_stays_empty_when_quest_outcomes_are_off(setup):
    skyrim, templates, config = setup
    config.auto_quest_tag_outcomes = AutoQuestTagOutcomesEnum.OFF

    _write(templates, f"tag,description,code_1\n{QUEST_TAG},,getstagedone TagEditorQuest 30=1\n")
    old_version, new_version = skyrim.reload_bio_templates()

    assert old_version == new_version


def test_refresh_rebuilds_only_npcs_with_the_tag(setup):
    skyrim, templates, _ = setup
    tester = _character("Tag Tester", "0ABC01")
    other = _character("Other Npc", "0ABC02", bio="Other loaded bio.")
    player = _character("Dragonborn", "000007", is_player=True, bio="")

    _write(templates, f"tag,description\n{TAG},\"New text.\n- 1000: Something happened\"\n")
    skyrim.reload_bio_templates()
    refreshed = skyrim.refresh_characters_with_tag([tester, other, player], TAG)

    assert refreshed == ["Tag Tester"]
    assert tester.bio.startswith("Raw bio.")
    assert "New text." in tester.bio
    assert "Something happened" not in tester.bio
    assert tester.get_custom_character_value('mantella_dynamic_tag_events') == [(1000, "Something happened")]
    assert other.bio == "Other loaded bio."
    assert player.bio == ""


def test_refresh_clears_events_that_were_removed(setup):
    skyrim, templates, _ = setup
    tester = _character("Tag Tester", "0ABC01")
    tester.set_custom_character_value('mantella_dynamic_tag_events', [(1000, "Old event")])

    _write(templates, f"tag,description\n{TAG},No events now.\n")
    skyrim.reload_bio_templates()
    skyrim.refresh_characters_with_tag([tester], TAG)

    assert tester.get_custom_character_value('mantella_dynamic_tag_events') == []
