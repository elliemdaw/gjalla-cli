#!/usr/bin/env python3
"""
Comprehensive test suite for key gjalla CLI commands.

This test suite thoroughly tests the four critical CLI commands:
1. organize (actual reorganization)
2. organize --dry-run (preview mode)
3. undo (restore functionality)
4. requirements --kiro (structured requirements parsing)

These are the commands that must be working confidently before release.
"""

import tempfile
import shutil
import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime


class CLITestSuite:
    """Comprehensive CLI testing suite."""
    
    def __init__(self):
        self.test_dir = None
        self.cli_script = None
        self.test_results = []
        self.setup_paths()
    
    def setup_paths(self):
        """Set up paths for testing."""
        # Find the CLI entry point
        project_root = Path(__file__).parent.parent
        self.cli_script = project_root / "cli_tools" / "main_cli.py"
        
        if not self.cli_script.exists():
            raise FileNotFoundError(f"Could not find CLI entry point at {self.cli_script}")
    
    def run_cli_command(self, args, input_text=None, timeout=60):
        """Run a CLI command and return detailed results."""
        cmd = [sys.executable, str(self.cli_script)] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                input=input_text,
                timeout=timeout,
                cwd=self.test_dir
            )
            
            return {
                'success': result.returncode == 0,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'cmd': ' '.join(cmd)
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'returncode': -1,
                'stdout': '',
                'stderr': 'Command timed out',
                'cmd': ' '.join(cmd)
            }
        except Exception as e:
            return {
                'success': False,
                'returncode': -1,
                'stdout': '',
                'stderr': f'Exception: {str(e)}',
                'cmd': ' '.join(cmd)
            }
    
    def create_test_project(self):
        """Create a comprehensive test project with various file types."""
        self.test_dir = Path(tempfile.mkdtemp(prefix='cli_test_'))
        print(f"📁 Creating test project: {self.test_dir}")
        
        # Create markdown files for organization testing
        markdown_files = {
            'README.md': '# Test Project\nThis is a test project README.',
            'feature_001.md': '# Feature 001\nThis describes a new feature.',
            'bug_fix_123.md': '# Bug Fix 123\nThis documents a bug fix.',
            'user_guide.md': '# User Guide\nHow to use the application.',
            'architecture.md': '# Architecture\nSystem architecture documentation.',
            'requirements_old.md': '# Old Requirements\nSome old requirements.',
            'task_planning.md': '# Task Planning\nProject planning document.',
            'reference_docs.md': '# Reference\nReference documentation.',
        }
        
        for filename, content in markdown_files.items():
            (self.test_dir / filename).write_text(content)
        
        # Create .kiro directory for requirements testing
        kiro_dir = self.test_dir / '.kiro'
        kiro_dir.mkdir()
        
        # Create structured requirements files
        (kiro_dir / 'features').mkdir()
        (kiro_dir / 'features' / 'authentication.md').write_text("""
# Authentication Requirements

## REQ-AUTH-001: User Login
**WHEN** a user provides valid credentials **THEN** the system **SHALL** authenticate the user.

**Acceptance Criteria:**
- Username and password validation
- Session creation upon successful login
- Error message for invalid credentials

## REQ-AUTH-002: Session Management
**WHEN** a user is authenticated **THEN** the system **SHALL** maintain the user session.

**Acceptance Criteria:**
- Session timeout after 30 minutes of inactivity
- Session renewal on user activity
- Secure session token generation
""")
        
        (kiro_dir / 'api.md').write_text("""
# API Requirements

## REQ-API-001: Rate Limiting
**WHEN** API requests exceed 100 per minute **THEN** the system **SHALL** return a 429 status code.

**Acceptance Criteria:**
- Track requests per IP address
- Reset counter every minute
- Include retry-after header in response
""")
        
        print(f"✅ Test project created with {len(markdown_files)} markdown files and .kiro structure")
        return self.test_dir
    
    def record_test_result(self, test_name, success, details, duration=None):
        """Record a test result."""
        result = {
            'test_name': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now().isoformat(),
            'duration': duration
        }
        self.test_results.append(result)
        
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {details}")
    
    def test_organize_dry_run(self):
        """Test organize command in dry-run mode."""
        print("\n🔍 Testing: organize --dry-run")
        start_time = datetime.now()
        
        # Run organize in dry-run mode
        result = self.run_cli_command(['organize', str(self.test_dir), '--dry-run'])
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if not result['success']:
            self.record_test_result(
                'organize_dry_run_execution',
                False,
                f"Command failed (rc={result['returncode']}): stdout='{result['stdout']}' stderr='{result['stderr']}'",
                duration
            )
            return False
        
        # Check output content
        output = result['stdout']
        success = True
        details = []
        
        # Should show preview information
        if 'dry run' not in output.lower() and 'preview' not in output.lower():
            success = False
            details.append("Output doesn't indicate dry-run mode")
        
        # Should not actually move files
        original_files = list(self.test_dir.glob('*.md'))
        if len(original_files) == 0:
            success = False
            details.append("Original files were moved (should be preserved in dry-run)")
        
        # Should not create backup in dry-run
        backup_dir = self.test_dir / '.gjalla' / '.backup'
        if backup_dir.exists():
            success = False
            details.append("Backup directory created during dry-run (should not happen)")
        
        detail_text = "Dry-run executed successfully" if success else "; ".join(details)
        self.record_test_result('organize_dry_run', success, detail_text, duration)
        return success
    
    def test_organize_actual(self):
        """Test actual organize command."""
        print("\n📂 Testing: organize (actual)")
        start_time = datetime.now()
        
        # Count original files
        original_files = list(self.test_dir.glob('*.md'))
        original_count = len(original_files)
        
        # Run organize command
        result = self.run_cli_command(['organize', str(self.test_dir)])
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if not result['success']:
            self.record_test_result(
                'organize_actual_execution',
                False,
                f"Command failed: {result['stderr']}",
                duration
            )
            return False
        
        success = True
        details = []
        
        # Check that backup was created
        backup_dir = self.test_dir / '.gjalla' / '.backup'
        if not backup_dir.exists():
            success = False
            details.append("No backup directory created")
        
        # Check that specs directory was created
        specs_dir = self.test_dir / 'specs'
        if not specs_dir.exists():
            success = False
            details.append("No specs directory created")
        
        # Check that files were organized (fewer files in root)
        remaining_files = list(self.test_dir.glob('*.md'))
        if len(remaining_files) >= original_count:
            success = False
            details.append(f"Files not organized (still {len(remaining_files)} in root)")
        
        # Check for organized subdirectories
        expected_dirs = ['features', 'fixes', 'reference']
        created_dirs = [d.name for d in specs_dir.iterdir() if d.is_dir()]
        if len(created_dirs) == 0:
            success = False
            details.append("No organization subdirectories created")
        
        detail_text = f"Organized {original_count} files into {len(created_dirs)} directories" if success else "; ".join(details)
        self.record_test_result('organize_actual', success, detail_text, duration)
        return success
    
    def test_undo_dry_run(self):
        """Test undo command in dry-run mode."""
        print("\n🔄 Testing: undo --dry-run")
        start_time = datetime.now()
        
        # Run undo in dry-run mode
        result = self.run_cli_command(['undo', str(self.test_dir), '--dry-run'])
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if not result['success']:
            self.record_test_result(
                'undo_dry_run_execution',
                False,
                f"Command failed: {result['stderr']}",
                duration
            )
            return False
        
        success = True
        details = []
        
        # Check that files are still organized (dry-run shouldn't restore)
        specs_dir = self.test_dir / 'specs'
        if not specs_dir.exists():
            success = False
            details.append("Files were actually restored during dry-run")
        
        # Check output mentions dry-run
        output = result['stdout']
        if 'dry run' not in output.lower() and 'preview' not in output.lower():
            success = False
            details.append("Output doesn't indicate dry-run mode")
        
        detail_text = "Undo dry-run executed without making changes" if success else "; ".join(details)
        self.record_test_result('undo_dry_run', success, detail_text, duration)
        return success
    
    def test_undo_actual(self):
        """Test actual undo command."""
        print("\n↩️ Testing: undo (actual)")
        start_time = datetime.now()
        
        # Run undo command (simulate confirmation)
        result = self.run_cli_command(['undo', str(self.test_dir)], input_text='y\n')
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if not result['success']:
            self.record_test_result(
                'undo_actual_execution',
                False,
                f"Command failed: {result['stderr']}",
                duration
            )
            return False
        
        success = True
        details = []
        
        # Check that files were restored to root
        root_md_files = list(self.test_dir.glob('*.md'))
        if len(root_md_files) < 5:  # Should have multiple files back in root
            success = False
            details.append(f"Files not properly restored (only {len(root_md_files)} in root)")
        
        # Check that specs directory is empty or removed
        specs_dir = self.test_dir / 'specs'
        if specs_dir.exists():
            specs_files = list(specs_dir.rglob('*.md'))
            if len(specs_files) > 0:
                success = False
                details.append(f"Specs directory still contains {len(specs_files)} files")
        
        detail_text = f"Restored {len(root_md_files)} files to original locations" if success else "; ".join(details)
        self.record_test_result('undo_actual', success, detail_text, duration)
        return success
    
    def test_requirements_kiro(self):
        """Test requirements --kiro command."""
        print("\n📋 Testing: requirements --kiro")
        start_time = datetime.now()
        
        # Run requirements command with --kiro flag
        result = self.run_cli_command(['requirements', str(self.test_dir), '--kiro'])
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if not result['success']:
            self.record_test_result(
                'requirements_kiro_execution',
                False,
                f"Command failed: {result['stderr']}",
                duration
            )
            return False
        
        success = True
        details = []
        
        # Check that requirements.md was created
        requirements_file = self.test_dir / 'specs' / 'requirements.md'
        if not requirements_file.exists():
            success = False
            details.append("requirements.md file not created")
        else:
            # Check content
            content = requirements_file.read_text()
            if 'REQ-AUTH-001' not in content:
                success = False
                details.append("Authentication requirements not found in output")
            
            if 'REQ-API-001' not in content:
                success = False
                details.append("API requirements not found in output")
            
            if 'EARS' not in content:
                success = False
                details.append("EARS format not maintained in output")
        
        # Check output mentions kiro parsing
        output = result['stdout']
        if 'kiro' not in output.lower():
            success = False
            details.append("Output doesn't mention kiro parsing")
        
        detail_text = "Kiro requirements parsed and requirements.md created" if success else "; ".join(details)
        self.record_test_result('requirements_kiro', success, detail_text, duration)
        return success
    
    def test_requirements_list(self):
        """Test requirements --list command."""
        print("\n📄 Testing: requirements --list")
        start_time = datetime.now()
        
        # Run requirements list command
        result = self.run_cli_command(['requirements', str(self.test_dir), '--list'])
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if not result['success']:
            self.record_test_result(
                'requirements_list_execution',
                False,
                f"Command failed: {result['stderr']}",
                duration
            )
            return False
        
        success = True
        details = []
        
        # Check output shows requirements
        output = result['stdout']
        if 'REQ-AUTH-001' not in output and 'REQ-API-001' not in output:
            success = False
            details.append("Requirements not listed in output")
        
        detail_text = "Requirements listed successfully" if success else "; ".join(details)
        self.record_test_result('requirements_list', success, detail_text, duration)
        return success
    
    def run_full_workflow_test(self):
        """Run a complete workflow test."""
        print("\n🔄 Testing: Complete Workflow")
        print("Testing the full workflow: organize → undo → requirements")
        
        workflow_success = True
        
        # 1. Test organize dry-run
        if not self.test_organize_dry_run():
            workflow_success = False
            print("❌ Workflow failed at organize dry-run")
        
        # 2. Test actual organize
        if workflow_success and not self.test_organize_actual():
            workflow_success = False
            print("❌ Workflow failed at organize")
        
        # 3. Test undo dry-run
        if workflow_success and not self.test_undo_dry_run():
            workflow_success = False
            print("❌ Workflow failed at undo dry-run")
        
        # 4. Test requirements --kiro (should work with organized structure)
        if workflow_success and not self.test_requirements_kiro():
            workflow_success = False
            print("❌ Workflow failed at requirements --kiro")
        
        # 5. Test requirements --list
        if workflow_success and not self.test_requirements_list():
            workflow_success = False
            print("❌ Workflow failed at requirements --list")
        
        # 6. Test actual undo
        if workflow_success and not self.test_undo_actual():
            workflow_success = False
            print("❌ Workflow failed at undo")
        
        self.record_test_result(
            'complete_workflow',
            workflow_success,
            "Full workflow completed successfully" if workflow_success else "Workflow failed at one or more steps"
        )
        
        return workflow_success
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  • {result['test_name']}: {result['details']}")
        
        print("\n📋 DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            duration = f" ({result['duration']:.2f}s)" if result['duration'] else ""
            print(f"  {status} {result['test_name']}: {result['details']}{duration}")
    
    def cleanup(self):
        """Clean up test directory."""
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
            print(f"🧹 Cleaned up test directory: {self.test_dir}")


def main():
    """Main test execution."""
    print("🚀 COMPREHENSIVE GJALLA CLI TESTING")
    print("="*60)
    print("Testing critical commands: organize, organize --dry-run, undo, requirements --kiro")
    
    suite = CLITestSuite()
    
    try:
        # Create test project
        test_dir = suite.create_test_project()
        
        # Run comprehensive workflow test
        workflow_success = suite.run_full_workflow_test()
        
        # Print summary
        suite.print_summary()
        
        # Return appropriate exit code
        return 0 if workflow_success else 1
        
    except Exception as e:
        print(f"❌ Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        suite.cleanup()


if __name__ == '__main__':
    sys.exit(main())