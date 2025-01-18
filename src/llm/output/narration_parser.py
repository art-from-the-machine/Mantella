import re
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import sentence_content

class narration_parser(output_parser):
    """Class to track narrations in the current output of the LLM."""
    def __init__(self, start_chars: list[str] = ["*","(","["], end_chars: list[str] = ["*",")","]"]) -> None:
        super().__init__()
        base_regex_def = "^.*?[{narration_chars}]"
        self.__start_chars: list[str] = start_chars
        self.__end_chars: list[str] = end_chars
        self.__start_narration_reg = re.compile(base_regex_def.format(narration_chars = "\\" + "\\".join(start_chars))) #Should look like ^.*?[\*\(\[]
        self.__end_narration_reg = re.compile(base_regex_def.format(narration_chars = "\\" + "\\".join(end_chars))) #Should look like ^.*?[\*\)\]]

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[sentence_content | None, str]:
        stripped_output = output.lstrip()
        while True: #loop will only be run a maximum of two times
            if current_settings.is_narration: #If we are currently in a narration, look for the next end of narration
                match = self.__end_narration_reg.match(stripped_output)
            else: #Otherwise look for the next start of a narration
                match = self.__start_narration_reg.match(stripped_output)

            if not match: #If there is no match, there is no change between spoken text and narration within the current output -> nothing to do here
                return None, stripped_output
            
            matchedText = match.group()
            if matchedText in self.__start_chars or matchedText in self.__end_chars: #If the output starts with a start or end of a narration
                stripped_output = stripped_output.removeprefix(matchedText) #remove the leading narration change
                current_settings.is_narration = not current_settings.is_narration #Flip the narration flag
                continue #Go into the loop a second time

            rest = stripped_output.removeprefix(matchedText)
            for char in self.__start_chars + self.__end_chars:
                if matchedText.endswith(char):
                    matchedText = matchedText.removesuffix(char)
                    break
            
            current_settings.is_narration = not current_settings.is_narration #Flip the narration flag
            return sentence_content(current_settings.current_speaker, matchedText, not current_settings.is_narration, False), rest
           

    def modify_sentence_content(self, content: sentence_content, settings: sentence_generation_settings) -> bool:
        return True