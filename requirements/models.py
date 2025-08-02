"""
Enhanced data models for requirements tracking and management.

This module extends the basic requirements models to support living document
management, git tracking, and status monitoring.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime


class RequirementStatus(Enum):
    """Status of a requirement in the codebase."""
    SUPPORTED = "supported"        # ✅ Requirement is implemented and working
    DEPRECATED = "deprecated"      # ⚠️ Requirement is deprecated but still functional
    REMOVED = "removed"           # ❌ Requirement is no longer supported
    UNKNOWN = "unknown"           # ❓ Status cannot be determined
    
    # Kiro-specific statuses for structured requirements
    IMPLEMENTED = "implemented"    # ✅ Task is complete and requirement is implemented
    IN_PROGRESS = "in_progress"    # 🚧 Some acceptance criteria are done, others pending
    TODO = "todo"                 # 📝 Task is not yet complete


class RequirementSource(Enum):
    """Source where a requirement was discovered."""
    DOCUMENTATION = "documentation"  # Found in markdown files
    CODE_ANALYSIS = "code_analysis"  # Inferred from code structure/comments
    COMMIT_MESSAGE = "commit_message"  # Extracted from git commit messages
    MANUAL = "manual"               # Manually added


@dataclass
class RequirementRecord:
    """
    Enhanced requirement record with status tracking and git integration.
    
    This represents a single requirement in the living document with full
    lifecycle tracking capabilities.
    """
    # Core requirement data
    id: str                           # REQ-001, REQ-002, etc.
    ears_format: str                  # The requirement in EARS format
    original_text: str               # Original text before EARS conversion
    
    # Status and lifecycle
    status: RequirementStatus
    source_type: RequirementSource
    source_location: str             # File path and line number or code location
    
    # Git tracking
    added_date: datetime
    added_commit: str
    last_verified_date: datetime
    last_verified_commit: str
    deprecated_date: Optional[datetime] = None
    deprecated_commit: Optional[str] = None
    deprecated_reason: Optional[str] = None
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    related_requirements: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Ensure data consistency after initialization."""
        if not self.id.startswith('REQ-'):
            raise ValueError(f"Requirement ID must start with 'REQ-': {self.id}")
        
        if self.status == RequirementStatus.DEPRECATED and not self.deprecated_date:
            self.deprecated_date = datetime.now()
    
    @property
    def status_emoji(self) -> str:
        """Get emoji representation of the status."""
        return {
            RequirementStatus.SUPPORTED: "✅",
            RequirementStatus.DEPRECATED: "⚠️", 
            RequirementStatus.REMOVED: "❌",
            RequirementStatus.UNKNOWN: "❓",
            RequirementStatus.IMPLEMENTED: "✅",
            RequirementStatus.IN_PROGRESS: "🚧",
            RequirementStatus.TODO: "📝"
        }[self.status]
    
    @property
    def age_days(self) -> int:
        """Get the age of the requirement in days."""
        return (datetime.now() - self.added_date).days
    
    def to_markdown_section(self) -> str:
        """Convert this requirement to a markdown section for the living document."""
        lines = [
            f"## {self.id}: {self._extract_requirement_title()}",
            f"**EARS Format**: {self.ears_format}",
            f"**Status**: {self.status_emoji} {self.status.value.title()}",
            f"**Source**: {self.source_location} ({self.source_type.value})",
            f"**Added**: {self.added_date.strftime('%Y-%m-%d')} ({self.added_commit[:8]})",
            f"**Last Verified**: {self.last_verified_date.strftime('%Y-%m-%d')} ({self.last_verified_commit[:8]})"
        ]
        
        if self.status == RequirementStatus.DEPRECATED and self.deprecated_date:
            lines.append(f"**Deprecated**: {self.deprecated_date.strftime('%Y-%m-%d')} ({self.deprecated_commit[:8]}) - {self.deprecated_reason or 'No reason provided'}")
        
        if self.tags:
            lines.append(f"**Tags**: {', '.join(self.tags)}")
        
        if self.related_requirements:
            lines.append(f"**Related**: {', '.join(self.related_requirements)}")
        
        lines.append("")  # Empty line after each requirement
        return "\n".join(lines)
    
    def _extract_requirement_title(self) -> str:
        """Extract a concise title from the EARS format requirement."""
        # Try to extract the core action from EARS format
        text = self.ears_format.lower()
        
        # Look for SHALL/SHOULD/MUST clauses
        for keyword in ['shall', 'should', 'must']:
            if keyword in text:
                parts = text.split(keyword, 1)
                if len(parts) > 1:
                    action = parts[1].strip()
                    # Take first 50 chars and clean up
                    title = action[:50].strip()
                    if title.endswith(',') or title.endswith('.'):
                        title = title[:-1]
                    return title.title()
        
        # Fallback: use first part of original text
        return self.original_text[:50].strip()


@dataclass
class RequirementsMetadata:
    """
    Metadata about the requirements tracking process.
    
    This is stored in .gjalla/requirements_metadata.json to track the state
    of requirements discovery and analysis.
    """
    # Git tracking
    last_scan_commit: str
    last_scan_date: datetime
    
    # File tracking
    analyzed_files: List[str] = field(default_factory=list)      # Files analyzed for requirements
    excluded_files: List[str] = field(default_factory=list)      # Files excluded from analysis
    
    # Statistics
    total_requirements: int = 0
    requirements_by_status: Dict[str, int] = field(default_factory=dict)
    requirements_by_source: Dict[str, int] = field(default_factory=dict)
    
    # Processing info
    analysis_mode: str = "full"  # "full", "incremental", "documentation_only"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'last_scan_commit': self.last_scan_commit,
            'last_scan_date': self.last_scan_date.isoformat(),
            'analyzed_files': self.analyzed_files,
            'excluded_files': self.excluded_files,
            'total_requirements': self.total_requirements,
            'requirements_by_status': self.requirements_by_status,
            'requirements_by_source': self.requirements_by_source,
            'analysis_mode': self.analysis_mode,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'RequirementsMetadata':
        """Create instance from dictionary loaded from JSON."""
        return cls(
            last_scan_commit=data['last_scan_commit'],
            last_scan_date=datetime.fromisoformat(data['last_scan_date']),
            analyzed_files=data.get('analyzed_files', []),
            excluded_files=data.get('excluded_files', []),
            total_requirements=data.get('total_requirements', 0),
            requirements_by_status=data.get('requirements_by_status', {}),
            requirements_by_source=data.get('requirements_by_source', {}),
            analysis_mode=data.get('analysis_mode', 'full'),
        )


@dataclass 
class RequirementsChangeSet:
    """
    Represents a set of changes to requirements between scans.
    
    This is used to track what has changed since the last requirements
    analysis and helps generate meaningful reports.
    """
    # New requirements discovered
    added_requirements: List[RequirementRecord] = field(default_factory=list)
    
    # Requirements that changed status
    status_changes: List[tuple] = field(default_factory=list)  # (requirement_id, old_status, new_status, reason)
    
    # Requirements that were removed/no longer found
    removed_requirements: List[str] = field(default_factory=list)  # requirement IDs
    
    # Files that were analyzed this scan
    files_analyzed: Set[str] = field(default_factory=set)
    
    # Git info
    from_commit: str = ""
    to_commit: str = ""
    scan_date: datetime = field(default_factory=datetime.now)
    
    @property
    def has_changes(self) -> bool:
        """Check if this changeset contains any changes."""
        return bool(
            self.added_requirements or 
            self.status_changes or 
            self.removed_requirements
        )
    
    def summary(self) -> str:
        """Generate a human-readable summary of changes."""
        if not self.has_changes:
            return "No requirements changes detected."
        
        parts = []
        if self.added_requirements:
            parts.append(f"{len(self.added_requirements)} new requirements")
        if self.status_changes:
            parts.append(f"{len(self.status_changes)} status changes")
        if self.removed_requirements:
            parts.append(f"{len(self.removed_requirements)} requirements removed")
        
        return f"Requirements changes: {', '.join(parts)}"


# Error classes
class RequirementsTrackingError(Exception):
    """Base exception for requirements tracking errors."""
    pass


class GitIntegrationError(RequirementsTrackingError):
    """Error related to git operations."""
    pass