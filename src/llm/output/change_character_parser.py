import logging
from src.character_manager import Character
from src.characters_manager import Characters
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import sentence_content


class change_character_parser(output_parser):
    """Class to check if character change is in the current output of the LLM."""
    def __init__(self, characters_in_conversation: Characters) -> None:
        super().__init__()
        self.__dict_name_permutations: dict[str, Character] = {} #Dictionary to hold permutations of the name for easy checks. e.g. "Svana Far-Shield" -> ["Svana Far-Shield", "Svana", "Far-Shield"]
        for actor in characters_in_conversation.get_all_characters():
            if actor.is_player_character:
                self.__dict_name_permutations["player"] = actor
                self.__dict_name_permutations["Player"] = actor
            self.__dict_name_permutations[actor.name] = actor
            split_name = actor.name.split()
            if len(split_name) > 1:
                for name in split_name:
                    self.__dict_name_permutations[name] = actor
        

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[sentence_content | None, str]:
        if not ':' in output:
            return None, output
        
        parts = output.split(':', 1)
        for name, character in self.__dict_name_permutations.items():
            if parts[0].endswith(name):
                character_switch_removed = parts[0].removesuffix(name)
                cleaned_prefix_rest = character_switch_removed.strip()
                if not len(cleaned_prefix_rest) == 0: #Special case where there is still text in front of a character change that needs to be processed first somehow
                    rest = str.join("", [name, ":", parts[1]])
                    return sentence_content(current_settings.current_speaker, cleaned_prefix_rest, current_settings.is_narration, False), rest
                else: #New sentence starts with character change
                    if character.is_player_character:
                        logging.log(28, f"Stopped LLM from speaking on behalf of the player")
                        current_settings.stop_generation = True
                        return None, ""
                    current_settings.current_speaker = character
                    current_settings.is_narration = False #Character change always resets narration tracker to False, i.e. don't actually carry forward potentially non-closed narrations from the last speaker
                    return None, parts[1]

        return None, output #There is a ':' in the text, but it doesn't seem to be part of a character change

    def modify_sentence_content(self, content: sentence_content, settings: sentence_generation_settings) -> bool:
        return True