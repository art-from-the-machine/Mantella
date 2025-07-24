"""
Random LLM Selector for Conversation Types

This module provides functionality to randomly select LLMs from user-defined pools
for different conversation types (one-on-one, multi-NPC) and automatically apply
associated profiles if they exist.
"""

import json
import random
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from src.model_profile_manager import ModelProfileManager


@dataclass
class LLMSelection:
    """Represents a selected LLM configuration"""
    service: str           # LLM service (e.g., "OpenRouter", "OpenAI")
    model: str            # Model identifier 
    parameters: Dict[str, Any]  # LLM parameters (from profile or fallback)
    token_count: int      # Custom token count
    from_profile: bool    # Whether parameters came from a profile


class RandomLLMSelector:
    """Handles random LLM selection from pools with profile application"""
    
    def __init__(self, profile_manager: Optional[ModelProfileManager] = None):
        """
        Initialize the random LLM selector
        
        Args:
            profile_manager: Optional ModelProfileManager instance. If None, creates one.
        """
        self.profile_manager = profile_manager or ModelProfileManager()
    
    def select_random_llm_for_conversation(
        self,
        conversation_type: str,
        config: Any,
        fallback_service: str,
        fallback_model: str,
        fallback_params: Dict[str, Any],
        fallback_token_count: int
    ) -> LLMSelection:
        """
        Select a random LLM for the specified conversation type
        
        Args:
            conversation_type: "one_on_one" or "multi_npc"
            config: Configuration object with random LLM settings
            fallback_service: Service to use if no random selection
            fallback_model: Model to use if no random selection  
            fallback_params: Parameters to use if no profile exists
            fallback_token_count: Token count to use if no random selection
            
        Returns:
            LLMSelection with chosen LLM configuration
        """
        try:
            # Check if random selection is enabled for this conversation type
            if conversation_type == "one_on_one":
                is_enabled = getattr(config, 'random_llm_one_on_one_enabled', False)
                pool = getattr(config, 'llm_pool_one_on_one', [])
            elif conversation_type == "multi_npc":
                is_enabled = getattr(config, 'random_llm_multi_npc_enabled', False)
                pool = getattr(config, 'llm_pool_multi_npc', [])
            else:
                logging.warning(f"Unknown conversation type: {conversation_type}")
                return self._create_fallback_selection(
                    fallback_service, fallback_model, fallback_params, fallback_token_count
                )
            
            # If random selection is disabled or pool is empty, use fallback
            if not is_enabled or not pool:
                logging.debug(f"Random LLM selection disabled or empty pool for {conversation_type}")
                return self._create_fallback_selection(
                    fallback_service, fallback_model, fallback_params, fallback_token_count
                )
            
            # Parse pool if it's a JSON string
            if isinstance(pool, str):
                try:
                    pool = json.loads(pool)
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing {conversation_type} LLM pool JSON: {e}")
                    return self._create_fallback_selection(
                        fallback_service, fallback_model, fallback_params, fallback_token_count
                    )
            
            # Validate pool format
            if not isinstance(pool, list) or not pool:
                logging.warning(f"Invalid or empty {conversation_type} LLM pool")
                return self._create_fallback_selection(
                    fallback_service, fallback_model, fallback_params, fallback_token_count
                )
            
            # Randomly select an LLM from the pool
            selected_llm = random.choice(pool)
            
            if not isinstance(selected_llm, dict) or 'service' not in selected_llm or 'model' not in selected_llm:
                logging.error(f"Invalid LLM entry in {conversation_type} pool: {selected_llm}")
                return self._create_fallback_selection(
                    fallback_service, fallback_model, fallback_params, fallback_token_count
                )
            
            service = selected_llm['service']
            model = selected_llm['model']
            
            # Try to apply profile for the selected LLM
            profile_params = self.profile_manager.apply_profile_to_params(
                service=service,
                model=model,
                fallback_params=fallback_params
            )
            
            # Check if we got parameters from a profile or fallback
            has_profile = self.profile_manager.has_profile(service, model)
            
            # Log the selection with parameter information
            profile_status = "with profile" if has_profile else "without profile"
            logging.info(f"Randomly selected LLM for {conversation_type}: {service}/{model} ({profile_status})")
            logging.info(f"Random LLM Parameters: {profile_params}")
            
            return LLMSelection(
                service=service,
                model=model,
                parameters=profile_params,
                token_count=fallback_token_count,  # Use fallback token count
                from_profile=has_profile
            )
            
        except Exception as e:
            logging.error(f"Error in random LLM selection for {conversation_type}: {e}")
            return self._create_fallback_selection(
                fallback_service, fallback_model, fallback_params, fallback_token_count
            )
    
    def _create_fallback_selection(
        self,
        service: str,
        model: str, 
        params: Dict[str, Any],
        token_count: int
    ) -> LLMSelection:
        """Create a fallback LLM selection"""
        return LLMSelection(
            service=service,
            model=model,
            parameters=params,
            token_count=token_count,
            from_profile=False
        )
    
    def get_pool_summary(self, conversation_type: str, config: Any) -> Dict[str, Any]:
        """
        Get summary information about the LLM pool for a conversation type
        
        Args:
            conversation_type: "one_on_one" or "multi_npc"
            config: Configuration object
            
        Returns:
            Dictionary with pool information
        """
        try:
            if conversation_type == "one_on_one":
                is_enabled = getattr(config, 'random_llm_one_on_one_enabled', False)
                pool = getattr(config, 'llm_pool_one_on_one', [])
            elif conversation_type == "multi_npc":
                is_enabled = getattr(config, 'random_llm_multi_npc_enabled', False)
                pool = getattr(config, 'llm_pool_multi_npc', [])
            else:
                return {"error": f"Unknown conversation type: {conversation_type}"}
            
            # Parse pool if it's a JSON string
            if isinstance(pool, str):
                try:
                    pool = json.loads(pool)
                except json.JSONDecodeError:
                    pool = []
            
            if not isinstance(pool, list):
                pool = []
            
            # Count how many LLMs have profiles
            llms_with_profiles = 0
            for llm in pool:
                if isinstance(llm, dict) and 'service' in llm and 'model' in llm:
                    if self.profile_manager.has_profile(llm['service'], llm['model']):
                        llms_with_profiles += 1
            
            return {
                "enabled": is_enabled,
                "total_llms": len(pool),
                "llms_with_profiles": llms_with_profiles,
                "llms_without_profiles": len(pool) - llms_with_profiles,
                "pool": pool
            }
            
        except Exception as e:
            logging.error(f"Error getting pool summary for {conversation_type}: {e}")
            return {"error": str(e)} 