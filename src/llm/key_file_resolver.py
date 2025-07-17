"""
Key file resolver for different LLM services.
Provides a clean OOP interface for determining which API key files to use for each service.
"""

from typing import List
from abc import ABC, abstractmethod


class KeyFileStrategy(ABC):
    """Abstract base class for key file resolution strategies"""
    
    @abstractmethod
    def get_key_files(self, fallback_key_file: str) -> List[str]:
        """
        Returns a list of key files to try in priority order.
        
        Args:
            fallback_key_file (str): The default/fallback key file to use
            
        Returns:
            List[str]: List of key files in priority order
        """
        pass


class NanoGPTKeyFileStrategy(KeyFileStrategy):
    """Key file strategy for NanoGPT service"""
    
    def get_key_files(self, fallback_key_file: str) -> List[str]:
        return ['NANOGPT_SECRET_KEY.txt', fallback_key_file]


class OpenAIKeyFileStrategy(KeyFileStrategy):
    """Key file strategy for OpenAI service"""
    
    def get_key_files(self, fallback_key_file: str) -> List[str]:
        return [fallback_key_file]


class OpenRouterKeyFileStrategy(KeyFileStrategy):
    """Key file strategy for OpenRouter service"""
    
    def get_key_files(self, fallback_key_file: str) -> List[str]:
        return [fallback_key_file]


class DefaultKeyFileStrategy(KeyFileStrategy):
    """Default key file strategy for local or unknown services"""
    
    def get_key_files(self, fallback_key_file: str) -> List[str]:
        return [fallback_key_file]


class KeyFileResolver:
    """
    Resolves appropriate key files for different LLM services using strategy pattern.
    """
    
    def __init__(self):
        self._strategies = {
            'nanogpt': NanoGPTKeyFileStrategy(),
            'openai': OpenAIKeyFileStrategy(),
            'openrouter': OpenRouterKeyFileStrategy(),
        }
        self._default_strategy = DefaultKeyFileStrategy()
    
    def get_key_files_for_service(self, service: str, fallback_key_file: str) -> List[str]:
        """
        Get the appropriate key files for a given service.
        
        Args:
            service (str): The LLM service name (case-insensitive)
            fallback_key_file (str): The default key file to use as fallback
            
        Returns:
            List[str]: List of key files to try in priority order
        """
        # Normalize service name
        normalized_service = service.lower().strip().replace(' ', '').replace('-', '')
        
        # Get appropriate strategy
        strategy = self._strategies.get(normalized_service, self._default_strategy)
        
        # Return key files from strategy
        return strategy.get_key_files(fallback_key_file)
    
    def register_strategy(self, service: str, strategy: KeyFileStrategy) -> None:
        """
        Register a custom key file strategy for a service.
        
        Args:
            service (str): The service name (will be normalized)
            strategy (KeyFileStrategy): The strategy to use for this service
        """
        normalized_service = service.lower().strip().replace(' ', '').replace('-', '')
        self._strategies[normalized_service] = strategy


# Global instance for use throughout the application
key_file_resolver = KeyFileResolver() 