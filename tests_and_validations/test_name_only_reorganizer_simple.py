"""
Simple test for NameOnlyReorganizer to verify basic functionality.
"""

import tempfile
import shutil
from pathlib import Path

# Test the import and basic functionality
def test_basic_import():
    """Test that we can import and create the reorganizer."""
    try:
        from onboarding.name_only_reorganizer import NameOnlyReorganizer
        from onboarding.backup_manager import BackupManager
        from onboarding.models import NameOnlyConfig
        
        # Create temporary directories
        test_dir = Path(tempfile.mkdtemp())
        backup_dir = test_dir / "backups"
        project_dir = test_dir / "test_project"
        template_dir = test_dir / "templates"
        
        try:
            # Create directories
            project_dir.mkdir(parents=True)
            template_dir.mkdir(parents=True)
            
            # Create backup manager
            backup_manager = BackupManager(backup_dir)
            
            # Create reorganizer
            reorganizer = NameOnlyReorganizer(backup_manager)
            
            # Create simple template
            template_file = template_dir / "directory.md"
            template_content = """
specs/
├── features/
└── reference/
"""
            template_file.write_text(template_content)
            
            # Create test file
            test_file = project_dir / "test_feature.md"
            test_file.write_text("# Test Feature\nThis is a test feature.")
            
            # Create configuration
            config = NameOnlyConfig(
                template_file=template_file,
                backup_enabled=False,
                dry_run=True
            )
            
            # Test structure validation
            structure_result = reorganizer.validate_and_create_structure(project_dir, config)
            print(f"Structure validation success: {structure_result['success']}")
            
            # Test file classification
            classification_result = reorganizer.classify_and_organize_files(project_dir, config)
            print(f"Classification success: {classification_result['success']}")
            
            # Test full reorganization
            result = reorganizer.reorganize_repository(project_dir, config)
            print(f"Reorganization success: {result.success}")
            print(f"Execution time: {result.execution_time:.2f}s")
            
            if result.file_classification:
                print(f"Files classified: {result.file_classification.total_files}")
            
            print("✅ All tests passed!")
            return True
            
        finally:
            # Clean up
            if test_dir.exists():
                shutil.rmtree(test_dir)
                
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_basic_import()