from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import SentenceContent
from src.conversation.action import Action
import src.utils as utils

logger = utils.get_logger()

    
class actions_parser(output_parser):
    def __init__(self, actions: list[Action]) -> None:
        super().__init__()
        self.__actions = actions

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[SentenceContent|None, str|None]:
        return None, output

    def modify_sentence_content(self, cut_content: SentenceContent, last_content: SentenceContent | None, settings: sentence_generation_settings) -> tuple[SentenceContent | None, SentenceContent | None]:
        if ":" in cut_content.text:
            for action in self.__actions:
                keyword = action.keyword + ":"
                if keyword in cut_content.text:
                    cut_content.text = cut_content.text.replace(keyword,"").strip()
                    cut_content.actions.append({'identifier': action.identifier})
                    logger.log(28, f'Action triggered: {action.name} ({action.identifier})')
                    if action.is_interrupting:
                        settings.stop_generation = True
        return cut_content, last_content
    
    def get_cut_indicators(self) -> list[str]:
        return [":"]
