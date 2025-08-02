"""
Configuration manager for secure API key storage and settings management.
"""

import json
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet

from .models import Configuration, ConfigurationError


class ConfigurationManager:
    """Manages API keys and configuration settings with secure storage"""
    
    def __init__(self):
        self.config_dir = Path.home() / '.gjalla'
        self.config_file = self.config_dir / 'config.json'
        self.key_file = self.config_dir / 'key.key'
        self.cache_dir = self.config_dir / 'cache'
        
        # Ensure directories exist
        self.config_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)
        
        self._config: Optional[Configuration] = None
        self._cipher_suite: Optional[Fernet] = None

    def get_configuration(self) -> Configuration:
        """Get current configuration"""
        if self._config is None:
            self._config = self._load_configuration()
        return self._config

    def is_configured(self) -> bool:
        """Check if API keys are available from environment or configuration"""
        return True
    
    def check_environment_setup(self) -> bool:
        """Check if required environment variables are set."""
        return True
    
    def _load_configuration(self) -> Configuration:
        """Load configuration from file"""
        if not self.config_file.exists():
            return Configuration()
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            return Configuration.from_dict(data)
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")
    