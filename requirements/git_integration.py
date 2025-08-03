"""
Git integration utilities for requirements tracking.

This module provides functionality to track git changes, analyze diffs,
and determine what files and code changes have occurred since the last
requirements scan.
"""

import subprocess
import re
from typing import List, Dict, Set, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from .models import GitIntegrationError


@dataclass
class GitFileChange:
    """Represents a change to a file in git."""
    file_path: str
    change_type: str  # 'A' (added), 'M' (modified), 'D' (deleted), 'R' (renamed)
    old_path: Optional[str] = None  # For renamed files
    lines_added: int = 0
    lines_removed: int = 0
    
    @property
    def is_markdown(self) -> bool:
        """Check if this is a markdown file."""
        return self.file_path.lower().endswith(('.md', '.markdown'))
    
    @property
    def is_source_code(self) -> bool:
        """Check if this is a source code file."""
        source_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php'}
        return Path(self.file_path).suffix.lower() in source_extensions


@dataclass
class GitCommitInfo:
    """Information about a git commit."""
    hash: str
    author: str
    date: datetime
    message: str
    files_changed: List[GitFileChange]
    
    @property
    def short_hash(self) -> str:
        """Get the short version of the commit hash."""
        return self.hash[:8]


class GitIntegration:
    """
    Handles git operations for requirements tracking.
    
    This class provides methods to analyze git history, track changes,
    and extract information relevant to requirements discovery.
    """
    
    def __init__(self, project_path: Path):
        """Initialize git integration for a project."""
        self.project_path = project_path
        self._validate_git_repo()
    
    def _validate_git_repo(self) -> None:
        """Validate that the project path is a git repository."""
        if not (self.project_path / '.git').exists():
            raise GitIntegrationError(f"Not a git repository: {self.project_path}")
    
    def _run_git_command(self, args: List[str], cwd: Optional[Path] = None) -> str:
        """Run a git command and return the output."""
        cmd = ['git'] + args
        cwd = cwd or self.project_path
        
        try:
            result = subprocess.run(
                cmd, 
                cwd=cwd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitIntegrationError(f"Git command failed: {' '.join(cmd)}\nError: {e.stderr}")
        except FileNotFoundError:
            raise GitIntegrationError("Git command not found. Please ensure git is installed and in PATH.")
    
    def get_current_commit(self) -> str:
        """Get the current commit hash."""
        try:
            return self._run_git_command(['rev-parse', 'HEAD'])
        except GitIntegrationError as e:
            # Handle case where repository has no commits yet
            if "unknown revision or path not in the working tree" in str(e):
                return "0000000000000000000000000000000000000000"  # Null SHA for no commits
            raise
    
    def get_commit_info(self, commit_hash: str) -> GitCommitInfo:
        """Get detailed information about a specific commit."""
        # Get commit details
        format_str = '%H|%an|%ai|%s'
        commit_line = self._run_git_command(['show', '--format=' + format_str, '--no-patch', commit_hash])
        
        parts = commit_line.split('|', 3)
        if len(parts) != 4:
            raise GitIntegrationError(f"Failed to parse commit info for {commit_hash}")
        
        hash_full, author, date_str, message = parts
        
        # Parse git date format: "2025-08-01 21:54:09 -0500"
        # Convert to ISO format that Python can parse
        if ' ' in date_str:
            # Split date/time from timezone
            date_parts = date_str.rsplit(' ', 1)
            if len(date_parts) == 2:
                datetime_part, tz_part = date_parts
                # Convert "2025-08-01 21:54:09" to "2025-08-01T21:54:09"
                iso_datetime = datetime_part.replace(' ', 'T')
                # For now, ignore timezone and parse as local time
                date = datetime.fromisoformat(iso_datetime)
            else:
                # Fallback: just replace space with T
                date = datetime.fromisoformat(date_str.replace(' ', 'T'))
        else:
            date = datetime.fromisoformat(date_str)
        
        # Get file changes for this commit
        files_changed = self._get_commit_file_changes(commit_hash)
        
        return GitCommitInfo(
            hash=hash_full,
            author=author,
            date=date,
            message=message,
            files_changed=files_changed
        )
    
    def _get_commit_file_changes(self, commit_hash: str) -> List[GitFileChange]:
        """Get file changes for a specific commit."""
        # Get file change information
        changes_output = self._run_git_command([
            'show', '--name-status', commit_hash
        ])
        
        file_changes = []
        # Skip commit header lines and only process file change lines
        lines = changes_output.split('\n')
        in_file_section = False
        
        for line in lines:
            if not line.strip():
                in_file_section = True  # Empty line indicates start of file changes
                continue
            
            # Skip commit header lines (commit, author, date, message)
            if not in_file_section and (
                line.startswith('commit ') or 
                line.startswith('Author: ') or 
                line.startswith('Date: ') or
                not '\t' in line
            ):
                continue
            
            # Process file change lines
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            
            change_type = parts[0][0]  # A, M, D, R, etc.
            file_path = parts[1]
            old_path = parts[2] if len(parts) > 2 and change_type == 'R' else None
            
            # Get line change stats if it's a modification
            lines_added, lines_removed = 0, 0
            if change_type in ['M', 'A']:
                lines_added, lines_removed = self._get_file_line_changes(commit_hash, file_path)
            
            file_changes.append(GitFileChange(
                file_path=file_path,
                change_type=change_type,
                old_path=old_path,
                lines_added=lines_added,
                lines_removed=lines_removed
            ))
        
        return file_changes
    
    def _get_file_line_changes(self, commit_hash: str, file_path: str) -> Tuple[int, int]:
        """Get the number of lines added/removed for a file in a commit."""
        try:
            stat_output = self._run_git_command([
                'show', '--numstat', '--no-patch', commit_hash, '--', file_path
            ])
            
            if stat_output:
                parts = stat_output.split('\t')
                if len(parts) >= 2:
                    added = int(parts[0]) if parts[0] != '-' else 0
                    removed = int(parts[1]) if parts[1] != '-' else 0
                    return added, removed
        except (ValueError, GitIntegrationError):
            # If we can't get stats, return 0
            pass
        
        return 0, 0
    
    def get_changes_since_commit(self, since_commit: str) -> List[GitCommitInfo]:
        """Get all commits and their changes since a specific commit."""
        # Handle case where there are no commits yet
        if since_commit == "0000000000000000000000000000000000000000":
            return []
            
        try:
            # Get list of commits since the specified commit
            commit_hashes = self._run_git_command([
                'rev-list', f'{since_commit}..HEAD', '--reverse'
            ])
            
            if not commit_hashes:
                return []
            
            commits = []
            for commit_hash in commit_hashes.split('\n'):
                if commit_hash.strip():
                    commits.append(self.get_commit_info(commit_hash.strip()))
            
            return commits
        except GitIntegrationError as e:
            # Handle case where repository has no commits or invalid range
            if any(phrase in str(e) for phrase in ["unknown revision", "bad revision", "ambiguous argument", "Invalid revision range"]):
                return []
            raise
    
    def get_file_diff_since_commit(self, file_path: str, since_commit: str) -> str:
        """Get the diff for a specific file since a commit."""
        try:
            return self._run_git_command([
                'diff', since_commit, 'HEAD', '--', file_path
            ])
        except GitIntegrationError as e:
            # File might be new or deleted, or no commits exist
            if any(phrase in str(e) for phrase in ["unknown revision", "bad revision", "ambiguous argument"]):
                return ""
            # File might be new or deleted
            return ""
    
    def get_changed_files_since_commit(self, since_commit: str) -> List[GitFileChange]:
        """Get all file changes since a specific commit."""
        all_changes = {}  # file_path -> GitFileChange
        
        commits = self.get_changes_since_commit(since_commit)
        
        for commit in commits:
            for file_change in commit.files_changed:
                file_path = file_change.file_path
                
                if file_path in all_changes:
                    # Aggregate changes
                    existing = all_changes[file_path]
                    existing.lines_added += file_change.lines_added
                    existing.lines_removed += file_change.lines_removed
                    
                    # Update change type (prefer most recent significant change)
                    if file_change.change_type in ['A', 'D']:
                        existing.change_type = file_change.change_type
                else:
                    all_changes[file_path] = file_change
        
        return list(all_changes.values())
    
    def get_commit_messages_since(self, since_commit: str) -> List[str]:
        """Get all commit messages since a specific commit."""
        commits = self.get_changes_since_commit(since_commit)
        return [commit.message for commit in commits]
    
    def get_files_containing_pattern(self, pattern: str, file_extensions: Optional[List[str]] = None) -> List[str]:
        """Find files containing a specific pattern using git grep."""
        args = ['grep', '-l', pattern]
        
        if file_extensions:
            for ext in file_extensions:
                args.extend(['--', f'*.{ext}'])
        
        try:
            output = self._run_git_command(args)
            return output.split('\n') if output else []
        except GitIntegrationError:
            # git grep returns non-zero if no matches found
            return []
    
    def extract_requirements_from_commit_messages(self, commit_messages: List[str]) -> List[str]:
        """Extract potential requirements from commit messages."""
        requirements = []
        
        # Patterns that might indicate requirements
        patterns = [
            r'(?i)(?:add|implement|support|require|need|must|should|shall).{10,100}',
            r'(?i)when.{5,50}then.{5,50}shall.{5,100}',
            r'(?i)req(?:uirement)?[:\s-]+.{10,100}',
            r'(?i)feature[:\s-]+.{10,100}',
            r'(?i)user story[:\s-]+.{10,100}'
        ]
        
        for message in commit_messages:
            # Clean up the message
            message = re.sub(r'\n+', ' ', message)
            message = re.sub(r'\s+', ' ', message).strip()
            
            for pattern in patterns:
                matches = re.findall(pattern, message)
                for match in matches:
                    # Clean up the match
                    match = match.strip()
                    if len(match) > 20:  # Only include substantial matches
                        requirements.append(match)
        
        return list(set(requirements))  # Remove duplicates
    
    def is_clean_working_directory(self) -> bool:
        """Check if the working directory is clean (no uncommitted changes)."""
        try:
            status = self._run_git_command(['status', '--porcelain'])
            return not status.strip()
        except GitIntegrationError:
            return False
    
    def get_repo_info(self) -> Dict[str, str]:
        """Get basic repository information."""
        try:
            current_commit = self.get_current_commit()
            branch = self._run_git_command(['branch', '--show-current'])
            remote_url = ""
            
            try:
                remote_url = self._run_git_command(['remote', 'get-url', 'origin'])
            except GitIntegrationError:
                pass  # No remote configured
            
            return {
                'current_commit': current_commit,
                'current_branch': branch,
                'remote_url': remote_url,
                'is_clean': self.is_clean_working_directory()
            }
        except GitIntegrationError:
            raise GitIntegrationError("Failed to get repository information")


def validate_commit_hash(commit_hash: str) -> bool:
    """Validate that a string looks like a git commit hash."""
    if not commit_hash:
        return False
    
    # Git commit hashes are 40 character hex strings (or shorter for short hashes)
    if len(commit_hash) < 7 or len(commit_hash) > 40:
        return False
    
    return all(c in '0123456789abcdef' for c in commit_hash.lower())


def extract_requirements_from_diff(diff_content: str) -> List[str]:
    """Extract potential requirements from git diff content."""
    requirements = []
    
    # Look for added lines that might contain requirements
    added_lines = []
    for line in diff_content.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            added_lines.append(line[1:].strip())
    
    # Patterns for requirements in code/documentation
    patterns = [
        r'(?i)(?:req|requirement)[:\s-]+.{10,150}',
        r'(?i)when\s+.{5,50}\s+then\s+.{5,50}\s+shall\s+.{5,100}',
        r'(?i)(?:must|should|shall|will)\s+(?:be able to|support|provide|allow|enable)\s+.{10,100}',
        r'(?i)as\s+a\s+.{3,30}\s+i\s+(?:want|need)\s+.{10,100}',
        r'(?i)(?:feature|functionality)[:\s-]+.{10,100}'
    ]
    
    for line in added_lines:
        # Skip very short lines and lines that look like code
        if len(line) < 20 or line.startswith(('import ', 'from ', 'def ', 'class ', 'if ', 'for ', 'while ')):
            continue
        
        for pattern in patterns:
            matches = re.findall(pattern, line)
            for match in matches:
                match = match.strip()
                if len(match) > 20:
                    requirements.append(match)
    
    return list(set(requirements))