import configparser
import json
import os
from src.config.config_file_writer import ConfigFileWriter
from src.config.config_values import ConfigValues
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_group import ConfigValueGroup
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_string import ConfigValueString
from src.config.config_loader import ConfigLoader
from src.config.definitions.game_definitions import GameEnum


def _build_config(*config_values) -> ConfigValues:
    """Build a minimal ConfigValues containing the given config values in a single group."""
    config = ConfigValues()
    group = ConfigValueGroup("test_section", "Test Section", "A test section")
    for cv in config_values:
        group.add_config_value(cv)
    config.add_base_group(group)
    return config


def _write_and_read_back(tmp_path, config: ConfigValues) -> configparser.ConfigParser:
    """Write config values to an INI file and read them back with configparser."""
    ini_path = str(tmp_path / "test.ini")
    writer = ConfigFileWriter()
    writer.write(ini_path, config)
    reader = configparser.ConfigParser()
    reader.read(ini_path, encoding='utf-8')
    return reader


def _round_trip_string(tmp_path, identifier: str, value: str) -> str:
    """Write a ConfigValueString to disk and read it back through the same decode path as ConfigLoader."""
    cv = ConfigValueString(identifier, "Test", "desc", "default")
    cv.parse(value)
    config = _build_config(cv)

    reader = _write_and_read_back(tmp_path, config)
    raw = reader.get("test_section", identifier)
    unescaped = ConfigFileWriter.unescape_hash_symbols(raw)
    # Mirror ConfigLoader: try JSON decode first for string values
    try:
        decoded = json.loads(unescaped)
        if isinstance(decoded, str):
            return decoded
    except Exception:
        pass
    return unescaped


class TestHashSymbolEscaping:
    def test_single_hash_survives_round_trip(self, tmp_path):
        value = "Use # for headers"
        result = _round_trip_string(tmp_path, "prompt", value)
        assert result == value

    def test_markdown_heading_survives_round_trip(self, tmp_path):
        value = "## Instructions\nBe helpful."
        result = _round_trip_string(tmp_path, "prompt", value)
        assert result == value

    def test_multiple_hashes_in_multiline(self, tmp_path):
        value = "# Section 1\nContent\n## Section 2\nMore content\n### Section 3"
        result = _round_trip_string(tmp_path, "prompt", value)
        assert result == value

    def test_hash_in_single_line_value(self, tmp_path):
        result = _round_trip_string(tmp_path, "tag", "C#")
        assert result == "C#"

    def test_escape_unescape_are_inverses(self):
        original = "## Heading\n# Another\nNo hash here"
        assert ConfigFileWriter.unescape_hash_symbols(ConfigFileWriter.escape_hash_symbols(original)) == original


class TestMultilineStringPreservation:
    def test_multiline_value_survives_round_trip(self, tmp_path):
        value = "Line 1\nLine 2\nLine 3"
        result = _round_trip_string(tmp_path, "prompt", value)
        assert result == value

    def test_indented_multiline_value_preserves_indentation(self, tmp_path):
        value = "Top level\n    Indented line\n        Double indented"
        result = _round_trip_string(tmp_path, "prompt", value)
        assert result == value

    def test_multiline_with_hashes_and_indentation(self, tmp_path):
        value = "# Role\nYou are a guard.\n## Rules\n    - Stay in character\n    - Be concise\n### Notes\nRemember your name is {name}."
        result = _round_trip_string(tmp_path, "prompt", value)
        assert result == value

    def test_empty_lines_in_multiline_preserved(self, tmp_path):
        value = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
        result = _round_trip_string(tmp_path, "prompt", value)
        assert result == value


class TestValueTypeRoundTrips:
    def test_simple_string(self, tmp_path):
        result = _round_trip_string(tmp_path, "name", "Lydia")
        assert result == "Lydia"

    def test_empty_string(self, tmp_path):
        cv = ConfigValueString("name", "Test", "desc", "default")
        cv.parse("")
        config = _build_config(cv)
        reader = _write_and_read_back(tmp_path, config)
        assert reader.get("test_section", "name") == ""

    def test_int_round_trip(self, tmp_path):
        cv = ConfigValueInt("count", "Count", "desc", 5, 0, 100)
        cv.parse("42")
        config = _build_config(cv)
        reader = _write_and_read_back(tmp_path, config)
        assert reader.get("test_section", "count") == "42"

    def test_float_round_trip(self, tmp_path):
        cv = ConfigValueFloat("rate", "Rate", "desc", 1.0, 0.0, 10.0)
        cv.parse("3.14")
        config = _build_config(cv)
        reader = _write_and_read_back(tmp_path, config)
        assert reader.get("test_section", "rate") == "3.14"

    def test_bool_round_trip(self, tmp_path):
        cv = ConfigValueBool("enabled", "Enabled", "desc", False)
        cv.parse("True")
        config = _build_config(cv)
        reader = _write_and_read_back(tmp_path, config)
        assert reader.get("test_section", "enabled") == "True"

    def test_multiple_values_in_one_group(self, tmp_path):
        cv_str = ConfigValueString("name", "Name", "desc", "default")
        cv_str.parse("Lydia")
        cv_int = ConfigValueInt("count", "Count", "desc", 5, 0, 100)
        cv_int.parse("10")
        cv_bool = ConfigValueBool("enabled", "Enabled", "desc", True)
        cv_bool.parse("False")

        config = _build_config(cv_str, cv_int, cv_bool)
        reader = _write_and_read_back(tmp_path, config)
        assert reader.get("test_section", "name") == "Lydia"
        assert reader.get("test_section", "count") == "10"
        assert reader.get("test_section", "enabled") == "False"


class TestBackup:
    def test_backup_creates_numbered_file(self, tmp_path):
        ini_path = str(tmp_path / "test.ini")
        cv = ConfigValueString("key", "Key", "desc", "val")
        config = _build_config(cv)

        writer = ConfigFileWriter()
        writer.write(ini_path, config)

        # Now write again with backup
        writer.write(ini_path, config, create_back_up_configini=True)
        assert os.path.exists(str(tmp_path / "config_backup_0.ini"))

    def test_backup_increments_counter(self, tmp_path):
        ini_path = str(tmp_path / "test.ini")
        cv = ConfigValueString("key", "Key", "desc", "val")
        config = _build_config(cv)

        writer = ConfigFileWriter()
        writer.write(ini_path, config)

        writer.write(ini_path, config, create_back_up_configini=True)
        writer.write(ini_path, config, create_back_up_configini=True)
        assert os.path.exists(str(tmp_path / "config_backup_0.ini"))
        assert os.path.exists(str(tmp_path / "config_backup_1.ini"))


class TestConfigLoaderRoundTrip:
    def test_prompt_with_hashes_survives_config_loader_round_trip(self, tmp_path):
        """A prompt containing markdown headers written through ConfigLoader survives reload."""
        prompt_with_hashes = "# Role\nYou are {name} in {location}.\n## Rules\n- Stay in character\n- Be concise"

        loader = ConfigLoader(mygame_folder_path=str(tmp_path), game_override=GameEnum.SKYRIM)
        # Modify the skyrim_prompt to contain hashes
        prompt_def = loader.definitions.get_config_value_definition("skyrim_prompt")
        prompt_def.parse(prompt_with_hashes)

        # Force a write
        writer = ConfigFileWriter()
        writer.write(str(tmp_path / "config.ini"), loader.definitions)

        # Reload and verify
        loader2 = ConfigLoader(mygame_folder_path=str(tmp_path), game_override=GameEnum.SKYRIM)
        reloaded_prompt = loader2.definitions.get_config_value_definition("skyrim_prompt")
        assert reloaded_prompt.value == prompt_with_hashes
