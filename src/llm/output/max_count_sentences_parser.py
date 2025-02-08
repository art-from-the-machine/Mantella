from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import sentence_content

class max_count_sentences_parser(output_parser):
    def __init__(self, max_sentences: int, is_radiant: bool) -> None:
        super().__init__()
        self.__max_sentences = max_sentences
        self.__sentence_counter = 0
        self.__is_radiant = is_radiant

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[sentence_content|None, str|None]:
        return None, output

    def modify_sentence_content(self, cut_content: sentence_content, last_content: sentence_content | None, settings: sentence_generation_settings) -> tuple[sentence_content | None, sentence_content | None]:
        self.__sentence_counter = self.__sentence_counter + 1
        if self.__sentence_counter >= self.__max_sentences and not self.__is_radiant:
            settings.stop_generation = True
        return cut_content, last_content