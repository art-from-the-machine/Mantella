import re

from src.llm.output.clean_sentence_parser import (
    LINE_BOUNDARY_MARKER,
    RESPONSE_BOUNDARY_MARKER,
    clean_sentence_parser,
)


class accumulated_sentence(str):
    """A sentence carrying boundary metadata without changing its text value."""

    def __new__(cls, value: str, starts_at_response: bool = False, starts_at_line: bool = False):
        result = super().__new__(cls, value)
        result.starts_at_response = starts_at_response
        result.starts_at_line = starts_at_line
        return result


class sentence_accumulator:
    """Accumulates the token-wise output of an LLM into raw sentences.
    """
    def __init__(self, cut_indicators: list[str]) -> None:
        self.__cut_indicators = cut_indicators
        self.__cleaned_llm_output: str = ""
        # Match at least one word character, then the first sentence-ending punctuation.
        # A standalone period (not part of an ellipsis) or any other end-of-sentence char.
        other_chars = [c for c in cut_indicators if c != '.']
        other_chars_escaped = ''.join([re.escape(c) for c in other_chars])
        self.__sentence_end_reg = re.compile(rf"^.*?\w.*?(?:(?<!\.)\.(?!\.)|[{other_chars_escaped}])+")
        self.__unparseable: str = ""
        self.__prepared_match: str = ""
        self.__cleaner = clean_sentence_parser()
        self.__response_boundary_pending = True
    
    def has_next_sentence(self) -> bool:
        if len(self.__prepared_match) > 0:
            return True
        
        match = self.__sentence_end_reg.match(self.__cleaned_llm_output)
        if not match:
            return False
        else:
            self.__prepared_match = match.group()
            self.__cleaned_llm_output = self.__cleaned_llm_output.removeprefix(self.__prepared_match)
            return True
    
    def get_next_sentence(self) -> accumulated_sentence:
        raw_result = self.__unparseable + self.__prepared_match
        self.__unparseable = ""
        self.__prepared_match = ""
        starts_at_response = raw_result.startswith(RESPONSE_BOUNDARY_MARKER)
        starts_at_line = raw_result.startswith(LINE_BOUNDARY_MARKER) or (
            starts_at_response and raw_result[len(RESPONSE_BOUNDARY_MARKER):].startswith(LINE_BOUNDARY_MARKER)
        )
        result = raw_result.lstrip(RESPONSE_BOUNDARY_MARKER + LINE_BOUNDARY_MARKER)
        return accumulated_sentence(result, starts_at_response, starts_at_line)
    
    def accumulate(self, llm_output: str):
        llm_output = self.__cleaner.clean_sentence(llm_output)
        if llm_output and self.__response_boundary_pending:
            llm_output = RESPONSE_BOUNDARY_MARKER + llm_output
            self.__response_boundary_pending = False
        self.__cleaned_llm_output += llm_output
    
    def refuse(self, refused_text: str):
        self.__unparseable = refused_text
    


    
