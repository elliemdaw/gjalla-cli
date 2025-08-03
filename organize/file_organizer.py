"""
File organizer for moving classified files to appropriate directories.

This module provides file organization capabilities for the name-only reorganization
feature, including file movement, conflict resolution, and backup integration.
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

try:
    from .models import (
        ClassifiedFile, BackupSession, FileOperation, 
        FileOrganizationError, ParsedTemplate
    )
    from .backup_manager import BackupManager
except ImportError:
    # Fallback for direct execution
    from requirements.models import (
        ClassifiedFile, BackupSession, FileOperation,
        FileOrganizationError, ParsedTemplate
    )
    from backup_manager import BackupManager


@dataclass
class MoveResult:
    """Result of moving a single file."""
    source_path: Path
    target_path: Path
    success: bool
    conflict_resolved: bool = False
    error_message: Optional[str] = None
    
    def validate(self) -> List[str]:
        """Validate the move result."""
        errors = []
        
        if not self.source_path:
            errors.append("Source path is required")
        
        if not self.target_path:
            errors.append("Target path is required")
        
        if not self.success and not self.error_message:
            errors.append("Error message required when success is False")
        
        return errors


@dataclass
class OrganizationResult:
    """Result of file organization process."""
    moved_files: List[MoveResult]
    successful_moves: int
    failed_moves: int
    conflicts_resolved: int
    total_processing_time: float = 0.0
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
        
        if self.total_processing_time < 0:
            errors.append("Processing time cannot be negative")
        
        if not isinstance(self.errors, list):
            errors.append("Errors must be a list")
        
        if not isinstance(self.warnings, list):
            errors.append("Warnings must be a list")
        
        return errors


class FileOrganizer:
    """
    Organizes classified files by moving them to appropriate directories.
    
    This class handles:
    - Moving files to target directories based on classification
    - Resolving naming conflicts when files already exist
    - Integrating with backup system for undo capability
    - Updating internal references after moves (basic implementation)
    """
    
    def __init__(self, backup_manager: BackupManager):
        """
        Initialize the file organizer.
        
        Args:
            backup_manager: Backup manager for tracking file operations
        """
        self.backup_manager = backup_manager
    
    def organize_files(self, classified_files: List[ClassifiedFile], 
                      template: ParsedTemplate, 
                      backup_session: BackupSession) -> OrganizationResult:
        """
        Organize classified files by moving them to appropriate directories.
        
        Args:
            classified_files: List of classified files to organize
            template: Parsed template with directory structure and placement rules
            backup_session: Backup session for tracking operations
            
        Returns:
            OrganizationResult with details of the organization process
            
        Raises:
            FileOrganizationError: If organization fails
        """
        if not classified_files:
            return OrganizationResult(
                moved_files=[],
                successful_moves=0,
                failed_moves=0,
                conflicts_resolved=0
            )
        
        start_time = datetime.now()
        moved_files = []
        successful_moves = 0
        failed_moves = 0
        conflicts_resolved = 0
        errors = []
        warnings = []
        
        try:
            # Get category mapping from template
            category_mapping = template.get_category_mapping()
            
            for classified_file in classified_files:
                try:
                    if classified_file.category == 'aimarkdowns':
                        target_dir = Path('aimarkdowns')
                    else:
                        target_dir = self._get_target_directory(
                            classified_file.category, 
                            category_mapping,
                            template
                            )
                    
                    if not target_dir:
                        error_msg = f"No target directory found for category '{classified_file.category}'"
                        errors.append(error_msg)
                        move_result = MoveResult(
                            source_path=classified_file.file_path,
                            target_path=classified_file.file_path,  # No change
                            success=False,
                            error_message=error_msg
                        )
                        moved_files.append(move_result)
                        failed_moves += 1
                        continue
                    
                    # Move the file
                    move_result = self.move_file_to_category(
                        classified_file, 
                        target_dir, 
                        backup_session
                    )
                    
                    moved_files.append(move_result)
                    
                    if move_result.success:
                        successful_moves += 1
                        if move_result.conflict_resolved:
                            conflicts_resolved += 1
                    else:
                        failed_moves += 1
                        if move_result.error_message:
                            errors.append(f"Failed to move {classified_file.file_path}: {move_result.error_message}")
                
                except Exception as e:
                    error_msg = f"Error organizing file {classified_file.file_path}: {str(e)}"
                    errors.append(error_msg)
                    move_result = MoveResult(
                        source_path=classified_file.file_path,
                        target_path=classified_file.file_path,  # No change
                        success=False,
                        error_message=error_msg
                    )
                    moved_files.append(move_result)
                    failed_moves += 1
            
            # Validate that all moves completed successfully
            all_successful, validation_errors = self.validate_moves_completed(moved_files)
            if validation_errors:
                errors.extend(validation_errors)
            
            # Update internal references for successful moves
            successful_moves_list = [
                (mr.source_path, mr.target_path) 
                for mr in moved_files 
                if mr.success and mr.source_path != mr.target_path
            ]
            
            if successful_moves_list:
                try:
                    reference_warnings = self.update_internal_references(successful_moves_list)
                    warnings.extend(reference_warnings)
                except Exception as e:
                    warnings.append(f"Failed to update internal references: {str(e)}")
            
            # Calculate processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Create organization result
            result = OrganizationResult(
                moved_files=moved_files,
                successful_moves=successful_moves,
                failed_moves=failed_moves,
                conflicts_resolved=conflicts_resolved,
                total_processing_time=processing_time,
                errors=errors,
                warnings=warnings
            )
            
            # Validate result
            result_validation_errors = result.validate()
            if result_validation_errors:
                raise FileOrganizationError(f"Invalid organization result: {'; '.join(result_validation_errors)}")
            
            return result
            
        except Exception as e:
            raise FileOrganizationError(f"Failed to organize files: {str(e)}") from e
    
    def move_file_to_category(self, classified_file: ClassifiedFile, 
                             target_dir: Path, 
                             backup_session: BackupSession) -> MoveResult:
        """
        Move a single classified file to its target directory.
        
        Args:
            classified_file: File to move with classification information
            target_dir: Target directory for the file
            backup_session: Backup session for tracking the operation
            
        Returns:
            MoveResult with details of the move operation
        """
        source_path = classified_file.file_path
        
        try:
            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine target file path
            target_path = target_dir / source_path.name
            
            # Handle naming conflicts
            conflict_resolved = False
            if target_path.exists() and target_path != source_path:
                original_target = target_path
                target_path = self.resolve_naming_conflicts(source_path, target_path)
                conflict_resolved = (target_path != original_target)
            
            # Skip if source and target are the same
            if source_path.resolve() == target_path.resolve():
                return MoveResult(
                    source_path=source_path,
                    target_path=target_path,
                    success=True,
                    conflict_resolved=False
                )
            
            # Create backup before moving (if file exists)
            if source_path.exists():
                # Track the move operation
                operation = FileOperation(
                    operation_type="MOVE",
                    source_path=source_path,
                    target_path=target_path,
                    timestamp=datetime.now()
                )
                
                self.backup_manager.track_operation(backup_session.session_id, operation)
                
                # Perform the move
                shutil.move(str(source_path), str(target_path))
                
                return MoveResult(
                    source_path=source_path,
                    target_path=target_path,
                    success=True,
                    conflict_resolved=conflict_resolved
                )
            else:
                return MoveResult(
                    source_path=source_path,
                    target_path=target_path,
                    success=False,
                    error_message="Source file does not exist"
                )
        
        except Exception as e:
            return MoveResult(
                source_path=source_path,
                target_path=target_path if 'target_path' in locals() else source_path,
                success=False,
                error_message=str(e)
            )
    
    def resolve_naming_conflicts(self, source_path: Path, target_path: Path) -> Path:
        """
        Resolve naming conflicts when target file already exists.
        
        Args:
            source_path: Original source file path
            target_path: Intended target file path that conflicts
            
        Returns:
            Path: New target path that doesn't conflict
        """
        if not target_path.exists():
            return target_path
        
        # Extract file parts
        target_dir = target_path.parent
        file_stem = target_path.stem
        file_suffix = target_path.suffix
        
        # Try numbered variations
        counter = 1
        while counter <= 999:  # Reasonable limit
            new_name = f"{file_stem}_{counter:03d}{file_suffix}"
            new_target = target_dir / new_name
            
            if not new_target.exists():
                return new_target
            
            counter += 1
        
        # If we can't find a unique name, use timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_name = f"{file_stem}_{timestamp}{file_suffix}"
        return target_dir / fallback_name
    
    def _get_target_directory(self, category: str, 
                             category_mapping: Dict[str, str],
                             template: ParsedTemplate) -> Optional[Path]:
        """
        Get the target directory for a file category.
        
        Args:
            category: File category (e.g., "features", "fixes", "reference")
            category_mapping: Mapping from categories to directory paths
            template: Parsed template for fallback directory resolution
            
        Returns:
            Path to target directory or None if not found
        """
        
        # First try direct mapping
        if category in category_mapping:
            return Path(category_mapping[category])
        
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
                    return Path(fallback_path)
                
                # Check if directory exists in template structure
                if self._directory_exists_in_template(fallback_path, template):
                    return Path(fallback_path)
        
        # Final fallback - use first available directory from template
        available_dirs = template.flatten_directory_paths()
        if available_dirs:
            return Path(available_dirs[0])
        
        return None
    
    def _directory_exists_in_template(self, dir_path: str, template: ParsedTemplate) -> bool:
        """
        Check if a directory path exists in the template structure.
        
        Args:
            dir_path: Directory path to check
            template: Parsed template to search
            
        Returns:
            True if directory exists in template, False otherwise
        """
        available_dirs = template.flatten_directory_paths()
        return dir_path in available_dirs
    
    def update_internal_references(self, moved_files: List[Tuple[Path, Path]]) -> List[str]:
        """
        Update internal references in markdown files after moves.
        
        This is a basic implementation that updates relative links in markdown files
        when files have been moved to new locations.
        
        Args:
            moved_files: List of (old_path, new_path) tuples for moved files
            
        Returns:
            List of warnings about references that couldn't be updated
        """
        if not moved_files:
            return []
        
        warnings = []
        
        # Create mapping of old paths to new paths
        path_mapping = {str(old_path): str(new_path) for old_path, new_path in moved_files}
        
        # Get all markdown files that might contain references
        all_markdown_files = set()
        for old_path, new_path in moved_files:
            # Add the new file location
            if new_path.exists():
                all_markdown_files.add(new_path)
            
            # Add files in the same directory as the old location
            if old_path.parent.exists():
                for md_file in old_path.parent.glob("*.md"):
                    if md_file.exists():
                        all_markdown_files.add(md_file)
            
            # Add files in the same directory as the new location
            if new_path.parent.exists():
                for md_file in new_path.parent.glob("*.md"):
                    if md_file.exists():
                        all_markdown_files.add(md_file)
        
        # Update references in each markdown file
        for md_file in all_markdown_files:
            try:
                updated_content = self._update_file_references(md_file, path_mapping)
                if updated_content:
                    # Write the updated content back to the file
                    md_file.write_text(updated_content, encoding='utf-8')
            except Exception as e:
                warnings.append(f"Failed to update references in {md_file}: {str(e)}")
        
        return warnings
    
    def _update_file_references(self, file_path: Path, path_mapping: Dict[str, str]) -> Optional[str]:
        """
        Update references in a single markdown file.
        
        Args:
            file_path: Path to the markdown file to update
            path_mapping: Mapping of old paths to new paths
            
        Returns:
            Updated content if changes were made, None if no changes needed
        """
        try:
            content = file_path.read_text(encoding='utf-8')
            original_content = content
            
            # Update markdown links [text](path)
            import re
            
            # Pattern to match markdown links
            link_pattern = r'\[([^\]]*)\]\(([^)]+)\)'
            
            def replace_link(match):
                link_text = match.group(1)
                link_path = match.group(2)
                
                # Skip external links (http, https, mailto, etc.)
                if '://' in link_path or link_path.startswith('mailto:'):
                    return match.group(0)
                
                # Check if this path needs to be updated
                for old_path, new_path in path_mapping.items():
                    old_name = Path(old_path).name
                    new_name = Path(new_path).name
                    
                    # Simple name-based matching for relative links
                    if old_name in link_path:
                        updated_path = link_path.replace(old_name, new_name)
                        return f'[{link_text}]({updated_path})'
                
                return match.group(0)
            
            content = re.sub(link_pattern, replace_link, content)
            
            # Update simple file references (just filenames)
            for old_path, new_path in path_mapping.items():
                old_name = Path(old_path).name
                new_name = Path(new_path).name
                
                if old_name != new_name:
                    # Replace standalone filename references
                    content = re.sub(
                        r'\b' + re.escape(old_name) + r'\b',
                        new_name,
                        content
                    )
            
            # Return updated content only if changes were made
            return content if content != original_content else None
            
        except Exception:
            return None
    
    def validate_moves_completed(self, move_results: List[MoveResult]) -> Tuple[bool, List[str]]:
        """
        Validate that all file moves completed successfully.
        
        Args:
            move_results: List of move results to validate
            
        Returns:
            Tuple of (all_successful, list_of_errors)
        """
        errors = []
        all_successful = True
        
        for move_result in move_results:
            if not move_result.success:
                all_successful = False
                error_msg = f"Move failed: {move_result.source_path} -> {move_result.target_path}"
                if move_result.error_message:
                    error_msg += f" ({move_result.error_message})"
                errors.append(error_msg)
            else:
                # Verify the target file actually exists
                if not move_result.target_path.exists():
                    all_successful = False
                    errors.append(f"Target file does not exist after move: {move_result.target_path}")
                
                # Verify the source file no longer exists (unless it's the same as target)
                if (move_result.source_path != move_result.target_path and 
                    move_result.source_path.exists()):
                    all_successful = False
                    errors.append(f"Source file still exists after move: {move_result.source_path}")
        
        return all_successful, errors
    
    def rollback_failed_operations(self, backup_session: BackupSession, 
                                  failed_operations: List[MoveResult]) -> OrganizationResult:
        """
        Rollback failed file operations using backup data.
        
        Args:
            backup_session: Backup session containing operation history
            failed_operations: List of failed move results to rollback
            
        Returns:
            OrganizationResult with rollback details
        """
        if not failed_operations:
            return OrganizationResult(
                moved_files=[],
                successful_moves=0,
                failed_moves=0,
                conflicts_resolved=0
            )
        
        start_time = datetime.now()
        rollback_results = []
        successful_rollbacks = 0
        failed_rollbacks = 0
        errors = []
        warnings = []
        
        try:
            # Use backup manager to restore the session
            restore_result = self.backup_manager.restore_backup(backup_session.session_id)
            
            if restore_result.success:
                # Create move results for successful rollbacks
                for restored_file in restore_result.restored_files:
                    rollback_result = MoveResult(
                        source_path=restored_file,  # This is where it was restored to
                        target_path=restored_file,  # Same location
                        success=True,
                        conflict_resolved=False
                    )
                    rollback_results.append(rollback_result)
                    successful_rollbacks += 1
                
                # Handle failed rollbacks
                for failed_file, error_msg in restore_result.failed_files:
                    rollback_result = MoveResult(
                        source_path=failed_file,
                        target_path=failed_file,
                        success=False,
                        error_message=f"Rollback failed: {error_msg}"
                    )
                    rollback_results.append(rollback_result)
                    failed_rollbacks += 1
                    errors.append(f"Failed to rollback {failed_file}: {error_msg}")
                
                # Add restore warnings
                warnings.extend(restore_result.warnings)
                errors.extend(restore_result.errors)
            
            else:
                # Backup restore failed entirely
                errors.append("Backup restore failed completely")
                for failed_op in failed_operations:
                    rollback_result = MoveResult(
                        source_path=failed_op.source_path,
                        target_path=failed_op.target_path,
                        success=False,
                        error_message="Backup restore failed"
                    )
                    rollback_results.append(rollback_result)
                    failed_rollbacks += 1
        
        except Exception as e:
            error_msg = f"Rollback operation failed: {str(e)}"
            errors.append(error_msg)
            
            # Create failed rollback results
            for failed_op in failed_operations:
                rollback_result = MoveResult(
                    source_path=failed_op.source_path,
                    target_path=failed_op.target_path,
                    success=False,
                    error_message=error_msg
                )
                rollback_results.append(rollback_result)
                failed_rollbacks += 1
        
        # Calculate processing time
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        return OrganizationResult(
            moved_files=rollback_results,
            successful_moves=successful_rollbacks,
            failed_moves=failed_rollbacks,
            conflicts_resolved=0,  # Rollbacks don't resolve conflicts
            total_processing_time=processing_time,
            errors=errors,
            warnings=warnings
        )