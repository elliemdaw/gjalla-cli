"""
Data models and configuration structures for the onboarding system.

This module contains all the core data models, enums, and configuration
structures used throughout the onboarding process.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime

class DocumentType(Enum):
    """Types of documents that can be discovered and organized."""
    README = "readme"
    API_DOCS = "api_docs"
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    TASKS = "tasks"
    USER_GUIDE = "user_guide"
    CHANGELOG = "changelog"
    CONTRIBUTING = "contributing"
    ARCHITECTURE = "architecture"
    SPECIFICATION = "specification"
    UNKNOWN = "unknown"


class ImplementationStatus(Enum):
    """Implementation status for requirements tracking."""
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    NOT_IMPLEMENTED = "not_implemented"
    UNKNOWN = "unknown"


class RequirementType(Enum):
    """Types of requirements that can be extracted."""
    EARS = "ears"
    GENERAL = "general"
    USER_STORY = "user_story"


@dataclass
class DiscoveredDocument:
    """Information about a discovered documentation file."""
    path: Path
    size: int
    last_modified: datetime
    detected_type: DocumentType
    confidence: float
    content_preview: Optional[str] = None
    
    def __post_init__(self):
        """Validate the discovered document data."""
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        
        if self.size < 0:
            raise ValueError("File size cannot be negative")


@dataclass
class ExtractedRequirement:
    """A requirement extracted from documentation."""
    text: str
    source_file: Path
    line_number: int
    requirement_type: RequirementType
    context: str
    extraction_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RequirementsAggregate:
    """Aggregated requirements from all discovered documents."""
    requirements: List[ExtractedRequirement]
    total_extracted: int
    duplicates_removed: int
    source_files: List[Path]
    generation_timestamp: datetime = field(default_factory=datetime.now)


class OnboardingError(Exception):
    """Base exception for onboarding operations."""
    pass


class RequirementsExtractionError(OnboardingError):
    """Error during requirements extraction."""
    pass


class BackupError(OnboardingError):
    """Error during backup operations."""
    pass


class RestoreError(OnboardingError):
    """Error during restore operations."""
    pass


# Name-only reorganization specific exceptions
class NameOnlyReorganizationError(OnboardingError):
    """Base exception for name-only reorganization operations."""
    pass


class TemplateParsingError(NameOnlyReorganizationError):
    """Error parsing directory template."""
    pass


class ClassificationError(NameOnlyReorganizationError):
    """Error during file classification."""
    pass


class FileOrganizationError(NameOnlyReorganizationError):
    """Error during file organization."""
    pass


class DirectoryCreationError(NameOnlyReorganizationError):
    """Error creating directories."""
    pass


@dataclass
class FileOperation:
    """Record of a file operation for backup/restore purposes."""
    operation_type: str  # MOVE, RENAME, MODIFY, CREATE, DELETE
    source_path: Optional[Path]
    target_path: Optional[Path]
    timestamp: datetime
    checksum_before: Optional[str] = None
    checksum_after: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Validate the file operation record."""
        errors = []
        
        valid_operations = {"MOVE", "RENAME", "MODIFY", "CREATE", "DELETE"}
        if self.operation_type not in valid_operations:
            errors.append(f"Invalid operation type: {self.operation_type}")
        
        # Validate paths based on operation type
        if self.operation_type in {"MOVE", "RENAME", "MODIFY"}:
            if not self.source_path:
                errors.append(f"{self.operation_type} operation requires source_path")
            if self.operation_type in {"MOVE", "RENAME"} and not self.target_path:
                errors.append(f"{self.operation_type} operation requires target_path")
        elif self.operation_type == "CREATE":
            if not self.target_path:
                errors.append("CREATE operation requires target_path")
        elif self.operation_type == "DELETE":
            if not self.source_path:
                errors.append("DELETE operation requires source_path")
        
        return errors


@dataclass
class BackedUpFile:
    """Information about a backed up file."""
    original_path: Path
    backup_path: Path
    checksum: str
    file_size: int
    backup_timestamp: datetime
    
    def validate(self) -> List[str]:
        """Validate the backed up file record."""
        errors = []
        
        if not self.original_path:
            errors.append("Original path is required")
        
        if not self.backup_path:
            errors.append("Backup path is required")
        
        if not self.checksum or not self.checksum.strip():
            errors.append("Checksum is required")
        
        if self.file_size < 0:
            errors.append("File size cannot be negative")
        
        return errors


@dataclass
class BackupSession:
    """Information about a backup session."""
    session_id: str
    timestamp: datetime
    operation_type: str
    backed_up_files: List[BackedUpFile]
    operation_log: List[FileOperation]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate the backup session."""
        errors = []
        
        if not self.session_id or not self.session_id.strip():
            errors.append("Session ID is required")
        
        if not self.operation_type or not self.operation_type.strip():
            errors.append("Operation type is required")
        
        if not isinstance(self.backed_up_files, list):
            errors.append("Backed up files must be a list")
        
        if not isinstance(self.operation_log, list):
            errors.append("Operation log must be a list")
        
        # Validate individual backed up files
        for i, backed_up_file in enumerate(self.backed_up_files):
            file_errors = backed_up_file.validate()
            errors.extend([f"Backed up file {i}: {error}" for error in file_errors])
        
        # Validate individual operations
        for i, operation in enumerate(self.operation_log):
            op_errors = operation.validate()
            errors.extend([f"Operation {i}: {error}" for error in op_errors])
        
        return errors


@dataclass
class RestoreResult:
    """Result of a backup restore operation."""
    session_id: str
    success: bool
    restored_files: List[Path]
    failed_files: List[Tuple[Path, str]]  # (path, error_message)
    validation_results: Dict[Path, bool]  # path -> checksum_valid
    restore_timestamp: datetime = field(default_factory=datetime.now)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    restored_directories: List[Path] = field(default_factory=list)


# Name-only reorganization data models
@dataclass
class NameOnlyConfig:
    """Configuration for name-only reorganization."""
    template_file: Path = Path("templates/directory.md")
    custom_classification_patterns: Dict[str, List[str]] = field(default_factory=dict)
    exclusion_patterns: List[str] = field(default_factory=lambda: [
        "README*", "CONTRIBUTING*", "LICENSE*", "CHANGELOG*"
    ])  # Note: .gitignore patterns and hidden files are automatically excluded
    backup_enabled: bool = True
    create_missing_directories: bool = True
    resolve_conflicts: bool = True
    dry_run: bool = False
    confidence_threshold: float = 0.3  # Minimum confidence for classification
    fallback_category: str = "reference"
    
    def validate(self) -> List[str]:
        """Validate the name-only configuration."""
        errors = []
        
        if not self.template_file:
            errors.append("Template file path is required")
        
        if not isinstance(self.custom_classification_patterns, dict):
            errors.append("Custom classification patterns must be a dictionary")
        
        if not isinstance(self.exclusion_patterns, list):
            errors.append("Exclusion patterns must be a list")
        
        if self.confidence_threshold < 0.0 or self.confidence_threshold > 1.0:
            errors.append("Confidence threshold must be between 0.0 and 1.0")
        
        if not self.fallback_category or not self.fallback_category.strip():
            errors.append("Fallback category cannot be empty")
        
        return errors


@dataclass
class ParsedTemplate:
    """Parsed directory template structure."""
    template_name: str
    directory_structure: Dict[str, Any]
    file_placement_rules: Dict[str, str]
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate the parsed template."""
        errors = []
        
        if not self.template_name or not self.template_name.strip():
            errors.append("Template name cannot be empty")
        
        if not isinstance(self.directory_structure, dict):
            errors.append("Directory structure must be a dictionary")
        
        if not isinstance(self.file_placement_rules, dict):
            errors.append("File placement rules must be a dictionary")
        
        if not isinstance(self.metadata, dict):
            errors.append("Metadata must be a dictionary")
        
        return errors
    
    def flatten_directory_paths(self) -> List[str]:
        """Convert nested structure to flat list of directory paths."""
        paths = []
        
        def _extract_paths(structure: Dict[str, Any], prefix: str = ""):
            for key, value in structure.items():
                if isinstance(value, dict):
                    # This is a directory
                    current_path = f"{prefix}/{key}" if prefix else key
                    paths.append(current_path)
                    _extract_paths(value, current_path)
                # Files (None values) are ignored in directory path extraction
        
        _extract_paths(self.directory_structure)
        return paths
    
    def get_category_mapping(self) -> Dict[str, str]:
        """Get mapping of file categories to target directories."""
        return self.file_placement_rules.copy()


@dataclass
class ClassifiedFile:
    """A file that has been classified for organization."""
    file_path: Path
    category: str  # "features", "fixes", "reference", "misc"
    confidence: float
    classification_reasons: List[str]  # Why it was classified this way
    content_preview: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Validate the classified file."""
        errors = []
        
        if not self.file_path:
            errors.append("File path is required")
        
        if not self.category or not self.category.strip():
            errors.append("Category cannot be empty")
        
        if self.confidence < 0.0 or self.confidence > 1.0:
            errors.append("Confidence must be between 0.0 and 1.0")
        
        if not isinstance(self.classification_reasons, list):
            errors.append("Classification reasons must be a list")
        
        return errors


@dataclass
class StructureValidationResult:
    """Result of repository structure validation."""
    project_dir: Path
    template_used: str
    existing_directories: List[Path]
    missing_directories: List[Path]
    compliance_score: float
    
    def validate(self) -> List[str]:
        """Validate the validation result."""
        errors = []
        
        if not self.project_dir:
            errors.append("Project directory is required")
        
        if not self.template_used or not self.template_used.strip():
            errors.append("Template used cannot be empty")
        
        if not isinstance(self.existing_directories, list):
            errors.append("Existing directories must be a list")
        
        if not isinstance(self.missing_directories, list):
            errors.append("Missing directories must be a list")
        
        if self.compliance_score < 0.0 or self.compliance_score > 1.0:
            errors.append("Compliance score must be between 0.0 and 1.0")
        
        return errors

@dataclass
class CreationResult:
    """Result of directory creation operations."""
    created_directories: List[Path]
    failed_directories: List[Tuple[Path, str]]  # (path, error_message)
    success: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def validate(self) -> List[str]:
        """Validate the creation result."""
        errors = []
        
        if not isinstance(self.created_directories, list):
            errors.append("Created directories must be a list")
        
        if not isinstance(self.failed_directories, list):
            errors.append("Failed directories must be a list")
        
        if not isinstance(self.errors, list):
            errors.append("Errors must be a list")
        
        if not isinstance(self.warnings, list):
            errors.append("Warnings must be a list")
        
        return errors


@dataclass
class ClassificationResult:
    """Result of file classification process."""
    classified_files: List[ClassifiedFile]
    total_files: int
    classification_distribution: Dict[str, int]
    low_confidence_files: List[ClassifiedFile]  # confidence < threshold
    processing_time: float
    
    def validate(self) -> List[str]:
        """Validate the classification result."""
        errors = []
        
        if not isinstance(self.classified_files, list):
            errors.append("Classified files must be a list")
        
        if self.total_files < 0:
            errors.append("Total files cannot be negative")
        
        if len(self.classified_files) > self.total_files:
            errors.append("Classified files cannot exceed total files")
        
        if not isinstance(self.classification_distribution, dict):
            errors.append("Classification distribution must be a dictionary")
        
        if not isinstance(self.low_confidence_files, list):
            errors.append("Low confidence files must be a list")
        
        if self.processing_time < 0.0:
            errors.append("Processing time cannot be negative")
        
        return errors


@dataclass
class MoveResult:
    """Result of a single file move operation."""
    source_path: Path
    target_path: Path
    success: bool
    conflict_resolved: bool
    error_message: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Validate the move result."""
        errors = []
        
        if not self.source_path:
            errors.append("Source path is required")
        
        if not self.target_path:
            errors.append("Target path is required")
        
        if not self.success and not self.error_message:
            errors.append("Error message is required when success is False")
        
        return errors


@dataclass
class OrganizationResult:
    """Result of file organization process."""
    moved_files: List[MoveResult]
    successful_moves: int
    failed_moves: int
    conflicts_resolved: int
    total_processing_time: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def validate(self) -> List[str]:
        """Validate the organization result."""
        errors = []
        
        if not isinstance(self.moved_files, list):
            errors.append("Moved files must be a list")
        
        if self.successful_moves < 0:
            errors.append("Successful moves cannot be negative")
        
        if self.failed_moves < 0:
            errors.append("Failed moves cannot be negative")
        
        if self.conflicts_resolved < 0:
            errors.append("Conflicts resolved cannot be negative")
        
        if self.successful_moves + self.failed_moves != len(self.moved_files):
            errors.append("Sum of successful and failed moves must equal total moved files")
        
        if self.total_processing_time < 0.0:
            errors.append("Total processing time cannot be negative")
        
        if not isinstance(self.errors, list):
            errors.append("Errors must be a list")
        
        if not isinstance(self.warnings, list):
            errors.append("Warnings must be a list")
        
        return errors


@dataclass
class ReorganizationResult:
    """Complete result of name-only reorganization process."""
    project_dir: Path
    success: bool
    structure_validation: StructureValidationResult
    directory_creation: CreationResult
    file_classification: ClassificationResult
    file_organization: OrganizationResult
    backup_session: Optional[BackupSession]
    execution_time: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary_report: str = ""
    
    def validate(self) -> List[str]:
        """Validate the reorganization result."""
        errors = []
        
        if not self.project_dir:
            errors.append("Project directory is required")
        
        # Validate nested results
        validation_errors = self.structure_validation.validate()
        errors.extend([f"Structure validation: {error}" for error in validation_errors])
        
        creation_errors = self.directory_creation.validate()
        errors.extend([f"Directory creation: {error}" for error in creation_errors])
        
        classification_errors = self.file_classification.validate()
        errors.extend([f"File classification: {error}" for error in classification_errors])
        
        organization_errors = self.file_organization.validate()
        errors.extend([f"File organization: {error}" for error in organization_errors])
        
        if self.backup_session:
            backup_errors = self.backup_session.validate()
            errors.extend([f"Backup session: {error}" for error in backup_errors])
        
        if self.execution_time < 0.0:
            errors.append("Execution time cannot be negative")
        
        if not isinstance(self.errors, list):
            errors.append("Errors must be a list")
        
        if not isinstance(self.warnings, list):
            errors.append("Warnings must be a list")
        
        return errors