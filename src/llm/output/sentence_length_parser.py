from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import SentenceContent

class sentence_length_parser(output_parser):
    def __init__(self, min_words_tts: int) -> None:
        super().__init__()
        self.__min_words_tts = min_words_tts

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[SentenceContent|None, str|None]:
        return None, output

    def __count_words(self, text: str) -> int:
        return len(text.split())

    def modify_sentence_content(self, next_content: SentenceContent, last_content: SentenceContent | None, settings: sentence_generation_settings) -> tuple[SentenceContent | None, SentenceContent | None]:
        """Checks and potentially merges sentences based on word count requirements.
        
        Args:
            next_content: The newly parsed sentence
            last_content: The previous sentence that might need merging
            settings: Current generation settings
            
        Returns:
            tuple: (parsed_sentence, pending_sentence) where:
                - parsed_sentence is a sentence ready for output
                - pending_sentence is a sentence being held for potential merging
        """
        # First sentence case
        if not last_content:
            # Hold short sentences for potential merging
            if self.__count_words(next_content.text) < self.__min_words_tts:
                return None, next_content
            return next_content, None
        
        # We have a previous sentence - check if either needs merging
        if (self.__count_words(next_content.text) < self.__min_words_tts or 
            self.__count_words(last_content.text) < self.__min_words_tts):
            # Only merge if same speaker and type
            if (last_content.speaker == next_content.speaker and 
                last_content.sentence_type == next_content.sentence_type):
                last_content.append_other_sentence_content(next_content.text, next_content.actions)
                return last_content, None
        
        # Either both sentences are long enough or they can't be merged
        return last_content, next_content
