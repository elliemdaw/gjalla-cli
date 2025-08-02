"""
Requirements tracking and management system.

This package provides comprehensive requirements discovery, tracking,
and living document management capabilities.
"""

from .models import (
    RequirementRecord, RequirementsMetadata, RequirementsChangeSet,
    RequirementStatus, RequirementSource, RequirementsTrackingError
)
from .tracker import RequirementsTracker
from .living_document import LivingRequirementsDocument
from .kiro_parser import KiroRequirementsParser
from .requirements_aggregator import RequirementsAggregator

__all__ = [
    'RequirementRecord',
    'RequirementsMetadata', 
    'RequirementsChangeSet',
    'RequirementStatus',
    'RequirementSource',
    'RequirementsTrackingError',
    'RequirementsTracker',
    'LivingRequirementsDocument',
    'KiroRequirementsParser',
    'RequirementsAggregator'
]