"""
Configuration data models.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path


class SpecStandardizationError(Exception):
    """Base exception for spec standardization errors"""
    pass


class ConfigurationError(SpecStandardizationError):
    """Configuration-related errors"""
    pass


@dataclass
class Configuration:
    """Configuration settings for the CLI tool"""
    cache_enabled: bool = True
    cache_ttl_hours: int = 24
    max_file_size_mb: int = 10
    parallel_processing: bool = True
    max_workers: int = 4
    backup_enabled: bool = True
    backup_directory: Optional[Path] = None
    log_level: str = "INFO"
    version: str = "1.1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Path):
                result[key] = str(value)
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Configuration":
        """Create configuration from dictionary"""
        # Convert string paths back to Path objects
        if "backup_directory" in data and data["backup_directory"]:
            data["backup_directory"] = Path(data["backup_directory"])
        
        return cls(**data)