import pytest
from src.llm.output.sentence_end_parser import sentence_end_parser
from src.llm.output.output_parser import sentence_generation_settings
from src.llm.sentence_content import SentenceTypeEnum, SentenceContent
from src.character_manager import Character
from unittest.mock import MagicMock


@pytest.fixture
def parser():
    return sentence_end_parser()

@pytest.fixture
def mock_character():
    char = MagicMock(spec=Character)
    char.name = "TestNPC"
    return char

@pytest.fixture
def settings(mock_character):
    return sentence_generation_settings(mock_character)


class TestBasicSentenceEnding:
    """Tests for basic sentence boundary detection at each punctuation type."""

    def test_cut_at_period(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that a sentence is cut at a period."""
        text = "Hello there. How are you?"
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "Hello there."
        assert rest == " How are you?"

    def test_cut_at_question_mark(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that a sentence is cut at a question mark."""
        text = "How are you? I am fine."
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "How are you?"
        assert rest == " I am fine."

    def test_cut_at_exclamation(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that a sentence is cut at an exclamation mark."""
        text = "Watch out! There's danger ahead."
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "Watch out!"
        assert rest == " There's danger ahead."

    def test_cut_at_semicolon(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that a sentence is cut at a semicolon."""
        text = "I came; I saw; I conquered."
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "I came;"
        assert rest == " I saw; I conquered."

    def test_no_sentence_end(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that no cut happens when there is no sentence-ending character."""
        text = "This has no ending"
        result, rest = parser.cut_sentence(text, settings)

        assert result is None
        assert rest == "This has no ending"


class TestMultiplePunctuation:
    """Tests for consecutive or mixed punctuation marks."""

    def test_multiple_exclamation_marks(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that multiple consecutive exclamation marks are consumed together."""
        text = "Stop right there!! I mean it."
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "Stop right there!!"
        assert rest == " I mean it."

    def test_multiple_question_marks(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that multiple consecutive question marks are consumed together."""
        text = "What?? Are you serious?"
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "What??"
        assert rest == " Are you serious?"

    def test_interrobang_style(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that mixed punctuation like ?! is consumed together."""
        text = "You did what?! That's incredible."
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "You did what?!"
        assert rest == " That's incredible."


class TestEllipsis:
    """Tests for ellipsis handling - consecutive dots should not trigger a sentence cut."""

    def test_ellipsis_mid_sentence(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that an ellipsis in the middle of a sentence does not cause a premature cut."""
        text = "I think... maybe we should go."
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "I think... maybe we should go."
        assert rest == ""

    def test_ellipsis_at_end(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that a sentence ending with only an ellipsis is not cut (no sentence boundary found)."""
        text = "I wonder..."
        result, rest = parser.cut_sentence(text, settings)

        assert result is None
        assert rest == "I wonder..."

    def test_ellipsis_followed_by_more_text(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that an ellipsis followed by more text does not cut at the ellipsis."""
        text = "Well... I suppose that's fine. Let's go."
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "Well... I suppose that's fine."
        assert rest == " Let's go."

    def test_two_dots_not_ellipsis(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that two consecutive dots are not treated as a sentence boundary."""
        text = "Hmm.. okay then."
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "Hmm.. okay then."
        assert rest == ""


class TestCJKPunctuation:
    """Tests for CJK (fullwidth) punctuation handling."""

    def test_cut_at_cjk_period(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that a sentence is cut at a CJK period (。)."""
        text = "こんにちは。元気ですか？"
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "こんにちは。"
        assert rest == "元気ですか？"

    def test_cut_at_cjk_question_mark(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test CJK question mark (？) handling.
        
        NFKC normalization converts ？ to ASCII ?, so the regex end-of-sentence
        characters are ASCII. The fullwidth ？ in the input text is not matched
        by the regex - the sentence runs until 。 instead.
        """
        text = "元気ですか？はい。"
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "元気ですか？はい。"
        assert rest == ""


class TestEdgeCases:
    """Tests for edge cases and known limitations."""

    def test_empty_string(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that an empty string returns no cut."""
        text = ""
        result, rest = parser.cut_sentence(text, settings)

        assert result is None
        assert rest == ""

    def test_just_ellipsis(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that just an ellipsis produces no sentence."""
        text = "..."
        result, rest = parser.cut_sentence(text, settings)

        assert result is None
        assert rest == "..."

    def test_just_other_punctuation(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test with only non-period punctuation characters."""
        text = "?!"
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "?!"
        assert rest == ""


class TestSentenceMetadata:
    """Tests for speaker, sentence type preservation and other output_parser methods."""

    def test_cut_preserves_speaker(self, parser: sentence_end_parser, settings: sentence_generation_settings, mock_character):
        """Test that the cut result preserves the speaker from settings."""
        text = "Hello there."
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.speaker == mock_character

    def test_cut_preserves_sentence_type(self, parser: sentence_end_parser, settings: sentence_generation_settings):
        """Test that the cut result preserves the sentence type from settings."""
        settings.sentence_type = SentenceTypeEnum.NARRATION
        text = "He walked away."
        result, rest = parser.cut_sentence(text, settings)

        assert result is not None
        assert result.sentence_type == SentenceTypeEnum.NARRATION

    def test_modify_sentence_content_passthrough(self, parser: sentence_end_parser, settings: sentence_generation_settings, mock_character):
        """Test that modify_sentence_content passes through content unchanged."""
        cut_content = SentenceContent(mock_character, "Hello.", SentenceTypeEnum.SPEECH)
        last_content = SentenceContent(mock_character, "Previous.", SentenceTypeEnum.SPEECH)

        result_cut, result_last = parser.modify_sentence_content(cut_content, last_content, settings)

        assert result_cut is cut_content
        assert result_last is last_content

    def test_get_cut_indicators_returns_all_end_chars(self, parser: sentence_end_parser):
        """Test that get_cut_indicators returns all configured end-of-sentence characters."""
        indicators = parser.get_cut_indicators()
        assert '.' in indicators
        assert '?' in indicators
        assert '!' in indicators
        assert ';' in indicators


class TestCustomEndChars:
    """Tests for parser initialized with custom end-of-sentence characters."""

    def test_custom_end_chars(self, settings: sentence_generation_settings):
        """Test parser with custom end-of-sentence characters."""
        custom_parser = sentence_end_parser(end_of_sentence_chars=['.', '|'])
        text = "Hello| World."
        result, rest = custom_parser.cut_sentence(text, settings)

        assert result is not None
        assert result.text == "Hello|"
        assert rest == " World."
