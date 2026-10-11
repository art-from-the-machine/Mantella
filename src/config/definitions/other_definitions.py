from src.conversation.action import Action
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_string import ConfigValueString
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_multi_selection import ConfigValueMultiSelection


class OtherDefinitions:
    @staticmethod
    def get_show_first_time_setup_config_value() -> ConfigValue:
        return ConfigValueBool("first_time_setup","","Show Setup Guide on Startup",True, [], True)
    
    @staticmethod
    def get_automatic_greeting_config_value() -> ConfigValue:
        automatic_greeting_description = """Should a conversation be started with an automatic greeting from the LLM / NPC.
                                        - If enabled: Conversations are always started by the LLM.
                                        - If disabled: The LLM will not respond until the player speaks first."""
        return ConfigValueBool("automatic_greeting","Automatic Greeting",automatic_greeting_description,True)
    
    #Conversation        
    @staticmethod
    def get_active_actions(actions: list[Action]) -> ConfigValue:
        description = "The actions Mantella will provide."
        default_value:list[str] = [a.name for a in actions]
        return ConfigValueMultiSelection("active_actions","Actions",description, default_value, default_value)
    
    @staticmethod
    def get_max_count_events_config_value() -> ConfigValue:
        max_count_events_description = """Maximum number of in-game events that are sent to the LLM per player message. 
                                    If the maximum number is reached, the oldest events will be dropped.
                                    Increasing this number will cost more prompt tokens and lead to the context limit being reached faster."""
        return ConfigValueInt("max_count_events","Max Count Events",max_count_events_description,5,0,999999,tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_events_refresh_time_config_value() -> ConfigValue:
        max_count_events_description = """Determines how much time (in seconds) can pass between the last NPC's response and the player's input before in-game events need to be refreshed.
                                        Note that updating in-game events increases response times. If the player responds before this set number in seconds, response times will be reduced.
                                        Increase this value to allow more time for the player to respond before events need to be refreshed. Decrease this value to make in-game events more up to date."""
        return ConfigValueInt("events_refresh_time","Time to Wait before Updating Events",max_count_events_description,10,0,999999,tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_hourly_time_config_value() -> ConfigValue:
        description = """If enabled, NPCs will be made aware of the time every in-game hour. Otherwise, time updates will be less granular (eg 'The conversation now takes place in the morning' / 'at night' etc).
                        To remove mentions of the hour entirely, prompts also need to be edited from 'The time is {time} {time_group}.' to 'The conversation takes place {time_group}.'"""
        return ConfigValueBool("hourly_time","Report In-Game Time Hourly",description,False,tags=[ConfigValueTag.advanced])
    
    #Player Character
    @staticmethod
    def get_player_character_description() -> ConfigValue:
        player_character_description_description = """A description of your player character in-game. This is sent to the LLM as part of the prompt using the '{player_description}' variable.
                                                    This is not meant to be a bio but rather a description how the NPC(s) perceive the player character when they speak to them.
                                                    e.g. 'A tall man with long red hair.'
                                                    If the in-game MCM offers to set this option the text sent from the game takes precendence over this."""
        return ConfigValueString("player_character_description","Player Character Description",player_character_description_description,"",tags=[ConfigValueTag.advanced])

    @staticmethod
    def get_voice_player_input() -> ConfigValue:
        voice_player_input_description = """Should the input of the player (both by text or voice) be spoken by the player character in-game?
                                            Can be used for immersion or to fill the initial gap between input and reply.
                                            Use the 'Player Voice Model' setting to select the voice model of the TTS for the player character."""
        return ConfigValueBool("voice_player_input","Voice Player Input",voice_player_input_description,False,tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_player_voice_model() -> ConfigValue:
        player_voice_model_description = """The voice model for the player character to use if 'Voice player input' is activated."""
        return ConfigValueString("player_voice_model","Player Voice Model",player_voice_model_description,"",tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    #HTTP
    @staticmethod
    def get_port_config_value() -> ConfigValue:
        return ConfigValueInt("port","Port","The port for the Mantella HTTP server to use.",4999, 0, 65535, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_show_http_debug_messages_config_value() -> ConfigValue:
        return ConfigValueBool("show_http_debug_messages","Show HTTP Debug Messages","Display the JSON going in and out of the server in Mantella.exe's log.", False, tags=[ConfigValueTag.advanced,ConfigValueTag.share_row])
    
    @staticmethod
    def get_advanced_logs_config_value() -> ConfigValue:
        description = """Show the full LLM requests and responses in Mantella.exe's log, and save advanced logs to Mantella's My Games/Mantella/logging.log file.
                        Useful for troubleshooting issues."""
        return ConfigValueBool("advanced_logs", "Debug Mode", description, False, tags=[ConfigValueTag.advanced])
    
    #Debugging
    @staticmethod
    def get_debugging_config_value() -> ConfigValue:
        return ConfigValueBool("debugging","Activate Debugging","Whether debugging is enabled.\nIf this is enabled, the values of all other variables in this section are ignored.", False, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_play_audio_from_script_config_value() -> ConfigValue:
        return ConfigValueBool("play_audio_from_script","Play Audio From Script","Whether to play the generated voicelines directly from the exe.\nEnable this value if testing Mantella while Skyrim is not running.", True, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_debugging_npc_config_value() -> ConfigValue:
        return ConfigValueString("debugging_npc","Debugging NPC","Selects the NPC to test.\nSet this value to None if you would instead prefer to select an NPC via the mod's spell / gun.", "Hulda", tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_use_default_player_response_config_value() -> ConfigValue:
        description = """Whether a default response is sent on the player's behalf (good for quickly testing if Mantella works without player input).
                        When this value is enabled, the sentence contained in default_player_response (see below) will be repeatedly sent to the LLM.
                        When this value is disabled, allows you to use mic / text input (depending on microphone_enabled setting)."""
        return ConfigValueBool("use_default_player_response","Use Default Player Response",description, False, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_default_player_response_config_value() -> ConfigValue:
        return ConfigValueString("default_player_response","Default Player Response","The default text sent to the LLM if 'Use Default Player Response' is enabled.", "Can you tell me something about yourself?", tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_exit_on_first_exchange_config_value() -> ConfigValue:
        description = """Whether to end the conversation after the first back and forth exchange.
                        Enable this value if testing conversation saving on exit functionality."""
        return ConfigValueBool("exit_on_first_exchange","Exit on First Exchange",description, False, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_save_audio_data_to_character_folder_config_value() -> ConfigValue:
        description = """Whether to save audio data to an NPC's voice folder instead of MantellaVoice00.
                        Enable this value if voicelines are not being played in-game."""
        return ConfigValueBool("save_audio_data_to_character_folder", "Save Game Audio to Character Folder", description, False, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_hot_swap_enabled_config_value() -> ConfigValue:
        description = """Whether to enable hot-swapping settings during active conversations.
                        If enabled: Settings changes (LLM model settings, prompts) will be applied without ending conversations.
                        If disabled: Settings changes will end the current conversation and restart (classic behavior)."""
        return ConfigValueBool("hot_swap_enabled", "Enable Hot-Swap Settings", description, True, tags=[ConfigValueTag.advanced])
    
    @staticmethod
    def get_conversation_summary_enabled_config_value() -> ConfigValue:
        description = """Whether to generate and save conversation summaries when conversations end.
                        If enabled: Summaries will be generated and saved to help NPCs remember past conversations.
                        If disabled: No summaries will be generated, conversations will end without sending summary requests to the LLM."""
        return ConfigValueBool("conversation_summary_enabled", "Enable Conversation Summaries", description, True, row_group="memory_saving_row")

    @staticmethod
    def get_inner_monologue_enabled_config_value() -> ConfigValue:
        description = """Whether to generate and save a private inner monologue when a conversation ends and a summary is saved.
                        Requires Enable Conversation Summaries to be on. If summaries are off, thoughts are not saved even if this is on.
                        If enabled: after a summary is written, the NPC also records a first-person private thought.
                        If disabled: summaries still save (when enabled), but no new private thoughts are written.
                        Whether saved thoughts appear in the next conversation prompt is controlled separately by Send Private Thoughts to LLM.
                        Save Summary Now has its own Inner Thoughts toggle and does not use this setting."""
        return ConfigValueBool("inner_monologue_enabled", "Save Private Thoughts", description, False, row_group="memory_saving_row")

    @staticmethod
    def get_inner_monologue_load_count_config_value() -> ConfigValue:
        description = """How many of the most recent private thoughts are sent to the conversation LLM.
                        Newest means the thought blocks with the highest ts= Unix timestamps in the latest thought file (same real-world clock as summaries). If no ts= markers exist, the last blocks in the file are used.
                        Thoughts are sent oldest first, so the newest thought sits closest to the conversation.
                        This does not change whether new thoughts are saved — that is controlled by Save Private Thoughts.
                        - 1: send only the most recent private thought (default).
                        - 0: do not send private thoughts to the conversation LLM, even if thought files already exist.
                        Older thoughts remain on disk. All of them are used as {previous_thoughts} when generating a new thought."""
        return ConfigValueInt(
            "inner_monologue_load_count",
            "Send Private Thoughts to LLM",
            description,
            1,
            0,
            50,
            tags=[ConfigValueTag.advanced],
        )

    @staticmethod
    def get_personal_reflection_enabled_config_value() -> ConfigValue:
        description = """Whether to generate and save a personal reflection when a conversation ends and a summary is saved.
                        Personal reflections are long-term (bio + past summaries), unlike private thoughts which focus on the latest conversation.
                        If enabled: after a summary is written, the NPC also records a first-person personal reflection, as long as that NPC already has summaries.
                        A conversation that is too short to summarize does not write a new reflection.
                        If disabled: summaries still save (when enabled), but no new personal reflections are written.
                        Whether saved reflections appear in the next conversation prompt is controlled separately by Send Personal Reflection to LLM.
                        Manual Save Personal Reflection Now and Bio Editor Generate still work when this is off.
                        Save Summary Now has its own Personal Reflection toggle and does not use this setting."""
        return ConfigValueBool("personal_reflection_enabled", "Save Personal Reflection", description, False, row_group="memory_saving_row")

    @staticmethod
    def get_personal_reflection_load_mode_config_value() -> ConfigValue:
        description = """Only the most recent personal reflection is sent to the conversation LLM — never the full history of older reflections.
                        Latest means the reflection block with the highest ts= Unix timestamp in the latest reflection file (same real-world clock as summaries). If no ts= markers exist, the last block in the file is used.
                        This does not change whether new reflections are saved — that is controlled by Save Personal Reflection.
                        - Latest: send only the most recent personal reflection at the end of the NPC's bio (default).
                        - None: do not send personal reflections to the conversation LLM, even if reflection files already exist.
                        Older reflections remain on disk. They are used only as {previous_reflection} when generating a new reflection, not during chat."""
        return ConfigValueSelection(
            "personal_reflection_load_mode",
            "Send Personal Reflection to LLM",
            description,
            "Latest",
            ["Latest", "None"],
            tags=[ConfigValueTag.advanced],
        )

    @staticmethod
    def get_random_llm_one_on_one_enabled_config_value() -> ConfigValue:
        return ConfigValueBool(
            identifier="random_llm_one_on_one_enabled",
            name="Enable Per-Conversation Random LLM Selection (One-on-One)",
            description="Enable random LLM selection from the one-on-one pool for each new one-on-one conversation.",
            default_value=False,
            tags=["random_llm", "conversation", ConfigValueTag.share_row, ConfigValueTag.advanced]
        )

    @staticmethod
    def get_random_llm_multi_npc_enabled_config_value() -> ConfigValue:
        return ConfigValueBool(
            identifier="random_llm_multi_npc_enabled",
            name="Enable Per-Conversation Random LLM Selection (Multi-NPC)",
            description="Enable random LLM selection from the multi-NPC pool for each new multi-NPC conversation.",
            default_value=False,
            tags=["random_llm", "conversation", ConfigValueTag.share_row, ConfigValueTag.advanced]
        )

    @staticmethod
    def get_random_llm_one_on_one_per_request_enabled_config_value() -> ConfigValue:
        return ConfigValueBool(
            identifier="random_llm_one_on_one_per_request_enabled",
            name="Enable Per-Request Random LLM (One-on-One)",
            description=(
                "When enabled, every request in one-on-one conversations uses a randomly selected LLM "
                "from the one-on-one pool. This overrides per-character LLM overrides for that request."
            ),
            default_value=False,
            tags=["random_llm", "conversation", ConfigValueTag.share_row, ConfigValueTag.advanced],
            row_group="random_llm_per_request_row",
        )

    @staticmethod
    def get_random_llm_multi_npc_per_request_enabled_config_value() -> ConfigValue:
        return ConfigValueBool(
            identifier="random_llm_multi_npc_per_request_enabled",
            name="Enable Per-Request Random LLM (Multi-NPC)",
            description=(
                "When enabled, every request in multi-NPC conversations uses a randomly selected LLM "
                "from the multi-NPC pool. This overrides the per-conversation multi-NPC model selection."
            ),
            default_value=False,
            tags=["random_llm", "conversation", ConfigValueTag.share_row, ConfigValueTag.advanced],
            row_group="random_llm_per_request_row",
        )

    @staticmethod
    def get_llm_pool_one_on_one_config_value() -> ConfigValue:
        return ConfigValueString(
            identifier="llm_pool_one_on_one",
            name="LLM Pool (One-on-One)",
            description="JSON array of LLM models for random selection in one-on-one conversations. Edit this JSON directly to manage your pool.\n\nExample format:\n[\n  {\"service\": \"OpenRouter\", \"model\": \"deepseek/deepseek-chat\"},\n  {\"service\": \"OpenRouter\", \"model\": \"anthropic/claude-3-haiku\"},\n  {\"service\": \"OpenAI\", \"model\": \"gpt-4o-mini\"},\n  {\"service\": \"NanoGPT\", \"model\": \"gpt-4\"}\n]",
            default_value="[]",
            tags=["random_llm", "conversation", "pool", ConfigValueTag.share_row, ConfigValueTag.advanced],
            row_group="llm_pool_row",
        )

    @staticmethod
    def get_llm_pool_multi_npc_config_value() -> ConfigValue:
        return ConfigValueString(
            identifier="llm_pool_multi_npc",
            name="LLM Pool (Multi-NPC)",
            description="JSON array of LLM models for random selection in multi-NPC conversations. Edit this JSON directly to manage your pool.\n\nExample format:\n[\n  {\"service\": \"OpenRouter\", \"model\": \"meta-llama/llama-3.1-8b-instruct\"},\n  {\"service\": \"OpenRouter\", \"model\": \"anthropic/claude-3-sonnet\"},\n  {\"service\": \"NanoGPT\", \"model\": \"gpt-4o\"}\n]",
            default_value="[]",
            tags=["random_llm", "conversation", "pool", ConfigValueTag.share_row, ConfigValueTag.advanced],
            row_group="llm_pool_row",
        )

    @staticmethod
    def get_sequential_llm_one_on_one_per_request_enabled_config_value() -> ConfigValue:
        return ConfigValueBool(
            identifier="sequential_llm_one_on_one_per_request_enabled",
            name="Enable Per-Request Sequential LLM (One-on-One)",
            description=(
                "When enabled, every request in one-on-one conversations uses the next LLM "
                "from the sequential one-on-one pool, in listed order, wrapping around after the last model. "
                "This takes priority over per-request random LLM selection. "
                "If a model fails, the next model in the pool is tried. The position resets at the start of each new conversation."
            ),
            default_value=False,
            tags=["sequential_llm", "conversation", ConfigValueTag.share_row],
            row_group="sequential_llm_per_request_row",
        )

    @staticmethod
    def get_sequential_llm_multi_npc_per_request_enabled_config_value() -> ConfigValue:
        return ConfigValueBool(
            identifier="sequential_llm_multi_npc_per_request_enabled",
            name="Enable Per-Request Sequential LLM (Multi-NPC)",
            description=(
                "When enabled, every request in multi-NPC conversations uses the next LLM "
                "from the sequential multi-NPC pool, in listed order, wrapping around after the last model. "
                "This takes priority over per-request random LLM selection. "
                "If a model fails, the next model in the pool is tried. The position resets at the start of each new conversation."
            ),
            default_value=False,
            tags=["sequential_llm", "conversation", ConfigValueTag.share_row],
            row_group="sequential_llm_per_request_row",
        )

    @staticmethod
    def get_sequential_llm_pool_one_on_one_config_value() -> ConfigValue:
        return ConfigValueString(
            identifier="sequential_llm_pool_one_on_one",
            name="Sequential LLM Pool (One-on-One)",
            description="JSON array of LLM models to iterate through in order for one-on-one conversations. Edit this JSON directly to manage your pool.\n\nExample format:\n[\n  {\"service\": \"OpenRouter\", \"model\": \"deepseek/deepseek-chat\"},\n  {\"service\": \"OpenRouter\", \"model\": \"anthropic/claude-3-haiku\"},\n  {\"service\": \"OpenAI\", \"model\": \"gpt-4o-mini\"}\n]",
            default_value="[]",
            tags=["sequential_llm", "conversation", "pool", ConfigValueTag.share_row],
            row_group="sequential_llm_pool_row",
        )

    @staticmethod
    def get_sequential_llm_pool_multi_npc_config_value() -> ConfigValue:
        return ConfigValueString(
            identifier="sequential_llm_pool_multi_npc",
            name="Sequential LLM Pool (Multi-NPC)",
            description="JSON array of LLM models to iterate through in order for multi-NPC conversations. Edit this JSON directly to manage your pool.\n\nExample format:\n[\n  {\"service\": \"OpenRouter\", \"model\": \"meta-llama/llama-3.1-8b-instruct\"},\n  {\"service\": \"OpenRouter\", \"model\": \"anthropic/claude-3-sonnet\"},\n  {\"service\": \"NanoGPT\", \"model\": \"gpt-4o\"}\n]",
            default_value="[]",
            tags=["sequential_llm", "conversation", "pool", ConfigValueTag.share_row],
            row_group="sequential_llm_pool_row",
        )

    @staticmethod
    def get_reload_character_data_config_value() -> ConfigValue:
        description = """Reload character CSV files and overrides from disk to pick up any changes.
                        This refreshes character data that is cached in memory.
                        Note: If there is an active conversation, it will be ended before reloading."""
        return ConfigValueString("reload_character_data", "Reload Character Data", description, "")

    @staticmethod
    def get_save_summary_now_config_value() -> ConfigValue:
        description = """Trigger saving a conversation summary (and log) without ending the active conversation.
                        Useful if the game crashes and Mantella doesn't receive the normal end-conversation event.
                        Use the toggles below this button to also write Inner Thoughts and/or Personal Reflection with this save.
                        Those toggles are only for this button; they do not change conversation-end behavior.
                        Note: When the conversation later ends normally, another summary may be generated again."""
        return ConfigValueString("save_summary_now", "Save Summary Now", description, "")

    @staticmethod
    def get_save_summary_now_also_save_inner_thoughts_config_value() -> ConfigValue:
        description = """When Save Summary Now is clicked, also generate and save Inner Thoughts for NPCs in the conversation.
                        This is independent of Save Private Thoughts, which only controls conversation-end saves.
                        Manual Save Inner Thoughts still works on its own."""
        return ConfigValueBool(
            "save_summary_now_also_save_inner_thoughts",
            "Also Save Inner Thoughts",
            description,
            True,
        )

    @staticmethod
    def get_save_summary_now_also_save_personal_reflection_config_value() -> ConfigValue:
        description = """When Save Summary Now is clicked, also generate and save Personal Reflections for NPCs that already have summaries.
                        This is independent of Save Personal Reflection, which only controls conversation-end saves.
                        Manual Save Personal Reflection and Bio Editor Generate still work on their own."""
        return ConfigValueBool(
            "save_summary_now_also_save_personal_reflection",
            "Also Save Personal Reflection",
            description,
            True,
        )

    @staticmethod
    def get_save_inner_thoughts_now_config_value() -> ConfigValue:
        description = """Trigger saving private inner thoughts without ending the active conversation, and without writing a new summary.
                        Useful if you want to capture the NPC's current unspoken take on the talk so far.
                        Note: When the conversation later ends normally, another thought may be generated again."""
        return ConfigValueString("save_inner_thoughts_now", "Save Inner Thoughts Now", description, "")

    @staticmethod
    def get_save_personal_reflection_now_config_value() -> ConfigValue:
        description = """Trigger saving personal reflections for every NPC in the active conversation without ending it, and without writing a new summary.
                        Uses each NPC's bio and existing summaries (including any already on file). NPCs with no summaries are skipped.
                        Note: When the conversation later ends normally, another reflection may be generated again if Save Personal Reflection is on."""
        return ConfigValueString("save_personal_reflection_now", "Save Personal Reflection Now", description, "")

    @staticmethod
    def get_real_world_timestamp_config_value() -> ConfigValue:
        description = """Display the current real-world date and time. Click 'Get Timestamp' to update the display with the current Unix timestamp (seconds since epoch)."""
        return ConfigValueString("real_world_timestamp", "Real World Timestamp", description, "")