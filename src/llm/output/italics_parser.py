import re
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import SentenceContent

class italics_parser(output_parser):
    """Parser to detect and strip inline italic formatting (eg *word*) that should not be treated as narration indicators.

    This parser should run BEFORE narration_parser to prevent simple emphasis from triggering narration mode.
    """
    
    def __init__(self) -> None:
        super().__init__()
        # Pattern to match inline italics: *word* (single words only)
        # - Must start with * and end with *
        # - Can only contain a single word (letters, hyphens, apostrophes - NO spaces)
        # - Should NOT contain sentence-ending punctuation (.!?;) or spaces inside
        # Only strips obvious single-word emphasis
        self.__inline_italic_pattern = re.compile(r'\*([a-zA-Z\'\-]+)\*')
        
    def get_cut_indicators(self) -> list[str]:
        return []

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[SentenceContent | None, str]:
        modified_output = self.__strip_inline_italics(output)
        return None, modified_output
    
    def modify_sentence_content(self, cut_content: SentenceContent, last_content: SentenceContent | None, 
                                settings: sentence_generation_settings) -> tuple[SentenceContent | None, SentenceContent | None]:
        """Apply italic stripping to already-cut sentence content as well."""
        if cut_content:
            cut_content.text = self.__strip_inline_italics(cut_content.text)
        if last_content:
            last_content.text = self.__strip_inline_italics(last_content.text)
        return cut_content, last_content
    
    def __strip_inline_italics(self, text: str) -> str:
        """Remove asterisks from single-word inline italic formatting patterns.
        
        Example: "I *really* mean it" -> "I really mean it"
        
        But preserves multi-word phrases and narrations:
            "*draws sword*" -> unchanged (multi-word, handled by narration_parser)
            "*bows head*" -> unchanged (multi-word, handled by narration_parser)
        
        Args:
            text: The text to process
            
        Returns:
            Text with single-word italic asterisks removed
        """
        # Replace single-word italic patterns with just the word (no asterisks)
        # Only matches *word* where word has no spaces inside
        modified_text = self.__inline_italic_pattern.sub(r'\1', text)
        return modified_text
