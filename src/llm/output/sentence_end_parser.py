import re
import unicodedata
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import SentenceContent


class sentence_end_parser(output_parser):
    """Class to cut the LLM output at the end of a sentence."""
    def __init__(self, end_of_sentence_chars: list[str] = ['.', '?', '!', ';', '。', '？', '！', '；', '：']) -> None:
        super().__init__()
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in end_of_sentence_chars]
        # Updated regex: only match a period if it is not part of an ellipsis (three or more periods)
        # For other sentence end chars, match as before
        # This regex will match a single period not followed or preceded by another period, or any of the other end chars
        # Note: '：' (fullwidth colon) should be removed if you don't want it as a terminator
        period = '\.'
        # Remove colon if not wanted
        other_chars = [c for c in self.__end_of_sentence_chars if c != '.']
        # Build regex: match a period not part of ellipsis, or any other end char
        # (?!\.{2,}) ensures not followed by two or more periods (i.e., not the start of an ellipsis)
        # (?<!\.) ensures not preceded by a period (i.e., not the middle or end of an ellipsis)
        other_chars_escaped = ''.join([re.escape(c) for c in other_chars])
        base_regex_def = rf"^.*?(?:(?<!\.)\.(?!\.)|[{other_chars_escaped}])+"
        self.__sentence_end_reg = re.compile(base_regex_def)

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[SentenceContent | None, str]:
        match = self.__sentence_end_reg.match(output)
        if not match:
            return None, output
        
        matched_text = match.group()
        rest = output.removeprefix(matched_text)
        return SentenceContent(current_settings.current_speaker, matched_text, current_settings.sentence_type, False), rest

    def modify_sentence_content(self, cut_content: SentenceContent, last_content: SentenceContent | None, settings: sentence_generation_settings) -> tuple[SentenceContent | None, SentenceContent | None]:
        return cut_content, last_content
    
    def get_cut_indicators(self) -> list[str]:
        return self.__end_of_sentence_chars
