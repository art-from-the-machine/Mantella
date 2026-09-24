from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum

class max_count_sentences_parser(output_parser):
    def __init__(self, max_sentences: int, is_radiant: bool, read_thoughts_after_cap: bool = False) -> None:
        super().__init__()
        self.__max_sentences = max_sentences
        self.__sentence_counter = 0
        self.__is_radiant = is_radiant
        self.__read_thoughts_after_cap = read_thoughts_after_cap

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[SentenceContent|None, str|None]:
        return None, output

    def modify_sentence_content(self, cut_content: SentenceContent, last_content: SentenceContent | None, settings: sentence_generation_settings) -> tuple[SentenceContent | None, SentenceContent | None]:
        if self.__read_thoughts_after_cap:
            if cut_content.sentence_type == SentenceTypeEnum.THOUGHT:
                return cut_content, last_content
            if settings.speech_cap_reached:
                # Spoken lines past the cap are not voiced. The stream keeps going so a later thought block can still be saved.
                return None, last_content
            self.__sentence_counter = self.__sentence_counter + 1
            if self.__sentence_counter >= self.__max_sentences and not self.__is_radiant:
                settings.speech_cap_reached = True
            return cut_content, last_content

        self.__sentence_counter = self.__sentence_counter + 1
        if self.__sentence_counter >= self.__max_sentences and not self.__is_radiant:
            settings.stop_generation = True
        return cut_content, last_content