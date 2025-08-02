"""
Structure validator for repository validation.

This module provides functionality to validate repository structure against
expected directory templates and generate compliance reports.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from .template_parser import TemplateParser
    from .models import (
        StructureValidationResult as ValidationResult, ParsedTemplate,
        StructureValidationError
    )
except ImportError:
    # Define minimal classes for standalone testing
    from pathlib import Path
    from typing import List, Dict, Any, Optional
    from dataclasses import dataclass
    
    class StructureValidationError(Exception):
        pass

    @dataclass
    class ParsedTemplate:
        template_name: str
        directory_structure: Dict[str, Any]
        file_placement_rules: Dict[str, str]
        
        def flatten_directory_paths(self) -> List[str]:
            paths = []
            def _extract_paths(structure: Dict[str, Any], prefix: str = ""):
                for key, value in structure.items():
                    if isinstance(value, dict):
                        current_path = f"{prefix}/{key}" if prefix else key
                        paths.append(current_path)
                        _extract_paths(value, current_path)
            _extract_paths(self.directory_structure)
            return paths
    
    class TemplateParser:
        pass


@dataclass
class ComplianceReport:
    """Report on directory structure compliance."""
    total_expected: int
    found_directories: int
    missing_directories: List[str]
    compliance_percentage: float
    structure_issues: List[str]


class StructureValidator:
    """Validates repository structure against expected directory templates."""
    
    def __init__(self, template_parser: Optional[TemplateParser] = None):
        """
        Initialize the structure validator.
        
        Args:
            template_parser: Optional template parser instance. If None, creates a new one.
        """
        self.template_parser = template_parser or TemplateParser()
    
    def validate_structure(self, project_dir: Path, template: ParsedTemplate) -> ValidationResult:
        """
        Compare if the provided repository contains the defined structure from the template.
        
        Args:
            project_dir: Path to the project directory to validate
            template: Parsed template containing expected structure
            
        Returns:
            ValidationResult containing validation details
            
        Raises:
            StructureValidationError: If validation fails due to errors
        """
        try:
            if not project_dir.exists():
                raise StructureValidationError(f"Project directory does not exist: {project_dir}")
            
            if not project_dir.is_dir():
                raise StructureValidationError(f"Project path is not a directory: {project_dir}")
            
            # Get expected directories from template
            expected_directories = template.flatten_directory_paths()
            
            # Find existing directories in project
            existing_directories = self._find_existing_directories(project_dir, expected_directories)
            
            # Identify missing directories
            missing_directories = self._identify_missing_directories(
                project_dir, expected_directories, existing_directories
            )
            
            # Generate compliance score
            compliance_score = self.generate_compliance_score(
                len(expected_directories), len(existing_directories)
            )

            return ValidationResult(
                project_dir=project_dir,
                template_used=template.template_name,
                existing_directories=[project_dir / path for path in existing_directories],
                missing_directories=[project_dir / path for path in missing_directories],
                compliance_score=compliance_score,
            )
            
        except Exception as e:
            if isinstance(e, StructureValidationError):
                raise
            raise StructureValidationError(f"Failed to validate structure: {str(e)}")
    
    def generate_compliance_score(self, total_expected: int, found_directories: int) -> float:
        """
        Quantify structure adherence with a score between 0.0 and 1.0.
        
        Args:
            total_expected: Total number of expected directories
            found_directories: Number of directories found
            
        Returns:
            Compliance score between 0.0 and 1.0
        """
        if total_expected == 0:
            return 1.0  # Perfect compliance if no directories expected
        
        if found_directories < 0 or found_directories > total_expected:
            return 0.0  # Invalid input
        
        return found_directories / total_expected
    
    def _find_existing_directories(self, project_dir: Path, expected_directories: List[str]) -> List[str]:
        """
        Find which expected directories actually exist in the project.
        
        Args:
            project_dir: Path to the project directory
            expected_directories: List of expected directory paths
            
        Returns:
            List of directory paths that exist
        """
        existing = []
        
        for expected_dir in expected_directories:
            dir_path = project_dir / expected_dir
            if dir_path.exists() and dir_path.is_dir():
                existing.append(expected_dir)
        
        return existing
    
    def _identify_missing_directories(
        self, 
        project_dir: Path, 
        expected_directories: List[str], 
        existing_directories: List[str]
    ) -> List[str]:
        """
        Identify directories that are expected but missing.
        
        Args:
            project_dir: Path to the project directory
            expected_directories: List of expected directory paths
            existing_directories: List of existing directory paths
            
        Returns:
            List of missing directory paths
        """
        existing_set = set(existing_directories)
        missing = []
        
        for expected_dir in expected_directories:
            if expected_dir not in existing_set:
                missing.append(expected_dir)
        
        return missing
    