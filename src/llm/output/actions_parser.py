import logging
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import sentence_content
from src.conversation.action import action
    
class actions_parser(output_parser):
    def __init__(self, actions: list[action]) -> None:
        super().__init__()
        self.__actions = actions

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[sentence_content|None, str|None]:
        return None, output

    def modify_sentence_content(self, cut_content: sentence_content, last_content: sentence_content | None, settings: sentence_generation_settings) -> tuple[sentence_content | None, sentence_content | None]:
        if ":" in cut_content.text:
            for action in self.__actions:
                keyword = action.keyword + ":"
                if keyword in cut_content.text:
                    cut_content.text = cut_content.text.replace(keyword,"").strip()
                    cut_content.actions.append(action.identifier)
                    logging.log(28, action.info_text)
                    # TODO: Add back this functionality while keeping the first delivered sentence intact
                    # ie "Inventory: Here you go." instead of just "Inventory:" with no further response
                    # if action.is_interrupting:
                    #     settings.stop_generation = True
        return cut_content, last_content
