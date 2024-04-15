from src.config.types.config_value import ConfigValue
from src.config.types.config_value_group import ConfigValueGroup
from src.config.definitions.game_definitions import GameDefinitions
from src.config.definitions.language_definitions import LanguageDefinitions
from src.config.definitions.llm_definitions import LLMDefinitions
from src.config.definitions.other_definitions import OtherDefinitions
from src.config.definitions.prompt_definitions import PromptDefinitions
from src.config.definitions.stt_definitions import STTDefinitions
from src.config.definitions.tts_definitions import TTSDefinitions


class MantellaConfigValueDefinitionsClassic:
    @staticmethod
    def get_config_values() -> list[ConfigValue]:
        result: list[ConfigValue] = []

        game_category = ConfigValueGroup("Game", "Game", "Settings for the games Mantella supports")
        game_category.add_config_value(GameDefinitions.get_game_config_value())
        result.append(game_category)
        
        paths_category = ConfigValueGroup("Paths", "Paths", "Settings to make MantellaSoftware aware where the different programs are located")
        paths_category.add_config_value(GameDefinitions.get_skyrim_mod_folder_config_value())
        paths_category.add_config_value(GameDefinitions.get_skyrimvr_mod_folder_config_value())
        paths_category.add_config_value(GameDefinitions.get_fallout4_mod_folder_config_value())
        paths_category.add_config_value(GameDefinitions.get_fallout4vr_mod_folder_config_value())
        paths_category.add_config_value(GameDefinitions.get_fallout4vr_folder_config_value())        
        paths_category.add_config_value(TTSDefinitions.get_xvasynth_folder_config_value())
        paths_category.add_config_value(TTSDefinitions.get_xtts_folder_config_value())
        paths_category.add_config_value(TTSDefinitions.get_facefx_folder_config_value())
        result.append(paths_category)
        
        language_category = ConfigValueGroup("Language", "Language", "Basic language settings")
        language_category.add_config_value(LanguageDefinitions.get_language_config_value())
        language_category.add_config_value(LanguageDefinitions.get_end_conversation_keyword_config_value())
        result.append(language_category)
        
        microphone_category = ConfigValueGroup("Microphone", "Microphone", "Note: Whether to use the microphone or text as input for the player is decided by the game itself. Check the options for Mantella ingame")
        microphone_category.add_config_value(STTDefinitions.get_use_automatic_audio_threshold_folder_config_value())
        microphone_category.add_config_value(STTDefinitions.get_audio_threshold_folder_config_value())
        result.append(microphone_category)
        
        languagemodel_category = ConfigValueGroup("LanguageModel", "Language model", "Basic settings for the Large Language Model (LLM) Mantella uses to generate NPC responses")
        languagemodel_category.add_config_value(LLMDefinitions.get_model_config_value())
        languagemodel_category.add_config_value(LLMDefinitions.get_max_response_sentences_config_value())
        result.append(languagemodel_category)
        
        speech_category = ConfigValueGroup("Speech", "Speech", "Basic settings for the Text-To-Speech service used")
        speech_category.add_config_value(TTSDefinitions.get_tts_service_config_value())
        result.append(speech_category)
        
        conversation_category = ConfigValueGroup("Conversation", "Conversation", "Settings about the flow of a conversation")
        conversation_category.add_config_value(OtherDefinitions.get_automatic_greeting_folder_config_value())
        result.append(conversation_category)
        
        cleanup_category = ConfigValueGroup("Cleanup", "Cleanup", "")
        cleanup_category.add_config_value(OtherDefinitions.get_remove_mei_folders_config_value())
        result.append(cleanup_category)
        
        prompt_category = ConfigValueGroup("Prompt", "Prompt", "Here you can change the different LLM prompts used by Mantella")
        prompt_category.add_config_value(PromptDefinitions.get_skyrim_prompt_config_value())
        prompt_category.add_config_value(PromptDefinitions.get_skyrim_multi_npc_prompt_config_value())
        prompt_category.add_config_value(PromptDefinitions.get_fallout4_prompt_config_value())
        prompt_category.add_config_value(PromptDefinitions.get_fallout4_multi_npc_prompt_config_value())
        prompt_category.add_config_value(PromptDefinitions.get_radiant_start_prompt_config_value())
        prompt_category.add_config_value(PromptDefinitions.get_radiant_end_prompt_config_value())
        prompt_category.add_config_value(PromptDefinitions.get_memory_prompt_config_value())
        prompt_category.add_config_value(PromptDefinitions.get_resummarize_prompt_config_value())
        result.append(prompt_category)
        
        language_advanced_category = ConfigValueGroup("Language.Advanced", "Language advanced", "More advanced language settings.\nIf you are changing the base language to something else than 'en' you will most likely also want to adjust some of these ")
        language_advanced_category.add_config_value(LanguageDefinitions.get_goodbye_npc_response())
        language_advanced_category.add_config_value(LanguageDefinitions.get_collecting_thoughts_npc_response())
        language_advanced_category.add_config_value(LanguageDefinitions.get_offended_npc_response())
        language_advanced_category.add_config_value(LanguageDefinitions.get_forgiven_npc_response())
        language_advanced_category.add_config_value(LanguageDefinitions.get_follow_npc_response())
        result.append(language_advanced_category)
        
        microphone_advanced_category = ConfigValueGroup("Microphone.Advanced", "Microphone advanced", "More advanced settings concerning microphone input and voice transription.")
        microphone_advanced_category.add_config_value(STTDefinitions.get_model_size_config_value())
        microphone_advanced_category.add_config_value(STTDefinitions.get_pause_threshold_config_value())
        microphone_advanced_category.add_config_value(STTDefinitions.get_listen_timeout_config_value())
        microphone_advanced_category.add_config_value(STTDefinitions.get_stt_language_config_value())
        microphone_advanced_category.add_config_value(STTDefinitions.get_stt_translate_config_value())
        microphone_advanced_category.add_config_value(STTDefinitions.get_process_device_config_value())
        microphone_advanced_category.add_config_value(STTDefinitions.get_whisper_type_config_value())
        microphone_advanced_category.add_config_value(STTDefinitions.get_whisper_url_config_value())
        result.append(microphone_advanced_category)
        
        llm_advanced_category = ConfigValueGroup("LanguageModel.Advanced", "Language model Advanced", "More advanced settings concerning LLMs")
        llm_advanced_category.add_config_value(LLMDefinitions.get_llm_api_config_value())
        llm_advanced_category.add_config_value(LLMDefinitions.get_custom_token_count_config_value())
        llm_advanced_category.add_config_value(LLMDefinitions.get_wait_time_buffer_config_value())
        llm_advanced_category.add_config_value(LLMDefinitions.get_temperature_config_value())
        llm_advanced_category.add_config_value(LLMDefinitions.get_top_p_config_value())
        llm_advanced_category.add_config_value(LLMDefinitions.get_stop_config_value())
        llm_advanced_category.add_config_value(LLMDefinitions.get_frequency_penalty_config_value())
        llm_advanced_category.add_config_value(LLMDefinitions.get_max_tokens_config_value())
        result.append(llm_advanced_category)
        
        speech_advanced_category = ConfigValueGroup("Speech.Advanced", "Speech Advanced", "More advanced settings concerning the voice generation")
        speech_advanced_category.add_config_value(TTSDefinitions.get_number_words_tts_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_xtts_url_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_xtts_default_model_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_xtts_device_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_xtts_deepspeed_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_xtts_lowvram_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_xtts_data_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_tts_process_device_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_pace_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_use_cleanup_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_use_sr_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_FO4_NPC_response_volume_config_value())
        speech_advanced_category.add_config_value(TTSDefinitions.get_tts_print_config_value())
        result.append(speech_advanced_category)
        
        http_category = ConfigValueGroup("HTTP", "HTTP", "Settings for the HTTP server MantellaSoftware provides for the games to connect to")
        http_category.add_config_value(OtherDefinitions.get_port_config_value())
        http_category.add_config_value(OtherDefinitions.get_show_http_debug_messages_config_value())
        result.append(http_category)
        
        debugging_category = ConfigValueGroup("Debugging", "Debugging", "Settings that might help debug problems with Mantella")
        debugging_category.add_config_value(OtherDefinitions.get_debugging_config_value())
        debugging_category.add_config_value(OtherDefinitions.get_play_audio_from_script_config_value())
        debugging_category.add_config_value(OtherDefinitions.get_debugging_npc_config_value())
        debugging_category.add_config_value(OtherDefinitions.get_use_default_player_response_config_value())
        debugging_category.add_config_value(OtherDefinitions.get_default_player_response_config_value())
        debugging_category.add_config_value(OtherDefinitions.get_exit_on_first_exchange_config_value())
        debugging_category.add_config_value(OtherDefinitions.get_add_voicelines_to_all_voice_folders_config_value())
        result.append(debugging_category)
        return result