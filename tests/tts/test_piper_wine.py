"""Tests for running Piper on macOS / Linux through Wine (build_piper_command / find_wine)."""
import os
from pathlib import Path
from unittest.mock import patch

from src.tts import piper as piper_module
from src.tts.piper import build_piper_command, find_wine

EXE = Path('/mods/MantellaSoftware/piper/piper.exe')


def test_windows_runs_piper_exe_directly():
    command, env = build_piper_command(EXE, system='Windows', environ={'PATH': 'x'})
    assert command == EXE
    assert env is None  # upstream behaviour: inherit the environment unchanged


def test_non_windows_wraps_piper_in_wine_with_dedicated_prefix():
    environ = {'MANTELLA_WINE': '/opt/wine/bin/wine', 'MANTELLA_WINEPREFIX': '/tmp/piper-prefix', 'PATH': '/usr/bin'}
    command, env = build_piper_command(EXE, system='Darwin', environ=environ)
    assert command == ['/opt/wine/bin/wine', str(EXE)]
    assert env['WINEPREFIX'] == '/tmp/piper-prefix'
    assert env['WINEDEBUG'] == '-all'
    assert env['PATH'] == '/usr/bin'


def test_default_wine_prefix_is_separate_from_game_prefix():
    _, env = build_piper_command(EXE, system='Linux', environ={'MANTELLA_WINE': 'wine'})
    assert env['WINEPREFIX'] == os.path.expanduser('~/Games/mantella-wine')


def test_find_wine_prefers_env_var():
    assert find_wine({'MANTELLA_WINE': '/custom/wine'}) == '/custom/wine'


def test_find_wine_uses_skyrimmt_bundle_when_present(tmp_path):
    bundled = tmp_path / 'wine'
    bundled.write_text('')
    with patch.object(piper_module, 'SKYRIMMT_WINE', str(bundled)):
        assert find_wine({}) == str(bundled)


def test_find_wine_falls_back_to_path(tmp_path):
    with patch.object(piper_module, 'SKYRIMMT_WINE', str(tmp_path / 'missing')), \
         patch('src.tts.piper.shutil.which', side_effect=lambda n: '/opt/homebrew/bin/wine' if n == 'wine' else None):
        assert find_wine({}) == '/opt/homebrew/bin/wine'


def test_find_wine_last_resort_is_plain_wine(tmp_path):
    with patch.object(piper_module, 'SKYRIMMT_WINE', str(tmp_path / 'missing')), \
         patch('src.tts.piper.shutil.which', return_value=None):
        assert find_wine({}) == 'wine'
