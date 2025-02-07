from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import sentence_content

class sentence_length_parser(output_parser):
    def __init__(self, min_words_tts: int) -> None:
        super().__init__()
        self.__min_words_tts = min_words_tts

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[sentence_content|None, str|None]:
        return None, output

    def __count_words(self, text: str) -> int:
        return len(text.split())

    def modify_sentence_content(self, next_content: sentence_content, last_content: sentence_content | None, settings: sentence_generation_settings) -> tuple[sentence_content | None, sentence_content]:
        new_content: sentence_content | None = next_content
        if last_content:
            if self.__count_words(new_content.text) < self.__min_words_tts or self.__count_words(last_content.text) < self.__min_words_tts: #narration and character parser max produce sentences shorter than allowed
                if last_content.speaker == new_content.speaker and last_content.sentence_type == new_content.sentence_type:
                    #If the previous sentence was by the same speaker and was/wasn't a narration as well, add the sentence that is too short to the last one
                    last_content.append_other_sentence_content(new_content.text, new_content.actions)
                    new_content = None
            #If there was a change in speaker or narration flag we can never join them with the next sentence so we just send out the last one
        else:
            last_content = new_content  #If we don't have a last sentence, set the first one as last and wait for the second
            new_content = None
        
        return new_content, last_content