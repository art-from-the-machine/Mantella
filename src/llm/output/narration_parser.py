import re
from typing import Callable
from src.llm.output.output_parser import MarkedTextStateEnum, output_parser, sentence_generation_settings
from src.llm.sentence_content import SentenceTypeEnum, sentence_content
from src import utils

class narration_parser(output_parser):
    """Class to track narrations in the current output of the LLM."""
    def __init__(self, narration_start_chars: list[str] = ["^"], narration_end_chars: list[str] = ["`"],
                speech_start_chars: list[str] = ["="], speech_end_chars: list[str] = ["="]) -> None:
        super().__init__()
        base_regex_def = "^.*?[{chars}]"
        self.__narration_start_chars: list[str] = narration_start_chars
        self.__narration_end_chars: list[str] = narration_end_chars
        self.__start_narration_reg = re.compile(base_regex_def.format(chars = "\\" + "\\".join(narration_start_chars))) #Should look like ^.*?[\*\(\[]
        self.__end_narration_reg = re.compile(base_regex_def.format(chars = "\\" + "\\".join(narration_end_chars))) #Should look like ^.*?[\*\)\]]
        self.__speech_start_chars: list[str] = speech_start_chars
        self.__speech_end_chars: list[str] = speech_end_chars
        self.__start_speech_reg = re.compile(base_regex_def.format(chars = "\\" + "\\".join(speech_start_chars))) #Should look like ^.*?[\*\(\[]
        self.__end_speech_reg = re.compile(base_regex_def.format(chars = "\\" + "\\".join(speech_end_chars))) #Should look like ^.*?[\*\)\]]

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[sentence_content | None, str]:
        output = output.lstrip()
        while True: #loop will only be run a maximum of two times
            if current_settings.current_text_state == MarkedTextStateEnum.UNMARKED: #If we are currently in unmarked text, which is the default
                match = self.__start_narration_reg.match(output) #First, try to locate a start of a narration. The default assumption is that unmarked text is speech
                if match:
                    current_settings.current_text_state = MarkedTextStateEnum.MARKED_NARRATION
                    current_settings.sentence_type = SentenceTypeEnum.NARRATION
                    current_settings.unmarked_text = SentenceTypeEnum.SPEECH #We just identified a switch TO narration FROM unmarked so the previous sentence must be speech
                else: #In case no start of narration indicator could be found
                    match = self.__start_speech_reg.match(output) #Try to look for a start of speech indicator instead
                    if match:
                        current_settings.current_text_state = MarkedTextStateEnum.MARKED_SPEECH
                        current_settings.sentence_type = SentenceTypeEnum.SPEECH
                        current_settings.unmarked_text = SentenceTypeEnum.NARRATION #We just identified a switch TO speech FROM unmarked so the previous sentence must be narration
            elif current_settings.current_text_state == MarkedTextStateEnum.MARKED_SPEECH:
                match = self.__end_speech_reg.match(output) #We are within text that started with a start speech indicator somewhere
                if match:
                    current_settings.current_text_state = MarkedTextStateEnum.UNMARKED
                    current_settings.sentence_type = SentenceTypeEnum.NARRATION
                    current_settings.unmarked_text = SentenceTypeEnum.NARRATION
                else: #In case no end of speech indicator could be found
                    match = self.__start_narration_reg.match(output) #Check for any start of narration indicators, in case the LLM forgot to terminate the previous sentence correctly
                    if match:
                        current_settings.current_text_state = MarkedTextStateEnum.MARKED_NARRATION
                        current_settings.sentence_type = SentenceTypeEnum.NARRATION
                        current_settings.unmarked_text = SentenceTypeEnum.SPEECH
            else: #We are in MARKED_NARRATION
                match = self.__end_narration_reg.match(output) #We are within text that started with a start narration indicator somewhere
                if match:
                    current_settings.current_text_state = MarkedTextStateEnum.UNMARKED
                    current_settings.sentence_type = SentenceTypeEnum.SPEECH
                    current_settings.unmarked_text = SentenceTypeEnum.SPEECH
                else: #In case no end of narration indicator could be found
                    match = self.__start_speech_reg.match(output) #Check for any start of speech indicators, in case the LLM forgot to terminate the previous sentence correctly
                    if match:
                        current_settings.current_text_state = MarkedTextStateEnum.MARKED_SPEECH
                        current_settings.sentence_type = SentenceTypeEnum.SPEECH
                        current_settings.unmarked_text = SentenceTypeEnum.NARRATION

            if not match: #If there is no match, there is no change between spoken text and narration within the current output -> nothing to do here
                return None, output
            
            matchedText = match.group() #matchedText contains everything up to and including the first indicator char
            if self.__is_speech_or_narration_char(matchedText): #If the output begins with a start or end of a narration or speech
                output = output.removeprefix(matchedText) #remove the leading narration change
                continue #Go into the loop a second time to check the remainder of the text for a possible complete sentence (unlikely, but still...)

            rest = output.removeprefix(matchedText)
            for char in self.__narration_start_chars + self.__narration_end_chars + self.__speech_start_chars + self.__speech_end_chars:
                if matchedText.endswith(char):
                    matchedText = matchedText.removesuffix(char)
                    break

            return sentence_content(current_settings.current_speaker, matchedText, self.__flip_sentence_type(current_settings.sentence_type), False), rest

    def __flip_sentence_type(self, sentence_type: SentenceTypeEnum) -> SentenceTypeEnum:
        if sentence_type == SentenceTypeEnum.NARRATION:
            return SentenceTypeEnum.SPEECH
        else:
            return SentenceTypeEnum.NARRATION

    def __is_speech_or_narration_char(self, text: str) -> bool:
        lists = [self.__narration_start_chars, self.__narration_end_chars, self.__speech_start_chars, self.__speech_end_chars]
        for char_list  in lists:
            if text in char_list:
                return True
        return False
    
    def modify_sentence_content(self, cut_content: sentence_content, last_content: sentence_content | None, settings: sentence_generation_settings) -> tuple[sentence_content | None, sentence_content | None]:
        return cut_content, last_content