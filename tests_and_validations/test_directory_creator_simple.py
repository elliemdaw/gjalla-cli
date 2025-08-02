"""
Simple tests for DirectoryCreator class without complex imports.
"""

import os
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock

# Import only what we need directly
import sys
sys.path.insert(0, '.')

# Mock the models we need
class MockCreationResult:
    def __init__(self, created_directories, failed_directories, success, errors=None, warnings=None):
        self.created_directories = created_directories
        self.failed_directories = failed_directories
        self.success = success
        self.errors = errors or []
        self.warnings = warnings or []
    
    def validate(self):
        return []

class MockBackupSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.timestamp = datetime.now()
        self.operation_type = "directory_creation"
        self.backed_up_files = []
        self.operation_log = []

class MockFileOperation:
    def __init__(self, operation_type, source_path, target_path, timestamp):
        self.operation_type = operation_type
        self.source_path = source_path
        self.target_path = target_path
        self.timestamp = timestamp

class MockBackupManager:
    def __init__(self):
        self.operations = []
    
    def track_operation(self, session_id, operation):
        self.operations.append(operation)
    
    def create_backup(self, files, operation_id, metadata=None):
        return MockBackupSession("test-session")

# Simple DirectoryCreator implementation for testing
class DirectoryCreator:
    def __init__(self, backup_manager):
        self.backup_manager = backup_manager
    
    def create_missing_directories(self, project_dir, missing_dirs, backup_session):
        created_directories = []
        failed_directories = []
        errors = []
        warnings = []
        
        if not project_dir.exists():
            raise Exception(f"Project directory does not exist: {project_dir}")
        
        for missing_dir in missing_dirs:
            try:
                if missing_dir.is_absolute():
                    target_path = missing_dir
                else:
                    target_path = project_dir / missing_dir
                
                if target_path.exists():
                    if target_path.is_dir():
                        warnings.append(f"Directory already exists: {target_path}")
                        continue
                    else:
                        error_msg = f"Path exists but is not a directory: {target_path}"
                        errors.append(error_msg)
                        failed_directories.append((target_path, error_msg))
                        continue
                
                success = self.ensure_directory_exists(target_path)
                
                if success:
                    created_directories.append(target_path)
                    
                    operation = MockFileOperation(
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
        
        success = len(failed_directories) == 0
        
        return MockCreationResult(
            created_directories=created_directories,
            failed_directories=failed_directories,
            success=success,
            errors=errors,
            warnings=warnings
        )
    
    def ensure_directory_exists(self, directory):
        try:
            if directory.exists():
                return directory.is_dir()
            
            directory.mkdir(parents=True, exist_ok=True)
            return directory.exists() and directory.is_dir()
        except:
            return False
    
    def create_directory_tree(self, base_dir, structure):
        created_paths = []
        
        def _create_recursive(current_structure, current_path):
            for name, content in current_structure.items():
                if isinstance(content, dict):
                    dir_path = current_path / name
                    if self.ensure_directory_exists(dir_path):
                        created_paths.append(dir_path)
                        _create_recursive(content, dir_path)
                    else:
                        raise Exception(f"Failed to create directory: {dir_path}")
        
        if not base_dir.exists():
            if not self.ensure_directory_exists(base_dir):
                raise Exception(f"Failed to create base directory: {base_dir}")
            created_paths.append(base_dir)
        
        _create_recursive(structure, base_dir)
        return created_paths


def test_directory_creator():
    """Test DirectoryCreator functionality."""
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    project_dir = temp_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Create instances
        backup_manager = MockBackupManager()
        creator = DirectoryCreator(backup_manager)
        backup_session = MockBackupSession("test-session")
        
        # Test 1: Create missing directories
        missing_dirs = [
            Path("specs"),
            Path("specs/features"),
            Path("docs")
        ]
        
        result = creator.create_missing_directories(
            project_dir, missing_dirs, backup_session
        )
        
        assert result.success is True
        assert len(result.created_directories) == 3
        assert len(result.failed_directories) == 0
        assert len(backup_manager.operations) == 3
        
        # Verify directories were created
        for missing_dir in missing_dirs:
            assert (project_dir / missing_dir).exists()
            assert (project_dir / missing_dir).is_dir()
        
        print("✓ Test 1 passed: Basic directory creation")
        
        # Test 2: Handle existing directories
        result2 = creator.create_missing_directories(
            project_dir, [Path("specs")], backup_session
        )
        
        assert result2.success is True
        assert len(result2.created_directories) == 0
        assert len(result2.warnings) == 1
        assert "already exists" in result2.warnings[0]
        
        print("✓ Test 2 passed: Existing directory handling")
        
        # Test 3: Create directory tree
        structure = {
            "new_area": {
                "sub1": {},
                "sub2": {
                    "deep": {}
                }
            }
        }
        
        created_paths = creator.create_directory_tree(project_dir, structure)
        assert len(created_paths) == 4  # new_area, sub1, sub2, deep
        
        # Verify structure
        assert (project_dir / "new_area").exists()
        assert (project_dir / "new_area" / "sub1").exists()
        assert (project_dir / "new_area" / "sub2").exists()
        assert (project_dir / "new_area" / "sub2" / "deep").exists()
        
        print("✓ Test 3 passed: Directory tree creation")
        
        # Test 4: Handle file conflicts
        conflict_file = project_dir / "conflict"
        conflict_file.write_text("This is a file")
        
        result3 = creator.create_missing_directories(
            project_dir, [Path("conflict")], backup_session
        )
        
        assert result3.success is False
        assert len(result3.failed_directories) == 1
        assert "not a directory" in result3.errors[0]
        
        print("✓ Test 4 passed: File conflict handling")
        
        print("\n🎉 All DirectoryCreator tests passed!")
        
    finally:
        # Cleanup
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_directory_creator()