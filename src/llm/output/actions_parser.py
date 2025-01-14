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

    def modify_sentence_content(self, content: sentence_content, settings: sentence_generation_settings):
        if ":" in content.text:
            for action in self.__actions:
                keyword = action.keyword + ":"
                if keyword in content.text:
                    content.text = content.text.replace(keyword,"").strip()
                    content.actions.append(action.identifier)
                    logging.log(28, action.info_text)
                    if action.is_interrupting:
                        settings.stop_generation = True