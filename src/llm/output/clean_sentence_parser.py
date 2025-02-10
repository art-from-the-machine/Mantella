import logging
import re
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import sentence_content
import src.utils as utils

class clean_sentence_parser(output_parser):
    """Class to track narrations in the current output of the LLM."""
    def __init__(self) -> None:
        super().__init__()

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[sentence_content | None, str]:
        return None, self.clean_sentence(output)
        
    @utils.time_it
    def clean_sentence(self, sentence: str) -> str:
        def remove_as_a(sentence: str) -> str:
            """Remove 'As an XYZ,' from beginning of sentence"""
            if sentence.startswith('As a'):
                if ', ' in sentence:
                    logging.log(28, f"Removed '{sentence.split(', ')[0]} from response")
                    sentence = sentence.replace(sentence.split(', ')[0]+', ', '')
            return sentence
        
        if ('Well, well, well' in sentence):
            sentence = sentence.replace('Well, well, well', 'Well well well')

        sentence = remove_as_a(sentence)
        sentence = sentence.replace('\n', ' ')
        sentence = sentence.replace('[', '(')
        sentence = sentence.replace(']', ')')
        sentence = sentence.replace('{', '(')
        sentence = sentence.replace('}', ')')
        # local models sometimes get the idea in their head to use double asterisks **like this** in sentences instead of single
        # this converts double asterisks to single so that they can be filtered out appropriately
        sentence = sentence.replace('**','*')
        return sentence
           

    def modify_sentence_content(self, cut_content: sentence_content, last_content: sentence_content | None, settings: sentence_generation_settings) -> tuple[sentence_content | None, sentence_content | None]:
        return cut_content, last_content