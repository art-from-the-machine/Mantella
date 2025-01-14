import re
import unicodedata
import textwrap
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import sentence_content


class sentence_end_parser(output_parser):
    """Class to cut the LLM output at the end of a sentence."""
    def __init__(self, min_words: int, max_characters: int, end_of_sentence_chars: list[str] = ['.', '?', '!', ':', ';', '。', '？', '！', '；', '：']) -> None:
        super().__init__()
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in end_of_sentence_chars]
        self.__min_words = min_words
        self.__max_characters = max_characters
        base_regex_def = "^.*?[{narration_chars}]"
        self.__sentence_end_reg = re.compile(base_regex_def.format(narration_chars = "\\" + "\\".join(self.__end_of_sentence_chars))) #Should look like ^.*?[\*\(\[]

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[sentence_content | None, str]:
        match = self.__sentence_end_reg.match(output)
        if not match:
            return None, output
        
        matched_text = match.group()
        while True:
            if self.count_words(matched_text) >= self.__min_words and len(matched_text) <= self.__max_characters:
                rest = output.removeprefix(matched_text)
                return sentence_content(current_settings.current_speaker, matched_text, current_settings.is_narration, False), rest
            elif self.count_words(matched_text) >= self.__min_words: #If our matched text is longer than the maximum number of characters
                wrapped_text = textwrap.wrap(matched_text, int(self.__max_characters * 0.75), break_long_words=False)[0] #wrap it at 75% of the maximum character count
                rest = output.removeprefix(wrapped_text)
                return sentence_content(current_settings.current_speaker, wrapped_text, current_settings.is_narration, False), rest
            else: #Our matched sentence is shorter than the minimum number of words, lets check if there is another sentence after it
                rest = output.removeprefix(matched_text)
                match = self.__sentence_end_reg.match(rest)
                if not match:
                    return None, output
                else:
                    matched_text += match.group()
    
    @staticmethod
    def count_words(text: str) -> int:
        return len(text.split())

    def modify_sentence_content(self, content: sentence_content, settings: sentence_generation_settings) -> bool:
        return True