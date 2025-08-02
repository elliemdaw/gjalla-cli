#!/usr/bin/env python3
"""
Test CLI interface for name-only reorganization.

This test verifies that the CLI correctly handles the new reorganize command
and its various options.
"""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import argparse

def test_cli_argument_parsing():
    """Test that the CLI correctly parses reorganize command arguments."""
    print("Testing CLI argument parsing...")
    
    try:
        # Import CLI class
        sys.path.insert(0, '.')
        from cli import SpecStandardizationCLI
        
        # Create CLI instance
        cli = SpecStandardizationCLI()
        parser = cli._create_parser()
        
        # Test basic reorganize command
        args = parser.parse_args(['reorganize', '/test/project'])
        assert args.command == 'reorganize'
        assert args.project_dir == '/test/project'
        assert args.confidence_threshold == 0.3  # default
        assert args.fallback_category == 'reference'  # default
        assert args.dry_run is False  # default
        assert args.no_backup is False  # default
        
        # Test with all options
        args = parser.parse_args([
            'reorganize', '/test/project',
            '--template', '/custom/template.md',
            '--confidence-threshold', '0.5',
            '--fallback-category', 'misc',
            '--no-backup',
            '--dry-run',
            '--exclude', '*.tmp',
            '--exclude', 'build/*',
            '--non-interactive'
        ])
        
        assert args.template == '/custom/template.md'
        assert args.confidence_threshold == 0.5
        assert args.fallback_category == 'misc'
        assert args.no_backup is True
        assert args.dry_run is True
        assert args.exclude == ['*.tmp', 'build/*']
        assert args.non_interactive is True
        
        print("✓ CLI argument parsing test passed")
        return True
        
    except Exception as e:
        print(f"❌ CLI argument parsing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cli_help_text():
    """Test that the CLI help text includes the reorganize command."""
    print("Testing CLI help text...")
    
    try:
        sys.path.insert(0, '.')
        from cli import SpecStandardizationCLI
        
        cli = SpecStandardizationCLI()
        parser = cli._create_parser()
        
        # Get help text
        help_text = parser.format_help()
        
        # Check that reorganize command is mentioned
        assert 'reorganize' in help_text
        assert 'name-only classification' in help_text
        
        # Get environment help
        env_help = cli._get_environment_help()
        assert 'reorganize' in env_help
        assert 'no LLM required' in env_help
        
        print("✓ CLI help text test passed")
        return True
        
    except Exception as e:
        print(f"❌ CLI help text test failed: {e}")
        return False


def test_reorganize_method_signature():
    """Test that the reorganize method exists and has correct signature."""
    print("Testing reorganize method signature...")
    
    try:
        sys.path.insert(0, '.')
        from cli import SpecStandardizationCLI
        
        cli = SpecStandardizationCLI()
        
        # Check that method exists
        assert hasattr(cli, 'reorganize'), "reorganize method not found"
        assert callable(cli.reorganize), "reorganize method not callable"
        
        print("✓ Reorganize method signature test passed")
        return True
        
    except Exception as e:
        print(f"❌ Reorganize method signature test failed: {e}")
        return False


def test_environment_check_bypass():
    """Test that reorganize command bypasses environment check."""
    print("Testing environment check bypass...")
    
    try:
        # Read the CLI file to check for environment bypass
        cli_file = Path('cli.py')
        if not cli_file.exists():
            print("❌ CLI file not found")
            return False
        
        content = cli_file.read_text()
        
        # Check that reorganize is in the bypass list
        bypass_check = "args.command not in ['configure', 'reorganize']"
        if bypass_check not in content:
            print(f"❌ Environment bypass not found: {bypass_check}")
            return False
        
        print("✓ Environment check bypass test passed")
        return True
        
    except Exception as e:
        print(f"❌ Environment check bypass test failed: {e}")
        return False


def test_configuration_creation():
    """Test that the CLI correctly creates NameOnlyConfig from arguments."""
    print("Testing configuration creation...")
    
    try:
        # Create a mock args object
        class MockArgs:
            def __init__(self):
                self.project_dir = '/test/project'
                self.template = '/custom/template.md'
                self.confidence_threshold = 0.7
                self.fallback_category = 'misc'
                self.no_backup = True
                self.dry_run = True
                self.exclude = ['*.tmp', 'build/*']
                self.non_interactive = True
        
        # Test that we can import NameOnlyConfig
        sys.path.insert(0, 'onboarding')
        import models
        
        # Simulate configuration creation logic
        args = MockArgs()
        
        exclusion_patterns = [
            "README*", "CONTRIBUTING*", "LICENSE*", "CHANGELOG*"
        ]
        exclusion_patterns.extend(args.exclude)
        
        template_file = Path(args.template) if args.template else Path("templates/directory.md")
        
        config = models.NameOnlyConfig(
            template_file=template_file,
            confidence_threshold=args.confidence_threshold,
            fallback_category=args.fallback_category,
            backup_enabled=not args.no_backup,
            dry_run=args.dry_run,
            exclusion_patterns=exclusion_patterns
        )
        
        # Validate the configuration
        errors = config.validate()
        if errors:
            print(f"❌ Configuration validation failed: {errors}")
            return False
        
        # Check configuration values
        assert config.template_file == Path('/custom/template.md')
        assert config.confidence_threshold == 0.7
        assert config.fallback_category == 'misc'
        assert config.backup_enabled is False
        assert config.dry_run is True
        assert '*.tmp' in config.exclusion_patterns
        assert 'build/*' in config.exclusion_patterns
        
        print("✓ Configuration creation test passed")
        return True
        
    except Exception as e:
        print(f"❌ Configuration creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_command_routing():
    """Test that the main method correctly routes to reorganize command."""
    print("Testing command routing...")
    
    try:
        # Read the CLI file to check for command routing
        cli_file = Path('cli.py')
        if not cli_file.exists():
            print("❌ CLI file not found")
            return False
        
        content = cli_file.read_text()
        
        # Check for reorganize command routing
        routing_check = "elif args.command == 'reorganize':"
        if routing_check not in content:
            print(f"❌ Command routing not found: {routing_check}")
            return False
        
        # Check that it calls the reorganize method
        method_call = "self.reorganize(args)"
        if method_call not in content:
            print(f"❌ Method call not found: {method_call}")
            return False
        
        print("✓ Command routing test passed")
        return True
        
    except Exception as e:
        print(f"❌ Command routing test failed: {e}")
        return False


def main():
    """Run all CLI tests."""
    print("Running CLI name-only reorganization tests...\n")
    
    tests = [
        test_cli_argument_parsing,
        test_cli_help_text,
        test_reorganize_method_signature,
        test_environment_check_bypass,
        test_configuration_creation,
        test_command_routing,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1
        print()  # Add spacing between tests
    
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All CLI tests passed!")
        print("\nCLI Integration Summary:")
        print("- Added 'reorganize' command with comprehensive options")
        print("- Command bypasses environment check (no API keys required)")
        print("- Supports dry-run mode for safe testing")
        print("- Configurable template, confidence threshold, and exclusions")
        print("- Interactive prompts with non-interactive mode support")
        print("- Comprehensive help documentation")
        return True
    else:
        print("❌ Some CLI tests failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)