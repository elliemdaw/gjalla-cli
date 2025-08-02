"""
Name-only reorganizer main orchestrator.

This module provides the main orchestration logic for name-only reorganization,
coordinating structure validation, directory creation, file classification,
and file organization using fast regex-based classification.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from rich.console import Console
from rich.table import Table

try:
    from .models import (
        NameOnlyConfig, ReorganizationResult,
        CreationResult, ClassificationResult, OrganizationResult,
        ClassifiedFile, BackupSession, NameOnlyReorganizationError
    )
    from .structure_validator import StructureValidator
    from .directory_creator import DirectoryCreator
    from .simple_classifier import SimpleClassifier
    from .file_organizer import FileOrganizer
    from .template_parser import TemplateParser
    from .backup_manager import BackupManager
    from .exclusion_utils import ExclusionUtils
except ImportError:
    # Fallback for direct execution - import modules directly
    try:
        from requirements.models import (
            NameOnlyConfig, ReorganizationResult,
            CreationResult, ClassificationResult, OrganizationResult,
            ClassifiedFile, BackupSession, NameOnlyReorganizationError
        )
        from organize.structure_validator import StructureValidator
        from organize.directory_creator import DirectoryCreator
        from organize.simple_classifier import SimpleClassifier
        from organize.file_organizer import FileOrganizer
        from organize.template_parser import TemplateParser
        from organize.backup_manager import BackupManager
        from organize.exclusion_utils import ExclusionUtils
    except ImportError:
        # Final fallback - import as standalone modules (should not be reached)
        raise ImportError("Cannot import required onboarding modules. Please check the package installation.")


# Set up logging
logger = logging.getLogger(__name__)


class NameOnlyReorganizer:
    """
    Main orchestrator for name-only reorganization process.
    
    This class coordinates the entire name-only reorganization workflow:
    1. Validates repository structure against templates
    2. Creates missing directories as needed
    3. Classifies markdown files using simple Python-based classification
    4. Organizes files into appropriate directories
    5. Provides comprehensive backup and reporting capabilities
    """
    
    def __init__(self, backup_manager: BackupManager, template_parser: Optional[TemplateParser] = None):
        """
        Initialize the name-only reorganizer.
        
        Args:
            backup_manager: BackupManager instance for tracking operations
            template_parser: Optional TemplateParser instance. If None, creates a new one.
        """
        self.backup_manager = backup_manager
        self.template_parser = template_parser or TemplateParser()
        
        # Initialize component instances
        self.structure_validator = StructureValidator(self.template_parser)
        self.directory_creator = DirectoryCreator(self.backup_manager)
        self.simple_classifier = SimpleClassifier(filename_only=True)
        self.file_organizer = FileOrganizer(self.backup_manager)
    
    def reorganize_repository(self, project_dir: Path, config: NameOnlyConfig) -> ReorganizationResult:
        """
        Main entry point for name-only reorganization.
        
        Orchestrates the complete reorganization process including structure validation,
        directory creation, file classification, and organization.
        
        Args:
            project_dir: Path to the project directory to reorganize
            config: Configuration for the reorganization process
            
        Returns:
            ReorganizationResult: Comprehensive result of the reorganization process
            
        Raises:
            NameOnlyReorganizationError: If reorganization fails
        """
        start_time = datetime.now()
        errors = []
        warnings = []
        backup_session = None
        
        try:
            logger.info(f"Starting name-only reorganization for {project_dir}")
            
            # Validate configuration
            config_errors = config.validate()
            if config_errors:
                raise NameOnlyReorganizationError(f"Invalid configuration: {'; '.join(config_errors)}")
            
            # Validate project directory
            if not project_dir.exists():
                raise NameOnlyReorganizationError(f"Project directory does not exist: {project_dir}")
            
            if not project_dir.is_dir():
                raise NameOnlyReorganizationError(f"Project path is not a directory: {project_dir}")
            
            # Create backup session if backup is enabled
            if config.backup_enabled and not config.dry_run:
                try:
                    backup_session = self._create_backup_session(project_dir, config)
                    logger.info(f"Created backup session: {backup_session.session_id}")
                except Exception as e:
                    warnings.append(f"Failed to create backup session: {str(e)}")
                    logger.warning(f"Backup creation failed: {str(e)}")
            
            # Step 1: Validate and create structure
            logger.info("Validating repository structure")
            structure_result = self.validate_and_create_structure(project_dir, config, backup_session)
            
            # Step 2: Classify and organize files
            logger.info("Classifying and organizing files")
            organization_result = self.classify_and_organize_files(project_dir, config, backup_session)
            
            # Calculate execution time
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            # Determine overall success
            success = (
                structure_result.get('success', True) and
                organization_result.get('success', True) and
                len(errors) == 0
            )
            
            # Generate summary report
            summary_report = self._generate_summary_report(
                project_dir, structure_result, organization_result, execution_time
            )
            
            # Create comprehensive result
            result = ReorganizationResult(
                project_dir=project_dir,
                success=success,
                structure_validation=structure_result.get('validation_result'),
                directory_creation=structure_result.get('creation_result'),
                file_classification=organization_result.get('classification_result'),
                file_organization=organization_result.get('organization_result'),
                backup_session=backup_session,
                execution_time=execution_time,
                errors=errors,
                warnings=warnings,
                summary_report=summary_report
            )
            
            logger.info(f"Name-only reorganization completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            if isinstance(e, NameOnlyReorganizationError):
                logger.error(f"Reorganization failed: {str(e)}")
                raise
            
            error_msg = f"Unexpected error during reorganization: {str(e)}"
            logger.error(error_msg)
            raise NameOnlyReorganizationError(error_msg) from e
    
    def validate_and_create_structure(self, project_dir: Path, config: NameOnlyConfig, backup_session: Optional[BackupSession] = None) -> Dict[str, Any]:
        """
        Coordinate validation and directory creation.
        
        Args:
            project_dir: Path to the project directory
            config: Configuration for the reorganization process
            backup_session: Optional backup session for tracking operations
            
        Returns:
            Dict containing validation and creation results
            
        Raises:
            NameOnlyReorganizationError: If validation or creation fails
        """
        try:
            # Parse template
            template = self.template_parser.parse_template_file(config.template_file)
            logger.info(f"Parsed template: {template.template_name}")
            
            # Validate current structure
            validation_result = self.structure_validator.validate_structure(project_dir, template)
            logger.info(f"Structure compliance: {validation_result.compliance_score:.2f}")
            
            creation_result = None
            
            # Create missing directories if enabled and needed
            if config.create_missing_directories and validation_result.missing_directories:
                logger.info(f"Creating {len(validation_result.missing_directories)} missing directories")
                
                if config.dry_run:
                    logger.info("Dry run mode: would create directories but not actually creating them")
                    # Create a mock creation result for dry run
                    creation_result = CreationResult(
                        created_directories=validation_result.missing_directories,
                        failed_directories=[],
                        success=True,
                        errors=[],
                        warnings=["Dry run mode: directories not actually created"]
                    )
                else:
                    # Convert absolute paths to relative paths for directory creation
                    relative_missing_dirs = []
                    for missing_dir in validation_result.missing_directories:
                        try:
                            relative_path = missing_dir.relative_to(project_dir)
                            relative_missing_dirs.append(relative_path)
                        except ValueError:
                            # If path is not relative to project_dir, use as-is
                            relative_missing_dirs.append(missing_dir)
                    
                    creation_result = self.directory_creator.create_missing_directories(
                        project_dir, relative_missing_dirs, backup_session
                    )
                    
                    if creation_result.success:
                        logger.info(f"Successfully created {len(creation_result.created_directories)} directories")
                    else:
                        logger.warning(f"Directory creation had {len(creation_result.failed_directories)} failures")
            
            return {
                'success': True,
                'validation_result': validation_result,
                'creation_result': creation_result,
                'template': template
            }
            
        except Exception as e:
            error_msg = f"Failed to validate and create structure: {str(e)}"
            logger.error(error_msg)
            raise NameOnlyReorganizationError(error_msg) from e
    
    def classify_and_organize_files(self, project_dir: Path, config: NameOnlyConfig,
                                  backup_session: Optional[BackupSession] = None) -> Dict[str, Any]:
        """
        Coordinate classification and organization of files.
        
        Args:
            project_dir: Path to the project directory
            config: Configuration for the reorganization process
            backup_session: Optional backup session for tracking operations
            
        Returns:
            Dict containing classification and organization results
            
        Raises:
            NameOnlyReorganizationError: If classification or organization fails
        """
        try:
            # Find markdown files to classify
            markdown_files = self._find_markdown_files(project_dir, config.exclusion_patterns)
            logger.info(f"Found {len(markdown_files)} markdown files to classify")
            
            if not markdown_files:
                logger.info("No markdown files found to organize")
                return {
                    'success': True,
                    'classification_result': None,
                    'organization_result': None
                }
            
            # Initialize classifier with custom patterns if provided
            # For name-only reorganization, use filename-only classification
            if config.custom_classification_patterns:
                classifier = SimpleClassifier(config.custom_classification_patterns, filename_only=True)
            else:
                classifier = SimpleClassifier(filename_only=True)
            
            # Classify files
            start_time = datetime.now()
            
            # Handle special files that should go directly to aimarkdowns/ without classification
            special_files = []
            regular_files = []
            
            for file_path in markdown_files:
                if file_path.name.upper() in ['GEMINI.MD', 'CLAUDE.MD']:
                    # Create a special ClassifiedFile for these files
                    special_file = ClassifiedFile(
                        file_path=file_path,
                        category='aimarkdowns',  # Special category that maps directly to aimarkdowns/
                        confidence=1.0,
                        classification_reasons=[f"Special file {file_path.name} always goes to aimarkdowns/"],
                        content_preview=None
                    )
                    special_files.append(special_file)
                    logger.info(f"Special handling: {file_path.name} -> aimarkdowns/")
                else:
                    regular_files.append(file_path)
            
            # Classify regular files
            if regular_files:
                classified_regular_files = classifier.classify_files(regular_files)
            else:
                classified_regular_files = []
            
            # Combine special files and classified regular files
            classified_files = special_files + classified_regular_files
            classification_time = (datetime.now() - start_time).total_seconds()
            
            # Create classification result
            classification_distribution = {}
            low_confidence_files = []
            
            for classified_file in classified_files:
                category = classified_file.category
                classification_distribution[category] = classification_distribution.get(category, 0) + 1
                
                if classified_file.confidence < config.confidence_threshold:
                    low_confidence_files.append(classified_file)
            
            classification_result = ClassificationResult(
                classified_files=classified_files,
                total_files=len(markdown_files),
                classification_distribution=classification_distribution,
                low_confidence_files=low_confidence_files,
                processing_time=classification_time
            )
            
            # Organize files if not in dry run mode
            organization_result = None
            
            if config.dry_run:
                logger.info("Dry run mode: calculating what would be done without making changes")
                # Calculate actual target paths for dry run preview
                from .models import MoveResult
                
                # Parse template to get category mapping (same as real organization)
                template = self.template_parser.parse_template_file(config.template_file)
                category_mapping = template.get_category_mapping()
                
                mock_moves = []
                planned_moves = []  # For detailed reporting
                
                for classified_file in classified_files:
                    # Calculate actual target directory (same logic as file_organizer)
                    target_dir = self._calculate_target_directory_for_dry_run(
                        classified_file.category, category_mapping, template, project_dir
                    )
                    
                    if target_dir:
                        # Calculate full target path with conflict resolution
                        target_path = target_dir / classified_file.file_path.name
                        
                        # Handle potential naming conflicts in dry run
                        conflict_resolved = False
                        if target_path.exists() and target_path != classified_file.file_path:
                            original_name = target_path.name
                            target_path = self._resolve_naming_conflicts_dry_run(
                                classified_file.file_path, target_path
                            )
                            conflict_resolved = (target_path.name != original_name)
                        
                        # Store detailed move information for reporting
                        planned_moves.append({
                            'source_path': classified_file.file_path,
                            'target_path': target_path,
                            'category': classified_file.category,
                            'confidence': classified_file.confidence,
                            'conflict_resolved': conflict_resolved,
                            'would_move': target_path != classified_file.file_path
                        })
                        
                        mock_moves.append(MoveResult(
                            source_path=classified_file.file_path,
                            target_path=target_path,
                            success=True,
                            conflict_resolved=conflict_resolved
                        ))
                    else:
                        # No target directory found
                        mock_moves.append(MoveResult(
                            source_path=classified_file.file_path,
                            target_path=classified_file.file_path,  # No change
                            success=False,
                            error_message=f"No target directory found for category '{classified_file.category}'"
                        ))
                
                # Store planned moves for detailed dry-run reporting
                organization_result = OrganizationResult(
                    moved_files=mock_moves,
                    successful_moves=len([m for m in mock_moves if m.success and m.target_path != m.source_path]),
                    failed_moves=len([m for m in mock_moves if not m.success]),
                    conflicts_resolved=len([m for m in mock_moves if m.conflict_resolved]),
                    total_processing_time=0.0,
                    errors=[],
                    warnings=["Dry run mode: files not actually moved"]
                )
                
                # Add planned moves to organization result for detailed reporting
                organization_result.planned_moves = planned_moves
            else:
                # Parse template for file organization
                template = self.template_parser.parse_template_file(config.template_file)
                
                # Organize files
                organization_result = self.file_organizer.organize_files(
                    classified_files, template, backup_session or self._create_dummy_backup_session()
                )
                
                if organization_result.successful_moves > 0:
                    logger.info(f"Successfully moved {organization_result.successful_moves} files")
                if organization_result.failed_moves > 0:
                    logger.warning(f"Failed to move {organization_result.failed_moves} files")
                if organization_result.conflicts_resolved > 0:
                    logger.info(f"Resolved {organization_result.conflicts_resolved} naming conflicts")
            
            return {
                'success': True,
                'classification_result': classification_result,
                'organization_result': organization_result
            }
            
        except Exception as e:
            error_msg = f"Failed to classify and organize files: {str(e)}"
            logger.error(error_msg)
            raise NameOnlyReorganizationError(error_msg) from e
    
    def _find_markdown_files(self, project_dir: Path, exclusion_patterns: List[str]) -> List[Path]:
        """
        Find markdown files in the project directory, excluding specified patterns.
        
        Args:
            project_dir: Path to the project directory
            exclusion_patterns: List of patterns to exclude
            
        Returns:
            List of markdown file paths
        """
        return ExclusionUtils.find_markdown_files(project_dir, exclusion_patterns)
    
    def _create_backup_session(self, project_dir: Path, config: NameOnlyConfig) -> BackupSession:
        """
        Create a backup session for the reorganization operation.
        
        Args:
            project_dir: Path to the project directory
            config: Configuration for the reorganization process
            
        Returns:
            BackupSession: Created backup session
        """
        # Find only files that will actually be moved (not all markdown files)
        files_to_backup = []
        
        # Only backup markdown files that will be processed for reorganization
        markdown_files = self._find_markdown_files(project_dir, config.exclusion_patterns)
        files_to_backup.extend(markdown_files)
        
        # Note: We don't backup ALL markdown files, only those that will be moved.
        # Files that won't be moved don't need to be backed up.
        
        # Create backup session metadata
        metadata = {
            "backup_created_for": "reorganization",
            "operation_type": "name_only_reorganization",
            "project_dir": str(project_dir),
            "template_file": str(config.template_file),
            "dry_run": config.dry_run,
            "total_files": len(files_to_backup)
        }
        
        return self.backup_manager.create_backup(
            files=files_to_backup,
            operation_id="name_only_reorganization",
            metadata=metadata
        )
    
    def _create_dummy_backup_session(self) -> BackupSession:
        """
        Create a dummy backup session for operations that don't have a real backup.
        
        Returns:
            BackupSession: Dummy backup session
        """
        from .models import BackupSession
        import uuid
        
        return BackupSession(
            session_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            operation_type="dummy",
            backed_up_files=[],
            operation_log=[],
            metadata={"dummy": True}
        )
    
    def _calculate_target_directory_for_dry_run(self, category: str, category_mapping: Dict[str, str], 
                                               template, project_dir: Path) -> Optional[Path]:
        """
        Calculate target directory for a file category in dry-run mode.
        
        Args:
            category: File category (e.g., "features", "fixes", "reference")
            category_mapping: Mapping from categories to directory paths  
            template: Parsed template for directory resolution
            project_dir: Project directory path
            
        Returns:
            Path to target directory or None if not found
        """
        # First try direct mapping
        if category in category_mapping:
            return project_dir / category_mapping[category]
        
        # Try common fallback mappings
        fallback_mappings = {
            "features": ["aimarkdowns/features", "features", "aimarkdowns"],
            "fixes": ["aimarkdowns/fixes", "fixes", "aimarkdowns"], 
            "reference": ["aimarkdowns/reference", "reference", "docs", "aimarkdowns"],
            "misc": ["aimarkdowns/reference", "reference", "docs", "aimarkdowns"]
        }
        
        if category in fallback_mappings:
            for fallback_path in fallback_mappings[category]:
                if fallback_path in category_mapping.values():
                    return project_dir / fallback_path
                
                # Check if directory exists in template structure
                available_dirs = template.flatten_directory_paths()
                if fallback_path in available_dirs:
                    return project_dir / fallback_path
        
        # Final fallback - use first available directory from template
        available_dirs = template.flatten_directory_paths()
        if available_dirs:
            return project_dir / available_dirs[0]
        
        return None
    
    def _resolve_naming_conflicts_dry_run(self, source_path: Path, target_path: Path) -> Path:
        """
        Resolve naming conflicts for dry-run mode.
        
        Args:
            source_path: Original file path
            target_path: Proposed target path that has conflicts
            
        Returns:
            Path: Resolved target path that would avoid conflicts
        """
        if not target_path.exists():
            return target_path
        
        # Generate alternative name with counter
        counter = 1
        stem = target_path.stem
        suffix = target_path.suffix
        parent = target_path.parent
        
        while True:
            new_name = f"{stem}_{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
            # Safety limit to prevent infinite loop
            if counter > 100:
                return target_path
    
    def _generate_summary_report(self, project_dir: Path, structure_result: Dict[str, Any], organization_result: Dict[str, Any], execution_time: float) -> str:
        """
        Generate a comprehensive summary report of the reorganization process using Rich formatting.
        
        Args:
            project_dir: Path to the project directory
            structure_result: Results from structure validation and creation
            organization_result: Results from file classification and organization
            execution_time: Total execution time in seconds
            
        Returns:
            Rich-formatted summary report string
        """
        from io import StringIO
        console = Console(file=StringIO(), width=80)
        
        # Create summary tables
        summary_table = Table(title="📊 Reorganization Summary", show_header=True, header_style="bold magenta")
        summary_table.add_column("Component", style="cyan", width=24)
        summary_table.add_column("Status", style="green", width=18)
        summary_table.add_column("Details", style="white", width=40)
        
        # Directory creation summary
        creation_result = structure_result.get('creation_result')
        if creation_result:
            creation_status = "[green]✓ Success[/green]" if creation_result.success else "[red]✗ Failed[/red]"
            summary_table.add_row(
                "Directory Creation",
                creation_status,
                f"Created: {len(creation_result.created_directories)} | Failed: {len(creation_result.failed_directories)}"
            )
        
        # File classification summary
        classification_result = organization_result.get('classification_result')
        if classification_result:
            low_conf_count = len(classification_result.low_confidence_files)
            conf_color = "green" if low_conf_count == 0 else "yellow" if low_conf_count < 5 else "red"
            summary_table.add_row(
                "File Classification",
                f"[{conf_color}]{classification_result.total_files} files[/{conf_color}]",
                f"Time: {classification_result.processing_time:.2f}s | Low confidence: {low_conf_count}"
            )
        
        # File organization summary
        org_result = organization_result.get('organization_result')
        if org_result:
            org_status = "[green]✓ Complete[/green]" if org_result.failed_moves == 0 else f"[yellow]⚠ {org_result.failed_moves} failed[/yellow]"
            summary_table.add_row(
                "File Organization",
                org_status,
                f"Moved: {org_result.successful_moves} | Conflicts: {org_result.conflicts_resolved} | Time: {org_result.total_processing_time:.2f}s"
            )
        
        console.print(summary_table)
        
        # File distribution table (if classification data is available)
        if classification_result and classification_result.classification_distribution:
            console.print()
            dist_table = Table(title="📁 File Distribution", show_header=True, header_style="bold cyan")
            dist_table.add_column("Category", style="cyan", width=15)
            dist_table.add_column("Count", justify="right", style="magenta", width=10)
            dist_table.add_column("Percentage", justify="right", style="green", width=12)
            
            total_files = sum(classification_result.classification_distribution.values())
            for category, count in sorted(classification_result.classification_distribution.items()):
                percentage = (count / total_files * 100) if total_files > 0 else 0
                # Add emoji icons for categories
                category_icon = {
                    'features': '🚀',
                    'fixes': '🐛', 
                    'reference': '📚',
                    'aimarkdowns': '⭐'
                }.get(category, '📄')
                
                dist_table.add_row(
                    f"{category_icon} {category.title()}",
                    str(count),
                    f"{percentage:.1f}%"
                )
            
            console.print(dist_table)
        
        # Get the output as string
        output = console.file.getvalue()
        console.file.close()
        return output