import json
import os
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path


class ModelProfile:
    """Represents a model profile with LLM parameters"""
    
    def __init__(self, name: str, service: str, model: str, parameters: Dict[str, Any]):
        self.name = name
        self.service = service
        self.model = model
        self.parameters = parameters
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for JSON serialization"""
        # Map display names to short service identifiers and back
        service_map = {
            "OpenRouter": "or",
            "NanoGPT": "nano", 
            "OpenAI": "openai"
        }
        display_name_map = {v: k for k, v in service_map.items()}
        
        service_id = service_map.get(self.service, self.service.lower())
        service_display = display_name_map.get(service_id, self.service)
        
        return {
            "name": self.name,
            "service": service_id,  # Short identifier for consistency
            "service_display_name": service_display,  # Human readable name
            "model": self.model,
            "parameters": self.parameters
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelProfile':
        """Create profile from dictionary (JSON deserialization)"""
        # Handle both old and new formats
        if "service_display_name" in data:
            # New format - use display name for internal storage
            service = data["service_display_name"]
        else:
            # Legacy format or short identifier - map back to display name
            service_map = {
                "or": "OpenRouter",
                "nano": "NanoGPT", 
                "openai": "OpenAI"
            }
            service = service_map.get(data["service"], data["service"])
        
        return cls(
            name=data["name"],
            service=service,
            model=data["model"],
            parameters=data["parameters"]
        )
    
    def get_profile_id(self) -> str:
        """Generate a unique ID for this profile"""
        # Map display names to short service identifiers
        service_map = {
            "OpenRouter": "or",
            "NanoGPT": "nano", 
            "OpenAI": "openai"
        }
        service_id = service_map.get(self.service, self.service.lower())
        return f"{service_id}:{self.model}"


class ModelProfileManager:
    """Manages model profiles with JSON-based storage"""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the profile manager
        
        Args:
            storage_path: Optional path to the profiles storage file.
                         If None, defaults to data/model_profiles.json
        """
        if storage_path is None:
            # Use data directory relative to the main application
            # Get the current script directory and go to the project root
            current_dir = Path(__file__).parent
            project_root = current_dir.parent  # Go up one level from src/
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            self.storage_path = data_dir / "model_profiles.json"
        else:
            self.storage_path = Path(storage_path)
        
        self._profiles: Dict[str, ModelProfile] = {}
        self._load_profiles()
    
    def _load_profiles(self) -> None:
        """Load profiles from JSON storage"""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Handle both old and new formats
                    if "profiles" in data:
                        # New format
                        profiles_data = data["profiles"]
                        version = data.get("metadata", {}).get("version", "1.0")
                        logging.info(f"Loading profile format version {version}")
                    else:
                        # Legacy format - convert on the fly
                        profiles_data = data
                        logging.info("Loading legacy profile format")
                    
                    self._profiles = {
                        profile_id: ModelProfile.from_dict(profile_data)
                        for profile_id, profile_data in profiles_data.items()
                    }
                    
                logging.info(f"Loaded {len(self._profiles)} model profiles from {self.storage_path}")
            else:
                logging.info("No existing model profiles found, starting with empty profiles")
        except Exception as e:
            logging.error(f"Error loading model profiles: {e}")
            self._profiles = {}
    
    def _save_profiles(self) -> None:
        """Save profiles to JSON storage"""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert profiles to new format with metadata
            profiles_data = {
                profile_id: profile.to_dict()
                for profile_id, profile in self._profiles.items()
            }
            
            data = {
                "profiles": profiles_data,
                "metadata": {
                    "version": "1.0",
                    "total_profiles": len(self._profiles)
                }
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Saved {len(self._profiles)} model profiles to {self.storage_path}")
        except Exception as e:
            logging.error(f"Error saving model profiles: {e}")
    
    def _get_service_short_name(self, service: str) -> str:
        """
        Convert service display name to short format used in profile IDs
        
        Args:
            service: Service display name (e.g., 'OpenRouter', 'OpenAI')
        
        Returns:
            Short service name (e.g., 'or', 'openai')
        """
        service_mapping = {
            'OpenRouter': 'or',
            'OpenAI': 'openai', 
            'NanoGPT': 'nano',
            'KoboldCpp': 'kobold',
            'textgenwebui': 'textgen'
        }
        return service_mapping.get(service, service.lower())

    def create_or_update_profile(self, service: str, model: str, parameters: Dict[str, Any]) -> bool:
        """
        Create or update a model profile
        
        Args:
            service: LLM service (e.g., 'OpenRouter', 'OpenAI')
            model: Model identifier
            parameters: Dictionary of model parameters
        
        Returns:
            True if profile was created/updated successfully, False otherwise
        """
        try:
            # Use model name as the profile name
            name = model.split('/')[-1] if '/' in model else model
            profile = ModelProfile(name, service, model, parameters)
            profile_id = profile.get_profile_id()
            
            # Always allow overwrite since each model has only one profile
            self._profiles[profile_id] = profile
            self._save_profiles()
            
            action = "Updated" if profile_id in self._profiles else "Created"
            logging.info(f"{action} model profile: {profile_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error creating/updating model profile: {e}")
            return False
    
    def update_profile(self, profile_id: str, name: str, service: str, model: str, parameters: Dict[str, Any]) -> bool:
        """
        Update an existing model profile
        
        Args:
            profile_id: ID of the profile to update
            name: New name for the profile
            service: New service
            model: New model
            parameters: New parameters
        
        Returns:
            True if profile was updated successfully, False otherwise
        """
        try:
            if profile_id not in self._profiles:
                logging.warning(f"Profile with ID {profile_id} not found")
                return False
            
            # Create new profile and check if the new ID conflicts with existing profiles
            new_profile = ModelProfile(name, service, model, parameters)
            new_profile_id = new_profile.get_profile_id()
            
            if new_profile_id != profile_id and new_profile_id in self._profiles:
                logging.warning(f"Cannot update profile: new ID {new_profile_id} already exists")
                return False
            
            # Remove old profile if ID changed
            if new_profile_id != profile_id:
                del self._profiles[profile_id]
            
            self._profiles[new_profile_id] = new_profile
            self._save_profiles()
            logging.info(f"Updated model profile: {profile_id} -> {new_profile_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error updating model profile: {e}")
            return False
    
    def delete_profile(self, profile_id: str) -> bool:
        """
        Delete a model profile
        
        Args:
            profile_id: ID of the profile to delete
        
        Returns:
            True if profile was deleted successfully, False otherwise
        """
        try:
            if profile_id not in self._profiles:
                logging.warning(f"Profile with ID {profile_id} not found")
                return False
            
            del self._profiles[profile_id]
            self._save_profiles()
            logging.info(f"Deleted model profile: {profile_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error deleting model profile: {e}")
            return False
    
    def get_profile(self, service: str, model: str) -> Optional[ModelProfile]:
        """
        Get a model profile by service and model
        
        Args:
            service: LLM service (e.g., 'OpenRouter', 'OpenAI') 
            model: Model identifier
        
        Returns:
            ModelProfile if found, None otherwise
        """
        # Convert service to short format for profile lookup
        service_short = self._get_service_short_name(service)
        profile_id = f"{service_short}:{model}"
        return self._profiles.get(profile_id)
    
    def get_profile_by_id(self, profile_id: str) -> Optional[ModelProfile]:
        """
        Get a specific model profile by ID
        
        Args:
            profile_id: ID of the profile to retrieve
        
        Returns:
            ModelProfile if found, None otherwise
        """
        return self._profiles.get(profile_id)
    
    def apply_profile_to_params(self, service: str, model: str, fallback_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply profile parameters to existing LLM parameters if a profile exists
        
        Args:
            service: LLM service (e.g., 'OpenRouter', 'OpenAI')
            model: Model identifier
            fallback_params: Default parameters to use if no profile exists
        
        Returns:
            Dictionary of LLM parameters (either from profile or fallback)
        """
        try:
            profile = self.get_profile(service, model)
            if profile and profile.parameters:
                logging.info(f"Applying profile parameters for {service}/{model}")
                return profile.parameters.copy()
            else:
                logging.debug(f"No profile found for {service}/{model}, using fallback parameters")
                return fallback_params if fallback_params else {}
        except Exception as e:
            logging.error(f"Error applying profile for {service}/{model}: {e}")
            return fallback_params if fallback_params else {}
    
    def has_profile(self, service: str, model: str) -> bool:
        """
        Check if a profile exists for the given service and model
        
        Args:
            service: LLM service (e.g., 'OpenRouter', 'OpenAI')
            model: Model identifier
        
        Returns:
            True if profile exists, False otherwise
        """
        try:
            profile = self.get_profile(service, model) 
            return profile is not None
        except Exception as e:
            logging.error(f"Error checking if profile exists for {service}/{model}: {e}")
            return False

    def get_all_profiles(self) -> Dict[str, ModelProfile]:
        """
        Get all model profiles
        
        Returns:
            Dictionary of profile_id -> ModelProfile
        """
        return self._profiles.copy()
    
    def get_profiles_for_service(self, service: str) -> Dict[str, ModelProfile]:
        """
        Get all profiles for a specific service
        
        Args:
            service: Service name to filter by
        
        Returns:
            Dictionary of profile_id -> ModelProfile for the specified service
        """
        return {
            profile_id: profile
            for profile_id, profile in self._profiles.items()
            if profile.service == service
        }
    
    def get_profiles_for_model(self, service: str, model: str) -> Dict[str, ModelProfile]:
        """
        Get all profiles for a specific model
        
        Args:
            service: Service name
            model: Model name
        
        Returns:
            Dictionary of profile_id -> ModelProfile for the specified model
        """
        return {
            profile_id: profile
            for profile_id, profile in self._profiles.items()
            if profile.service == service and profile.model == model
        }
    
    def get_profile_for_model(self, service: str, model: str) -> Optional[ModelProfile]:
        """
        Get the profile for a specific model
        
        Args:
            service: Service name (display name like "OpenRouter")
            model: Model name
        
        Returns:
            ModelProfile if found, None otherwise
        """
        # Map display name to short identifier for lookup
        service_map = {
            "OpenRouter": "or",
            "NanoGPT": "nano", 
            "OpenAI": "openai"
        }
        service_id = service_map.get(service, service.lower())
        profile_id = f"{service_id}:{model}"
        return self._profiles.get(profile_id)
    
    def has_profile_for_model(self, service: str, model: str) -> bool:
        """
        Check if a profile exists for a specific model
        
        Args:
            service: Service name (display name like "OpenRouter")
            model: Model name
        
        Returns:
            True if profile exists, False otherwise
        """
        # Map display name to short identifier for lookup
        service_map = {
            "OpenRouter": "or",
            "NanoGPT": "nano", 
            "OpenAI": "openai"
        }
        service_id = service_map.get(service, service.lower())
        profile_id = f"{service_id}:{model}"
        return profile_id in self._profiles
    
    def get_all_available_profiles(self) -> List[Dict[str, str]]:
        """
        Get all available profiles for random selection
        
        Returns:
            List of dicts with service, model, and profile_id for each profile
        """
        profiles_list = []
        for profile_id, profile in self._profiles.items():
            # Extract service ID from profile ID (should be short format like 'nano', 'or')
            service_id = profile_id.split(':', 1)[0]
            profiles_list.append({
                "profile_id": profile_id,
                "service": service_id,  # Short identifier (or, nano, openai)
                "service_display": profile.service,  # Display name (OpenRouter, NanoGPT)
                "model": profile.model,
                "name": profile.name
            })
        return profiles_list
    
    def get_random_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get a random profile for automatic selection
        
        Returns:
            Dict with profile info or None if no profiles exist
        """
        if not self._profiles:
            return None
        
        import random
        profile_id = random.choice(list(self._profiles.keys()))
        profile = self._profiles[profile_id]
        
        # Extract service ID from profile ID (should be short format like 'nano', 'or')
        service_id = profile_id.split(':', 1)[0]
        
        return {
            "profile_id": profile_id,
            "service": service_id,  # Short identifier for CSV compatibility (nano, or, openai)
            "service_display": profile.service,  # Display name (NanoGPT, OpenRouter, OpenAI)
            "model": profile.model,
            "parameters": profile.parameters,
            "name": profile.name
        } 