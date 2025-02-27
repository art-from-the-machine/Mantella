import re


class sentence_accumulator:
    """Accumulates the token-wise output of an LLM into raw sentences.
    """
    def __init__(self, cut_indicators: list[str]) -> None:
        self.__cut_indicators = cut_indicators
        self.__unprocessed_llm_output: str = ""
        base_regex_def = "^.*?[{sentence_end_chars}]+"
        self.__sentence_end_reg = re.compile(base_regex_def.format(sentence_end_chars = "\\" + "\\".join(cut_indicators)))
        self.__unparseable: str = ""
        self.__prepared_match: str = ""
    
    def has_next_sentence(self) -> bool:
        if len(self.__prepared_match) > 0:
            return True
        
        match = self.__sentence_end_reg.match(self.__unprocessed_llm_output)
        if not match:
            return False
        else:
            self.__prepared_match = match.group()
            self.__unprocessed_llm_output = self.__unprocessed_llm_output.removeprefix(self.__prepared_match)
            return True
    
    def get_next_sentence(self) -> str:
        result = self.__unparseable + self.__prepared_match
        self.__unparseable = ""
        self.__prepared_match = ""
        return result
    
    def accumulate(self, llm_output: str):
        llm_output = llm_output.replace('\r\n', ' ')
        llm_output = llm_output.replace('\n', ' ')
        self.__unprocessed_llm_output += llm_output
    
    def refuse(self, refused_text: str):
        self.__unparseable = refused_text
    


    
