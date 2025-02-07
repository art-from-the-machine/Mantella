import logging
from typing import Callable, OrderedDict
from src.character_manager import Character
from src.characters_manager import Characters
from src.llm.output.output_parser import MarkedTextStateEnum, output_parser, sentence_generation_settings
from src.llm.sentence_content import sentence_content


class change_character_parser(output_parser):
    """Class to check if character change is in the current output of the LLM."""
    def __init__(self, characters_in_conversation: Characters) -> None:
        super().__init__()
        self.__dict_name_permutations: OrderedDict[str, Character] = OrderedDict() #Dictionary to hold permutations of the name for easy checks. e.g. "Svana Far-Shield" -> ["Svana Far-Shield", "Svana", "Far-Shield"]
        for actor in characters_in_conversation.get_all_characters():
            if actor.is_player_character:
                self.__dict_name_permutations["player"] = actor
            self.__dict_name_permutations[actor.name] = actor
        
        split_names_to_add: OrderedDict[str, Character] = OrderedDict()
        for name, character in self.__dict_name_permutations.items():
            split_name = character.name.split()        
            if len(split_name) > 1:
                for name in split_name:
                    if not split_names_to_add.__contains__(name):
                        split_names_to_add[name] = character
        
        for name, character in split_names_to_add.items():
            self.__dict_name_permutations[name] = character
        

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[sentence_content | None, str]:
        if not ':' in output:
            return None, output
        
        parts = output.split(':', 1)
        for name, character in self.__dict_name_permutations.items():
            if parts[0].lower().endswith(name.lower()):
                character_switch_removed = parts[0][:-len(name)]
                cleaned_prefix_rest = character_switch_removed.strip()
                if not len(cleaned_prefix_rest) == 0: #Special case where there is still text in front of a character change that needs to be processed first somehow
                    rest = str.join("", [name, ":", parts[1]])
                    return sentence_content(current_settings.current_speaker, cleaned_prefix_rest, current_settings.sentence_type, False), rest
                else: #New sentence starts with character change
                    if character.is_player_character:
                        logging.log(28, f"Stopped LLM from speaking on behalf of the player")
                        current_settings.stop_generation = True
                        return None, ""
                    current_settings.current_speaker = character
                    current_settings.sentence_type = current_settings.unmarked_text #Reset to the last unmarked text type
                    current_settings.current_text_state = MarkedTextStateEnum.UNMARKED
                    return None, parts[1]

        return None, output #There is a ':' in the text, but it doesn't seem to be part of a character change

    def modify_sentence_content(self, cut_content: sentence_content, last_content: sentence_content | None, settings: sentence_generation_settings) -> tuple[sentence_content | None, sentence_content | None]:
        return cut_content, last_content