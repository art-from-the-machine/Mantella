import pytest
import os
import pandas as pd
from src.bio_template_manager import BioTemplateManager
from src import utils


def _write_csv(path, rows):
    """Write a simple two-column CSV (tag, description) to *path*."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('tag,description\n')
        for tag, desc in rows:
            f.write(f'{tag},{desc}\n')


class TestTemplateLoading:
    def test_load_from_single_csv(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('fighter', 'A strong fighter.'),
            ('healer', 'A gifted healer.'),
        ])

        mgr = BioTemplateManager(base_folder)
        assert mgr.get_template('fighter') == 'A strong fighter.'
        assert mgr.get_template('healer') == 'A gifted healer.'
        assert mgr.get_template_count() == 2

    def test_load_from_multiple_csvs(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'base.csv'), [('a', 'desc_a')])
        _write_csv(os.path.join(base_folder, 'extra.csv'), [('b', 'desc_b')])

        mgr = BioTemplateManager(base_folder)
        assert mgr.get_template('a') == 'desc_a'
        assert mgr.get_template('b') == 'desc_b'

    def test_ignores_non_csv_files(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'tags.csv'), [('tag1', 'desc1')])
        # Write a .txt file that should be ignored
        with open(os.path.join(base_folder, 'notes.txt'), 'w') as f:
            f.write('tag,description\nhidden,should be ignored\n')

        mgr = BioTemplateManager(base_folder)
        assert mgr.get_template('tag1') == 'desc1'
        assert mgr.get_template('hidden') is None

    def test_tags_stored_lowercase(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('Warrior', 'Fighter description.'),
            ('MAGE', 'Mage description.'),
        ])

        mgr = BioTemplateManager(base_folder)
        assert mgr.get_template('warrior') == 'Fighter description.'
        assert mgr.get_template('mage') == 'Mage description.'
        assert mgr.get_template('Warrior') == 'Fighter description.'

    def test_missing_base_folder_loads_nothing(self, tmp_path):
        """If base folder doesn't exist, no templates are loaded."""
        base_folder = str(tmp_path / 'nonexistent')
        mgr = BioTemplateManager(base_folder)
        assert mgr.get_template_count() == 0


class TestCascadingOverrides:
    def test_mod_override_takes_precedence_over_base(self, tmp_path):
        base_folder = str(tmp_path / 'base' / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'Base warrior.'),
            ('mage', 'Base mage.'),
        ])

        mod_path_base = str(tmp_path / 'mod')
        mod_folder = os.path.join(mod_path_base, 'SKSE', 'Plugins', 'MantellaSoftware', 'data', 'Skyrim', 'bio_templates')
        os.makedirs(mod_folder, exist_ok=True)
        _write_csv(os.path.join(mod_folder, 'bio_templates.csv'), [
            ('warrior', 'Mod warrior override.'),
        ])

        mgr = BioTemplateManager(base_folder, mod_path_base=mod_path_base)
        assert mgr.get_template('warrior') == 'Mod warrior override.'
        assert mgr.get_template('mage') == 'Base mage.'

    def test_personal_override_takes_precedence_over_mod(self, tmp_path):
        base_folder = str(tmp_path / 'base' / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'Base warrior.'),
        ])

        mod_path_base = str(tmp_path / 'mod')
        save_folder = str(tmp_path / 'save')

        mod_folder = os.path.join(mod_path_base, 'SKSE', 'Plugins', 'MantellaSoftware', 'data', 'Skyrim', 'bio_templates')
        os.makedirs(mod_folder, exist_ok=True)
        _write_csv(os.path.join(mod_folder, 'bio_templates.csv'), [
            ('warrior', 'Mod warrior.'),
        ])

        personal_folder = os.path.join(save_folder, 'data', 'Skyrim', 'bio_templates')
        os.makedirs(personal_folder, exist_ok=True)
        _write_csv(os.path.join(personal_folder, 'bio_templates.csv'), [
            ('warrior', 'Personal warrior.'),
        ])

        mgr = BioTemplateManager(base_folder, mod_path_base=mod_path_base, save_folder=save_folder, game_name="Skyrim")
        assert mgr.get_template('warrior') == 'Personal warrior.'

    def test_override_folders_not_required_to_exist(self, tmp_path):
        """If mod/personal override folders don't exist, only base templates load."""
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [('tag1', 'desc1')])

        mgr = BioTemplateManager(base_folder, mod_path_base=str(tmp_path / 'mod'), save_folder=str(tmp_path / 'save'), game_name="Skyrim")
        assert mgr.get_template('tag1') == 'desc1'


class TestExpandBioWithTags:
    def test_single_tag(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'Known for combat prowess.'),
        ])
        mgr = BioTemplateManager(base_folder)

        result = mgr.expand_bio_with_tags('Base bio.', 'warrior')
        assert 'Base bio.' in result
        assert 'Known for combat prowess.' in result

    def test_multiple_tags(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
            ('nord', 'A northerner.'),
        ])
        mgr = BioTemplateManager(base_folder)

        result = mgr.expand_bio_with_tags('Base bio.', 'warrior,nord')
        assert 'A fighter.' in result
        assert 'A northerner.' in result

    def test_missing_tag_ignored(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
        ])
        mgr = BioTemplateManager(base_folder)

        result = mgr.expand_bio_with_tags('Base bio.', 'warrior,nonexistent')
        assert 'A fighter.' in result
        assert 'nonexistent' not in result

    def test_all_tags_missing_returns_original_bio(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
        ])
        mgr = BioTemplateManager(base_folder)

        result = mgr.expand_bio_with_tags('Base bio.', 'nonexistent1,nonexistent2')
        assert result == 'Base bio.'

    def test_empty_tags_string(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [('warrior', 'desc')])
        mgr = BioTemplateManager(base_folder)

        assert mgr.expand_bio_with_tags('Bio.', '') == 'Bio.'

    def test_none_tags(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [('warrior', 'desc')])
        mgr = BioTemplateManager(base_folder)

        assert mgr.expand_bio_with_tags('Bio.', None) == 'Bio.'

    def test_nan_tags(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [('warrior', 'desc')])
        mgr = BioTemplateManager(base_folder)

        assert mgr.expand_bio_with_tags('Bio.', float('nan')) == 'Bio.'

    def test_pandas_nan_tags(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [('warrior', 'desc')])
        mgr = BioTemplateManager(base_folder)

        assert mgr.expand_bio_with_tags('Bio.', pd.NA) == 'Bio.'

    def test_whitespace_only_tags(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [('warrior', 'desc')])
        mgr = BioTemplateManager(base_folder)

        assert mgr.expand_bio_with_tags('Bio.', '   ') == 'Bio.'

    def test_tags_with_extra_whitespace(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
            ('mage', 'A caster.'),
        ])
        mgr = BioTemplateManager(base_folder)

        result = mgr.expand_bio_with_tags('Bio.', '  warrior , mage  ')
        assert 'A fighter.' in result
        assert 'A caster.' in result


class TestTagsOverwrite:
    def test_overwrite_replaces_tags(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
            ('mage', 'A caster.'),
        ])
        mgr = BioTemplateManager(base_folder)

        result = mgr.expand_bio_with_tags('Bio.', 'warrior', tags_overwrite='mage')
        assert 'A caster.' in result
        assert 'A fighter.' not in result

    def test_empty_overwrite_uses_original_tags(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
        ])
        mgr = BioTemplateManager(base_folder)

        result = mgr.expand_bio_with_tags('Bio.', 'warrior', tags_overwrite='')
        assert 'A fighter.' in result

    def test_nan_overwrite_uses_original_tags(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
        ])
        mgr = BioTemplateManager(base_folder)

        result = mgr.expand_bio_with_tags('Bio.', 'warrior', tags_overwrite=float('nan'))
        assert 'A fighter.' in result

    def test_none_overwrite_uses_original_tags(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
        ])
        mgr = BioTemplateManager(base_folder)

        result = mgr.expand_bio_with_tags('Bio.', 'warrior', tags_overwrite=None)
        assert 'A fighter.' in result


class TestCaseInsensitivity:
    def test_lookup_is_case_insensitive(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
        ])
        mgr = BioTemplateManager(base_folder)

        assert mgr.get_template('Warrior') == 'A fighter.'
        assert mgr.get_template('WARRIOR') == 'A fighter.'
        assert mgr.get_template('warrior') == 'A fighter.'

    def test_expand_with_mixed_case_tags(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
            ('nord', 'A northerner.'),
        ])
        mgr = BioTemplateManager(base_folder)

        result = mgr.expand_bio_with_tags('Bio.', 'Warrior,NORD')
        assert 'A fighter.' in result
        assert 'A northerner.' in result


class TestConfigGating:
    def test_disabled_config_returns_original_bio(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
        ])

        mgr = BioTemplateManager(base_folder, enable_tag_reading=False, game_name="Skyrim")

        result = mgr.expand_bio_with_tags('Original bio.', 'warrior')
        assert result == 'Original bio.'

    def test_enabled_config_expands_bio(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('warrior', 'A fighter.'),
        ])

        mgr = BioTemplateManager(base_folder, enable_tag_reading=True, game_name="Skyrim")

        result = mgr.expand_bio_with_tags('Original bio.', 'warrior')
        assert 'A fighter.' in result


class TestUtilityMethods:
    def test_list_all_tags_sorted(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('mage', 'desc'),
            ('archer', 'desc'),
            ('warrior', 'desc'),
        ])
        mgr = BioTemplateManager(base_folder)
        assert mgr.list_all_tags() == ['archer', 'mage', 'warrior']

    def test_get_template_count(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [
            ('a', 'desc_a'),
            ('b', 'desc_b'),
            ('c', 'desc_c'),
        ])
        mgr = BioTemplateManager(base_folder)
        assert mgr.get_template_count() == 3

    def test_get_template_returns_none_for_unknown(self, tmp_path):
        base_folder = str(tmp_path / 'bio_templates')
        os.makedirs(base_folder, exist_ok=True)
        _write_csv(os.path.join(base_folder, 'bio_templates.csv'), [('a', 'desc')])
        mgr = BioTemplateManager(base_folder)
        assert mgr.get_template('zzz_unknown') is None
