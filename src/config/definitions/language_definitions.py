from src.conversation.action import action
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString


class LanguageDefinitions:    
    @staticmethod
    def get_language_config_value() -> ConfigValue:
        return ConfigValueSelection("language","Language","The language used by Mantella (speech-to-text, LLM responses, and text-to-speech).","en",["en", "ar", "cs", "da", "de", "el", "es", "fi", "fr", "hi", "hu", "it", "ja", "ko", "nl", "pl", "pt", "ro", "ru", "sv", "sw", "uk", "ha", "tr", "vi", "yo", "zh"])
    
    @staticmethod
    def get_end_conversation_keyword_config_value() -> ConfigValue:
        description = """The keyword(s) Mantella will listen out for to end the conversation (lowercase / uppercase does not matter).
                        To add multiple options, you can split keywords using commas."""
        return ConfigValueString("end_conversation_keyword","End Conversation Keyword(s)",description,"goodbye, bye, good-bye, good bye, good to buy")
    
    @staticmethod
    def get_goodbye_npc_response() -> ConfigValue:
        return ConfigValueString("goodbye_npc_response","NPC Response: Goodbye","The response the NPC gives at the end of the conversation.","Safe travels",tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_collecting_thoughts_npc_response() -> ConfigValue:
        return ConfigValueString("collecting_thoughts_npc_response", "NPC Response: Collecting Thoughts","The response the NPC gives when they need to summarise the conversation because the maximum token count has been reached.","I need to gather my thoughts for a moment", tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])

    @staticmethod
    def get_action_keyword_override(action: action) -> ConfigValue:
        identifier = action.identifier.lstrip("mantella_").lstrip("npc_")
        return ConfigValueString(f"{identifier}_npc_response",f"NPC Response override: {action.name}",action.description, action.keyword, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
