import pytest
from src.conversation.action import Action
from src.llm.output.change_character_parser import change_character_parser
from src.llm.output.output_parser import sentence_generation_settings
from src.character_manager import Character
from src.characters_manager import Characters


@pytest.fixture
def parser(example_characters_multi_npc: Characters) -> change_character_parser:
    return change_character_parser(example_characters_multi_npc)


@pytest.fixture
def parser_with_actions(example_characters_multi_npc: Characters) -> change_character_parser:
    actions = [
        Action(identifier="wave", name="Wave", keyword="Wave", description="", prompt_text="", requires_response=False, is_interrupting=False, one_on_one=True, multi_npc=True, radiant=True),
        Action(identifier="inventory", name="Inventory", keyword="Inventory", description="", prompt_text="", requires_response=False, is_interrupting=False, one_on_one=True, multi_npc=True, radiant=True),
        Action(identifier="attack", name="Attack", keyword="Attack", description="", prompt_text="", requires_response=False, is_interrupting=False, one_on_one=True, multi_npc=True, radiant=True),
    ]
    return change_character_parser(example_characters_multi_npc, actions)


@pytest.fixture
def settings(example_skyrim_npc_character: Character) -> sentence_generation_settings:
    return sentence_generation_settings(example_skyrim_npc_character)


class TestKnownCharacterSwitch:
    """Tests for switching to a character that is in the conversation."""

    def test_switch_to_known_character(self, parser: change_character_parser, settings: sentence_generation_settings):
        result, rest = parser.cut_sentence("Lydia: Hello there!", settings)
        assert result is None
        assert rest == " Hello there!"
        assert settings.current_speaker.name == "Lydia"

    def test_text_before_character_switch(self, parser: change_character_parser, settings: sentence_generation_settings):
        """When there is text before the character name, it should be returned as a sentence for the current speaker."""
        result, rest = parser.cut_sentence("Some text Lydia: Hello!", settings)
        assert result is not None
        assert result.text == "Some text"
        assert result.speaker.name == "Guard" # Current speaker says the prefix
        assert rest == "Lydia: Hello!" # Character switch re-queued

    def test_no_colon_in_text(self, parser: change_character_parser, settings: sentence_generation_settings):
        result, rest = parser.cut_sentence("Hello there", settings)
        assert result is None
        assert rest == "Hello there"

    def test_player_character_stops_generation(self, parser: change_character_parser, settings: sentence_generation_settings):
        result, rest = parser.cut_sentence("player: I should not say this", settings)
        assert result is None
        assert rest == ""
        assert settings.stop_generation is True

    def test_split_name_match(self, example_skyrim_player_character: Character):
        """Characters with multi-word names should be matchable by individual parts."""
        chars = Characters()
        npc = Character(base_id='0', ref_id='0', name='Svana Far-Shield', gender=1, race='Nord',
                        is_player_character=False, bio='', is_in_combat=False, is_enemy=False,
                        relationship_rank=0, is_generic_npc=False, ingame_voice_model='FemaleEvenToned',
                        tts_voice_model='FemaleEvenToned', csv_in_game_voice_model='FemaleEvenToned',
                        advanced_voice_model='FemaleEvenToned', voice_accent='en',
                        equipment=None, custom_character_values=None, llm_service='', llm_model='', tts_service='')
        chars.add_or_update_character(example_skyrim_player_character)
        chars.add_or_update_character(npc)
        p = change_character_parser(chars)
        s = sentence_generation_settings(npc)

        result, rest = p.cut_sentence("Svana: Welcome!", s)
        assert result is None
        assert rest == " Welcome!"
        assert s.current_speaker.name == "Svana Far-Shield"


class TestUnrecognizedCharacterDiscard:
    """Tests for discarding text when the LLM uses a character name not in the conversation."""

    def test_discard_unknown_single_name(self, parser: change_character_parser, settings: sentence_generation_settings):
        result, rest = parser.cut_sentence("Hulda: Another round!", settings)
        assert result is None
        assert rest == ""
        assert settings.stop_generation is True

    def test_discard_unknown_multi_word_name(self, parser: change_character_parser, settings: sentence_generation_settings):
        result, rest = parser.cut_sentence("Svana Far-Shield: Coming right up!", settings)
        assert result is None
        assert rest == ""
        assert settings.stop_generation is True

    def test_discard_unknown_lowercase_orc_name(self, parser: change_character_parser, settings: sentence_generation_settings):
        """Orc-style names with lowercase words (eg gro-Shub) should also be discarded."""
        result, rest = parser.cut_sentence("Urag gro-Shub: I have the book you need.", settings)
        assert result is None
        assert rest == ""
        assert settings.stop_generation is True

    def test_discard_stops_generation(self, parser: change_character_parser, settings: sentence_generation_settings):
        """Discarding an unrecognized name should stop generation so subsequent text is also dropped."""
        result, rest = parser.cut_sentence("Barkeeper: Here you go!", settings)
        assert settings.stop_generation is True
        assert rest == ""

    def test_discard_unknown_with_sentence_before(self, parser: change_character_parser, settings: sentence_generation_settings):
        """When there is dialogue text before the unknown name, the prefix is still discarded
        because the known-character endswith check doesn't match, so the whole thing is unrecognized."""
        result, rest = parser.cut_sentence("Another round please Hulda: Here you go!", settings)
        assert result is None
        assert rest == ""
        assert settings.stop_generation is True


class TestActionKeywordPassthrough:
    """Tests that action keywords are not incorrectly discarded as unrecognized character names."""

    def test_action_keyword_passes_through(self, parser_with_actions: change_character_parser, settings: sentence_generation_settings):
        result, rest = parser_with_actions.cut_sentence("Wave: Hello there!", settings)
        assert result is None
        assert rest == "Wave: Hello there!"
        assert settings.stop_generation is False

    def test_action_keyword_case_insensitive(self, parser_with_actions: change_character_parser, settings: sentence_generation_settings):
        result, rest = parser_with_actions.cut_sentence("wave: Hello there!", settings)
        assert result is None
        assert rest == "wave: Hello there!"
        assert settings.stop_generation is False


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_prefix_before_colon(self, parser: change_character_parser, settings: sentence_generation_settings):
        """A colon with nothing before it should pass through."""
        result, rest = parser.cut_sentence(": some text", settings)
        assert result is None
        assert rest == ": some text"
        assert settings.stop_generation is False

    def test_colon_only(self, parser: change_character_parser, settings: sentence_generation_settings):
        result, rest = parser.cut_sentence(":", settings)
        assert result is None
        assert rest == ":"
        assert settings.stop_generation is False
