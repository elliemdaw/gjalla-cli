#!/usr/bin/env python3
"""
Actual CLI execution tests - tests that run the real CLI commands.

This test suite actually executes the CLI commands to verify they work,
rather than just checking file structure or patterns.
"""

import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
import json
import os


def run_cli_command(args, timeout=60, input_text=None):
    """Run a CLI command and return the result."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text
        )
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'success': result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': 'Command timed out',
            'success': False
        }
    except Exception as e:
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': str(e),
            'success': False
        }


def test_cli_installation_actual():
    """Test that the CLI is actually installed and accessible."""
    print("Testing actual CLI installation...")
    
    result = run_cli_command(['spec-standardization', '--version'])
    
    if not result['success']:
        print(f"❌ CLI not installed or not accessible")
        print(f"   Return code: {result['returncode']}")
        print(f"   Stderr: {result['stderr']}")
        return False
    
    if 'spec-standardization' not in result['stdout']:
        print(f"❌ Version output doesn't contain expected text")
        print(f"   Output: {result['stdout']}")
        return False
    
    print("✅ CLI installation test passed")
    return True


def test_cli_help_actual():
    """Test that CLI help actually works."""
    print("Testing actual CLI help...")
    
    result = run_cli_command(['spec-standardization', '--help'])
    
    if not result['success']:
        print(f"❌ CLI help failed")
        print(f"   Return code: {result['returncode']}")
        print(f"   Stderr: {result['stderr']}")
        return False
    
    required_content = ['reorganize', 'usage:', 'positional arguments']
    for content in required_content:
        if content.lower() not in result['stdout'].lower():
            print(f"❌ Help output missing required content: {content}")
            print(f"   Output: {result['stdout'][:200]}...")
            return False
    
    print("✅ CLI help test passed")
    return True


def test_reorganize_help_actual():
    """Test that reorganize help actually works."""
    print("Testing actual reorganize help...")
    
    result = run_cli_command(['spec-standardization', 'reorganize', '--help'])
    
    if not result['success']:
        print(f"❌ Reorganize help failed")
        print(f"   Return code: {result['returncode']}")
        print(f"   Stderr: {result['stderr']}")
        return False
    
    required_options = ['--template', '--confidence-threshold', '--dry-run', '--non-interactive']
    for option in required_options:
        if option not in result['stdout']:
            print(f"❌ Help output missing required option: {option}")
            print(f"   Output: {result['stdout'][:500]}...")
            return False
    
    print("✅ Reorganize help test passed")
    return True


def test_dry_run_actual():
    """Test actual dry run execution with real project."""
    print("Testing actual dry run execution...")
    
    # Check if demo project exists
    demo_dir = Path('cli_demo_project')
    if not demo_dir.exists():
        print("❌ Demo project not found - creating it...")
        # Create demo project
        demo_dir.mkdir()
        (demo_dir / "README.md").write_text("# Demo Project")
        (demo_dir / "feature_spec.md").write_text("# Feature Spec\nUser story: As a user...")
        (demo_dir / "bug_fix.md").write_text("# Bug Fix\nFixed issue with...")
        (demo_dir / "api_docs.md").write_text("# API Docs\nReference documentation...")
        
        # Create template
        template_dir = demo_dir / "templates"
        template_dir.mkdir()
        (template_dir / "directory.md").write_text("specs/\nspecs/features/\nspecs/fixes/\nspecs/reference/")
    
    result = run_cli_command([
        'spec-standardization', 'reorganize', str(demo_dir),
        '--dry-run', '--non-interactive'
    ])
    
    if not result['success']:
        print(f"❌ Dry run failed")
        print(f"   Return code: {result['returncode']}")
        print(f"   Stderr: {result['stderr']}")
        print(f"   Stdout: {result['stdout']}")
        return False
    
    # Check for expected output content
    required_content = [
        'DRY RUN MODE',
        'Discovering documentation files',
        'Creating directory structure',
        'Organizing files',
        'This was a dry run'
    ]
    
    for content in required_content:
        if content not in result['stdout']:
            print(f"❌ Dry run output missing required content: {content}")
            print(f"   Output: {result['stdout']}")
            return False
    
    print("✅ Dry run execution test passed")
    return True


def test_actual_reorganization():
    """Test actual reorganization with a temporary project."""
    print("Testing actual reorganization...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test project
        test_project = Path(temp_dir) / "test_project"
        test_project.mkdir()
        
        # Create sample files
        (test_project / "README.md").write_text("# Test Project")
        (test_project / "user_login_feature.md").write_text("# User Login Feature\nUser story: As a user...")
        (test_project / "password_bug_fix.md").write_text("# Password Bug Fix\nFixed issue with...")
        (test_project / "api_reference.md").write_text("# API Reference\nDocumentation for...")
        
        # Create template
        template_dir = test_project / "templates"
        template_dir.mkdir()
        (template_dir / "directory.md").write_text("specs/\nspecs/features/\nspecs/fixes/\nspecs/reference/")
        
        # Run actual reorganization
        result = run_cli_command([
            'spec-standardization', 'reorganize', str(test_project),
            '--non-interactive'
        ], input_text='y\n')
        
        if not result['success']:
            print(f"❌ Actual reorganization failed")
            print(f"   Return code: {result['returncode']}")
            print(f"   Stderr: {result['stderr']}")
            print(f"   Stdout: {result['stdout']}")
            return False
        
        # Check that files were actually moved
        specs_dir = test_project / "specs"
        if not specs_dir.exists():
            print("❌ Specs directory was not created")
            return False
        
        # Check for organized files
        expected_dirs = ['features', 'fixes', 'reference']
        for dir_name in expected_dirs:
            dir_path = specs_dir / dir_name
            if not dir_path.exists():
                print(f"❌ Expected directory not created: {dir_name}")
                return False
        
        # Check that at least some files were moved
        total_files = sum(len(list(d.glob('*.md'))) for d in specs_dir.rglob('*') if d.is_dir())
        if total_files == 0:
            print("❌ No files were moved to organized directories")
            return False
        
        print("✅ Actual reorganization test passed")
        return True


def test_error_handling_actual():
    """Test actual error handling with invalid inputs."""
    print("Testing actual error handling...")
    
    # Test with non-existent directory
    result = run_cli_command([
        'spec-standardization', 'reorganize', '/non/existent/directory',
        '--dry-run', '--non-interactive'
    ])
    
    if result['success']:
        print("❌ Should have failed with non-existent directory")
        return False
    
    if 'does not exist' not in result['stdout'] and 'does not exist' not in result['stderr']:
        print("❌ Error message doesn't mention non-existent directory")
        print(f"   Stdout: {result['stdout']}")
        print(f"   Stderr: {result['stderr']}")
        return False
    
    # Test with invalid confidence threshold
    demo_dir = Path('cli_demo_project')
    if demo_dir.exists():
        result = run_cli_command([
            'spec-standardization', 'reorganize', str(demo_dir),
            '--confidence-threshold', '2.0',  # Invalid - should be 0.0-1.0
            '--dry-run', '--non-interactive'
        ])
        
        if result['success']:
            print("❌ Should have failed with invalid confidence threshold")
            return False
    
    print("✅ Error handling test passed")
    return True


def test_custom_options_actual():
    """Test actual execution with custom options."""
    print("Testing actual execution with custom options...")
    
    demo_dir = Path('cli_demo_project')
    if not demo_dir.exists():
        print("❌ Demo project not found for custom options test")
        return False
    
    # Test with custom confidence threshold and fallback category
    result = run_cli_command([
        'spec-standardization', 'reorganize', str(demo_dir),
        '--confidence-threshold', '0.7',
        '--fallback-category', 'misc',
        '--dry-run', '--non-interactive'
    ])
    
    if not result['success']:
        print(f"❌ Custom options test failed")
        print(f"   Return code: {result['returncode']}")
        print(f"   Stderr: {result['stderr']}")
        print(f"   Stdout: {result['stdout']}")
        return False
    
    # Check that custom options are reflected in output
    if 'misc' not in result['stdout']:
        print("❌ Custom fallback category not reflected in output")
        print(f"   Output: {result['stdout']}")
        return False
    
    print("✅ Custom options test passed")
    return True


def test_standalone_script_actual():
    """Test that the standalone script actually works."""
    print("Testing actual standalone script execution...")
    
    result = run_cli_command(['python', 'standalone_cli.py', '--help'])
    
    if not result['success']:
        print(f"❌ Standalone script failed")
        print(f"   Return code: {result['returncode']}")
        print(f"   Stderr: {result['stderr']}")
        return False
    
    if 'reorganize' not in result['stdout']:
        print("❌ Standalone script help doesn't contain reorganize command")
        print(f"   Output: {result['stdout']}")
        return False
    
    print("✅ Standalone script test passed")
    return True


def test_interactive_mode_actual():
    """Test actual interactive mode (with simulated input)."""
    print("Testing actual interactive mode...")
    
    demo_dir = Path('cli_demo_project')
    if not demo_dir.exists():
        print("❌ Demo project not found for interactive test")
        return False
    
    # Test interactive mode with 'n' (no) response
    result = run_cli_command([
        'spec-standardization', 'reorganize', str(demo_dir),
        '--dry-run'
    ], input_text='n\n')
    
    if not result['success']:
        print(f"❌ Interactive mode test failed")
        print(f"   Return code: {result['returncode']}")
        print(f"   Stderr: {result['stderr']}")
        return False
    
    if 'cancelled' not in result['stdout'].lower():
        print("❌ Interactive cancellation not reflected in output")
        print(f"   Output: {result['stdout']}")
        return False
    
    print("✅ Interactive mode test passed")
    return True


def main():
    """Run all actual CLI execution tests."""
    print("Running ACTUAL CLI execution tests...")
    print("=" * 60)
    print("These tests actually execute the CLI commands to verify functionality.")
    print()
    
    tests = [
        test_cli_installation_actual,
        test_cli_help_actual,
        test_reorganize_help_actual,
        test_dry_run_actual,
        test_actual_reorganization,
        test_error_handling_actual,
        test_custom_options_actual,
        test_standalone_script_actual,
        test_interactive_mode_actual,
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
            import traceback
            traceback.print_exc()
            failed += 1
        print()
    
    print(f"ACTUAL EXECUTION TEST RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All actual CLI execution tests passed!")
        print("The CLI is genuinely working and has been properly tested.")
    else:
        print("❌ Some actual CLI execution tests failed!")
        print("The CLI has real issues that need to be fixed.")
        print()
        print("This demonstrates the importance of testing actual execution,")
        print("not just file structure and patterns.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)