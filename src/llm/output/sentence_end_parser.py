import re
import unicodedata
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import SentenceContent


class sentence_end_parser(output_parser):
    """Class to cut the LLM output at the end of a sentence."""
    def __init__(self, end_of_sentence_chars: list[str] = ['.', '?', '!', ';', '。', '？', '！', '；', '：']) -> None:
        super().__init__()
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in end_of_sentence_chars]
        base_regex_def = "^.*?[{sentence_end_chars}]+"
        self.__sentence_end_reg = re.compile(base_regex_def.format(sentence_end_chars = "\\" + "\\".join(self.__end_of_sentence_chars)))

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[SentenceContent | None, str]:
        match = self.__sentence_end_reg.match(output)
        if not match:
            return None, output
        
        matched_text = match.group()
        rest = output.removeprefix(matched_text)
        return SentenceContent(current_settings.current_speaker, matched_text, current_settings.sentence_type, False), rest

    def modify_sentence_content(self, cut_content: SentenceContent, last_content: SentenceContent | None, settings: sentence_generation_settings) -> tuple[SentenceContent | None, SentenceContent | None]:
        return cut_content, last_content