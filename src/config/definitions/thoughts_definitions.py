from regex import Regex
from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult

class InnerThoughtsDefinitions:
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
    
	
    @staticmethod
    def get_auto_inner_thoughts_config_value() -> ConfigValueBool:
        auto_inner_thought_description = """Enable or disable the Inner Thoughts feature for NPCs. When enabled, the system will use AI to determine and display NPCs' emotional and cognitive states based on recent interactions with the player."""
        
        return ConfigValueBool(
            "auto_inner_thoughts",  # Identifier for the config value
            "Auto Inner Thoughts",  # Display name in UI
            auto_inner_thought_description,  # Updated description for the feature
            True  # Default value is set to True (enabled)
        )

    # Configuration for selecting fixed or random interval
    @staticmethod
    def get_interval_type_config_value() -> ConfigValue:
        interval_type_description = """Choose whether to use a fixed interval in seconds or a random interval between 60 and 180 seconds for checking the automatic greeting.
                                       - Fixed: A specific interval in seconds defined by the user. This can be better for creating a more dynamic flow in conversations, particularly in group chats, as it ensures regular opportunities for NPCs to speak, 
									     keeping the interaction steady and engaging
                                       - Random: A random interval between 60 and 180 seconds."""
        interval_type_options = ["Fixed", "Random"]

        return ConfigValueSelection(
            "interval_type",  # Identifier for the config value
            "Interval Type",  # Display name in UI
            interval_type_description,  # Description for the UI
            "Random",  # Default value is set to "Random"
            interval_type_options  # Options for selection
        )
    
    # Configuration for setting the fixed interval time
    @staticmethod
    def get_fixed_interval_config_value() -> ConfigValue:
        fixed_interval_description = """If 'Fixed' is selected for the interval type, set the interval time in seconds for checking the automatic greeting.
                                        - This value will be ignored if 'Random' is selected for the interval type."""
        
        # Minimum and maximum values can be set as per requirement
        return ConfigValueInt(
            "fixed_interval",  # Identifier for the config value
            "Fixed Interval (Seconds)",  # Display name in UI
            fixed_interval_description,  # Description for the UI
            120,  # Default value (e.g., 120 seconds)
            10,  # Minimum value
            3600  # Maximum value
        )    

    @staticmethod
    def get_intent_thoughts_length_config_value() -> ConfigValueInt:
        return ConfigValueInt(
            "intent_thoughts_length",  # Identifier
            "Intent Thoughts History Length",  # Display name in UI
            "The maximum number of recent thoughts to retain in memory for the game manager.",  # Description
            10,  # Default value
            5,  # Minimum value
            100  # Maximum value
        )

    @staticmethod
    def get_conversation_retrieval_count_config_value() -> ConfigValueInt:
        return ConfigValueInt(
            "conversation_retrieval_count",  # Identifier
            "Conversation Retrieval Count",  # Display name in UI
            "The default number of recent messages to retrieve from an ongoing conversation between the player and NPC.",  # Description
            5,  # Default value
            1,  # Minimum value
            50  # Maximum value
        )

	
    class PromptChecker(ConfigValueConstraint[str]):
        def __init__(self, allowed_prompt_variables: list[str]) -> None:
            super().__init__("Only variables from list of allowed variables may be used!")
            self.__allowed_prompt_variables = allowed_prompt_variables

        def apply_constraint(self, prompt: str) -> ConfigValueConstraintResult:
            check_regex = Regex("{(?P<variable>.*?)}")
            matches = check_regex.findall(prompt)
            allowed = self.__allowed_prompt_variables
            for m in matches:
                if not m in allowed:
                    if len(allowed) == 0:
                        return ConfigValueConstraintResult("Found variable '{" + m + "}' in text. No variables allowed.")
                    return ConfigValueConstraintResult(
                        "Found variable '{" + m + "}'" + f" in prompt which is not part of the allowed variables {', '.join(allowed[:-1]) + ' or ' + allowed[-1]}"
                    )
            return ConfigValueConstraintResult()

			
    @staticmethod
    def get_inner_thoughts_prompt_config_value() -> ConfigValue:
        inner_thoughts_prompt_description = """This prompt analyzes the NPC's current emotional state based on recent interactions with the player. 
        It returns a simple description of the emotional state and indicates whether the NPC should speak or remain silent. Ensure the following dynamic variables are contained in curly brackets {}: name = the NPC's name"""

        inner_thoughts_prompt = """Based on the recent interactions between The Player (user) and {name} (assistant), determine {name}'s current emotional state and indicate whether {name} should speak or remain silent.
        Possible emotional states: Happy, Sad, Irritated, Surprised, Fearful, Anxious, Confused, Neutral, Thoughtful, Remembering something, Distracted, Curious. 
        Action decision: {name} should speak. / {name} should remain silent. Response Format: {name} is [emotional state]. {name} should [speak / remain silent]. 
        Examples: - Lydia is curious. Lydia should speak. - Lydia is thoughtful. Lydia should remain silent. Now, based on the interactions:"""

        return ConfigValueString(
            "inner_thoughts_prompt",  # Identifier
            "Inner Thoughts Prompt",  # Display name in UI
            inner_thoughts_prompt_description,  # Description
            inner_thoughts_prompt,  # Default value
            [InnerThoughtsDefinitions.PromptChecker(InnerThoughtsDefinitions.ALLOWED_PROMPT_VARIABLES)],  # Constraint checker
            tags=[ConvigValueTag.advanced]
		)

    @staticmethod
    def get_multiple_inner_thoughts_prompt_config_value() -> ConfigValue:
        multiple_inner_thoughts_prompt_description = """This prompt analyzes the current emotional states of multiple NPCs based on recent interactions with the player. 
        It returns a simple description of each NPC's emotional state and indicates which NPC should speak next. 
        Ensure the following dynamic variables are contained in curly brackets {}: names = a list of NPCs' names involved in the conversation."""

        multiple_inner_thoughts_prompt = """Based on the recent interactions between The Player (user) and the following NPCs: {names}, determine each NPC's current emotional state and decide which NPC should speak next. 
		Possible emotional states: Happy, Sad, Irritated, Surprised, Fearful, Anxious, Confused, Neutral, Thoughtful, Remembering something, Distracted, Curious. Criteria for selecting which NPC should speak: 
		Prioritize NPCs who have been quieter or less engaged. 
		Consider the emotional state; NPCs who are curious, eager, or have relevant input may be more inclined to speak. 
		If multiple NPCs equally meet the criteria, choose the one whose input would most enrich the conversation.
		Do not select The Player (user) as the next speaker. Focus only on NPCs
		Response Format (provide no additional text or explanations): [NPC Name] is [emotional state]. [NPC Name] is [emotional state]. [Selected NPC Name] should speak next. 
		Examples: - Lydia is curious. Sven is thoughtful. Lydia should speak next. - Aela is distracted. Vilkas is irritated. Vilkas should speak next. Now, based on the interactions:"""


        return ConfigValueString("multiple_inner_thoughts_prompt", "Multiple Inner Thoughts Prompt", multiple_inner_thoughts_prompt_description, multiple_inner_thoughts_prompt, [InnerThoughtsDefinitions.PromptChecker(InnerThoughtsDefinitions.ALLOWED_PROMPT_VARIABLES)], tags=[ConvigValueTag.advanced])

    @staticmethod
    def get_temperature_config_value_i() -> ConfigValue:
        return ConfigValueFloat("temperature_i","Temperature","", 1.0, 0, 2,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_top_p_config_value_i() -> ConfigValue:
        return ConfigValueFloat("top_p_i","Top P","", 1.0, 0, 1,tags=[ConvigValueTag.advanced])
		
    @staticmethod
    def get_frequency_penalty_config_value_i() -> ConfigValue:
        return ConfigValueFloat("frequency_penalty_i","Frequency Penalty","", 0, -2, 2,tags=[ConvigValueTag.advanced])
    
    @staticmethod
    def get_presence_penalty_config_value_i() -> ConfigValue:
        return ConfigValueFloat("presence_penalty_i","Presence Penalty","", 0, -2, 2,tags=[ConvigValueTag.advanced])
	
    @staticmethod
    def get_max_tokens_config_value_i() -> ConfigValue:
        return ConfigValueInt("max_tokens_i","Max Tokens","Lowering this value can sometimes result in empty responses.", 250, 1, 999999,tags=[ConvigValueTag.advanced])		