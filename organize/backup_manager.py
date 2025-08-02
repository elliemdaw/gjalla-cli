"""
Backup manager for comprehensive undo functionality.

This module provides backup creation and session management capabilities
to support undo operations for all onboarding file modifications.
"""

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

try:
    from .models import (
        BackupSession, BackedUpFile, FileOperation, RestoreResult,
        BackupError, RestoreError
    )
except ImportError:
    # Fallback for standalone execution
    from requirements.models import (
        BackupSession, BackedUpFile, FileOperation, RestoreResult,
        BackupError, RestoreError
    )


class BackupManager:
    """
    Manages backup creation and restoration for comprehensive undo functionality.
    
    This class handles:
    - Creating backup sessions with file snapshots
    - Tracking file operations for restoration
    - Restoring files from backup sessions
    - Managing backup storage and cleanup
    """
    
    def __init__(self, backup_dir: Path):
        """
        Initialize the backup manager.
        
        Args:
            backup_dir: Directory where backups will be stored
        """
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for organization
        self.sessions_dir = self.backup_dir / "sessions"
        self.files_dir = self.backup_dir / "files"
        self.metadata_dir = self.backup_dir / "metadata"
        
        for directory in [self.sessions_dir, self.files_dir, self.metadata_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, files: List[Path], operation_id: str, 
                     metadata: Optional[Dict[str, Any]] = None) -> BackupSession:
        """
        Create a backup session for the specified files.
        
        Args:
            files: List of file paths to backup
            operation_id: Identifier for the operation being backed up
            metadata: Optional metadata to store with the session
            
        Returns:
            BackupSession: Information about the created backup session
            
        Raises:
            BackupError: If backup creation fails
        """
        try:
            session_id = str(uuid.uuid4())
            timestamp = datetime.now()
            backed_up_files = []
            
            # Create session directory
            session_dir = self.sessions_dir / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup each file
            for file_path in files:
                if file_path.exists() and file_path.is_file():
                    backed_up_file = self._backup_single_file(
                        file_path, session_id, timestamp
                    )
                    backed_up_files.append(backed_up_file)
            
            # Create backup session
            session = BackupSession(
                session_id=session_id,
                timestamp=timestamp,
                operation_type=operation_id,
                backed_up_files=backed_up_files,
                operation_log=[],  # Will be populated by track_operation
                metadata=metadata or {}
            )
            
            # Validate session
            validation_errors = session.validate()
            if validation_errors:
                raise BackupError(f"Invalid backup session: {'; '.join(validation_errors)}")
            
            # Save session metadata
            self._save_session_metadata(session)
            
            return session
            
        except Exception as e:
            raise BackupError(f"Failed to create backup: {str(e)}") from e
    
    def track_operation(self, session_id: str, operation: FileOperation) -> None:
        """
        Track a file operation in the specified backup session.
        
        Args:
            session_id: ID of the backup session
            operation: File operation to track
            
        Raises:
            BackupError: If operation tracking fails
        """
        try:
            # Validate operation
            validation_errors = operation.validate()
            if validation_errors:
                raise BackupError(f"Invalid operation: {'; '.join(validation_errors)}")
            
            # Load existing session
            session = self._load_session_metadata(session_id)
            if not session:
                raise BackupError(f"Backup session not found: {session_id}")
            
            # Add operation to log
            session.operation_log.append(operation)
            
            # Save updated session
            self._save_session_metadata(session)
            
        except Exception as e:
            raise BackupError(f"Failed to track operation: {str(e)}") from e
    
    def restore_backup(self, session_id: str) -> RestoreResult:
        """
        Restore files from a backup session.
        
        Args:
            session_id: ID of the backup session to restore
            
        Returns:
            RestoreResult: Result of the restore operation
            
        Raises:
            RestoreError: If restore operation fails
        """
        try:
            # Load session metadata
            session = self._load_session_metadata(session_id)
            if not session:
                raise RestoreError(f"Backup session not found: {session_id}")
            
            restored_files = []
            failed_files = []
            validation_results = {}
            errors = []
            warnings = []
            
            # Restore files in reverse order of operations
            for operation in reversed(session.operation_log):
                try:
                    self._restore_operation(operation, restored_files, failed_files)
                except Exception as e:
                    error_msg = f"Failed to restore operation {operation.operation_type}: {str(e)}"
                    errors.append(error_msg)
                    if operation.target_path:
                        failed_files.append((operation.target_path, error_msg))
            
            # Restore backed up files
            for backed_up_file in session.backed_up_files:
                try:
                    success, is_valid = self._restore_backed_up_file(backed_up_file)
                    if success:
                        restored_files.append(backed_up_file.original_path)
                        validation_results[backed_up_file.original_path] = is_valid
                        if not is_valid:
                            warnings.append(f"Checksum validation failed for {backed_up_file.original_path}")
                    else:
                        failed_files.append((
                            backed_up_file.original_path,
                            "Failed to restore file"
                        ))
                except Exception as e:
                    error_msg = f"Failed to restore {backed_up_file.original_path}: {str(e)}"
                    errors.append(error_msg)
                    failed_files.append((backed_up_file.original_path, error_msg))
            
            return RestoreResult(
                session_id=session_id,
                success=len(failed_files) == 0,
                restored_files=restored_files,
                failed_files=failed_files,
                validation_results=validation_results,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            raise RestoreError(f"Failed to restore backup: {str(e)}") from e
    
    def restore_most_recent_backup(self, dry_run: bool = False) -> RestoreResult:
        """
        Restore the most recent backup session.
        
        Args:
            dry_run: If True, preview the restore without making changes
            
        Returns:
            RestoreResult with operation details
            
        Raises:
            RestoreError: If no backup sessions exist or restore fails
        """
        sessions = self.list_backup_sessions()
        if not sessions:
            raise RestoreError("No backup sessions found")
        
        # Get the most recent session (sessions are sorted by timestamp descending)
        most_recent_session = sessions[0]
        
        if dry_run:
            # For dry run, return preview information
            return RestoreResult(
                session_id=most_recent_session.session_id,
                success=True,
                restored_files=[],
                failed_files=[],
                validation_results={},
                errors=[]
            )
        else:
            # Perform actual restore
            return self.restore_backup(most_recent_session.session_id)
    
    def restore_specific_session(self, session_id: str, dry_run: bool = False) -> RestoreResult:
        """
        Restore a specific backup session.
        
        Args:
            session_id: ID of the session to restore
            dry_run: If True, preview the restore without making changes
            
        Returns:
            RestoreResult with operation details
            
        Raises:
            RestoreError: If session not found or restore fails
        """
        if dry_run:
            # Load session metadata for preview
            session = self._load_session_metadata(session_id)
            if not session:
                raise RestoreError(f"Backup session '{session_id}' not found")
            
            return RestoreResult(
                session_id=session.session_id,
                success=True,
                restored_files=[],
                failed_files=[],
                validation_results={},
                errors=[]
            )
        else:
            # Perform actual restore
            return self.restore_backup(session_id)
    
    def list_backup_sessions(self) -> List[BackupSession]:
        """
        List all available backup sessions.
        
        Returns:
            List[BackupSession]: List of all backup sessions
        """
        sessions = []
        
        try:
            for session_file in self.metadata_dir.glob("*.json"):
                try:
                    session = self._load_session_metadata(session_file.stem)
                    if session:
                        sessions.append(session)
                except Exception:
                    # Skip corrupted session files
                    continue
            
            # Sort by timestamp (newest first)
            sessions.sort(key=lambda s: s.timestamp, reverse=True)
            
        except Exception:
            # Return empty list if directory doesn't exist or other errors
            pass
        
        return sessions
    
    def restore_selective(self, session_id: str, file_paths: List[Path]) -> RestoreResult:
        """
        Restore only specific files from a backup session.
        
        Args:
            session_id: ID of the backup session to restore
            file_paths: List of specific file paths to restore
            
        Returns:
            RestoreResult: Result of the selective restore operation
            
        Raises:
            RestoreError: If restore operation fails
        """
        try:
            # Load session metadata
            session = self._load_session_metadata(session_id)
            if not session:
                raise RestoreError(f"Backup session not found: {session_id}")
            
            restored_files = []
            failed_files = []
            validation_results = {}
            errors = []
            warnings = []
            
            # Filter backed up files to only those requested
            files_to_restore = [
                bf for bf in session.backed_up_files 
                if bf.original_path in file_paths
            ]
            
            if not files_to_restore:
                warnings.append("No matching files found in backup session")
            
            # Restore only the requested backed up files
            for backed_up_file in files_to_restore:
                try:
                    success, is_valid = self._restore_backed_up_file(backed_up_file)
                    if success:
                        restored_files.append(backed_up_file.original_path)
                        validation_results[backed_up_file.original_path] = is_valid
                        if not is_valid:
                            warnings.append(f"Checksum validation failed for {backed_up_file.original_path}")
                    else:
                        failed_files.append((
                            backed_up_file.original_path,
                            "Failed to restore file"
                        ))
                except Exception as e:
                    error_msg = f"Failed to restore {backed_up_file.original_path}: {str(e)}"
                    errors.append(error_msg)
                    failed_files.append((backed_up_file.original_path, error_msg))
            
            # Also restore operations that affect the requested files
            relevant_operations = [
                op for op in reversed(session.operation_log)
                if (op.source_path in file_paths if op.source_path else False) or
                   (op.target_path in file_paths if op.target_path else False)
            ]
            
            for operation in relevant_operations:
                try:
                    self._restore_operation(operation, restored_files, failed_files)
                except Exception as e:
                    error_msg = f"Failed to restore operation {operation.operation_type}: {str(e)}"
                    errors.append(error_msg)
                    if operation.target_path:
                        failed_files.append((operation.target_path, error_msg))
            
            return RestoreResult(
                session_id=session_id,
                success=len(failed_files) == 0,
                restored_files=restored_files,
                failed_files=failed_files,
                validation_results=validation_results,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            raise RestoreError(f"Failed to restore backup selectively: {str(e)}") from e
    
    def validate_backup_integrity(self, session_id: str) -> Dict[Path, bool]:
        """
        Validate the integrity of backed up files by checking checksums.
        
        Args:
            session_id: ID of the backup session to validate
            
        Returns:
            Dict[Path, bool]: Mapping of file paths to validation results
            
        Raises:
            BackupError: If validation fails
        """
        try:
            # Load session metadata
            session = self._load_session_metadata(session_id)
            if not session:
                raise BackupError(f"Backup session not found: {session_id}")
            
            validation_results = {}
            
            for backed_up_file in session.backed_up_files:
                try:
                    if backed_up_file.backup_path.exists():
                        current_checksum = self._calculate_checksum(backed_up_file.backup_path)
                        validation_results[backed_up_file.original_path] = (
                            current_checksum == backed_up_file.checksum
                        )
                    else:
                        validation_results[backed_up_file.original_path] = False
                except Exception:
                    validation_results[backed_up_file.original_path] = False
            
            return validation_results
            
        except Exception as e:
            raise BackupError(f"Failed to validate backup integrity: {str(e)}") from e
    
    def undo_operation(self, session_id: str, operation_index: int) -> RestoreResult:
        """
        Undo a specific operation from a backup session.
        
        Args:
            session_id: ID of the backup session
            operation_index: Index of the operation to undo (0-based)
            
        Returns:
            RestoreResult: Result of the undo operation
            
        Raises:
            RestoreError: If undo operation fails
        """
        try:
            # Load session metadata
            session = self._load_session_metadata(session_id)
            if not session:
                raise RestoreError(f"Backup session not found: {session_id}")
            
            if operation_index < 0 or operation_index >= len(session.operation_log):
                raise RestoreError(f"Invalid operation index: {operation_index}")
            
            operation = session.operation_log[operation_index]
            restored_files = []
            failed_files = []
            errors = []
            warnings = []
            
            try:
                self._restore_operation(operation, restored_files, failed_files)
            except Exception as e:
                error_msg = f"Failed to undo operation {operation.operation_type}: {str(e)}"
                errors.append(error_msg)
                if operation.target_path:
                    failed_files.append((operation.target_path, error_msg))
            
            return RestoreResult(
                session_id=session_id,
                success=len(failed_files) == 0,
                restored_files=restored_files,
                failed_files=failed_files,
                validation_results={},  # No checksum validation for single operations
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            raise RestoreError(f"Failed to undo operation: {str(e)}") from e
    
    def get_backup_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a backup session.
        
        Args:
            session_id: ID of the backup session
            
        Returns:
            Optional[Dict[str, Any]]: Backup session information or None if not found
        """
        try:
            session = self._load_session_metadata(session_id)
            if not session:
                return None
            
            # Calculate total backup size
            total_size = sum(bf.file_size for bf in session.backed_up_files)
            
            # Check backup file integrity
            integrity_results = self.validate_backup_integrity(session_id)
            valid_files = sum(1 for is_valid in integrity_results.values() if is_valid)
            
            return {
                "session_id": session.session_id,
                "timestamp": session.timestamp.isoformat(),
                "operation_type": session.operation_type,
                "total_files": len(session.backed_up_files),
                "total_size_bytes": total_size,
                "total_operations": len(session.operation_log),
                "integrity_valid_files": valid_files,
                "integrity_total_files": len(integrity_results),
                "metadata": session.metadata,
                "files": [
                    {
                        "original_path": str(bf.original_path),
                        "backup_path": str(bf.backup_path),
                        "size_bytes": bf.file_size,
                        "checksum": bf.checksum,
                        "backup_timestamp": bf.backup_timestamp.isoformat(),
                        "integrity_valid": integrity_results.get(bf.original_path, False)
                    }
                    for bf in session.backed_up_files
                ],
                "operations": [
                    {
                        "operation_type": op.operation_type,
                        "source_path": str(op.source_path) if op.source_path else None,
                        "target_path": str(op.target_path) if op.target_path else None,
                        "timestamp": op.timestamp.isoformat(),
                        "checksum_before": op.checksum_before,
                        "checksum_after": op.checksum_after
                    }
                    for op in session.operation_log
                ]
            }
            
        except Exception:
            return None
    
    def cleanup_old_backups(self, max_age_days: int = 30) -> int:
        """
        Clean up backup sessions older than the specified age.
        
        Args:
            max_age_days: Maximum age of backups to keep (in days)
            
        Returns:
            int: Number of sessions cleaned up
        """
        if max_age_days <= 0:
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        cleaned_count = 0
        
        try:
            sessions = self.list_backup_sessions()
            
            for session in sessions:
                if session.timestamp < cutoff_date:
                    try:
                        self._delete_session(session.session_id)
                        cleaned_count += 1
                    except Exception:
                        # Continue with other sessions if one fails
                        continue
                        
        except Exception:
            # Return count of what was cleaned up so far
            pass
        
        return cleaned_count
    
    # Reorganization-specific methods
    
    def create_reorganization_backup(self, project_dir: Path, files_to_backup: List[Path], 
                                   operation_type: str = "name_only_reorganization",
                                   metadata: Optional[Dict[str, Any]] = None) -> BackupSession:
        """
        Create a backup session specifically for reorganization operations.
        
        Args:
            project_dir: Root directory of the project being reorganized
            files_to_backup: List of files that will be affected by reorganization
            operation_type: Type of reorganization operation
            metadata: Optional metadata about the reorganization
            
        Returns:
            BackupSession: Information about the created backup session
            
        Raises:
            BackupError: If backup creation fails
        """
        try:
            # Enhance metadata with reorganization-specific information
            reorg_metadata = {
                "project_dir": str(project_dir),
                "reorganization_type": operation_type,
                "total_files_to_process": len(files_to_backup),
                "backup_created_for": "reorganization",
                **(metadata or {})
            }
            
            # Filter to only existing files
            existing_files = [f for f in files_to_backup if f.exists() and f.is_file()]
            
            if not existing_files:
                # Create empty session for tracking operations even if no files to backup
                session_id = str(uuid.uuid4())
                timestamp = datetime.now()
                
                session = BackupSession(
                    session_id=session_id,
                    timestamp=timestamp,
                    operation_type=operation_type,
                    backed_up_files=[],
                    operation_log=[],
                    metadata=reorg_metadata
                )
                
                self._save_session_metadata(session)
                return session
            
            # Create backup using existing method
            session = self.create_backup(existing_files, operation_type, reorg_metadata)
            
            return session
            
        except Exception as e:
            raise BackupError(f"Failed to create reorganization backup: {str(e)}") from e
    
    def backup_file_before_move(self, file_path: Path, backup_session: BackupSession) -> BackedUpFile:
        """
        Backup a single file before it's moved during reorganization.
        
        Args:
            file_path: Path to the file to backup
            backup_session: Active backup session to add the file to
            
        Returns:
            BackedUpFile: Information about the backed up file
            
        Raises:
            BackupError: If backup operation fails
        """
        try:
            if not file_path.exists() or not file_path.is_file():
                raise BackupError(f"File does not exist or is not a file: {file_path}")
            
            # Create backed up file record
            backed_up_file = self._backup_single_file(
                file_path, 
                backup_session.session_id, 
                datetime.now()
            )
            
            # Add to session's backed up files
            backup_session.backed_up_files.append(backed_up_file)
            
            # Save updated session metadata
            self._save_session_metadata(backup_session)
            
            return backed_up_file
            
        except Exception as e:
            raise BackupError(f"Failed to backup file before move: {str(e)}") from e
    
    def restore_reorganization(self, session_id: str) -> RestoreResult:
        """
        Restore files from a reorganization backup session with enhanced validation.
        
        Args:
            session_id: ID of the reorganization backup session to restore
            
        Returns:
            RestoreResult: Result of the restore operation with reorganization-specific details
            
        Raises:
            RestoreError: If restore operation fails
        """
        try:
            # Load session metadata
            session = self._load_session_metadata(session_id)
            if not session:
                raise RestoreError(f"Reorganization backup session not found: {session_id}")
            
            # Verify this is a reorganization backup
            if not session.metadata.get("backup_created_for") == "reorganization":
                raise RestoreError(f"Session {session_id} is not a reorganization backup")
            
            restored_files = []
            restored_directories = []
            failed_files = []
            validation_results = {}
            errors = []
            warnings = []
            
            # First, restore file operations in reverse order (undo moves, renames, etc.)
            # Separate CREATE operations (directories) to handle them last
            non_create_operations = []
            create_operations = []
            
            for operation in reversed(session.operation_log):
                if operation.operation_type == "CREATE":
                    create_operations.append(operation)
                else:
                    non_create_operations.append(operation)
            
            # First handle non-CREATE operations (moves, renames, etc.)
            for operation in non_create_operations:
                try:
                    self._restore_reorganization_operation(operation, restored_files, failed_files, restored_directories)
                except Exception as e:
                    error_msg = f"Failed to restore reorganization operation {operation.operation_type}: {str(e)}"
                    errors.append(error_msg)
                    if operation.target_path:
                        failed_files.append((operation.target_path, error_msg))
            
            # Then handle CREATE operations (directories) in reverse order of depth
            # Sort by depth (deepest first) to remove empty directories
            create_operations.sort(key=lambda op: len(op.target_path.parts) if op.target_path else 0, reverse=True)
            
            for operation in create_operations:
                try:
                    self._restore_reorganization_operation(operation, restored_files, failed_files, restored_directories)
                except Exception as e:
                    error_msg = f"Failed to restore reorganization operation {operation.operation_type}: {str(e)}"
                    errors.append(error_msg)
                    if operation.target_path:
                        failed_files.append((operation.target_path, error_msg))
            
            # Then, restore backed up files to their original locations
            # But only if they weren't already restored by operation undoing
            for backed_up_file in session.backed_up_files:
                # Skip files that were already restored by undoing operations
                if backed_up_file.original_path in restored_files:
                    continue
                    
                try:
                    success, is_valid = self._restore_backed_up_file(backed_up_file)
                    if success:
                        restored_files.append(backed_up_file.original_path)
                        validation_results[backed_up_file.original_path] = is_valid
                        if not is_valid:
                            warnings.append(f"Checksum validation failed for {backed_up_file.original_path}")
                    else:
                        failed_files.append((
                            backed_up_file.original_path,
                            "Failed to restore file from backup"
                        ))
                except Exception as e:
                    error_msg = f"Failed to restore {backed_up_file.original_path}: {str(e)}"
                    errors.append(error_msg)
                    failed_files.append((backed_up_file.original_path, error_msg))
            
            # Add reorganization-specific validation
            project_dir = session.metadata.get("project_dir")
            if project_dir:
                warnings.append(f"Reorganization restored for project: {project_dir}")
            
            total_files_processed = session.metadata.get("total_files_to_process", 0)
            if total_files_processed > 0:
                warnings.append(f"Original reorganization processed {total_files_processed} files")
            
            return RestoreResult(
                session_id=session_id,
                success=len(failed_files) == 0,
                restored_files=restored_files,
                failed_files=failed_files,
                validation_results=validation_results,
                errors=errors,
                warnings=warnings,
                restored_directories=restored_directories
            )
            
        except Exception as e:
            raise RestoreError(f"Failed to restore reorganization: {str(e)}") from e
    
    def validate_reorganization_backup_integrity(self, session_id: str) -> Dict[str, Any]:
        """
        Validate the integrity of a reorganization backup with enhanced checks.
        
        Args:
            session_id: ID of the reorganization backup session to validate
            
        Returns:
            Dict[str, Any]: Comprehensive validation results
            
        Raises:
            BackupError: If validation fails
        """
        try:
            # Load session metadata
            session = self._load_session_metadata(session_id)
            if not session:
                raise BackupError(f"Reorganization backup session not found: {session_id}")
            
            # Verify this is a reorganization backup
            if not session.metadata.get("backup_created_for") == "reorganization":
                raise BackupError(f"Session {session_id} is not a reorganization backup")
            
            # Basic integrity validation
            file_integrity = self.validate_backup_integrity(session_id)
            
            # Enhanced reorganization-specific validation
            validation_result = {
                "session_id": session_id,
                "is_reorganization_backup": True,
                "reorganization_type": session.metadata.get("reorganization_type", "unknown"),
                "project_dir": session.metadata.get("project_dir"),
                "backup_timestamp": session.timestamp.isoformat(),
                "total_backed_up_files": len(session.backed_up_files),
                "total_operations": len(session.operation_log),
                "file_integrity_results": {str(path): valid for path, valid in file_integrity.items()},
                "files_with_valid_checksums": sum(1 for valid in file_integrity.values() if valid),
                "files_with_invalid_checksums": sum(1 for valid in file_integrity.values() if not valid),
                "missing_backup_files": [],
                "operation_types": {},
                "validation_errors": [],
                "validation_warnings": []
            }
            
            # Check for missing backup files
            for backed_up_file in session.backed_up_files:
                if not backed_up_file.backup_path.exists():
                    validation_result["missing_backup_files"].append(str(backed_up_file.backup_path))
                    validation_result["validation_errors"].append(
                        f"Backup file missing: {backed_up_file.backup_path}"
                    )
            
            # Analyze operation types
            for operation in session.operation_log:
                op_type = operation.operation_type
                validation_result["operation_types"][op_type] = validation_result["operation_types"].get(op_type, 0) + 1
            
            # Check for potential issues
            if validation_result["files_with_invalid_checksums"] > 0:
                validation_result["validation_warnings"].append(
                    f"{validation_result['files_with_invalid_checksums']} files have invalid checksums"
                )
            
            if len(validation_result["missing_backup_files"]) > 0:
                validation_result["validation_errors"].append(
                    f"{len(validation_result['missing_backup_files'])} backup files are missing"
                )
            
            # Overall validation status
            validation_result["is_valid"] = (
                len(validation_result["validation_errors"]) == 0 and
                validation_result["files_with_invalid_checksums"] == 0
            )
            
            return validation_result
            
        except Exception as e:
            raise BackupError(f"Failed to validate reorganization backup integrity: {str(e)}") from e
    
    def _backup_single_file(self, file_path: Path, session_id: str, 
                           timestamp: datetime) -> BackedUpFile:
        """
        Backup a single file.
        
        Args:
            file_path: Path to the file to backup
            session_id: ID of the backup session
            timestamp: Timestamp of the backup
            
        Returns:
            BackedUpFile: Information about the backed up file
        """
        # Calculate checksum
        checksum = self._calculate_checksum(file_path)
        
        # Create backup file path
        backup_filename = f"{checksum}_{file_path.name}"
        backup_path = self.files_dir / backup_filename
        
        # Copy file to backup location (only if not already exists)
        if not backup_path.exists():
            shutil.copy2(file_path, backup_path)
        
        return BackedUpFile(
            original_path=file_path,
            backup_path=backup_path,
            checksum=checksum,
            file_size=file_path.stat().st_size,
            backup_timestamp=timestamp
        )
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """
        Calculate SHA-256 checksum of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Hexadecimal checksum
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def _save_session_metadata(self, session: BackupSession) -> None:
        """
        Save session metadata to disk.
        
        Args:
            session: Backup session to save
        """
        metadata_file = self.metadata_dir / f"{session.session_id}.json"
        
        # Convert session to dictionary for JSON serialization
        session_dict = {
            "session_id": session.session_id,
            "timestamp": session.timestamp.isoformat(),
            "operation_type": session.operation_type,
            "backed_up_files": [
                {
                    "original_path": str(bf.original_path),
                    "backup_path": str(bf.backup_path),
                    "checksum": bf.checksum,
                    "file_size": bf.file_size,
                    "backup_timestamp": bf.backup_timestamp.isoformat()
                }
                for bf in session.backed_up_files
            ],
            "operation_log": [
                {
                    "operation_type": op.operation_type,
                    "source_path": str(op.source_path) if op.source_path else None,
                    "target_path": str(op.target_path) if op.target_path else None,
                    "timestamp": op.timestamp.isoformat(),
                    "checksum_before": op.checksum_before,
                    "checksum_after": op.checksum_after
                }
                for op in session.operation_log
            ],
            "metadata": session.metadata
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(session_dict, f, indent=2)
    
    def _load_session_metadata(self, session_id: str) -> Optional[BackupSession]:
        """
        Load session metadata from disk.
        
        Args:
            session_id: ID of the session to load
            
        Returns:
            Optional[BackupSession]: Loaded session or None if not found
        """
        metadata_file = self.metadata_dir / f"{session_id}.json"
        
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r') as f:
                session_dict = json.load(f)
            
            # Convert dictionary back to BackupSession
            backed_up_files = [
                BackedUpFile(
                    original_path=Path(bf["original_path"]),
                    backup_path=Path(bf["backup_path"]),
                    checksum=bf["checksum"],
                    file_size=bf["file_size"],
                    backup_timestamp=datetime.fromisoformat(bf["backup_timestamp"])
                )
                for bf in session_dict["backed_up_files"]
            ]
            
            operation_log = [
                FileOperation(
                    operation_type=op["operation_type"],
                    source_path=Path(op["source_path"]) if op["source_path"] else None,
                    target_path=Path(op["target_path"]) if op["target_path"] else None,
                    timestamp=datetime.fromisoformat(op["timestamp"]),
                    checksum_before=op.get("checksum_before"),
                    checksum_after=op.get("checksum_after")
                )
                for op in session_dict["operation_log"]
            ]
            
            return BackupSession(
                session_id=session_dict["session_id"],
                timestamp=datetime.fromisoformat(session_dict["timestamp"]),
                operation_type=session_dict["operation_type"],
                backed_up_files=backed_up_files,
                operation_log=operation_log,
                metadata=session_dict.get("metadata", {})
            )
            
        except Exception:
            return None
    
    def _restore_operation(self, operation: FileOperation, 
                          restored_files: List[Path], 
                          failed_files: List[Tuple[Path, str]],
                          restored_directories: List[Path] = None) -> None:
        """
        Restore a single file operation.
        
        Args:
            operation: File operation to restore
            restored_files: List to append successfully restored files
            failed_files: List to append failed files with error messages
            restored_directories: Optional list to track restored directories
        """
        if operation.operation_type == "CREATE":
            # Remove created file or directory
            if operation.target_path and operation.target_path.exists():
                if operation.target_path.is_file():
                    operation.target_path.unlink()
                    restored_files.append(operation.target_path)
                elif operation.target_path.is_dir():
                    # Only remove if empty (reorganization shouldn't create non-empty dirs)
                    try:
                        operation.target_path.rmdir()
                        if restored_directories is not None:
                            restored_directories.append(operation.target_path)
                    except OSError:
                        # Directory not empty, leave it
                        pass
        
        elif operation.operation_type == "DELETE":
            # Cannot restore deleted files without backup
            # This should be handled by backed_up_files restoration
            pass
        
        elif operation.operation_type == "MOVE":
            # Move file back to original location
            if (operation.target_path and operation.source_path and 
                operation.target_path.exists()):
                operation.target_path.rename(operation.source_path)
                restored_files.append(operation.source_path)
        
        elif operation.operation_type == "RENAME":
            # Rename file back to original name
            if (operation.target_path and operation.source_path and 
                operation.target_path.exists()):
                operation.target_path.rename(operation.source_path)
                restored_files.append(operation.source_path)
    
    def _restore_reorganization_operation(self, operation: FileOperation, 
                                        restored_files: List[Path], 
                                        failed_files: List[Tuple[Path, str]],
                                        restored_directories: List[Path] = None) -> None:
        """
        Restore a single reorganization operation with enhanced error handling.
        
        Args:
            operation: File operation to restore
            restored_files: List to append successfully restored files
            failed_files: List to append failed files with error messages
        """
        try:
            if operation.operation_type == "CREATE":
                # Remove created file or directory
                if operation.target_path and operation.target_path.exists():
                    if operation.target_path.is_file():
                        operation.target_path.unlink()
                        restored_files.append(operation.target_path)
                    elif operation.target_path.is_dir():
                        # Only remove if empty (reorganization shouldn't create non-empty dirs)
                        try:
                            operation.target_path.rmdir()
                            if restored_directories is not None:
                                restored_directories.append(operation.target_path)
                        except OSError:
                            # Directory not empty, leave it
                            pass
            
            elif operation.operation_type == "DELETE":
                # Cannot restore deleted files without backup
                # This should be handled by backed_up_files restoration
                pass
            
            elif operation.operation_type == "MOVE":
                # Move file back to original location
                if (operation.target_path and operation.source_path and 
                    operation.target_path.exists()):
                    
                    # Ensure source directory exists
                    operation.source_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Handle potential conflicts at source location
                    if operation.source_path.exists():
                        # Create backup name for conflicting file
                        conflict_backup = operation.source_path.with_suffix(
                            f".conflict_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{operation.source_path.suffix}"
                        )
                        operation.source_path.rename(conflict_backup)
                    
                    operation.target_path.rename(operation.source_path)
                    restored_files.append(operation.source_path)
            
            elif operation.operation_type == "RENAME":
                # Rename file back to original name
                if (operation.target_path and operation.source_path and 
                    operation.target_path.exists()):
                    
                    # Handle potential conflicts at source location
                    if operation.source_path.exists():
                        # Create backup name for conflicting file
                        conflict_backup = operation.source_path.with_suffix(
                            f".conflict_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{operation.source_path.suffix}"
                        )
                        operation.source_path.rename(conflict_backup)
                    
                    operation.target_path.rename(operation.source_path)
                    restored_files.append(operation.source_path)
            
            elif operation.operation_type == "MODIFY":
                # For modifications, the backed up file should be restored
                # This operation type is mainly for tracking
                pass
                
        except Exception as e:
            error_msg = f"Failed to restore {operation.operation_type} operation: {str(e)}"
            if operation.target_path:
                failed_files.append((operation.target_path, error_msg))
            elif operation.source_path:
                failed_files.append((operation.source_path, error_msg))
    
    def _restore_backed_up_file(self, backed_up_file: BackedUpFile) -> Tuple[bool, bool]:
        """
        Restore a single backed up file.
        
        Args:
            backed_up_file: Information about the backed up file
            
        Returns:
            Tuple[bool, bool]: (success, checksum_valid)
        """
        try:
            # Ensure parent directory exists
            backed_up_file.original_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file back to original location
            shutil.copy2(backed_up_file.backup_path, backed_up_file.original_path)
            
            # Validate checksum
            current_checksum = self._calculate_checksum(backed_up_file.original_path)
            checksum_valid = current_checksum == backed_up_file.checksum
            
            return True, checksum_valid
            
        except Exception:
            return False, False
    
    def _delete_session(self, session_id: str) -> None:
        """
        Delete a backup session and its associated files.
        
        Args:
            session_id: ID of the session to delete
        """
        # Load session to get file references
        session = self._load_session_metadata(session_id)
        
        # Delete session directory if it exists
        session_dir = self.sessions_dir / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)
        
        # Delete metadata file
        metadata_file = self.metadata_dir / f"{session_id}.json"
        if metadata_file.exists():
            metadata_file.unlink()
        
        # Note: We don't delete backup files from files_dir as they might be
        # referenced by other sessions (same checksum = same file content)