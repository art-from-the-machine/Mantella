from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString


class LanguageDefinitions:    
    @staticmethod
    def get_language_config_value() -> ConfigValue:
        return ConfigValueSelection("language","Language","The language used by ChatGPT, xVASynth, and Whisper.","en",["en", "ar", "da", "de", "el", "es", "fi", "fr", "hu", "it", "ko", "nl", "pl", "pt", "ro", "ru", "sv", "sw", "uk", "ha", "tr", "vi", "yo"])
    
    @staticmethod
    def get_end_conversation_keyword_config_value() -> ConfigValue:
        return ConfigValueString("end_conversation_keyword","End Conversation Keyword","The keyword Mantella will listen out for to end the conversation.","Goodbye")
    
    @staticmethod
    def get_goodbye_npc_response() -> ConfigValue:
        return ConfigValueString("goodbye_npc_response","NPC Response: Goodbye","The response the NPC gives at the end of the conversation.","Safe travels",tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_collecting_thoughts_npc_response() -> ConfigValue:
        return ConfigValueString("collecting_thoughts_npc_response", "NPC Response: Collecting Thoughts","The response the NPC gives when they need to summarise the conversation because the maximum token count has been reached.","I need to gather my thoughts for a moment", tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_offended_npc_response() -> ConfigValue:
        description = """The keyword used by the NPC when they are offended.
                       This should match what is stated in the starting prompt."""
        return ConfigValueString("offended_npc_response","NPC Response: Offended",description, "Offended", tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_forgiven_npc_response() -> ConfigValue:
        description = """The keyword used by the NPC when they have forgiven the player for offending them.
                        This should match what is stated in the starting prompt."""
        return ConfigValueString("forgiven_npc_response","NPC Response: Forgiven",description,"Forgiven", tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_follow_npc_response() -> ConfigValue:
        description = """The keyword used by the NPC when they are willing to become a follower.
                        This should match what is stated in the starting prompt."""
        return ConfigValueString("follow_npc_response","NPC Response: Follow",description,"Follow", tags=[ConvigValueTag.advanced])