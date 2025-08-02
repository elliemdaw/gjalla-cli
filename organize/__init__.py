"""
Project organization and documentation management system.

This package provides functionality for organizing, standardizing,
and restructuring project documentation and files.
"""

# Core organization functionality - the essentials that we know work
from .name_only_reorganizer import NameOnlyReorganizer
from .simple_classifier import SimpleClassifier
from .backup_manager import BackupManager
from .models import NameOnlyConfig

__all__ = [
    # Core organization
    'NameOnlyReorganizer',
    'SimpleClassifier', 
    'BackupManager',
    'NameOnlyConfig'
]