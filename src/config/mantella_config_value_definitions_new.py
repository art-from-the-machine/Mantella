from typing import Any, Callable
from src.conversation.action import Action
from src.config.config_values import ConfigValues
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value import ConfigValue
from src.config.types.config_value_group import ConfigValueGroup
from src.config.definitions.game_definitions import GameDefinitions
from src.config.definitions.language_definitions import LanguageDefinitions
from src.config.definitions.llm_definitions import LLMDefinitions
from src.config.definitions.other_definitions import OtherDefinitions
from src.config.definitions.startup_definitions import StartupDefinitions
from src.config.definitions.prompt_definitions import PromptDefinitions
from src.config.definitions.stt_definitions import STTDefinitions
from src.config.definitions.tts_definitions import TTSDefinitions
from src.config.definitions.vision_definitions import VisionDefinitions
from src.config.definitions.model_profile_definitions import ModelProfileDefinitions
import sys


class MantellaConfigValueDefinitionsNew:
    @staticmethod
    def get_config_values(is_integrated: bool, actions: list[Action], on_value_change_callback: Callable[..., Any] | None = None) -> ConfigValues:
        result: ConfigValues = ConfigValues()
        is_integrated = "--integrated" in sys.argv
        # hidden_category= ConfigValueGroup("Hidden", "Hidden", "Don't show these on the UI", on_value_change_callback, is_hidden=True)
        # hidden_category.add_config_value(ConfigValueBool("show_advanced","","", False, is_hidden=True))
        # result.add_base_group(hidden_category)

        # if "--integrated" not in sys.argv: # if integrated, these paths are all relative so do not need to be manually set
        game_category = ConfigValueGroup("Game", "Game", "Settings for the games Mantella supports.", on_value_change_callback, is_integrated)
        game_category.add_config_value(GameDefinitions.get_game_config_value())
        game_category.add_config_value(GameDefinitions.get_skyrim_mod_folder_config_value())
        game_category.add_config_value(GameDefinitions.get_skyrimvr_mod_folder_config_value())
        game_category.add_config_value(GameDefinitions.get_fallout4_mod_folder_config_value())
        game_category.add_config_value(GameDefinitions.get_fallout4vr_mod_folder_config_value())
        game_category.add_config_value(GameDefinitions.get_fallout4_folder_config_value())
        game_category.add_config_value(GameDefinitions.get_fallout4vr_folder_config_value())
        result.add_base_group(game_category)
        
        llm_category = ConfigValueGroup("LLM", "Large Language Model", "Settings for the LLM providers and the LLMs themselves.", on_value_change_callback)
        llm_category.add_config_value(LLMDefinitions.get_llm_api_config_value())
        llm_category.add_config_value(LLMDefinitions.get_model_config_value())
        # llm_category.add_config_value(LLMDefinitions.get_llm_priority_config_value())
        llm_category.add_config_value(LLMDefinitions.get_max_response_sentences_single_config_value())
        llm_category.add_config_value(LLMDefinitions.get_max_response_sentences_multi_config_value())
        llm_category.add_config_value(LLMDefinitions.get_custom_token_count_config_value())
        #llm_category.add_config_value(LLMDefinitions.get_llm_custom_service_url_config_value())
        llm_category.add_config_value(LLMDefinitions.get_wait_time_buffer_config_value())
        # llm_category.add_config_value(LLMDefinitions.get_try_filter_narration())
        llm_category.add_config_value(LLMDefinitions.get_llm_params_config_value())
        llm_category.add_config_value(LLMDefinitions.get_allow_per_character_llm_overrides_config_value())
        # llm_category.add_config_value(LLMDefinitions.get_stop_llm_generation_on_assist_keyword())
        
        # Multi-NPC LLM Configuration
        llm_category.add_config_value(LLMDefinitions.get_multi_npc_llm_api_config_value())
        llm_category.add_config_value(LLMDefinitions.get_multi_npc_model_config_value())
        llm_category.add_config_value(LLMDefinitions.get_multi_npc_custom_token_count_config_value())
        llm_category.add_config_value(LLMDefinitions.get_multi_npc_llm_params_config_value())
        
        # Summary LLM Configuration
        llm_category.add_config_value(LLMDefinitions.get_summary_llm_api_config_value())
        llm_category.add_config_value(LLMDefinitions.get_summary_model_config_value())
        llm_category.add_config_value(LLMDefinitions.get_summary_custom_token_count_config_value())
        llm_category.add_config_value(LLMDefinitions.get_summary_llm_params_config_value())
        
        llm_category.add_config_value(LLMDefinitions.get_narration_handling())
        llm_category.add_config_value(LLMDefinitions.get_narrator_voice())
        llm_category.add_config_value(LLMDefinitions.get_narration_start_indicators())
        llm_category.add_config_value(LLMDefinitions.get_narration_end_indicators())
        llm_category.add_config_value(LLMDefinitions.get_speech_start_indicators())
        llm_category.add_config_value(LLMDefinitions.get_speech_end_indicators())
        llm_category.add_config_value(LLMDefinitions.get_narration_indicators())
        result.add_base_group(llm_category)

        tts_category = ConfigValueGroup("TTS", "Text-to-Speech", "Settings for the TTS methods Mantella supports.", on_value_change_callback)
        tts_category.add_config_value(TTSDefinitions.get_tts_service_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xvasynth_folder_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_folder_config_value())
        tts_category.add_config_value(TTSDefinitions.get_piper_folder_config_value(is_integrated))
        tts_category.add_config_value(TTSDefinitions.get_lipgen_folder_config_value(is_integrated))
        tts_category.add_config_value(TTSDefinitions.get_facefx_folder_config_value(is_integrated))
        tts_category.add_config_value(TTSDefinitions.get_number_words_tts_config_value())
        tts_category.add_config_value(TTSDefinitions.get_lip_generation_config_value())
        tts_category.add_config_value(TTSDefinitions.get_fast_response_mode_config_value())
        tts_category.add_config_value(TTSDefinitions.get_fast_response_mode_volume_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_url_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_default_model_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_device_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_deepspeed_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_lowvram_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_data_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_accent_config_value())
        tts_category.add_config_value(TTSDefinitions.get_tts_print_config_value())
        tts_category.add_config_value(TTSDefinitions.get_tts_process_device_config_value())
        tts_category.add_config_value(TTSDefinitions.get_pace_config_value())
        tts_category.add_config_value(TTSDefinitions.get_use_cleanup_config_value())
        tts_category.add_config_value(TTSDefinitions.get_use_sr_config_value())
        result.add_base_group(tts_category)

        stt_category = ConfigValueGroup("STT", "Speech-to-Text", "Settings for the STT methods Mantella supports.", on_value_change_callback)
        stt_category.add_config_value(STTDefinitions.get_audio_threshold_config_value())
        stt_category.add_config_value(STTDefinitions.get_allow_interruption_config_value()) 
        stt_category.add_config_value(STTDefinitions.get_save_mic_input_config_value())
        stt_category.add_config_value(STTDefinitions.get_stt_service_config_value())
        stt_category.add_config_value(STTDefinitions.get_pause_threshold_config_value())
        stt_category.add_config_value(STTDefinitions.get_play_cough_sound_config_value())
        stt_category.add_config_value(STTDefinitions.get_listen_timeout_config_value())
        stt_category.add_config_value(STTDefinitions.get_moonshine_model_size_config_value())
        stt_category.add_config_value(STTDefinitions.get_whisper_model_size_config_value())
        stt_category.add_config_value(STTDefinitions.get_proactive_mic_mode_config_value())
        stt_category.add_config_value(STTDefinitions.get_min_refresh_secs_config_value())
        stt_category.add_config_value(STTDefinitions.get_external_whisper_service_config_value())
        stt_category.add_config_value(STTDefinitions.get_whisper_url_config_value())
        stt_category.add_config_value(STTDefinitions.get_stt_language_config_value())
        stt_category.add_config_value(STTDefinitions.get_stt_translate_config_value())
        stt_category.add_config_value(STTDefinitions.get_process_device_config_value())
        stt_category.add_config_value(STTDefinitions.get_moonshine_folder_config_value(is_integrated))
        result.add_base_group(stt_category)

        vision_category = ConfigValueGroup("Vision", "Vision", "Vision settings.", on_value_change_callback)
        vision_category.add_config_value(VisionDefinitions.get_vision_enabled_config_value())
        vision_category.add_config_value(VisionDefinitions.get_low_resolution_mode_config_value())
        vision_category.add_config_value(VisionDefinitions.get_save_screenshot_config_value())
        vision_category.add_config_value(VisionDefinitions.get_image_quality_config_value())
        vision_category.add_config_value(VisionDefinitions.get_resize_method_config_value())
        vision_category.add_config_value(VisionDefinitions.get_capture_offset_config_value())
        vision_category.add_config_value(VisionDefinitions.get_custom_vision_model_config_value())
        vision_category.add_config_value(VisionDefinitions.get_vision_llm_api_config_value())
        vision_category.add_config_value(VisionDefinitions.get_vision_model_config_value())
        vision_category.add_config_value(VisionDefinitions.get_vision_custom_token_count_config_value())
        vision_category.add_config_value(VisionDefinitions.get_vision_llm_params_config_value())
        vision_category.add_config_value(VisionDefinitions.get_use_game_screenshots_config_value())
        result.add_base_group(vision_category)

        language_category = ConfigValueGroup("Language", "Language", "Change the language used by Mantella as well as keywords.", on_value_change_callback)
        language_category.add_config_value(LanguageDefinitions.get_language_config_value())
        language_category.add_config_value(LanguageDefinitions.get_end_conversation_keyword_config_value())
        language_category.add_config_value(LanguageDefinitions.get_goodbye_npc_response())
        language_category.add_config_value(LanguageDefinitions.get_collecting_thoughts_npc_response())
        for action in actions:
            language_category.add_config_value(LanguageDefinitions.get_action_keyword_override(action))
        result.add_base_group(language_category)

        prompts_category = ConfigValueGroup("Prompts", "Prompts", "Change the basic prompts used by Mantella.", on_value_change_callback)
        prompts_category.add_config_value(PromptDefinitions.get_skyrim_prompt_config_value())
        prompts_category.add_config_value(PromptDefinitions.get_skyrim_multi_npc_prompt_config_value())
        prompts_category.add_config_value(PromptDefinitions.get_skyrim_radiant_prompt_config_value())
        prompts_category.add_config_value(PromptDefinitions.get_fallout4_prompt_config_value())
        prompts_category.add_config_value(PromptDefinitions.get_fallout4_multi_npc_prompt_config_value())
        prompts_category.add_config_value(PromptDefinitions.get_fallout4_radiant_prompt_config_value())
        prompts_category.add_config_value(PromptDefinitions.get_memory_prompt_config_value())
        prompts_category.add_config_value(PromptDefinitions.get_resummarize_prompt_config_value())
        prompts_category.add_config_value(PromptDefinitions.get_vision_prompt_config_value())
        prompts_category.add_config_value(PromptDefinitions.get_radiant_start_prompt_config_value())
        prompts_category.add_config_value(PromptDefinitions.get_radiant_end_prompt_config_value())
        result.add_base_group(prompts_category)

        startup_category = ConfigValueGroup("Startup", "Startup", "Startup settings.", on_value_change_callback)
        startup_category.add_config_value(StartupDefinitions.get_auto_launch_ui_config_value())
        startup_category.add_config_value(StartupDefinitions.get_play_startup_sound_config_value())
        startup_category.add_config_value(StartupDefinitions.get_remove_mei_folders_config_value())
        result.add_base_group(startup_category)

        other_category = ConfigValueGroup("Other", "Other", "Other settings.", on_value_change_callback)
        other_category.add_config_value(OtherDefinitions.get_automatic_greeting_config_value())
        other_category.add_config_value(OtherDefinitions.get_conversation_summary_enabled_config_value())
        other_category.add_config_value(OtherDefinitions.get_active_actions(actions))
        other_category.add_config_value(OtherDefinitions.get_reload_character_data_config_value())
        other_category.add_config_value(OtherDefinitions.get_max_count_events_config_value())
        other_category.add_config_value(OtherDefinitions.get_events_refresh_time_config_value())
        other_category.add_config_value(OtherDefinitions.get_hourly_time_config_value())
        other_category.add_config_value(OtherDefinitions.get_player_character_description())
        other_category.add_config_value(OtherDefinitions.get_voice_player_input())
        other_category.add_config_value(OtherDefinitions.get_player_voice_model())
        other_category.add_config_value(OtherDefinitions.get_save_audio_data_to_character_folder_config_value())
        other_category.add_config_value(OtherDefinitions.get_hot_swap_enabled_config_value())
        other_category.add_config_value(OtherDefinitions.get_port_config_value())
        other_category.add_config_value(OtherDefinitions.get_show_http_debug_messages_config_value())
        other_category.add_config_value(OtherDefinitions.get_advanced_logs_config_value())
        # other_category.add_config_value(OtherDefinitions.get_debugging_config_value())
        # other_category.add_config_value(OtherDefinitions.get_play_audio_from_script_config_value())
        # other_category.add_config_value(OtherDefinitions.get_debugging_npc_config_value())
        # other_category.add_config_value(OtherDefinitions.get_use_default_player_response_config_value())
        # other_category.add_config_value(OtherDefinitions.get_default_player_response_config_value())
        # other_category.add_config_value(OtherDefinitions.get_exit_on_first_exchange_config_value())
        result.add_base_group(other_category)
        
        model_profiles_category = ConfigValueGroup("Model Profiles", "Model Profiles", "Create and manage model parameter profiles for different LLM models.", on_value_change_callback)
        model_profiles_category.add_config_value(ModelProfileDefinitions.get_selected_service_config_value())
        model_profiles_category.add_config_value(ModelProfileDefinitions.get_selected_model_config_value())
        model_profiles_category.add_config_value(ModelProfileDefinitions.get_profile_parameters_config_value())
        result.add_base_group(model_profiles_category)
      
        return result
