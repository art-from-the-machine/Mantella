import logging
from typing import Any, Hashable
import regex
from src.config.definitions.llm_definitions import NarrationHandlingEnum
from src.llm.summary_client import SummaryLLMCLient
from src.games.equipment import Equipment, EquipmentItem
from src.games.external_character_info import external_character_info
from src.games.gameable import Gameable
from src.llm.sentence import Sentence
from src.output_manager import ChatManager
from src.remember.remembering import Remembering
from src.remember.summaries import Summaries
from src.config.config_loader import ConfigLoader
from src.llm.llm_client import LLMClient
from src.conversation.conversation import Conversation
from src.conversation.context import Context
from src.character_manager import Character
import src.utils as utils
from src.http.communication_constants import communication_constants as comm_consts
from src.stt import Transcriber
from src.config.definitions.game_definitions import GameEnum
from src.games.fallout4 import Fallout4
from src.games.skyrim import Skyrim
from src.llm.sonnet_cache_connector import SonnetCacheConnector

class CharacterDoesNotExist(Exception):
    """Exception raised when NPC name cannot be found in skyrim_characters.csv/fallout4_characters.csv"""
    pass


class GameStateManager:
    TOKEN_LIMIT_PERCENT: float = 0.45 # not used?
    WORLD_ID_CLEANSE_REGEX: regex.Pattern = regex.compile('[^A-Za-z0-9]+')

    @utils.time_it
    def __init__(self, game: Gameable, chat_manager: ChatManager, config: ConfigLoader, language_info: dict[Hashable, str], client: LLMClient, summary_client:SummaryLLMCLient, stt_api_file: str, api_file: str):        
        self.__game: Gameable = game
        self.__config: ConfigLoader = config
        self.__language_info: dict[Hashable, str] = language_info 
        self.__client: LLMClient = client
        self.__chat_manager: ChatManager = chat_manager
        
        # Create separate LLM client for summaries if different settings are configured
        from src.llm.client_base import ClientBase
        from src.llm.key_file_resolver import key_file_resolver
        if (config.summary_llm_api != config.llm_api or 
            config.summary_llm != config.llm or 
            config.summary_llm_params != config.llm_params or 
            config.summary_custom_token_count != config.custom_token_count):
            # Create separate client for summaries with different settings
            summary_secret_key_files = key_file_resolver.get_key_files_for_service(config.summary_llm_api, api_file)
            
            # Apply profile parameters if enabled and profile exists
            summary_llm_params = config.summary_llm_params
            if config.apply_profile_summaries:
                try:
                    from src.model_profile_manager import ModelProfileManager
                    profile_manager = ModelProfileManager()
                    summary_llm_params = profile_manager.apply_profile_to_params(
                        service=config.summary_llm_api,
                        model=config.summary_llm,
                        fallback_params=config.summary_llm_params
                    )
                    
                    # Log profile application for summaries
                    has_profile = profile_manager.has_profile(config.summary_llm_api, config.summary_llm)
                    if has_profile:
                        logging.info(f"Applied profile for summaries: {config.summary_llm_api}/{config.summary_llm}")
                        logging.info(f"Summary Profile Parameters: {summary_llm_params}")
                    else:
                        logging.info(f"No profile found for summaries {config.summary_llm_api}/{config.summary_llm}, using manual parameters: {summary_llm_params}")
                        
                except Exception as e:
                    logging.error(f"Error applying profile for summaries: {e}")
                    summary_llm_params = config.summary_llm_params
            else:
                logging.info(f"Summary Parameters (manual): {summary_llm_params}")
            
            summary_client = ClientBase(
                config.summary_llm_api,
                config.summary_llm,
                summary_llm_params,
                config.summary_custom_token_count,
                summary_secret_key_files
            )
        elif config.apply_profile_summaries:
            # Same settings as main LLM but profile application is enabled for summaries
            # Create a separate client with profile-applied parameters
            summary_secret_key_files = key_file_resolver.get_key_files_for_service(config.llm_api, api_file)
            
            summary_llm_params = config.llm_params
            try:
                from src.model_profile_manager import ModelProfileManager
                profile_manager = ModelProfileManager()
                summary_llm_params = profile_manager.apply_profile_to_params(
                    service=config.llm_api,
                    model=config.llm,
                    fallback_params=config.llm_params
                )
                
                # Log profile application for summaries (same model as main)
                has_profile = profile_manager.has_profile(config.llm_api, config.llm)
                if has_profile:
                    logging.info(f"Applied profile for summaries (same model as main): {config.llm_api}/{config.llm}")
                    logging.info(f"Summary Profile Parameters (same model): {summary_llm_params}")
                else:
                    logging.info(f"No profile found for summaries {config.llm_api}/{config.llm}, using manual parameters: {summary_llm_params}")
                    
            except Exception as e:
                logging.error(f"Error applying profile for summaries: {e}")
                summary_llm_params = config.llm_params
            
            summary_client = ClientBase(
                config.llm_api,
                config.llm,
                summary_llm_params,
                config.custom_token_count,
                summary_secret_key_files
            )
        else:
            # Use the same client for summaries
            summary_client = None
            
        # Create separate LLM client for multi-NPC conversations if different settings are configured
        if (config.multi_npc_llm_api != config.llm_api or 
            config.multi_npc_llm != config.llm or 
            config.multi_npc_llm_params != config.llm_params or 
            config.multi_npc_custom_token_count != config.custom_token_count):
            # Create separate client for multi-NPC conversations with different settings
            multi_npc_secret_key_files = key_file_resolver.get_key_files_for_service(config.multi_npc_llm_api, api_file)
            
            # Apply profile parameters if enabled and profile exists
            multi_npc_llm_params = config.multi_npc_llm_params
            if config.apply_profile_multi_npc:
                try:
                    from src.model_profile_manager import ModelProfileManager
                    profile_manager = ModelProfileManager()
                    multi_npc_llm_params = profile_manager.apply_profile_to_params(
                        service=config.multi_npc_llm_api,
                        model=config.multi_npc_llm,
                        fallback_params=config.multi_npc_llm_params
                    )
                    
                    # Log profile application for multi-NPC
                    has_profile = profile_manager.has_profile(config.multi_npc_llm_api, config.multi_npc_llm)
                    if has_profile:
                        logging.info(f"Applied profile for multi-NPC conversations: {config.multi_npc_llm_api}/{config.multi_npc_llm}")
                        logging.info(f"Multi-NPC Profile Parameters: {multi_npc_llm_params}")
                    else:
                        logging.info(f"No profile found for multi-NPC {config.multi_npc_llm_api}/{config.multi_npc_llm}, using manual parameters: {multi_npc_llm_params}")
                        
                except Exception as e:
                    logging.error(f"Error applying profile for multi-NPC conversations: {e}")
                    multi_npc_llm_params = config.multi_npc_llm_params
            else:
                logging.info(f"Multi-NPC Parameters (manual): {multi_npc_llm_params}")
            
            multi_npc_client = ClientBase(
                config.multi_npc_llm_api,
                config.multi_npc_llm,
                multi_npc_llm_params,
                config.multi_npc_custom_token_count,
                multi_npc_secret_key_files
            )
            self._attach_sonnet_cache(multi_npc_client, config, "multi-NPC client (diff settings)")
        elif config.apply_profile_multi_npc:
            # Same settings as main LLM but profile application is enabled for multi-NPC
            # Create a separate client with profile-applied parameters
            multi_npc_secret_key_files = key_file_resolver.get_key_files_for_service(config.llm_api, api_file)
            
            multi_npc_llm_params = config.llm_params
            try:
                from src.model_profile_manager import ModelProfileManager
                profile_manager = ModelProfileManager()
                multi_npc_llm_params = profile_manager.apply_profile_to_params(
                    service=config.llm_api,
                    model=config.llm,
                    fallback_params=config.llm_params
                )
                
                # Log profile application for multi-NPC (same model as main)
                has_profile = profile_manager.has_profile(config.llm_api, config.llm)
                if has_profile:
                    logging.info(f"Applied profile for multi-NPC conversations (same model as main): {config.llm_api}/{config.llm}")
                    logging.info(f"Multi-NPC Profile Parameters (same model): {multi_npc_llm_params}")
                else:
                    logging.info(f"No profile found for multi-NPC {config.llm_api}/{config.llm}, using manual parameters: {multi_npc_llm_params}")
                    
            except Exception as e:
                logging.error(f"Error applying profile for multi-NPC conversations: {e}")
                multi_npc_llm_params = config.llm_params
            
            multi_npc_client = ClientBase(
                config.llm_api,
                config.llm,
                multi_npc_llm_params,
                config.custom_token_count,
                multi_npc_secret_key_files
            )
            self._attach_sonnet_cache(multi_npc_client, config, "multi-NPC client (profiled main settings)")
        else:
            # Use the same client for multi-NPC conversations
            multi_npc_client = None
        
        # Update chat manager with multi-NPC client
        chat_manager.update_multi_npc_client(multi_npc_client)
        
        # Clear per-character client cache to force recreation with new settings
        chat_manager.clear_per_character_client_cache()
            
        self.__rememberer: Remembering = Summaries(game, config, client, language_info['language'], summary_client)
        self.__talk: Conversation | None = None
        self.__mic_input: bool = False
        self.__mic_ptt: bool = False # push-to-talk
        self.__stt_api_file: str = stt_api_file
        self.__api_file: str = api_file
        self.__stt: Transcriber | None = None
        self.__first_line: bool = True
        self.__automatic_greeting: bool = config.automatic_greeting
        self.__conv_has_narrator: bool = config.narration_handling == NarrationHandlingEnum.USE_NARRATOR
        self.__should_reload: bool = False

    @property
    def game(self) -> Gameable:
        """Get the current game instance"""
        return self.__game

    def _attach_sonnet_cache(self, client: Any, config: ConfigLoader, client_context: str) -> None:
        """Attach the Sonnet cache connector to a client when applicable."""
        if not client or not getattr(config, 'sonnet_prompt_caching_enabled', False):
            return
        try:
            client._sonnet_cache_connector = SonnetCacheConnector(True)
        except Exception as e:
            logging.debug(f"Failed to attach Sonnet cache connector to {client_context}: {e}")

    @utils.time_it
    def hot_swap_settings(self, game: Gameable, chat_manager: ChatManager, config: ConfigLoader, llm_client: LLMClient, secret_key_file: str, image_secret_key_file: str) -> bool:
        """Attempts to hot-swap settings without ending active conversations.
        
        Args:
            game: Updated game instance
            chat_manager: Updated chat manager instance
            config: Updated config loader instance
            llm_client: Updated LLM client instance
            secret_key_file: Updated secret key file
            image_secret_key_file: Updated image secret key file
            
        Returns:
            bool: True if hot-swap was successful, False otherwise
        """
        try:
            # Update LLM client with hot-swapping
            llm_client_success = self.__client.hot_swap_settings(config, secret_key_file, image_secret_key_file)
            if not llm_client_success:
                logging.warning("LLM client hot-swap failed, using new client")
                self.__client = llm_client
            
            # Update basic components
            self.__game = game
            self.__config = config
            self.__chat_manager = chat_manager
            
            # Update config-derived values
            self.__automatic_greeting = config.automatic_greeting
            self.__conv_has_narrator = config.narration_handling == NarrationHandlingEnum.USE_NARRATOR
            
            # Create separate LLM client for summaries if different settings are configured
            from src.llm.client_base import ClientBase
            from src.llm.key_file_resolver import key_file_resolver
            if (config.summary_llm_api != config.llm_api or 
                config.summary_llm != config.llm or 
                config.summary_llm_params != config.llm_params or 
                config.summary_custom_token_count != config.custom_token_count):
                # Create separate client for summaries with different settings
                summary_secret_key_files = key_file_resolver.get_key_files_for_service(config.summary_llm_api, secret_key_file)
                
                # Apply profile parameters if enabled and profile exists
                summary_llm_params = config.summary_llm_params
                if config.apply_profile_summaries:
                    try:
                        from src.model_profile_manager import ModelProfileManager
                        profile_manager = ModelProfileManager()
                        summary_llm_params = profile_manager.apply_profile_to_params(
                            service=config.summary_llm_api,
                            model=config.summary_llm,
                            fallback_params=config.summary_llm_params
                        )
                        
                        # Log profile application for summaries (hot-swap)
                        has_profile = profile_manager.has_profile(config.summary_llm_api, config.summary_llm)
                        if has_profile:
                            logging.info(f"Hot-swap: Applied profile for summaries: {config.summary_llm_api}/{config.summary_llm}")
                            logging.info(f"Hot-swap Summary Profile Parameters: {summary_llm_params}")
                        else:
                            logging.info(f"Hot-swap: No profile found for summaries {config.summary_llm_api}/{config.summary_llm}, using manual parameters: {summary_llm_params}")
                            
                    except Exception as e:
                        logging.error(f"Error applying profile for summaries: {e}")
                        summary_llm_params = config.summary_llm_params
                else:
                    logging.info(f"Hot-swap Summary Parameters (manual): {summary_llm_params}")
                
                summary_client = ClientBase(
                    config.summary_llm_api,
                    config.summary_llm,
                    summary_llm_params,
                    config.summary_custom_token_count,
                    summary_secret_key_files
                )
            elif config.apply_profile_summaries:
                # Same settings as main LLM but profile application is enabled for summaries
                # Create a separate client with profile-applied parameters
                summary_secret_key_files = key_file_resolver.get_key_files_for_service(config.llm_api, secret_key_file)
                
                summary_llm_params = config.llm_params
                try:
                    from src.model_profile_manager import ModelProfileManager
                    profile_manager = ModelProfileManager()
                    summary_llm_params = profile_manager.apply_profile_to_params(
                        service=config.llm_api,
                        model=config.llm,
                        fallback_params=config.llm_params
                    )
                    
                    # Log profile application for summaries (same model as main - hot-swap)
                    has_profile = profile_manager.has_profile(config.llm_api, config.llm)
                    if has_profile:
                        logging.info(f"Hot-swap: Applied profile for summaries (same model as main): {config.llm_api}/{config.llm}")
                        logging.info(f"Hot-swap Summary Profile Parameters (same model): {summary_llm_params}")
                    else:
                        logging.info(f"Hot-swap: No profile found for summaries {config.llm_api}/{config.llm}, using manual parameters: {summary_llm_params}")
                        
                except Exception as e:
                    logging.error(f"Error applying profile for summaries: {e}")
                    summary_llm_params = config.llm_params
                
                summary_client = ClientBase(
                    config.llm_api,
                    config.llm,
                    summary_llm_params,
                    config.custom_token_count,
                    summary_secret_key_files
                )
            else:
                # Use the same client for summaries
                summary_client = None
            
            # Create separate LLM client for multi-NPC conversations if different settings are configured
            if (config.multi_npc_llm_api != config.llm_api or 
                config.multi_npc_llm != config.llm or 
                config.multi_npc_llm_params != config.llm_params or 
                config.multi_npc_custom_token_count != config.custom_token_count):
                # Create separate client for multi-NPC conversations with different settings
                multi_npc_secret_key_files = key_file_resolver.get_key_files_for_service(config.multi_npc_llm_api, secret_key_file)
                
                # Apply profile parameters if enabled and profile exists
                multi_npc_llm_params = config.multi_npc_llm_params
                if config.apply_profile_multi_npc:
                    try:
                        from src.model_profile_manager import ModelProfileManager
                        profile_manager = ModelProfileManager()
                        multi_npc_llm_params = profile_manager.apply_profile_to_params(
                            service=config.multi_npc_llm_api,
                            model=config.multi_npc_llm,
                            fallback_params=config.multi_npc_llm_params
                        )
                        
                        # Log profile application for multi-NPC (hot-swap)
                        has_profile = profile_manager.has_profile(config.multi_npc_llm_api, config.multi_npc_llm)
                        if has_profile:
                            logging.info(f"Hot-swap: Applied profile for multi-NPC conversations: {config.multi_npc_llm_api}/{config.multi_npc_llm}")
                            logging.info(f"Hot-swap Multi-NPC Profile Parameters: {multi_npc_llm_params}")
                        else:
                            logging.info(f"Hot-swap: No profile found for multi-NPC {config.multi_npc_llm_api}/{config.multi_npc_llm}, using manual parameters: {multi_npc_llm_params}")
                            
                    except Exception as e:
                        logging.error(f"Error applying profile for multi-NPC conversations: {e}")
                        multi_npc_llm_params = config.multi_npc_llm_params
                else:
                    logging.info(f"Hot-swap Multi-NPC Parameters (manual): {multi_npc_llm_params}")
                
                multi_npc_client = ClientBase(
                    config.multi_npc_llm_api,
                    config.multi_npc_llm,
                    multi_npc_llm_params,
                    config.multi_npc_custom_token_count,
                    multi_npc_secret_key_files
                )
                self._attach_sonnet_cache(multi_npc_client, config, "multi-NPC hot-swap client (diff settings)")
            elif config.apply_profile_multi_npc:
                # Same settings as main LLM but profile application is enabled for multi-NPC
                # Create a separate client with profile-applied parameters
                multi_npc_secret_key_files = key_file_resolver.get_key_files_for_service(config.llm_api, secret_key_file)
                
                multi_npc_llm_params = config.llm_params
                try:
                    from src.model_profile_manager import ModelProfileManager
                    profile_manager = ModelProfileManager()
                    multi_npc_llm_params = profile_manager.apply_profile_to_params(
                        service=config.llm_api,
                        model=config.llm,
                        fallback_params=config.llm_params
                    )
                    
                    # Log profile application for multi-NPC (same model as main - hot-swap)
                    has_profile = profile_manager.has_profile(config.llm_api, config.llm)
                    if has_profile:
                        logging.info(f"Hot-swap: Applied profile for multi-NPC conversations (same model as main): {config.llm_api}/{config.llm}")
                        logging.info(f"Hot-swap Multi-NPC Profile Parameters (same model): {multi_npc_llm_params}")
                    else:
                        logging.info(f"Hot-swap: No profile found for multi-NPC {config.llm_api}/{config.llm}, using manual parameters: {multi_npc_llm_params}")
                        
                except Exception as e:
                    logging.error(f"Error applying profile for multi-NPC conversations: {e}")
                    multi_npc_llm_params = config.llm_params
                
                multi_npc_client = ClientBase(
                    config.llm_api,
                    config.llm,
                    multi_npc_llm_params,
                    config.custom_token_count,
                    multi_npc_secret_key_files
                )
                self._attach_sonnet_cache(multi_npc_client, config, "multi-NPC hot-swap client (profiled main settings)")
            else:
                # Use the same client for multi-NPC conversations
                multi_npc_client = None
            
            # Update rememberer with new config and summary client
            self.__rememberer = Summaries(game, config, self.__client, self.__language_info['language'], summary_client)
            
            # Update chat manager with multi-NPC client
            chat_manager.update_multi_npc_client(multi_npc_client)
            
            # Clear per-character client cache to force recreation with new settings
            chat_manager.clear_per_character_client_cache()

            # Update STT settings (hot-swap) if a transcriber exists
            try:
                if self.__stt:
                    # Try in-place hot swap first
                    stt_in_place = False
                    if hasattr(self.__stt, 'hot_swap_settings'):
                        stt_in_place = self.__stt.hot_swap_settings(config)
                    if not stt_in_place:
                        # Rebuild transcriber on heavy changes
                        was_listening = False
                        try:
                            was_listening = self.__stt.is_listening
                        except Exception:
                            was_listening = False
                        try:
                            self.__stt.stop_listening()
                        except Exception:
                            pass
                        self.__stt = Transcriber(config, self.__stt_api_file, self.__api_file)
                        # Do not auto-start listening; the conversation loop will restart it as needed
                        if was_listening:
                            logging.info("Rebuilt STT transcriber due to hot-swap; listening will restart on next tick.")
            except Exception as e:
                logging.error(f"Failed to hot-swap STT settings: {e}")
            
            # If there's an active conversation, update it with new settings
            if self.__talk:
                # Determine which client to use for the conversation
                # If random selection is enabled, don't override with the main client
                conversation_client = self.__client  # Default to main client
                
                # Check if random selection is enabled for both conversation types
                try:
                    from src.random_llm_selector import RandomLLMSelector
                    from src.llm.client_base import ClientBase
                    from src.llm.key_file_resolver import key_file_resolver
                    random_selector = RandomLLMSelector()
                    
                    # Random selection for one-on-one conversations
                    if config.random_llm_one_on_one_enabled:
                        # Get a new random selection for this hot-swap
                        llm_selection = random_selector.select_random_llm_for_conversation(
                            conversation_type="one_on_one",
                            config=config,
                            fallback_service=config.llm_api,
                            fallback_model=config.llm,
                            fallback_params=config.llm_params,
                            fallback_token_count=config.custom_token_count
                        )
                        
                        # Create new client with random selection
                        selected_secret_key_files = key_file_resolver.get_key_files_for_service(llm_selection.service, secret_key_file)
                        
                        conversation_client = ClientBase(
                            llm_selection.service,
                            llm_selection.model,
                            llm_selection.parameters,
                            llm_selection.token_count,
                            selected_secret_key_files
                        )
                        self._attach_sonnet_cache(conversation_client, config, "random one-on-one hot-swap client")
                        
                        profile_status = "with profile" if llm_selection.from_profile else "without profile"
                        logging.info(f"Hot-swap: Using randomly selected LLM for one-on-one conversation: {llm_selection.service}/{llm_selection.model} ({profile_status})")
                    
                    # Random selection for multi-NPC conversations
                    if config.random_llm_multi_npc_enabled:
                        # Get a new random selection for multi-NPC hot-swap
                        multi_npc_selection = random_selector.select_random_llm_for_conversation(
                            conversation_type="multi_npc",
                            config=config,
                            fallback_service=config.multi_npc_llm_api,
                            fallback_model=config.multi_npc_llm,
                            fallback_params=config.multi_npc_llm_params,
                            fallback_token_count=config.multi_npc_custom_token_count
                        )
                        
                        # Create new multi-NPC client with random selection
                        multi_npc_secret_key_files = key_file_resolver.get_key_files_for_service(multi_npc_selection.service, secret_key_file)
                        
                        multi_npc_conversation_client = ClientBase(
                            multi_npc_selection.service,
                            multi_npc_selection.model,
                            multi_npc_selection.parameters,
                            multi_npc_selection.token_count,
                            multi_npc_secret_key_files
                        )
                        self._attach_sonnet_cache(multi_npc_conversation_client, config, "random multi-NPC hot-swap client")
                        # Update the chat manager with the randomly selected multi-NPC client
                        chat_manager.update_multi_npc_client(multi_npc_conversation_client)
                        
                        profile_status = "with profile" if multi_npc_selection.from_profile else "without profile"
                        logging.info(f"Hot-swap: Using randomly selected LLM for multi-NPC conversation: {multi_npc_selection.service}/{multi_npc_selection.model} ({profile_status})")
                        
                except Exception as e:
                    logging.error(f"Error in random LLM selection during hot-swap, using main client: {e}")
                    conversation_client = self.__client
                
                # Update the chat manager with the conversation client
                if conversation_client != self.__client:
                    chat_manager.update_primary_client(conversation_client)
                
                success = self.__talk.hot_swap_settings(
                    config=config,
                    llm_client=conversation_client,
                    chat_manager=chat_manager,
                    rememberer=self.__rememberer,
                    stt=self.__stt
                )
                if not success:
                    return False
            
            logging.info("GameStateManager hot-swap completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"GameStateManager hot-swap failed: {e}")
            return False

    ###### react to calls from the game #######
    @utils.time_it
    def start_conversation(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if self.__talk: #This should only happen if game and server are out of sync due to some previous error -> close conversation and start a new one
            self.__talk.end()
            self.__talk = None

        world_id = "default"
        if input_json.__contains__(comm_consts.KEY_STARTCONVERSATION_WORLDID):
            world_id = input_json[comm_consts.KEY_STARTCONVERSATION_WORLDID]
            world_id = self.WORLD_ID_CLEANSE_REGEX.sub("", world_id)

        if input_json.__contains__(comm_consts.KEY_INPUTTYPE):
            self.process_stt_setup(input_json)
        
        # Create conversation context to determine conversation type
        context_for_conversation = Context(world_id, self.__config, self.__client, self.__rememberer, self.__language_info)
        
        # Determine LLM client to use based on random selection settings
        conversation_llm_client = self.__client  # Default to main client
        
        # Check random LLM selection for both conversation types
        try:
            from src.random_llm_selector import RandomLLMSelector
            from src.llm.client_base import ClientBase
            from src.llm.key_file_resolver import key_file_resolver
            random_selector = RandomLLMSelector()
            
            # Random selection for one-on-one conversations
            if self.__config.random_llm_one_on_one_enabled:
                llm_selection = random_selector.select_random_llm_for_conversation(
                    conversation_type="one_on_one",
                    config=self.__config,
                    fallback_service=self.__config.llm_api,
                    fallback_model=self.__config.llm,
                    fallback_params=self.__config.llm_params,
                    fallback_token_count=self.__config.custom_token_count
                )
                
                # Always use the random selection result if random selection is enabled
                # Even if it's the same as current config, create a new client to ensure proper setup
                selected_secret_key_files = key_file_resolver.get_key_files_for_service(llm_selection.service, self.__api_file)
                
                # Create client for this conversation
                conversation_llm_client = ClientBase(
                    llm_selection.service,
                    llm_selection.model,
                    llm_selection.parameters,
                    llm_selection.token_count,
                    selected_secret_key_files
                )
                self._attach_sonnet_cache(conversation_llm_client, self.__config, "random one-on-one client")
                
                profile_status = "with profile" if llm_selection.from_profile else "without profile"
                logging.info(f"Using randomly selected LLM for one-on-one conversation: {llm_selection.service}/{llm_selection.model} ({profile_status})")
            
            # Random selection for multi-NPC conversations
            if self.__config.random_llm_multi_npc_enabled:
                multi_npc_selection = random_selector.select_random_llm_for_conversation(
                    conversation_type="multi_npc",
                    config=self.__config,
                    fallback_service=self.__config.multi_npc_llm_api,
                    fallback_model=self.__config.multi_npc_llm,
                    fallback_params=self.__config.multi_npc_llm_params,
                    fallback_token_count=self.__config.multi_npc_custom_token_count
                )
                
                # Create a new multi-NPC client for this conversation
                multi_npc_secret_key_files = key_file_resolver.get_key_files_for_service(multi_npc_selection.service, self.__api_file)
                
                multi_npc_conversation_client = ClientBase(
                    multi_npc_selection.service,
                    multi_npc_selection.model,
                    multi_npc_selection.parameters,
                    multi_npc_selection.token_count,
                    multi_npc_secret_key_files
                )
                
                self._attach_sonnet_cache(multi_npc_conversation_client, self.__config, "random multi-NPC client")
                
                # Update the chat manager with the randomly selected multi-NPC client
                self.__chat_manager.update_multi_npc_client(multi_npc_conversation_client)
                
                profile_status = "with profile" if multi_npc_selection.from_profile else "without profile"
                logging.info(f"Using randomly selected LLM for multi-NPC conversation: {multi_npc_selection.service}/{multi_npc_selection.model} ({profile_status})")
                    
        except Exception as e:
            logging.error(f"Error in random LLM selection, using default clients: {e}")
            conversation_llm_client = self.__client
        
        # Update the chat manager to use the conversation-specific client
        if conversation_llm_client != self.__client:
            self.__chat_manager.update_primary_client(conversation_llm_client)
        
        self.__talk = Conversation(context_for_conversation, self.__chat_manager, self.__rememberer, conversation_llm_client, self.__stt, self.__mic_input, self.__mic_ptt)
        self.__update_context(input_json)
        self.__try_preload_voice_model()
        self.__talk.start_conversation()
            
        return {
            comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTTYPE_STARTCONVERSATIONCOMPLETED,
            comm_consts.KEY_STARTCONVERSATION_USENARRATOR: self.__conv_has_narrator}
        
    
    @utils.time_it
    def continue_conversation(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if(not self.__talk ):
            return self.error_message("No running conversation.")
        
        # comm_consts.KEY_INPUTTYPE is passed when the mic settings have been changed in the MCM since beginning the conversation
        # If this happens, switch the STT settings to match the new input type
        if input_json.__contains__(comm_consts.KEY_INPUTTYPE):
            self.process_stt_setup(input_json)
        
        if self.__should_reload:
            self.__talk.reload_conversation()
            self.__should_reload = False

        topicInfoID: int = int(input_json.get(comm_consts.KEY_CONTINUECONVERSATION_TOPICINFOFILE,1))

        self.__update_context(input_json)

        while True:
            replyType, sentence_to_play = self.__talk.continue_conversation()
            if replyType == comm_consts.KEY_REQUESTTYPE_TTS:
                # if player input is detected mid-response, immediately process the player input
                reply = self.player_input({"mantella_context": {}, "mantella_player_input": "", "mantella_request_type": "mantella_player_input"})
                self.__first_line = False # since the NPC is already speaking in-game, setting this to True would just cause two voicelines to play at once
                continue # continue conversation with new player input (ie call self.__talk.continue_conversation() again)
            else:
                reply: dict[str, Any] = {comm_consts.KEY_REPLYTYPE: replyType}
                break

        if sentence_to_play:
            if not sentence_to_play.error_message:
                self.__game.prepare_sentence_for_game(sentence_to_play, self.__talk.context, self.__config, topicInfoID, self.__first_line)            
                reply[comm_consts.KEY_REPLYTYPE_NPCTALK] = self.sentence_to_json(sentence_to_play, topicInfoID)
                self.__first_line = False

                if comm_consts.ACTION_RELOADCONVERSATION in sentence_to_play.actions:
                    # Reload on next continue, but first inform the player that a reload will happen with the "gather thoughts" voiceline
                    self.__should_reload = True
            else:
                self.__talk.end()
                return self.error_message(sentence_to_play.error_message)        
        return reply

    @utils.time_it
    def player_input(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if(not self.__talk ):
            return self.error_message("No running conversation.")
        
        self.__first_line = True
        
        player_text: str = input_json.get(comm_consts.KEY_REQUESTTYPE_PLAYERINPUT, '')
        self.__update_context(input_json)
        updated_player_text, update_events, player_spoken_sentence = self.__talk.process_player_input(player_text)
        if update_events:
            return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REQUESTTYPE_TTS, comm_consts.KEY_TRANSCRIBE: updated_player_text}

        cleaned_player_text = utils.clean_text(updated_player_text)
        npcs_in_conversation = self.__talk.context.npcs_in_conversation
        if not npcs_in_conversation.contains_multiple_npcs(): # actions are only enabled in 1-1 conversations
            for action in self.__config.actions:
                # if the player response is just the name of an action, force the action to trigger
                if action.keyword.lower() == cleaned_player_text.lower() and npcs_in_conversation.last_added_character:
                    return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_NPCACTION,
                            comm_consts.KEY_REPLYTYPE_NPCACTION: {
                                'mantella_actor_speaker': npcs_in_conversation.last_added_character.name,
                                'mantella_actor_actions': [action.identifier],
                                }
                            }
        
        # if the player response is not an action command, return a regular player reply type
        if player_spoken_sentence:
            topicInfoID: int = int(input_json.get(comm_consts.KEY_CONTINUECONVERSATION_TOPICINFOFILE,1))
            self.__game.prepare_sentence_for_game(player_spoken_sentence, self.__talk.context, self.__config, topicInfoID, self.__first_line)
            self.__first_line = False
            return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_NPCTALK, comm_consts.KEY_REPLYTYPE_NPCTALK: self.sentence_to_json(player_spoken_sentence, topicInfoID)}
        else:
            return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_NPCTALK}

    @utils.time_it
    def end_conversation(self, input_json: dict[str, Any]) -> dict[str, Any]:
        if(self.__talk):
            self.__talk.end()
            self.__talk = None

        logging.log(24, '\nConversations not starting when you select an NPC? See here:')
        logging.log(25, 'https://art-from-the-machine.github.io/Mantella/pages/issues_qna')
        logging.log(24, '\nWaiting for player to select an NPC...')
        return {comm_consts.KEY_REPLYTYPE: comm_consts.KEY_REPLYTYPE_ENDCONVERSATION}
    
    def process_stt_setup(self, input_json: dict[str, Any]):
        '''Process the STT setup (mic / text / push-to-talk) based on the settings passed in the input JSON'''
        if input_json[comm_consts.KEY_INPUTTYPE] in (comm_consts.KEY_INPUTTYPE_MIC, comm_consts.KEY_INPUTTYPE_PTT):
            self.__mic_input = True
            # only init Transcriber if mic input is enabled
            if not self.__stt:
                self.__stt = Transcriber(self.__config, self.__stt_api_file, self.__api_file)
            if input_json[comm_consts.KEY_INPUTTYPE] == comm_consts.KEY_INPUTTYPE_PTT:
                self.__mic_ptt = True
        else:
            self.__mic_input = False
            if self.__stt:
                self.__stt.stop_listening()
                self.__stt = None

    ####### JSON constructions #########

    @utils.time_it
    def character_to_json(self, character_to_jsonfy: Character) -> dict[str, Any]:
        return {
            comm_consts.KEY_ACTOR_BASEID: character_to_jsonfy.base_id,
            comm_consts.KEY_ACTOR_NAME: character_to_jsonfy.name,
        }
    
    @utils.time_it
    def sentence_to_json(self, sentence_to_prepare: Sentence, topicID: int) -> dict[str, Any]:
        return {
            comm_consts.KEY_ACTOR_SPEAKER: sentence_to_prepare.speaker.name,
            comm_consts.KEY_ACTOR_LINETOSPEAK: self.__abbreviate_text(sentence_to_prepare.text.strip()),
            comm_consts.KEY_ACTOR_ISNARRATION: sentence_to_prepare.is_narration,
            comm_consts.KEY_ACTOR_VOICEFILE: sentence_to_prepare.voice_file,
            comm_consts.KEY_ACTOR_DURATION: sentence_to_prepare.voice_line_duration,
            comm_consts.KEY_ACTOR_ACTIONS: sentence_to_prepare.actions,
            comm_consts.KEY_CONTINUECONVERSATION_TOPICINFOFILE: topicID
        }
    
    def __abbreviate_text(self, text_to_abbreviate: str) -> str:
        return self.__game.modify_sentence_text_for_game(text_to_abbreviate)

    ##### utils #######

    @utils.time_it
    def __update_context(self,  json: dict[str, Any]):
        if self.__talk:
            if json.__contains__(comm_consts.KEY_ACTORS):
                actors_in_json: list[Character] = []
                for actorJson in json[comm_consts.KEY_ACTORS]:
                    if comm_consts.KEY_ACTOR_BASEID in actorJson:
                        actor: Character | None = self.load_character(actorJson)                
                        if actor:
                            actors_in_json.append(actor)
                self.__talk.add_or_update_character(actors_in_json)
            
            location = None
            time = None
            ingame_events = None
            weather = ""
            custom_context_values: dict[str, Any] = {}
            if json.__contains__(comm_consts.KEY_CONTEXT):
                if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_LOCATION):
                    location: str = json[comm_consts.KEY_CONTEXT].get(comm_consts.KEY_CONTEXT_LOCATION, None)
                
                if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_TIME):
                    time: int = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_TIME]

                if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_INGAMEEVENTS):
                    ingame_events: list[str] = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_INGAMEEVENTS]
                
                if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_WEATHER):
                    weather = self.__game.get_weather_description(json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_WEATHER])

                if json[comm_consts.KEY_CONTEXT].__contains__(comm_consts.KEY_CONTEXT_CUSTOMVALUES):
                    custom_context_values = json[comm_consts.KEY_CONTEXT][comm_consts.KEY_CONTEXT_CUSTOMVALUES]
            self.__talk.update_context(location, time, ingame_events, weather, custom_context_values)
    
    @utils.time_it
    def load_character(self, json: dict[str, Any]) -> Character | None:
        try:
            base_id: str = utils.convert_to_skyrim_hex_format(str(json[comm_consts.KEY_ACTOR_BASEID]))
            ref_id: str = utils.convert_to_skyrim_hex_format(str(json[comm_consts.KEY_ACTOR_REFID]))

            # ignore plugin ID at the start of the ref ID as this can vary by load order
            if ref_id.startswith('FE'):             #Item from lite mod, statically placed in CK, has 'FEXXX' prefix. 
                ref_id = ref_id[-3:].rjust(6,"0")   #Mask off prefix, pad w/'0'
            else:
                ref_id = ref_id[-6:]
            if base_id.startswith('FE'):
                base_id = base_id[-3:].rjust(6,"0")
            else:
                base_id = base_id[-6:]

            character_name: str = str(json[comm_consts.KEY_ACTOR_NAME])
            gender: int = int(json[comm_consts.KEY_ACTOR_GENDER])
            race: str = str(json[comm_consts.KEY_ACTOR_RACE])
            actor_voice_model: str = str(json[comm_consts.KEY_ACTOR_VOICETYPE])
            ingame_voice_model: str = actor_voice_model.split('<')[1].split(' ')[0]
            is_in_combat: bool = bool(json[comm_consts.KEY_ACTOR_ISINCOMBAT])
            is_enemy: bool = bool(json[comm_consts.KEY_ACTOR_ISENEMY])
            relationship_rank: int = int(json[comm_consts.KEY_ACTOR_RELATIONSHIPRANK])
            custom_values: dict[str, Any] = {}
            if json.__contains__(comm_consts.KEY_ACTOR_CUSTOMVALUES):
                custom_values = json[comm_consts.KEY_ACTOR_CUSTOMVALUES]
                if not custom_values:
                    custom_values: dict[str, Any] = {}
            equipment = Equipment({})
            if json.__contains__(comm_consts.KEY_ACTOR_EQUIPMENT):
                equipment = Equipment(self.__convert_to_equipment_item_dictionary(json[comm_consts.KEY_ACTOR_EQUIPMENT]))
            is_generic_npc: bool = False
            bio: str = ""
            tts_voice_model: str = ""
            csv_in_game_voice_model: str = ""
            advanced_voice_model: str = ""
            voice_accent: str = ""
            tts_service: str = ""
            llm_service: str = ""
            llm_model: str = ""
            is_player_character: bool = bool(json[comm_consts.KEY_ACTOR_ISPLAYER])
            if self.__talk and self.__talk.contains_character(ref_id):
                already_loaded_character: Character | None = self.__talk.get_character(ref_id)
                if already_loaded_character:
                    bio = already_loaded_character.bio
                    # Carry over previously loaded values
                    tts_voice_model = already_loaded_character.tts_voice_model
                    csv_in_game_voice_model = already_loaded_character.csv_in_game_voice_model
                    advanced_voice_model = already_loaded_character.advanced_voice_model
                    voice_accent = already_loaded_character.voice_accent
                    tts_service = getattr(already_loaded_character, 'tts_service', "")
                    llm_service = already_loaded_character.llm_service
                    llm_model = already_loaded_character.llm_model
                    is_generic_npc = already_loaded_character.is_generic_npc
            elif self.__talk and not is_player_character :#If this is not the player and the character has not already been loaded
                external_info: external_character_info = self.__game.load_external_character_info(base_id, character_name, race, gender, actor_voice_model)
                
                bio = external_info.bio
                tts_voice_model = external_info.tts_voice_model
                csv_in_game_voice_model = external_info.csv_in_game_voice_model
                advanced_voice_model = external_info.advanced_voice_model
                voice_accent = external_info.voice_accent
                tts_service = getattr(external_info, 'tts_service', "")
                llm_service = external_info.llm_service
                llm_model = external_info.llm_model
                is_generic_npc = external_info.is_generic_npc
                if is_generic_npc:
                    character_name = external_info.name
                    ingame_voice_model = external_info.ingame_voice_model
            elif self.__talk and is_player_character and self.__config.voice_player_input:
                if custom_values.__contains__(comm_consts.KEY_ACTOR_PC_VOICEMODEL):
                    tts_voice_model = self.__get_player_voice_model(str(custom_values[comm_consts.KEY_ACTOR_PC_VOICEMODEL]))
                else:
                    tts_voice_model = self.__get_player_voice_model(None)

            return Character(base_id,
                            ref_id,
                            character_name,
                            gender,
                            race,
                            is_player_character,
                            bio,
                            is_in_combat,
                            is_enemy,
                            relationship_rank,
                            is_generic_npc,
                            ingame_voice_model,
                            tts_voice_model,
                            csv_in_game_voice_model,
                            advanced_voice_model,
                            voice_accent,
                            equipment,
                            custom_values,
                            tts_service,
                            llm_service,
                            llm_model)
        except CharacterDoesNotExist:                 
            logging.log(23, 'Restarting...')
            return None 
        
    def error_message(self, message: str) -> dict[str, Any]:
        return {
                comm_consts.KEY_REPLYTYPE: "error",
                "mantella_message": message
            }
    
    @utils.time_it
    def __get_player_voice_model(self, game_value: str | None) -> str:
        if game_value == None:
            return self.__config.player_voice_model
        return game_value
    
    @utils.time_it
    def __convert_to_equipment_item_dictionary(self, input_dict: dict[str, Any]) -> dict[str, EquipmentItem]:
        result: dict[str, EquipmentItem] = {}
        if input_dict:
            for slot, itemname in input_dict.items():
                result[slot] = EquipmentItem(itemname)
        return result

    @utils.time_it
    def __try_preload_voice_model(self):
        '''
        If the conversation has the following conditions:

        1. Single NPC (ie only one possible voice model to load)
        2. The player is not the first to speak (ie there is no player voice model)
        3. The conversation does not have a narrator (ie their is no narrator voice model)

        Then pre-load the NPC's voice model
        '''
        is_npc_speaking_first: bool = self.__automatic_greeting

        if not self.__talk.context.npcs_in_conversation.contains_multiple_npcs() and is_npc_speaking_first and not self.__conv_has_narrator:
            character_to_talk = self.__talk.context.npcs_in_conversation.last_added_character
            if character_to_talk:
                self.__talk.output_manager.tts.change_voice(
                    character_to_talk.tts_voice_model, 
                    character_to_talk.in_game_voice_model, 
                    character_to_talk.csv_in_game_voice_model, 
                    character_to_talk.advanced_voice_model, 
                    character_to_talk.voice_accent, 
                    voice_gender=character_to_talk.gender, 
                    voice_race=character_to_talk.race
                )
            else:
                return self.error_message("Could not load initial character to talk to. Please try again.")

    @utils.time_it
    def reload_character_data(self) -> bool:
        """Reload character CSV files and overrides from disk.
        
        This method will:
        1. End any active conversation
        2. Create a new game instance to reload character data from disk
        3. Update the rememberer with the new game instance
        
        Returns:
            bool: True if reload was successful, False otherwise
        """
        try:
            # End any active conversation first
            if self.__talk:
                logging.info("Ending active conversation for character data reload...")
                self.__talk.end()
                self.__talk = None
                logging.info("Active conversation ended.")
            
            # Create a new game instance to reload character data
            logging.info("Reloading character data from disk...")
            if self.__config.game.base_game == GameEnum.FALLOUT4:
                self.__game = Fallout4(self.__config)
            else:
                self.__game = Skyrim(self.__config)
            
            # Update the rememberer with the new game instance
            self.__rememberer = Summaries(self.__game, self.__config, self.__client, self.__language_info['language'], None)
            
            logging.info("Character data reload completed successfully.")
            return True
            
        except Exception as e:
            logging.error(f"Error during character data reload: {e}")
            return False