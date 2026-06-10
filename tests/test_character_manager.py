from src.character_manager import Character, get_genders_text, get_races_text, get_genders_and_races_text


class TestGenderString:
    def test_male(self, example_skyrim_npc_character: Character):
        assert example_skyrim_npc_character.gender_string == "male"

    def test_female(self, another_example_skyrim_npc_character: Character):
        assert another_example_skyrim_npc_character.gender_string == "female"


class TestDisplayRace:
    def test_parses_raw_game_race_string(self, example_skyrim_npc_character: Character):
        assert example_skyrim_npc_character.race == '[Race <ImperialRace (00013744)>]'
        assert example_skyrim_npc_character.display_race == 'Imperial'

    def test_returns_plain_race_unchanged(self, another_example_skyrim_npc_character: Character):
        assert another_example_skyrim_npc_character.display_race == 'Nord'


class TestCharacterListDescriptions:
    """Tests for the natural language descriptions of a list of characters used to fill prompt variables."""

    def test_empty_list_returns_empty_strings(self):
        assert get_genders_text([]) == ""
        assert get_races_text([]) == ""
        assert get_genders_and_races_text([]) == ""

    def test_single_character_returns_one_sentence(self, example_skyrim_npc_character: Character):
        characters = [example_skyrim_npc_character]
        assert get_genders_text(characters) == "Guard is a male."
        assert get_races_text(characters) == "Guard is a Imperial."
        assert get_genders_and_races_text(characters) == "Guard is a male Imperial."

    def test_multiple_characters_return_one_sentence_each(self, example_skyrim_npc_character: Character, another_example_skyrim_npc_character: Character):
        characters = [example_skyrim_npc_character, another_example_skyrim_npc_character]
        assert get_genders_text(characters) == "Guard is a male. Lydia is a female."
        assert get_races_text(characters) == "Guard is a Imperial. Lydia is a Nord."
        assert get_genders_and_races_text(characters) == "Guard is a male Imperial. Lydia is a female Nord."
