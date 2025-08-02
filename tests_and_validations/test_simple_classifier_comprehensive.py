"""
Comprehensive test suite for SimpleClassifier with all classification methods.

Tests the complete functionality including filename patterns, content analysis,
directory context, and combined scoring with confidence thresholds.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add the onboarding directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'onboarding'))

from simple_classifier import SimpleClassifier, ClassificationResult


def create_comprehensive_test_structure():
    """Create a comprehensive test directory structure with various file types."""
    test_dir = Path(tempfile.mkdtemp())
    
    # Create directory structure
    (test_dir / "features").mkdir()
    (test_dir / "fixes").mkdir()
    (test_dir / "docs" / "reference").mkdir(parents=True)
    (test_dir / "misc").mkdir()
    
    # Test files with different classification signals
    test_files = {
        # Strong filename + content + directory signals
        "features/user_authentication_feature.md": """
        # User Authentication Feature Specification
        
        ## User Story
        As a user, I want to authenticate securely so that I can access my account.
        
        ## Acceptance Criteria
        - User can log in with username/password
        - System validates credentials
        - Failed attempts are logged
        
        ## Requirements
        The system shall implement secure authentication functionality.
        """,
        
        # Strong filename + content + directory signals for fixes
        "fixes/login_bug_fix.md": """
        # Login Bug Fix Documentation
        
        ## Problem Description
        Users experiencing authentication errors with special characters.
        
        ## Issue Analysis
        The bug occurs when passwords contain symbols.
        
        ## Resolution
        Fixed input validation to handle special characters properly.
        This patch resolves the defect in the login module.
        """,
        
        # Strong reference signals
        "docs/reference/api_documentation.md": """
        # API Reference Documentation
        
        ## Overview
        This guide provides comprehensive documentation for our REST API.
        
        ## Getting Started
        Follow these instructions to integrate with our API.
        
        ## Architecture
        The system follows microservices architecture patterns.
        
        ## Usage Examples
        Here are examples of how to use the API endpoints.
        """,
        
        # Conflicting signals (filename suggests feature, content suggests reference)
        "features/system_architecture.md": """
        # System Architecture Overview
        
        This document provides a comprehensive guide to the system architecture.
        The documentation covers all major components and their interactions.
        
        ## Reference Materials
        See the API documentation for detailed usage instructions.
        """,
        
        # Weak signals (should fallback)
        "misc/meeting_notes.md": """
        # Team Meeting Notes
        
        Discussion about project timeline and resource allocation.
        No specific technical content or implementation details.
        General project management and coordination topics.
        """,
        
        # Mixed signals (multiple categories could apply)
        "fixes/feature_enhancement_bug.md": """
        # Feature Enhancement Bug Fix
        
        ## User Story
        As a user, I want the enhanced search feature to work properly.
        
        ## Problem
        The new search functionality has a bug that causes crashes.
        
        ## Fix
        Resolved the issue in the search feature implementation.
        """,
    }
    
    # Create all test files
    for file_path, content in test_files.items():
        full_path = test_dir / file_path
        full_path.write_text(content.strip())
    
    return test_dir, test_files


def test_comprehensive_classification():
    """Test comprehensive classification with all methods combined."""
    print("Testing comprehensive classification...")
    
    test_dir, test_files = create_comprehensive_test_structure()
    classifier = SimpleClassifier()
    
    try:
        # Test each file
        expected_results = {
            "features/user_authentication_feature.md": ("features", 0.6),
            "fixes/login_bug_fix.md": ("fixes", 0.6),
            "docs/reference/api_documentation.md": ("reference", 0.6),
            "features/system_architecture.md": ("reference", 0.3),  # Content overrides filename
            "misc/meeting_notes.md": ("reference", 0.05),  # Fallback with very low confidence
            "fixes/feature_enhancement_bug.md": ("features", 0.4),  # Content keywords win over directory
        }
        
        for file_path, (expected_category, min_confidence) in expected_results.items():
            full_path = test_dir / file_path
            classified_file = classifier._classify_single_file(full_path)
            
            print(f"File: {file_path}")
            print(f"  Category: {classified_file.category} (confidence: {classified_file.confidence:.2f})")
            print(f"  Reasons: {classified_file.classification_reasons}")
            print(f"  Preview: {classified_file.content_preview[:50]}..." if classified_file.content_preview else "  Preview: None")
            print()
            
            assert classified_file.category == expected_category, \
                f"Expected '{expected_category}', got '{classified_file.category}' for {file_path}"
            assert classified_file.confidence >= min_confidence, \
                f"Expected confidence >= {min_confidence}, got {classified_file.confidence} for {file_path}"
            assert len(classified_file.classification_reasons) > 0, \
                f"Should have classification reasons for {file_path}"
        
        print("✓ Comprehensive classification test passed")
        
    finally:
        shutil.rmtree(test_dir)


def test_classification_result_generation():
    """Test generation of ClassificationResult with statistics."""
    print("Testing classification result generation...")
    
    test_dir, test_files = create_comprehensive_test_structure()
    classifier = SimpleClassifier()
    
    try:
        # Get all test files
        all_files = list(test_dir.rglob("*.md"))
        
        # Classify all files
        classified_files = classifier.classify_files(all_files)
        
        # Generate classification statistics
        total_files = len(classified_files)
        classification_distribution = {}
        low_confidence_files = []
        
        for cf in classified_files:
            # Count by category
            if cf.category not in classification_distribution:
                classification_distribution[cf.category] = 0
            classification_distribution[cf.category] += 1
            
            # Track low confidence files
            if cf.confidence < 0.5:
                low_confidence_files.append(cf)
        
        # Create ClassificationResult
        result = ClassificationResult(
            classified_files=classified_files,
            total_files=total_files,
            classification_distribution=classification_distribution,
            low_confidence_files=low_confidence_files,
            processing_time=0.1
        )
        
        # Validate result
        errors = result.validate()
        assert len(errors) == 0, f"ClassificationResult validation failed: {errors}"
        
        print(f"Total files classified: {result.total_files}")
        print(f"Distribution: {result.classification_distribution}")
        print(f"Low confidence files: {len(result.low_confidence_files)}")
        
        # Verify statistics
        assert result.total_files == len(test_files), "Total files count mismatch"
        assert sum(result.classification_distribution.values()) == result.total_files, "Distribution sum mismatch"
        assert all(cf.confidence < 0.5 for cf in result.low_confidence_files), "Low confidence threshold error"
        
        print("✓ Classification result generation test passed")
        
    finally:
        shutil.rmtree(test_dir)


def test_confidence_threshold_behavior():
    """Test behavior with different confidence thresholds."""
    print("Testing confidence threshold behavior...")
    
    classifier = SimpleClassifier()
    
    # Test combine_classification_scores with various scenarios
    test_scenarios = [
        # High confidence scenario
        {
            "scores": [("features", 0.8, "filename pattern"), ("features", 0.6, "content keywords")],
            "expected_category": "features",
            "min_confidence": 0.5
        },
        # Low confidence scenario (should fallback)
        {
            "scores": [("features", 0.1, "filename pattern"), ("fixes", 0.05, "content keywords")],
            "expected_category": "reference",  # fallback
            "max_confidence": 0.3
        },
        # Conflicting signals scenario
        {
            "scores": [("features", 0.8, "filename pattern"), ("reference", 0.6, "content keywords")],
            "expected_category": "features",  # filename has higher weight
            "min_confidence": 0.3
        }
    ]
    
    for i, scenario in enumerate(test_scenarios):
        category, confidence = classifier.combine_classification_scores(scenario["scores"])
        
        print(f"Scenario {i+1}: {category} (confidence: {confidence:.2f})")
        
        assert category == scenario["expected_category"], \
            f"Scenario {i+1}: Expected '{scenario['expected_category']}', got '{category}'"
        
        if "min_confidence" in scenario:
            assert confidence >= scenario["min_confidence"], \
                f"Scenario {i+1}: Expected confidence >= {scenario['min_confidence']}, got {confidence}"
        
        if "max_confidence" in scenario:
            assert confidence <= scenario["max_confidence"], \
                f"Scenario {i+1}: Expected confidence <= {scenario['max_confidence']}, got {confidence}"
    
    print("✓ Confidence threshold behavior test passed")


def test_edge_cases_and_robustness():
    """Test edge cases and robustness of the classifier."""
    print("Testing edge cases and robustness...")
    
    classifier = SimpleClassifier()
    
    # Test with empty content
    test_dir = Path(tempfile.mkdtemp())
    try:
        empty_file = test_dir / "empty.md"
        empty_file.write_text("")
        
        classified = classifier._classify_single_file(empty_file)
        assert classified.category in ["features", "fixes", "reference"], "Should classify empty file"
        assert 0.0 <= classified.confidence <= 1.0, "Confidence should be in valid range"
        
        # Test with very large content (should be truncated)
        large_file = test_dir / "large_feature_spec.md"
        large_content = "This is a feature specification. " * 1000 + "User story: As a user I want to access the system. Acceptance criteria: The system shall provide secure access."
        large_file.write_text(large_content)
        
        classified = classifier._classify_single_file(large_file)
        # Should classify based on filename and content keywords
        assert classified.category in ["features", "reference"], "Should classify large file to valid category"
        assert classified.confidence > 0.1, "Should have reasonable confidence for large file"
        
        # Test with special characters in filename
        special_file = test_dir / "special@#$%_feature.md"
        special_file.write_text("This is a feature specification.")
        
        classified = classifier._classify_single_file(special_file)
        assert classified.category == "features", "Should handle special characters in filename"
        
        print("✓ Edge cases and robustness test passed")
        
    finally:
        shutil.rmtree(test_dir)


def test_custom_patterns_with_content():
    """Test custom patterns work with content-based classification."""
    print("Testing custom patterns with content classification...")
    
    # Define custom patterns
    custom_patterns = {
        "documentation": [r".*docs.*\.md$", "documentation", "guide", "manual"],
        "testing": [r".*test.*\.md$", "test", "testing", "qa"],
        "deployment": [r".*deploy.*\.md$", "deployment", "infrastructure", "devops"]
    }
    
    classifier = SimpleClassifier(custom_patterns)
    
    test_dir = Path(tempfile.mkdtemp())
    try:
        # Create test files for custom categories
        test_files = {
            "user_docs.md": "This is a comprehensive guide and manual for users.",
            "test_plan.md": "This document covers testing procedures and QA processes.",
            "deploy_guide.md": "Infrastructure deployment and DevOps procedures."
        }
        
        for filename, content in test_files.items():
            file_path = test_dir / filename
            file_path.write_text(content)
            
            classified = classifier._classify_single_file(file_path)
            print(f"Custom classification '{filename}': {classified.category} (confidence: {classified.confidence:.2f})")
            
            # Verify it uses custom categories
            assert classified.category in custom_patterns.keys(), \
                f"Should use custom category for {filename}, got {classified.category}"
            assert classified.confidence > 0.3, \
                f"Should have reasonable confidence for {filename}"
        
        print("✓ Custom patterns with content test passed")
        
    finally:
        shutil.rmtree(test_dir)


def run_all_tests():
    """Run all comprehensive tests."""
    print("Running comprehensive SimpleClassifier tests...")
    print("=" * 70)
    
    try:
        test_comprehensive_classification()
        test_classification_result_generation()
        test_confidence_threshold_behavior()
        test_edge_cases_and_robustness()
        test_custom_patterns_with_content()
        
        print("=" * 70)
        print("✅ All comprehensive tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)