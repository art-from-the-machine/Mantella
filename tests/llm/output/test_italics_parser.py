import pytest
from src.llm.output.italics_parser import italics_parser
from src.llm.output.output_parser import sentence_generation_settings
from src.llm.sentence_content import SentenceTypeEnum, SentenceContent
from src.character_manager import Character
from unittest.mock import MagicMock

class TestItalicStripperParser:
    """Tests for the italic_stripper_parser to ensure inline italics are stripped correctly."""
    
    @pytest.fixture
    def parser(self):
        return italics_parser()
    
    @pytest.fixture
    def mock_character(self):
        """Create a mock character for testing."""
        char = MagicMock(spec=Character)
        char.name = "TestNPC"
        return char
    
    @pytest.fixture
    def settings(self, mock_character):
        return sentence_generation_settings(mock_character)
    
    def test_strip_single_word_italics(self, parser, settings):
        """Test that single-word italics are stripped."""
        text = "I *really* mean it"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None  # Parser doesn't cut sentences
        assert remaining == "I really mean it"
    
    def test_preserve_multiple_word_italics(self, parser, settings):
        """Test that multi-word italics are NOT stripped (preserved for narration parser)."""
        text = "That's *very important* to remember"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None
        # Multi-word phrases should be preserved
        assert remaining == "That's *very important* to remember"
    
    def test_strip_multiple_single_word_italic_sections(self, parser, settings):
        """Test that multiple single-word italic sections in one string are all stripped."""
        text = "I'm *really* not *sure* about this"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None
        assert remaining == "I'm really not sure about this"
    
    def test_preserve_longer_narrations(self, parser, settings):
        """Test that longer text in asterisks (likely narrations) is preserved."""
        # Narrations with punctuation inside should be preserved
        text = "*draws sword and steps forward menacingly.*"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None
        # Should be preserved because it contains punctuation (.)
        assert "*draws sword and steps forward menacingly.*" in remaining
    
    def test_preserve_very_long_asterisk_text(self, parser, settings):
        """Test that very long text in asterisks is preserved for narration parser."""
        text = "*he walks slowly across the room, examining each item carefully*"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None
        # Should be preserved because it's too long (> 30 chars)
        assert "*he walks slowly across the room, examining each item carefully*" in remaining
    
    def test_mixed_italics_and_narration(self, parser, settings):
        """Test handling of both single-word inline italics and multi-word narrations."""
        text = "I'm *truly* sorry about that. *bows head*"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None
        assert "I'm truly sorry about that. *bows head*" == remaining
        # "truly" (single word) should be stripped, but "*bows head*" (multi-word) should remain for narration parser
    
    def test_apostrophes_in_italics(self, parser, settings):
        """Test that italics with apostrophes are handled correctly."""
        text = "I *can't* believe it"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None
        assert remaining == "I can't believe it"
    
    def test_hyphens_in_italics(self, parser, settings):
        """Test that italics with hyphens are handled correctly."""
        text = "That's *well-known* around here"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None
        assert remaining == "That's well-known around here"
    
    def test_no_italics(self, parser, settings):
        """Test that text without italics is unchanged."""
        text = "This is just normal text"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None
        assert remaining == "This is just normal text"
    
    def test_modify_sentence_content(self, parser, settings, mock_character):
        """Test that modify_sentence_content also strips italics."""
        cut_content = SentenceContent(mock_character, "I *really* mean it", SentenceTypeEnum.SPEECH)
        
        result_cut, result_last = parser.modify_sentence_content(cut_content, None, settings)
        
        assert result_cut.text == "I really mean it"
        assert result_last is None
    
    def test_get_cut_indicators_empty(self, parser):
        """Test that this parser doesn't use cut indicators."""
        indicators = parser.get_cut_indicators()
        assert indicators == []
    
    def test_edge_case_asterisk_at_boundary(self, parser, settings):
        """Test asterisks at word boundaries."""
        text = "*Really* though, I mean it *seriously*"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None
        assert remaining == "Really though, I mean it seriously"
    
    def test_preserve_narration_with_question_mark(self, parser, settings):
        """Test that narrations with question marks are preserved."""
        text = "*looks around confused?*"
        result_sentence, remaining = parser.cut_sentence(text, settings)
        
        assert result_sentence is None
        # Should be preserved because it contains punctuation (?)
        assert "*looks around confused?*" in remaining
