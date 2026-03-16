import pytest
from src.llm.output.sentence_accumulator import sentence_accumulator


@pytest.fixture
def default_indicators():
    return ['.', '?', '!', ';']

@pytest.fixture
def accumulator(default_indicators):
    return sentence_accumulator(default_indicators)


class TestBasicAccumulation:
    """Tests for basic sentence detection from accumulated text."""

    def test_no_sentence_before_accumulation(self, accumulator: sentence_accumulator):
        """Test that a fresh accumulator has no sentences."""
        assert accumulator.has_next_sentence() is False

    def test_accumulate_incomplete_sentence(self, accumulator: sentence_accumulator):
        """Test that incomplete text without punctuation does not produce a sentence."""
        accumulator.accumulate("Hello there")
        assert accumulator.has_next_sentence() is False

    def test_accumulate_complete_sentence_period(self, accumulator: sentence_accumulator):
        """Test that text ending with a period produces a sentence."""
        accumulator.accumulate("Hello there.")
        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "Hello there."

    def test_accumulate_complete_sentence_question(self, accumulator: sentence_accumulator):
        """Test that text ending with a question mark produces a sentence."""
        accumulator.accumulate("How are you?")
        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "How are you?"

    def test_accumulate_complete_sentence_exclamation(self, accumulator: sentence_accumulator):
        """Test that text ending with an exclamation mark produces a sentence."""
        accumulator.accumulate("Watch out!")
        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "Watch out!"

    def test_accumulate_complete_sentence_semicolon(self, accumulator: sentence_accumulator):
        """Test that text ending with a semicolon produces a sentence."""
        accumulator.accumulate("I came;")
        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "I came;"


class TestTokenByTokenAccumulation:
    """Tests for token-by-token (streaming) sentence accumulation."""

    def test_accumulate_token_by_token(self, accumulator: sentence_accumulator):
        """Test accumulating a sentence one token at a time."""
        tokens = ["Hello", " there", "."]
        for token in tokens:
            accumulator.accumulate(token)

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "Hello there."

    def test_accumulate_token_by_token_two_sentences(self, accumulator: sentence_accumulator):
        """Test accumulating two sentences token-by-token."""
        tokens = ["Hello", ".", " How", " are", " you", "?"]
        for token in tokens:
            accumulator.accumulate(token)

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "Hello."

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == " How are you?"

    def test_accumulate_token_by_token_trailing_text(self, accumulator: sentence_accumulator):
        """Test that trailing text after a sentence is preserved for next accumulation."""
        accumulator.accumulate("Hello. World")

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "Hello."

        # "World" is still buffered but not a complete sentence
        assert accumulator.has_next_sentence() is False

        # Complete the second sentence
        accumulator.accumulate("!")
        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == " World!"

    def test_sentence_split_across_accumulates(self, accumulator: sentence_accumulator):
        """Test a sentence that arrives split across multiple accumulate calls."""
        accumulator.accumulate("The quick brown ")
        assert accumulator.has_next_sentence() is False

        accumulator.accumulate("fox jumps over the lazy ")
        assert accumulator.has_next_sentence() is False

        accumulator.accumulate("dog.")
        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "The quick brown fox jumps over the lazy dog."


class TestMultipleSentences:
    """Tests for multiple sentences and consecutive/mixed punctuation."""

    def test_multiple_sentences_in_one_accumulate(self, accumulator: sentence_accumulator):
        """Test that multiple sentences accumulated at once can be retrieved one by one."""
        accumulator.accumulate("First. Second! Third?")

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "First."

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == " Second!"

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == " Third?"

        assert accumulator.has_next_sentence() is False

    def test_multiple_exclamation_marks(self, accumulator: sentence_accumulator):
        """Test that multiple consecutive exclamation marks are consumed together."""
        accumulator.accumulate("Stop!! I mean it.")

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "Stop!!"

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == " I mean it."

    def test_interrobang(self, accumulator: sentence_accumulator):
        """Test that mixed punctuation like ?! is consumed together."""
        accumulator.accumulate("Really?! Yes.")

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "Really?!"


class TestEllipsis:
    """Tests for ellipsis handling. Consecutive dots should not trigger a sentence cut."""

    def test_ellipsis_mid_sentence(self, accumulator: sentence_accumulator):
        """Test that an ellipsis in the middle of text does not cause a premature cut."""
        accumulator.accumulate("I think... maybe we should go.")

        # Ellipsis is skipped; the whole text is one sentence ending at the final period
        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "I think... maybe we should go."

        assert accumulator.has_next_sentence() is False

    def test_ellipsis_at_end(self, accumulator: sentence_accumulator):
        """Test that text ending with only an ellipsis does not produce a sentence."""
        accumulator.accumulate("I wonder...")

        # Ellipsis alone is not a sentence boundary - text stays buffered
        assert accumulator.has_next_sentence() is False

    def test_ellipsis_at_end_then_more_text(self, accumulator: sentence_accumulator):
        """Test that buffered ellipsis text is emitted once a real sentence end arrives."""
        accumulator.accumulate("I wonder...")
        assert accumulator.has_next_sentence() is False

        accumulator.accumulate(" but okay.")
        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "I wonder... but okay."

    def test_ellipsis_created_token_by_token(self, accumulator: sentence_accumulator):
        """Test that ellipsis text is parsed correctly when accumulated token by token."""
        accumulator.accumulate("I wonder.")
        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "I wonder."

        accumulator.accumulate(".")
        assert accumulator.has_next_sentence() is False

        accumulator.accumulate(".")
        assert accumulator.has_next_sentence() is False

        accumulator.accumulate(" but okay.")
        assert accumulator.has_next_sentence() is True
        # The leading period tokens are not ideal, but the next sentence should still be preserved correctly
        assert accumulator.get_next_sentence() == ".. but okay."

    def test_two_dots(self, accumulator: sentence_accumulator):
        """Test that two consecutive dots are not treated as a sentence boundary."""
        accumulator.accumulate("Hmm.. okay.")

        # Two dots: each period is adjacent to the other, so neither is standalone
        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "Hmm.. okay."


class TestCleaning:
    """Tests for the cleaning behavior applied during accumulation."""

    def test_newlines_cleaned(self, accumulator: sentence_accumulator):
        """Test that newlines in accumulated text are replaced with spaces."""
        accumulator.accumulate("Hello\nthere.")

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "Hello there."

    def test_crlf_cleaned(self, accumulator: sentence_accumulator):
        """Test that CRLF in accumulated text is replaced with a space."""
        accumulator.accumulate("Hello\r\nthere.")

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "Hello there."

    def test_brackets_replaced(self, accumulator: sentence_accumulator):
        """Test that square and curly brackets are replaced with parentheses."""
        accumulator.accumulate("[Hello] {world}.")

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "(Hello) (world)."

    def test_double_asterisks_converted(self, accumulator: sentence_accumulator):
        """Test that double asterisks are converted to single asterisks."""
        accumulator.accumulate("I am **very** angry.")

        assert accumulator.has_next_sentence() is True
        assert accumulator.get_next_sentence() == "I am *very* angry."


class TestEdgeCases:
    """Tests for edge cases and state management."""

    def test_empty_accumulate(self, accumulator: sentence_accumulator):
        """Test that accumulating an empty string has no effect."""
        accumulator.accumulate("")
        assert accumulator.has_next_sentence() is False

    def test_just_ellipsis(self, accumulator: sentence_accumulator):
        """Test that accumulating just an ellipsis does not produce a sentence."""
        accumulator.accumulate("...")

        assert accumulator.has_next_sentence() is False

    def test_just_other_punctuation(self, accumulator: sentence_accumulator):
        """Test that bare punctuation with no word content does not produce a sentence."""
        accumulator.accumulate("?!")

        assert accumulator.has_next_sentence() is False

    def test_has_next_sentence_does_not_consume(self, accumulator: sentence_accumulator):
        """Test that calling has_next_sentence multiple times doesn't consume the sentence."""
        accumulator.accumulate("Hello.")

        assert accumulator.has_next_sentence() is True
        assert accumulator.has_next_sentence() is True # Still true
        assert accumulator.get_next_sentence() == "Hello."
        assert accumulator.has_next_sentence() is False

    def test_get_next_sentence_clears_prepared(self, accumulator: sentence_accumulator):
        """Test that get_next_sentence resets the prepared state."""
        accumulator.accumulate("Hello.")
        accumulator.has_next_sentence()
        accumulator.get_next_sentence()

        # After retrieval, no more sentences
        assert accumulator.has_next_sentence() is False
