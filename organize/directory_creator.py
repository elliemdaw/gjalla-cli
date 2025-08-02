"""
Directory creator for missing directory creation with backup integration.

This module provides functionality to create missing directories based on
template specifications while maintaining comprehensive backup tracking.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from .models import (
        CreationResult, BackupSession, FileOperation,
        DirectoryCreationError
    )
    from .backup_manager import BackupManager
except ImportError:
    # Fallback for standalone execution
    from requirements.models import (
        CreationResult, BackupSession, FileOperation,
        DirectoryCreationError
    )
    from organize.backup_manager import BackupManager


class DirectoryCreator:
    """
    Creates missing directories based on template specifications.
    
    This class handles:
    - Creating missing directories with proper error handling
    - Integrating with backup system for undo capabilities
    - Creating nested directory structures from templates
    - Ensuring directory existence with permission checks
    """
    
    def __init__(self, backup_manager: BackupManager):
        """
        Initialize the directory creator.
        
        Args:
            backup_manager: BackupManager instance for tracking operations
        """
        self.backup_manager = backup_manager
    
    def create_missing_directories(self, project_dir: Path, missing_dirs: List[Path], 
                                 backup_session: BackupSession) -> CreationResult:
        """
        Create missing directories with backup integration.
        
        Args:
            project_dir: Base project directory
            missing_dirs: List of missing directory paths (relative to project_dir)
            backup_session: Backup session for tracking operations
            
        Returns:
            CreationResult: Result of directory creation operations
            
        Raises:
            DirectoryCreationError: If critical directory creation fails
        """
        try:
            created_directories = []
            failed_directories = []
            errors = []
            warnings = []
            
            # Validate inputs
            if not project_dir.exists():
                raise DirectoryCreationError(f"Project directory does not exist: {project_dir}")
            
            if not project_dir.is_dir():
                raise DirectoryCreationError(f"Project path is not a directory: {project_dir}")
            
            # Sort directories by depth to create parent directories first
            sorted_dirs = sorted(missing_dirs, key=lambda p: len(p.parts))
            
            for missing_dir in sorted_dirs:
                try:
                    # Convert to absolute path
                    if missing_dir.is_absolute():
                        target_path = missing_dir
                    else:
                        target_path = project_dir / missing_dir
                    
                    # Check if directory already exists
                    if target_path.exists():
                        if target_path.is_dir():
                            warnings.append(f"Directory already exists: {target_path}")
                            continue
                        else:
                            error_msg = f"Path exists but is not a directory: {target_path}"
                            errors.append(error_msg)
                            failed_directories.append((target_path, error_msg))
                            continue
                    
                    # Create the directory
                    success = self.ensure_directory_exists(target_path)
                    
                    if success:
                        created_directories.append(target_path)
                        
                        # Track the creation operation
                        operation = FileOperation(
                            operation_type="CREATE",
                            source_path=None,
                            target_path=target_path,
                            timestamp=datetime.now()
                        )
                        self.backup_manager.track_operation(backup_session.session_id, operation)
                        
                    else:
                        error_msg = f"Failed to create directory: {target_path}"
                        errors.append(error_msg)
                        failed_directories.append((target_path, error_msg))
                
                except Exception as e:
                    error_msg = f"Error creating directory {missing_dir}: {str(e)}"
                    errors.append(error_msg)
                    failed_directories.append((missing_dir, error_msg))
            
            # Determine overall success
            success = len(failed_directories) == 0
            
            result = CreationResult(
                created_directories=created_directories,
                failed_directories=failed_directories,
                success=success,
                errors=errors,
                warnings=warnings
            )
            
            # Validate result
            validation_errors = result.validate()
            if validation_errors:
                raise DirectoryCreationError(f"Invalid creation result: {'; '.join(validation_errors)}")
            
            return result
            
        except Exception as e:
            if isinstance(e, DirectoryCreationError):
                raise
            raise DirectoryCreationError(f"Failed to create missing directories: {str(e)}") from e
    
    def create_directory_tree(self, base_dir: Path, structure: Dict[str, Any]) -> List[Path]:
        """
        Create nested directory structure from template.
        
        Args:
            base_dir: Base directory where structure should be created
            structure: Nested dictionary representing directory tree
            
        Returns:
            List[Path]: List of created directory paths
            
        Raises:
            DirectoryCreationError: If directory tree creation fails
        """
        try:
            created_paths = []
            
            def _create_recursive(current_structure: Dict[str, Any], current_path: Path):
                """Recursively create directory structure."""
                for name, content in current_structure.items():
                    if isinstance(content, dict):
                        # This is a directory
                        dir_path = current_path / name
                        
                        if self.ensure_directory_exists(dir_path):
                            created_paths.append(dir_path)
                            
                            # Recursively create subdirectories
                            _create_recursive(content, dir_path)
                        else:
                            raise DirectoryCreationError(f"Failed to create directory: {dir_path}")
                    
                    # Files (None values) are ignored in directory creation
            
            # Ensure base directory exists
            if not base_dir.exists():
                if not self.ensure_directory_exists(base_dir):
                    raise DirectoryCreationError(f"Failed to create base directory: {base_dir}")
                created_paths.append(base_dir)
            
            # Create the nested structure
            _create_recursive(structure, base_dir)
            
            return created_paths
            
        except Exception as e:
            if isinstance(e, DirectoryCreationError):
                raise
            raise DirectoryCreationError(f"Failed to create directory tree: {str(e)}") from e
    
    def ensure_directory_exists(self, directory: Path) -> bool:
        """
        Ensure directory exists with proper error handling.
        
        Args:
            directory: Path to directory that should exist
            
        Returns:
            bool: True if directory exists or was created successfully
        """
        try:
            # Check if already exists
            if directory.exists():
                return directory.is_dir()
            
            # Check parent directory permissions
            parent = directory.parent
            if parent.exists() and not os.access(parent, os.W_OK):
                return False
            
            # Create directory with parents
            directory.mkdir(parents=True, exist_ok=True)
            
            # Verify creation was successful
            return directory.exists() and directory.is_dir()
            
        except PermissionError:
            # Permission denied
            return False
        except OSError:
            # Other OS-level errors (disk full, invalid path, etc.)
            return False
        except Exception:
            # Any other unexpected errors
            return False
    
    def create_reorganization_backup(self, project_dir: Path, 
                                   operation_type: str = "directory_creation") -> BackupSession:
        """
        Create a backup session specifically for directory creation operations.
        
        Args:
            project_dir: Project directory being modified
            operation_type: Type of operation being performed
            
        Returns:
            BackupSession: Created backup session
            
        Raises:
            DirectoryCreationError: If backup creation fails
        """
        try:
            # For directory creation, we don't need to backup existing files
            # since we're only creating new directories, not modifying existing ones
            # However, we still create a session to track the operations
            
            metadata = {
                "project_dir": str(project_dir),
                "operation_type": operation_type,
                "timestamp": datetime.now().isoformat()
            }
            
            # Create backup session with empty file list
            backup_session = self.backup_manager.create_backup(
                files=[],  # No files to backup for directory creation
                operation_id=operation_type,
                metadata=metadata
            )
            
            return backup_session
            
        except Exception as e:
            raise DirectoryCreationError(f"Failed to create backup session: {str(e)}") from e
    
    def validate_directory_permissions(self, directories: List[Path]) -> Dict[Path, bool]:
        """
        Validate write permissions for directory creation.
        
        Args:
            directories: List of directories to validate
            
        Returns:
            Dict[Path, bool]: Mapping of directory paths to permission status
        """
        permissions = {}
        
        for directory in directories:
            try:
                if directory.exists():
                    # Directory exists, check if it's writable
                    permissions[directory] = os.access(directory, os.W_OK)
                else:
                    # Directory doesn't exist, check parent permissions
                    parent = directory.parent
                    if parent.exists():
                        permissions[directory] = os.access(parent, os.W_OK)
                    else:
                        # Need to check the closest existing parent
                        current = parent
                        while current and not current.exists():
                            current = current.parent
                        
                        if current:
                            permissions[directory] = os.access(current, os.W_OK)
                        else:
                            permissions[directory] = False
                            
            except Exception:
                permissions[directory] = False
        
        return permissions
    
    def get_directory_creation_plan(self, project_dir: Path, 
                                  missing_dirs: List[Path]) -> Dict[str, Any]:
        """
        Generate a plan for directory creation operations.
        
        Args:
            project_dir: Base project directory
            missing_dirs: List of missing directory paths
            
        Returns:
            Dict[str, Any]: Directory creation plan with analysis
        """
        try:
            # Sort directories by depth
            sorted_dirs = sorted(missing_dirs, key=lambda p: len(p.parts))
            
            # Convert to absolute paths
            absolute_dirs = []
            for missing_dir in sorted_dirs:
                if missing_dir.is_absolute():
                    absolute_dirs.append(missing_dir)
                else:
                    absolute_dirs.append(project_dir / missing_dir)
            
            # Check permissions
            permissions = self.validate_directory_permissions(absolute_dirs)
            
            # Analyze creation requirements
            creation_order = []
            permission_issues = []
            existing_dirs = []
            
            for dir_path in absolute_dirs:
                if dir_path.exists():
                    if dir_path.is_dir():
                        existing_dirs.append(dir_path)
                    else:
                        permission_issues.append(f"Path exists but is not a directory: {dir_path}")
                elif not permissions.get(dir_path, False):
                    permission_issues.append(f"No write permission for: {dir_path}")
                else:
                    creation_order.append(dir_path)
            
            return {
                "project_dir": str(project_dir),
                "total_directories": len(missing_dirs),
                "creation_order": [str(p) for p in creation_order],
                "existing_directories": [str(p) for p in existing_dirs],
                "permission_issues": permission_issues,
                "can_proceed": len(permission_issues) == 0,
                "estimated_operations": len(creation_order)
            }
            
        except Exception as e:
            return {
                "project_dir": str(project_dir),
                "error": f"Failed to generate creation plan: {str(e)}",
                "can_proceed": False
            }