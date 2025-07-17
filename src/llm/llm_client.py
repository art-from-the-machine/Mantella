import src.utils as utils
import logging
from openai import AsyncOpenAI
from src.config.config_loader import ConfigLoader
from src.llm.image_client import ImageClient
from src.llm.client_base import ClientBase

class LLMClient(ClientBase):
    '''LLM class to handle NPC responses
    '''
    @utils.time_it
    def __init__(self, config: ConfigLoader, secret_key_file: str, image_secret_key_file: str) -> None:
        from src.llm.key_file_resolver import key_file_resolver
        
        # Get appropriate secret key files for the LLM service
        secret_key_files = key_file_resolver.get_key_files_for_service(config.llm_api, secret_key_file)
        
        super().__init__(config.llm_api, config.llm, config.llm_params, config.custom_token_count, secret_key_files)

        if self._is_local:
            logging.info(f"Running Mantella with local language model")
        else:
            logging.log(23, f"Running Mantella with '{config.llm}'. The language model can be changed in the Mantella UI: http://localhost:4999/ui")

        self._startup_async_client: AsyncOpenAI | None = self.generate_async_client() # initialize first client in advance of sending first LLM request to save time

        if config.vision_enabled:
            logging.info(f"Setting up vision language model...")
            self._image_client: ImageClient | None = ImageClient(config, secret_key_file, image_secret_key_file)
    
    @utils.time_it
    def hot_swap_settings(self, config: ConfigLoader, secret_key_file: str, image_secret_key_file: str) -> bool:
        """Attempts to hot-swap settings without ending the conversation.
        
        Args:
            config: Updated config loader instance
            secret_key_file: Updated secret key file
            image_secret_key_file: Updated image secret key file
            
        Returns:
            bool: True if hot-swap was successful, False otherwise
        """
        try:
            # Choose appropriate secret key files based on the LLM service
            if config.llm_api.lower().strip() == 'nanogpt':
                secret_key_files = ['NANOGPT_SECRET_KEY.txt', secret_key_file]
            else:
                secret_key_files = [secret_key_file]
            
            # Update base client settings
            success = super().hot_swap_settings(
                config.llm_api, 
                config.llm, 
                config.llm_params, 
                config.custom_token_count, 
                secret_key_files
            )
            
            if not success:
                return False
            
            # Update image client if vision is enabled
            if config.vision_enabled:
                if self._image_client:
                    # Update existing image client
                    if hasattr(self._image_client, 'hot_swap_settings'):
                        self._image_client.hot_swap_settings(config, secret_key_file, image_secret_key_file)
                else:
                    # Create new image client
                    logging.info(f"Setting up vision language model...")
                    self._image_client = ImageClient(config, secret_key_file, image_secret_key_file)
            else:
                # Disable image client if vision is disabled
                self._image_client = None
            
            logging.info("LLMClient hot-swap completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"LLMClient hot-swap failed: {e}")
            return False