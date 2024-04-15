from src.config.types.config_value import ConfigValue
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString


class LanguageDefinitions:
    @staticmethod
    def get_language_config_value() -> ConfigValue:
        return ConfigValueSelection("language","Language","The language used by ChatGPT, xVASynth, and Whisper","en",["en", "ar", "da", "de", "el", "es", "fi", "fr", "hu", "it", "ko", "nl", "pl", "pt", "ro", "ru", "sv", "sw", "uk", "ha", "tr", "vi", "yo"])
    
    @staticmethod
    def get_end_conversation_keyword_config_value() -> ConfigValue:
        return ConfigValueString("end_conversation_keyword","End conversation keyword","The keyword Mantella will listen out for to end the conversation (you can also end conversations by re-casting the Mantella spell)","Goodbye")
    
    @staticmethod
    def get_goodbye_npc_response() -> ConfigValue:
        return ConfigValueString("goodbye_npc_response","Goodbye npc response","The response the NPC gives at the end of the conversation","Safe travels")

    @staticmethod
    def get_collecting_thoughts_npc_response() -> ConfigValue:
        return ConfigValueString("collecting_thoughts_npc_response", "collecting_thoughts_npc_response","The response the NPC gives when they need to summarise the conversation because the maximum token count has been reached","I need to gather my thoughts for a moment")

    @staticmethod
    def get_offended_npc_response() -> ConfigValue:
        description = """The keyword used by the NPC when they are offended
                       This should match what is stated in the prompt at the bottom of this config file"""
        return ConfigValueString("offended_npc_response","Offended npc response",description, "Offended")

    @staticmethod
    def get_forgiven_npc_response() -> ConfigValue:
        description = """The keyword used by the NPC when they have forgiven the player for offending them
                        This should match what is stated in the prompt at the bottom of this config file"""
        return ConfigValueString("forgiven_npc_response","forgiven_npc_response",description,"Forgiven")

    @staticmethod
    def get_follow_npc_response() -> ConfigValue:
        description = """The keyword used by the NPC when they are willing to become a follower
                        This should match what is stated in the prompt at the bottom of this config file"""
        return ConfigValueString("follow_npc_response","follow_npc_response",description,"Follow")