"""
Abstract LLM Service Provider interface and concrete implementations.
Provides a clean OOP way to handle different LLM services for per-character overrides.
"""

from abc import ABC, abstractmethod
from typing import List
import logging
from src.llm.client_base import ClientBase
from src.llm.sonnet_cache_connector import SonnetCacheConnector
from src.config.config_loader import ConfigLoader


class LLMServiceProvider(ABC):
    """Abstract base class for LLM service providers"""
    
    @abstractmethod
    def get_service_name(self) -> str:
        """Returns the service name identifier (e.g., 'or', 'nano')"""
        pass
    
    @abstractmethod
    def get_display_name(self) -> str:
        """Returns the human-readable display name (e.g., 'OpenRouter', 'NanoGPT')"""
        pass
    
    @abstractmethod
    def create_client(self, model: str, config: ConfigLoader) -> ClientBase:
        """Creates a client for this service with the specified model"""
        pass
    
    @abstractmethod
    def get_api_url(self) -> str:
        """Returns the API URL for this service"""
        pass
    
    @abstractmethod
    def get_secret_key_files(self, fallback_key_file: str) -> List[str]:
        """Returns the list of secret key files to try for this service"""
        pass


class OpenRouterServiceProvider(LLMServiceProvider):
    """OpenRouter LLM service provider"""
    
    def get_service_name(self) -> str:
        return "or"
    
    def get_display_name(self) -> str:
        return "OpenRouter"
    
    def create_client(self, model: str, config: ConfigLoader) -> ClientBase:
        """Create an OpenRouter client with the specified model"""
        # Apply profile parameters if available for this specific model
        llm_params = config.llm_params  # Default to global parameters
        
        try:
            from src.model_profile_manager import ModelProfileManager
            profile_manager = ModelProfileManager()
            llm_params = profile_manager.apply_profile_to_params(
                service=self.get_display_name(),
                model=model,
                fallback_params=config.llm_params
            )
            
            # Log profile application for per-character override
            has_profile = profile_manager.has_profile(self.get_display_name(), model)
            if has_profile:
                logging.info(f"Applied profile for per-character override: {self.get_display_name()}/{model}")
                logging.info(f"Per-character Profile Parameters: {llm_params}")
            else:
                logging.info(f"No profile found for per-character override {self.get_display_name()}/{model}, using global parameters: {llm_params}")
                
        except Exception as e:
            logging.error(f"Error applying profile for per-character LLM {self.get_display_name()}/{model}: {e}")
            llm_params = config.llm_params
        
        client = ClientBase(
            api_url=self.get_api_url(),
            llm=model,
            llm_params=llm_params,
            custom_token_count=config.custom_token_count,
            secret_key_files=self.get_secret_key_files('GPT_SECRET_KEY.txt')
        )
        try:
            client._sonnet_cache_connector = SonnetCacheConnector(getattr(config, 'sonnet_prompt_caching_enabled', False))
        except Exception as e:
            logging.debug(f"Failed to attach Sonnet cache connector: {e}")
        return client
    
    def get_api_url(self) -> str:
        return "OpenRouter"
    
    def get_secret_key_files(self, fallback_key_file: str) -> List[str]:
        return [fallback_key_file]


class NanoGPTServiceProvider(LLMServiceProvider):
    """NanoGPT LLM service provider"""
    
    def get_service_name(self) -> str:
        return "nano"
    
    def get_display_name(self) -> str:
        return "NanoGPT"
    
    def create_client(self, model: str, config: ConfigLoader) -> ClientBase:
        """Create a NanoGPT client with the specified model"""
        # Apply profile parameters if available for this specific model
        llm_params = config.llm_params  # Default to global parameters
        
        try:
            from src.model_profile_manager import ModelProfileManager
            profile_manager = ModelProfileManager()
            llm_params = profile_manager.apply_profile_to_params(
                service=self.get_display_name(),
                model=model,
                fallback_params=config.llm_params
            )
            
            # Log profile application for per-character override
            has_profile = profile_manager.has_profile(self.get_display_name(), model)
            if has_profile:
                logging.info(f"Applied profile for per-character override: {self.get_display_name()}/{model}")
                logging.info(f"Per-character Profile Parameters: {llm_params}")
            else:
                logging.info(f"No profile found for per-character override {self.get_display_name()}/{model}, using global parameters: {llm_params}")
                
        except Exception as e:
            logging.error(f"Error applying profile for per-character LLM {self.get_display_name()}/{model}: {e}")
            llm_params = config.llm_params
        
        return ClientBase(
            api_url=self.get_api_url(),
            llm=model,
            llm_params=llm_params,
            custom_token_count=config.custom_token_count,
            secret_key_files=self.get_secret_key_files('GPT_SECRET_KEY.txt')
        )
    
    def get_api_url(self) -> str:
        return "NanoGPT"
    
    def get_secret_key_files(self, fallback_key_file: str) -> List[str]:
        return ['NANOGPT_SECRET_KEY.txt', fallback_key_file]


class OpenAIServiceProvider(LLMServiceProvider):
    """OpenAI LLM service provider"""
    
    def get_service_name(self) -> str:
        return "openai"
    
    def get_display_name(self) -> str:
        return "OpenAI"
    
    def create_client(self, model: str, config: ConfigLoader) -> ClientBase:
        """Create an OpenAI client with the specified model"""
        # Apply profile parameters if available for this specific model
        llm_params = config.llm_params  # Default to global parameters
        
        try:
            from src.model_profile_manager import ModelProfileManager
            profile_manager = ModelProfileManager()
            llm_params = profile_manager.apply_profile_to_params(
                service=self.get_display_name(),
                model=model,
                fallback_params=config.llm_params
            )
            
            # Log profile application for per-character override
            has_profile = profile_manager.has_profile(self.get_display_name(), model)
            if has_profile:
                logging.info(f"Applied profile for per-character override: {self.get_display_name()}/{model}")
                logging.info(f"Per-character Profile Parameters: {llm_params}")
            else:
                logging.info(f"No profile found for per-character override {self.get_display_name()}/{model}, using global parameters: {llm_params}")
                
        except Exception as e:
            logging.error(f"Error applying profile for per-character LLM {self.get_display_name()}/{model}: {e}")
            llm_params = config.llm_params
        
        return ClientBase(
            api_url=self.get_api_url(),
            llm=model,
            llm_params=llm_params,
            custom_token_count=config.custom_token_count,
            secret_key_files=self.get_secret_key_files('GPT_SECRET_KEY.txt')
        )
    
    def get_api_url(self) -> str:
        return "OpenAI"
    
    def get_secret_key_files(self, fallback_key_file: str) -> List[str]:
        return [fallback_key_file]


class LLMServiceProviderFactory:
    """Factory for creating and managing LLM service providers"""
    
    def __init__(self):
        self._providers = {
            "or": OpenRouterServiceProvider(),
            "nano": NanoGPTServiceProvider(),
            "openai": OpenAIServiceProvider(),
        }
    
    def get_provider(self, service_name: str) -> LLMServiceProvider | None:
        """Get a service provider by name"""
        return self._providers.get(service_name.lower().strip())
    
    def register_provider(self, provider: LLMServiceProvider) -> None:
        """Register a new service provider"""
        self._providers[provider.get_service_name()] = provider
    
    def get_all_providers(self) -> dict[str, LLMServiceProvider]:
        """Get all registered providers"""
        return self._providers.copy()
    
    def is_supported_service(self, service_name: str) -> bool:
        """Check if a service is supported"""
        return service_name.lower().strip() in self._providers


# Global factory instance
llm_service_factory = LLMServiceProviderFactory() 