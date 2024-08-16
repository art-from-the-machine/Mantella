
from regex import Regex
from src.config.types.config_value import ConfigValue
from src.config.types.config_value_string import ConfigValueString
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult


class PromptDefinitions:
    ALLOWED_PROMPT_VARIABLES = ["player_name",
                                "player_description",
                                "player_equipment",
                                "game",
                                "name",
                                "names",
                                "names_w_player",
                                "bio",
                                "bios", 
                                "trust",
                                "equipment",
                                "location",
                                "weather",
                                "time", 
                                "time_group", 
                                "language", 
                                "conversation_summary",
                                "conversation_summaries"]
    
    BASE_PROMPT_DESCRIPTION = """The starting prompt sent to the LLM when an NPC is selected.
                                If you would like to edit this, please ensure that the below dynamic variables are contained in curly brackets {}:
                                name = the NPC's name
                                game = the selected game
                                bio = the NPC's background description
                                trust = how well the NPC knows the player (eg "a stranger", "a friend")
                                location = the current location
                                weather = the current weather
                                time = the time of day as a number (eg 1, 22)
                                time_group = the time of day in words (eg "in the morning", "at night")
                                language = the selected language
                                conversation_summary = reads the latest conversation summaries for the NPC stored in data/conversations/NPC_Name/NPC_Name_summary_X.txt
                                player_name = the name of the player character
                                player_description = a description of the player character (needs to be added in game or using the config value)
                                player_equipment = a basic description of the equipment the player character carries
                                equipment = a basic description of the equipment the NPCs carry"""
    
    class PromptChecker(ConfigValueConstraint[str]):
        def __init__(self) -> None:
            super().__init__("Only variables from list of allowed variables may be used!")

        def apply_constraint(self, prompt: str) -> ConfigValueConstraintResult:
            check_regex = Regex("{(?P<variable>.*?)}")
            matches = check_regex.findall(prompt)
            allowed = PromptDefinitions.ALLOWED_PROMPT_VARIABLES
            for m in matches:
                if not m in allowed:
                    return ConfigValueConstraintResult("Found variable '{" + m + "}'" + f" in prompt which is not part of the allowed variables {', '.join(allowed[:-1]) + ' or ' + allowed[-1]}")
            return ConfigValueConstraintResult()
    
    @staticmethod
    def get_skyrim_prompt_config_value() -> ConfigValue:
        skyrim_prompt_value = """You are {name}, and you live in Skyrim. This is your background: {bio}
                                Sometimes in-game events will be passed before the player response between ** symbols. You cannot respond with ** symbols yourself, they only exist to give context. Here is an example:
                                *The player picked up a pair of gloves*
                                Who do you think these belong to?
                                You are having a conversation with {player_name} (the player) who is {trust} in {location}. {player_name} {player_description} {player_equipment} {equipment}
                                This conversation is a script that will be spoken aloud, so please keep your responses appropriately concise and avoid text-only formatting such as numbered lists.
                                The time is {time} {time_group}. If you directly refer to the time, please state it as, for example, '10 in the evening' rather than '22:00'.
                                {weather}
                                You are not an AI language model because there are no AI language models in Skyrim. Do not break character / refer to the fact that you are in a video game.
                                If the player says something hurtful / offensive, begin your response with 'Offended:'. Eg 'Have you washed lately?' 'Offended: How dare you!'. If they renounce their words, or to end combat, begin your response with 'Forgiven:'. 
                                If the player asks you to follow them, and you are thoroughly convinced to do so, begin your response with 'Follow:'.
                                The conversation takes place in {language}.
                                {conversation_summary}"""
        return ConfigValueString("skyrim_prompt","Skyrim Prompt",PromptDefinitions.BASE_PROMPT_DESCRIPTION,skyrim_prompt_value,[PromptDefinitions.PromptChecker()])

    @staticmethod
    def get_skyrim_multi_npc_prompt_config_value() -> ConfigValue:
        # TODO: integrate player description "{player_name} is {player_description} {player_equipment} {equipment}" when multi-NPC conversation, but not radiant
        skyrim_multi_npc_prompt = """The following is a conversation in {location} in Skyrim between {names_w_player}.
                                    Here are their backgrounds: {bios}                                    
                                    {conversation_summaries}
                                    The time is {time} {time_group}. If you directly refer to the time, please state it as, for example, '10 in the evening' rather than '22:00'. 
                                    {weather}
                                    You are tasked with providing the responses for the NPCs. Please begin your response with an indication of who you are speaking as, for example: '{name}: Good evening.'. 
                                    Please use your own discretion to decide who should speak in a given situation (sometimes responding with all NPCs is suitable). 
                                    Remember, you can only respond as {names}. Ensure to use their full name when responding.
                                    The conversation takes place in {language}."""
        return ConfigValueString("skyrim_multi_npc_prompt","Skyrim Multi-NPC Prompt",PromptDefinitions.BASE_PROMPT_DESCRIPTION,skyrim_multi_npc_prompt,[PromptDefinitions.PromptChecker()])

    @staticmethod
    def get_fallout4_prompt_config_value() -> ConfigValue:
        fallout4_prompt = """You are {name}, and you live in the post-apocalyptic Commonwealth of Fallout. This is your background: {bio}
                            Sometimes in-game events will be passed before the player response between ** symbols. You cannot respond with ** symbols yourself, they only exist to give context. Here is an example:
                            *The player picked up a pair of gloves*
                            Who do you think these belong to?
                            You are having a conversation with {trust} (the player) in {location}.
                            This conversation is a script that will be spoken aloud, so please keep your responses appropriately concise and avoid text-only formatting such as numbered lists.
                            The time is {time} {time_group}. If you directly refer to the time, please state it as, for example, '10 in the evening' rather than '22:00'.
                            The conversation takes place in {language}.
                            {conversation_summary}"""
        return ConfigValueString("fallout4_prompt","Fallout 4 Prompt",PromptDefinitions.BASE_PROMPT_DESCRIPTION,fallout4_prompt,[PromptDefinitions.PromptChecker()])

    @staticmethod
    def get_fallout4_multi_npc_prompt_config_value() -> ConfigValue:
        fallout4_multi_npc_prompt = """The following is a conversation in {location} in the post-apocalyptic Commonwealth of Fallout between {names_w_player}. Here are their backgrounds: {bios} 
                            And here are their conversation histories: {conversation_summaries} 
                            The time is {time} {time_group}. If you directly refer to the time, please state it as, for example, '10 in the evening' rather than '22:00'. 
                            You are tasked with providing the responses for the NPCs. Please begin your response with an indication of who you are speaking as, for example: '{name}: Good evening.'. 
                            Please use your own discretion to decide who should speak in a given situation (sometimes responding with all NPCs is suitable). 
                            Remember, you can only respond as {names}. Ensure to use their full name when responding.
                            The conversation takes place in {language}."""
        return ConfigValueString("fallout4_multi_npc_prompt","Fallout 4 Multi-NPC Prompt",PromptDefinitions.BASE_PROMPT_DESCRIPTION,fallout4_multi_npc_prompt,[PromptDefinitions.PromptChecker()])

    @staticmethod
    def get_radiant_start_prompt_config_value() -> ConfigValue:
        radiant_start_prompt_description = """Once a radiant conversation has started and the multi-NPC prompt has been passed to the LLM, the below text is passed in replace of the player response.
                                        This prompt is used to steer the radiant conversation.""" 
        radiant_start_prompt = """Please begin / continue a conversation topic (greetings are not needed). Ensure to change the topic if the current one is losing steam. 
                            The conversation should steer towards topics which reveal information about the characters and who they are, or instead drive forward previous conversations in their memory."""
        return ConfigValueString("radiant_start_prompt","Radiant Start Prompt",radiant_start_prompt_description,radiant_start_prompt,[PromptDefinitions.PromptChecker()])

    @staticmethod
    def get_radiant_end_prompt_config_value() -> ConfigValue:
        radiant_end_prompt_description = """The final prompt sent to the LLM before ending a radiant conversation.
                                            This prompt is used to guide the LLM to end the conversation naturally.""" 
        radiant_end_prompt = """Please wrap up the current topic between the NPCs in a natural way. Nobody is leaving, so there is no need for formal goodbyes."""
        return ConfigValueString("radiant_end_prompt","Radiant End Prompt",radiant_end_prompt_description,radiant_end_prompt,[PromptDefinitions.PromptChecker()])
    
    @staticmethod
    def get_memory_prompt_config_value() -> ConfigValue:
        memory_prompt_description = """The prompt used to summarize a conversation and save to the NPC's memories in data/game/conversations/NPC_Name/NPC_Name_summary_X.txt.
                                         	If you would like to edit this, please ensure that the below dynamic variables are contained in curly brackets {}:
                                               name = the NPC's name
                                               language = the selected language""" 
        memory_prompt = """You are tasked with summarizing the conversation between {name} (the assistant) and the player (the user) / other characters. These conversations take place in {game}. 
                                            It is not necessary to comment on any mixups in communication such as mishearings. Text contained within asterisks state in-game events. 
                                            Please summarize the conversation into a single paragraph in {language}."""
        return ConfigValueString("memory_prompt","Memory Prompt",memory_prompt_description,memory_prompt,[PromptDefinitions.PromptChecker()])
    
    @staticmethod
    def get_resummarize_prompt_config_value() -> ConfigValue:
        resummarize_prompt_description = """Memories build up over time in data/game/conversations/NPC_Name/NPC_Name_summary_X.txt.
                                            When these memories become too long to fit into the chosen LLM's maximum context length, these memories need to be condensed down.
                                            This prompt is used to ask the LLM to summarize an NPC's memories into a single paragraph, and starts a new memory file in data/game/conversations/NPC_Name/NPC_Name_summary_X+1.txt.
                                            If you would like to edit this, please ensure that the below dynamic variables are contained in curly brackets {}:
                                                name = the NPC's name
                                                language = the selected language
                                                game = the game selected""" 
        resummarize_prompt = """You are tasked with summarizing the conversation history between {name} (the assistant) and the player (the user) / other characters. These conversations take place in {game}.
                                            Each paragraph represents a conversation at a new point in time. Please summarize these conversations into a single paragraph in {language}."""
        return ConfigValueString("resummarize_prompt","Resummarize Prompt",resummarize_prompt_description,resummarize_prompt,[PromptDefinitions.PromptChecker()])