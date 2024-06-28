from typing import Any, Callable
from src.config.config_values import ConfigValues
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value import ConfigValue
from src.config.types.config_value_group import ConfigValueGroup
from src.config.definitions.game_definitions import GameDefinitions
from src.config.definitions.language_definitions import LanguageDefinitions
from src.config.definitions.llm_definitions import LLMDefinitions
from src.config.definitions.other_definitions import OtherDefinitions
from src.config.definitions.prompt_definitions import PromptDefinitions
from src.config.definitions.stt_definitions import STTDefinitions
from src.config.definitions.tts_definitions import TTSDefinitions
import sys


class MantellaConfigValueDefinitionsNew:
    @staticmethod
    def get_config_values(on_value_change_callback: Callable[..., Any] | None = None) -> ConfigValues:
        result: ConfigValues = ConfigValues()

        # hidden_category= ConfigValueGroup("Hidden", "Hidden", "Don't show these on the UI", on_value_change_callback, is_hidden=True)
        # hidden_category.add_config_value(ConfigValueBool("show_advanced","","", False, is_hidden=True))
        # result.add_base_group(hidden_category)

        if "--integrated" not in sys.argv: # if integrated, these paths are all relative so do not need to be manually set
            game_category = ConfigValueGroup("Game", "Game", "Settings for the games Mantella supports.", on_value_change_callback)
            game_category.add_config_value(GameDefinitions.get_game_config_value())
            game_category.add_config_value(GameDefinitions.get_skyrim_mod_folder_config_value())
            game_category.add_config_value(GameDefinitions.get_skyrimvr_mod_folder_config_value())
            game_category.add_config_value(GameDefinitions.get_fallout4_mod_folder_config_value())
            game_category.add_config_value(GameDefinitions.get_fallout4vr_mod_folder_config_value())
            game_category.add_config_value(GameDefinitions.get_fallout4vr_folder_config_value())
            result.add_base_group(game_category)
        
        llm_category = ConfigValueGroup("LLM", "Large Language Model", "Settings for the LLM providers and the LLMs themselves.", on_value_change_callback)
        llm_category.add_config_value(LLMDefinitions.get_model_config_value())
        llm_category.add_config_value(LLMDefinitions.get_max_response_sentences_config_value())
        llm_category.add_config_value(PromptDefinitions.get_skyrim_prompt_config_value())
        llm_category.add_config_value(PromptDefinitions.get_skyrim_multi_npc_prompt_config_value())
        llm_category.add_config_value(PromptDefinitions.get_fallout4_prompt_config_value())
        llm_category.add_config_value(PromptDefinitions.get_fallout4_multi_npc_prompt_config_value())
        llm_category.add_config_value(PromptDefinitions.get_radiant_start_prompt_config_value())
        llm_category.add_config_value(PromptDefinitions.get_radiant_end_prompt_config_value())
        llm_category.add_config_value(PromptDefinitions.get_memory_prompt_config_value())
        llm_category.add_config_value(PromptDefinitions.get_resummarize_prompt_config_value())
        llm_category.add_config_value(LLMDefinitions.get_llm_api_config_value())
        llm_category.add_config_value(LLMDefinitions.get_llm_custom_service_url_config_value())
        llm_category.add_config_value(LLMDefinitions.get_custom_token_count_config_value())
        llm_category.add_config_value(LLMDefinitions.get_automatic_greeting_folder_config_value())
        llm_category.add_config_value(LLMDefinitions.get_wait_time_buffer_config_value())
        llm_category.add_config_value(LLMDefinitions.get_temperature_config_value())
        llm_category.add_config_value(LLMDefinitions.get_top_p_config_value())
        llm_category.add_config_value(LLMDefinitions.get_stop_config_value())
        llm_category.add_config_value(LLMDefinitions.get_frequency_penalty_config_value())
        llm_category.add_config_value(LLMDefinitions.get_max_tokens_config_value())
        # llm_category.add_config_value(LLMDefinitions.get_stop_llm_generation_on_assist_keyword())
        llm_category.add_config_value(LLMDefinitions.get_try_filter_narration())
        result.add_base_group(llm_category)

        tts_category = ConfigValueGroup("TTS", "Text-to-Speech", "Settings for the TTS methods Mantella supports.", on_value_change_callback)
        tts_category.add_config_value(TTSDefinitions.get_tts_service_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xvasynth_folder_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_folder_config_value())
        tts_category.add_config_value(TTSDefinitions.get_facefx_folder_config_value())
        tts_category.add_config_value(TTSDefinitions.get_number_words_tts_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_url_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_default_model_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_device_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_deepspeed_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_lowvram_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_data_config_value())
        tts_category.add_config_value(TTSDefinitions.get_xtts_accent_config_value())
        tts_category.add_config_value(TTSDefinitions.get_tts_process_device_config_value())
        tts_category.add_config_value(TTSDefinitions.get_pace_config_value())
        tts_category.add_config_value(TTSDefinitions.get_use_cleanup_config_value())
        tts_category.add_config_value(TTSDefinitions.get_use_sr_config_value())
        tts_category.add_config_value(TTSDefinitions.get_FO4_NPC_response_volume_config_value())
        tts_category.add_config_value(TTSDefinitions.get_tts_print_config_value())
        result.add_base_group(tts_category)

        stt_category = ConfigValueGroup("STT", "Speech-to-Text", "Settings for the STT methods Mantella supports.", on_value_change_callback)
        stt_category.add_config_value(STTDefinitions.get_use_automatic_audio_threshold_folder_config_value())
        stt_category.add_config_value(STTDefinitions.get_audio_threshold_folder_config_value())
        stt_category.add_config_value(STTDefinitions.get_model_size_config_value())
        stt_category.add_config_value(STTDefinitions.get_pause_threshold_config_value())
        stt_category.add_config_value(STTDefinitions.get_listen_timeout_config_value())
        stt_category.add_config_value(STTDefinitions.get_stt_language_config_value())
        stt_category.add_config_value(STTDefinitions.get_stt_translate_config_value())
        stt_category.add_config_value(STTDefinitions.get_process_device_config_value())
        stt_category.add_config_value(STTDefinitions.get_whisper_type_config_value())
        stt_category.add_config_value(STTDefinitions.get_whisper_url_config_value())
        result.add_base_group(stt_category)

        language_category = ConfigValueGroup("Language", "Language", "Change the language used by Mantella as well as keywords.", on_value_change_callback)
        language_category.add_config_value(LanguageDefinitions.get_language_config_value())
        language_category.add_config_value(LanguageDefinitions.get_end_conversation_keyword_config_value())
        language_category.add_config_value(LanguageDefinitions.get_goodbye_npc_response())
        language_category.add_config_value(LanguageDefinitions.get_collecting_thoughts_npc_response())
        language_category.add_config_value(LanguageDefinitions.get_offended_npc_response())
        language_category.add_config_value(LanguageDefinitions.get_forgiven_npc_response())
        language_category.add_config_value(LanguageDefinitions.get_follow_npc_response())
        result.add_base_group(language_category)

        other_category = ConfigValueGroup("Other", "Other", "Other settings.", on_value_change_callback)
        other_category.add_config_value(OtherDefinitions.get_auto_launch_ui_config_value())
        other_category.add_config_value(OtherDefinitions.get_port_config_value())
        other_category.add_config_value(OtherDefinitions.get_show_http_debug_messages_config_value())
        other_category.add_config_value(OtherDefinitions.get_remove_mei_folders_config_value())
        other_category.add_config_value(OtherDefinitions.get_player_character_description())
        other_category.add_config_value(OtherDefinitions.get_voice_player_input())
        other_category.add_config_value(OtherDefinitions.get_player_voice_model())
        # other_category.add_config_value(OtherDefinitions.get_debugging_config_value())
        # other_category.add_config_value(OtherDefinitions.get_play_audio_from_script_config_value())
        # other_category.add_config_value(OtherDefinitions.get_debugging_npc_config_value())
        # other_category.add_config_value(OtherDefinitions.get_use_default_player_response_config_value())
        # other_category.add_config_value(OtherDefinitions.get_default_player_response_config_value())
        # other_category.add_config_value(OtherDefinitions.get_exit_on_first_exchange_config_value())
        other_category.add_config_value(OtherDefinitions.get_add_voicelines_to_all_voice_folders_config_value())
        result.add_base_group(other_category)
      
        return result