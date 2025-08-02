"""
Simple tests for StructureValidator that can run standalone.
"""

import tempfile
import shutil
from pathlib import Path

# Import required classes
from organize.models import ParsedTemplate, StructureValidationError
from organize.structure_validator import StructureValidator


def test_structure_validator():
    """Test StructureValidator functionality."""
    print("Testing StructureValidator...")
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Create a sample template
        template = ParsedTemplate(
            template_name="test_template",
            directory_structure={
                "specs": {
                    "features": {},
                    "fixes": {},
                    "resources": {}
                }
            },
            file_placement_rules={
                "features": "specs/features",
                "fixes": "specs/fixes",
                "resources": "specs/resources"
            }
        )
        
        validator = StructureValidator()
        
        # Test 1: Empty directory (no compliance)
        result = validator.validate_structure(temp_dir, template)
        assert result.compliance_score == 0.0
        assert len(result.missing_directories) == 4  # specs, specs/features, specs/fixes, specs/resources
        assert len(result.existing_directories) == 0
        print("✓ Test 1 passed: Empty directory validation")
        
        # Test 2: Partial compliance
        (temp_dir / "specs").mkdir()
        (temp_dir / "specs" / "features").mkdir()
        
        result = validator.validate_structure(temp_dir, template)
        assert 0.0 < result.compliance_score < 1.0
        assert len(result.missing_directories) == 2  # specs/fixes, specs/resources
        assert len(result.existing_directories) == 2  # specs, specs/features
        print("✓ Test 2 passed: Partial compliance validation")
        
        # Test 3: Full compliance
        (temp_dir / "specs" / "fixes").mkdir()
        (temp_dir / "specs" / "resources").mkdir()
        
        result = validator.validate_structure(temp_dir, template)
        assert result.compliance_score == 1.0
        assert len(result.missing_directories) == 0
        assert len(result.existing_directories) == 4  # specs, specs/features, specs/fixes, specs/resources
        print("✓ Test 3 passed: Full compliance validation")
        
        # Test 4: Compliance reporting
        expected_dirs = ["specs/features", "specs/fixes", "specs/resources"]
        report = validator.check_directory_compliance(temp_dir, expected_dirs)
        assert report.compliance_percentage == 100.0
        assert report.found_directories == 3
        assert len(report.missing_directories) == 0
        print("✓ Test 4 passed: Compliance reporting")
        
        # Test 5: Score generation
        score = validator.generate_compliance_score(10, 7)
        assert score == 0.7
        
        score = validator.generate_compliance_score(5, 5)
        assert score == 1.0
        
        score = validator.generate_compliance_score(0, 0)
        assert score == 1.0
        print("✓ Test 5 passed: Score generation")
        
        # Test 6: Unexpected directories
        (temp_dir / "docs").mkdir()
        (temp_dir / "old_stuff").mkdir()
        
        result = validator.validate_structure(temp_dir, template)
        assert len(result.unexpected_directories) >= 2
        unexpected_names = [d.name for d in result.unexpected_directories]
        assert "docs" in unexpected_names
        assert "old_stuff" in unexpected_names
        print("✓ Test 6 passed: Unexpected directories detection")
        
        # Test 7: Error handling
        try:
            nonexistent_dir = temp_dir / "nonexistent"
            validator.validate_structure(nonexistent_dir, template)
            assert False, "Should have raised StructureValidationError"
        except StructureValidationError:
            pass
        print("✓ Test 7 passed: Error handling")
        
        # Test 8: Complex nested structure
        complex_template = ParsedTemplate(
            template_name="complex",
            directory_structure={
                "specs": {
                    "features": {
                        "auth": {},
                        "data": {}
                    },
                    "fixes": {},
                    "resources": {
                        "api": {},
                        "guides": {}
                    }
                }
            },
            file_placement_rules={}
        )
        
        # Create partial complex structure
        (temp_dir / "specs" / "features" / "auth").mkdir(parents=True)
        (temp_dir / "specs" / "resources" / "api").mkdir(parents=True)
        
        result = validator.validate_structure(temp_dir, complex_template)
        assert 0.0 < result.compliance_score < 1.0
        print("✓ Test 8 passed: Complex nested structure")
        
        print("\n🎉 All StructureValidator tests passed!")
        
    finally:
        # Clean up
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_structure_validator()
    print("\n✅ All tests completed successfully!")