"""
File exclusion utilities for Gjalla organize operations.

This module provides shared utilities for handling file exclusion patterns,
including .gitignore and .gjallaignore parsing, pattern matching, and
common exclusion logic used across different organize components.
"""

import fnmatch
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class ExclusionUtils:
    """Utilities for handling file exclusion patterns and gitignore parsing."""
    
    # System defaults that should always be excluded
    SYSTEM_EXCLUSIONS = [
        '.git', '.git/**', 
        '.venv', '.venv/**', 
        'venv', 'venv/**',
        '__pycache__', '__pycache__/**',
        '.pytest_cache', '.pytest_cache/**',
        'node_modules', 'node_modules/**',
        '.DS_Store',
        'build', 'build/**',
        'dist', 'dist/**',
        '.idea', '.idea/**',
        '.vscode', '.vscode/**',
        '.mypy_cache', '.mypy_cache/**',
        '.tox', '.tox/**',
        '.coverage',
        '*.pyc',
        '*.pyo',
        '*.egg-info',
        '*.egg-info/**',
        'htmlcov', 'htmlcov/**'
    ]
    
    @staticmethod
    def get_comprehensive_exclusion_patterns(project_dir: Path, user_patterns: List[str]) -> List[str]:
        """
        Get comprehensive exclusion patterns including .gitignore, system defaults, and user patterns.
        
        Args:
            project_dir: Path to the project directory
            user_patterns: User-provided exclusion patterns
            
        Returns:
            List of all exclusion patterns to apply
        """
        # Start with system defaults (always excluded)
        system_exclusions = ExclusionUtils.SYSTEM_EXCLUSIONS.copy()
        
        # Check if .gjallaignore exists, if so use it; otherwise use .gitignore
        gjallaignore_patterns = ExclusionUtils.parse_gjallaignore_files(project_dir)
        
        if gjallaignore_patterns:
            # Use .gjallaignore patterns (preferred)
            ignore_patterns = gjallaignore_patterns
            logger.info(f"Using .gjallaignore patterns ({len(gjallaignore_patterns)} patterns)")
        else:
            # Fall back to .gitignore patterns
            gitignore_patterns = ExclusionUtils.parse_gitignore_files(project_dir)
            ignore_patterns = gitignore_patterns
            if gitignore_patterns:
                logger.info(f"Using .gitignore patterns ({len(gitignore_patterns)} patterns)")
        
        # Combine all patterns: system defaults + ignore patterns + user patterns
        all_patterns = system_exclusions + ignore_patterns + user_patterns
        
        logger.info(f"Using {len(all_patterns)} total exclusion patterns ({len(system_exclusions)} system, "
                    f"{len(ignore_patterns)} ignore, {len(user_patterns)} user)")
        if ignore_patterns:
            logger.info(f"Ignore patterns: {ignore_patterns[:10]}...")  # Show first 10
        
        return all_patterns
    
    @staticmethod
    def parse_gitignore_files(project_dir: Path) -> List[str]:
        """
        Parse .gitignore files in the project directory and return exclusion patterns.
        
        Args:
            project_dir: Path to the project directory
            
        Returns:
            List of patterns from .gitignore files
        """
        gitignore_patterns = []
        
        # Look for .gitignore files in project directory and subdirectories
        try:
            for gitignore_file in project_dir.rglob('.gitignore'):
                try:
                    content = gitignore_file.read_text(encoding='utf-8', errors='ignore')
                    patterns = ExclusionUtils.parse_gitignore_content(content, gitignore_file.parent, project_dir)
                    gitignore_patterns.extend(patterns)
                    logger.debug(f"Loaded {len(patterns)} patterns from {gitignore_file}")
                except Exception as e:
                    logger.warning(f"Failed to parse .gitignore file {gitignore_file}: {str(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Error scanning for .gitignore files: {str(e)}")
        
        return gitignore_patterns
    
    @staticmethod
    def parse_gjallaignore_files(project_dir: Path) -> List[str]:
        """
        Parse .gjallaignore files in the project directory and return exclusion patterns.
        
        .gjallaignore files work similarly to .gitignore files but are specific to Gjalla
        reorganization operations. They take precedence over .gitignore patterns and allow
        users to specify additional files to exclude during documentation reorganization.
        
        Args:
            project_dir: Path to the project directory
            
        Returns:
            List of patterns from .gjallaignore files
        """
        gjallaignore_patterns = []
        
        # Look for .gjallaignore files in project directory and subdirectories
        try:
            for gjallaignore_file in project_dir.rglob('.gjallaignore'):
                try:
                    content = gjallaignore_file.read_text(encoding='utf-8', errors='ignore')
                    patterns = ExclusionUtils.parse_gitignore_content(content, gjallaignore_file.parent, project_dir)
                    gjallaignore_patterns.extend(patterns)
                    logger.info(f"Loaded {len(patterns)} patterns from .gjallaignore: {gjallaignore_file}")
                except Exception as e:
                    logger.warning(f"Failed to parse .gjallaignore file {gjallaignore_file}: {str(e)}")
                    continue
        except Exception as e:
            logger.warning(f"Error scanning for .gjallaignore files: {str(e)}")
        
        return gjallaignore_patterns
    
    @staticmethod
    def parse_gitignore_content(content: str, gitignore_dir: Path, project_dir: Path) -> List[str]:
        """
        Parse the content of a .gitignore file and return normalized patterns.
        
        Args:
            content: Content of the .gitignore file
            gitignore_dir: Directory containing the .gitignore file
            project_dir: Root project directory
            
        Returns:
            List of normalized exclusion patterns
        """
        patterns = []
        
        for line in content.splitlines():
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Handle negation patterns (we'll ignore them for simplicity)
            if line.startswith('!'):
                continue
            
            # Convert gitignore pattern to our format
            pattern = ExclusionUtils.normalize_gitignore_pattern(line, gitignore_dir, project_dir)
            if pattern:
                patterns.append(pattern)
        
        return patterns
    
    @staticmethod
    def normalize_gitignore_pattern(pattern: str, gitignore_dir: Path, project_dir: Path) -> Optional[str]:
        """
        Normalize a gitignore pattern for use with our exclusion system.
        
        Args:
            pattern: Original gitignore pattern
            gitignore_dir: Directory containing the .gitignore file
            project_dir: Root project directory
            
        Returns:
            Normalized pattern or None if pattern should be ignored
        """
        # Remove trailing whitespace
        pattern = pattern.rstrip()
        
        if not pattern:
            return None
        
        # Calculate relative path from project root to gitignore directory
        try:
            relative_gitignore_dir = gitignore_dir.relative_to(project_dir)
            prefix = str(relative_gitignore_dir) + '/' if relative_gitignore_dir != Path('.') else ''
        except ValueError:
            # gitignore_dir is not under project_dir, skip
            return None
        
        # Handle different gitignore pattern types
        if pattern.startswith('/'):
            # Absolute pattern from gitignore directory
            pattern = pattern[1:]  # Remove leading slash
            normalized = prefix + pattern
        elif '/' in pattern:
            # Pattern with directory separators
            normalized = prefix + pattern
        else:
            # Simple filename pattern
            if prefix:
                # If we're in a subdirectory, scope the pattern to that directory
                normalized = prefix + pattern
            else:
                # Global pattern from root .gitignore
                normalized = pattern
        
        # Ensure directory patterns end with /** for recursive matching
        if normalized.endswith('/'):
            normalized = normalized + '**'
        elif '/' in normalized and not normalized.endswith('/**') and '*' not in normalized:
            normalized = normalized + '/**'
        
        return normalized
    
    @staticmethod
    def matches_exclusion_pattern(file_path: Path, relative_path: Path, pattern: str) -> bool:
        """
        Check if a file matches an exclusion pattern.
        
        Args:
            file_path: Absolute path to the file
            relative_path: Path relative to project directory
            pattern: Exclusion pattern to check
            
        Returns:
            True if the file matches the exclusion pattern
        """
        # Convert paths to strings for pattern matching
        relative_str = str(relative_path).replace('\\', '/')  # Normalize path separators
        filename = file_path.name
        
        # Try different matching strategies
        # 1. Direct filename match
        if fnmatch.fnmatch(filename, pattern):
            return True
        
        # 2. Full relative path match
        if fnmatch.fnmatch(relative_str, pattern):
            return True
        
        # 3. Case-insensitive matches
        if fnmatch.fnmatch(filename.lower(), pattern.lower()):
            return True
        
        if fnmatch.fnmatch(relative_str.lower(), pattern.lower()):
            return True
        
        # 4. Check if any part of the path matches (for directory patterns)
        path_parts = relative_path.parts
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern) or fnmatch.fnmatch(part.lower(), pattern.lower()):
                return True
        
        # 5. Handle glob patterns with ** (recursive directory matching)
        if '**' in pattern:
            # Convert ** patterns to work with our path structure
            glob_pattern = pattern.replace('**/', '').replace('**', '*')
            if fnmatch.fnmatch(relative_str, glob_pattern) or fnmatch.fnmatch(filename, glob_pattern):
                return True
        
        return False
    
    @staticmethod
    def is_hidden_path(relative_path: Path) -> bool:
        """
        Check if a path contains hidden files or directories (starting with .).
        
        Args:
            relative_path: Path relative to project directory
            
        Returns:
            True if the path contains hidden components
        """
        # Check each part of the path
        for part in relative_path.parts:
            # Skip common non-hidden dotfiles that might be documentation
            if part.startswith('.') and part not in ['.md', '.markdown']:
                return True
        
        return False
    
    @staticmethod
    def find_markdown_files(project_dir: Path, exclusion_patterns: List[str]) -> List[Path]:
        """
        Find markdown files in the project directory, excluding specified patterns.
        
        Args:
            project_dir: Path to the project directory
            exclusion_patterns: List of patterns to exclude
            
        Returns:
            List of markdown file paths
        """
        markdown_files = []
        
        # Get comprehensive exclusion patterns including .gitignore
        all_exclusion_patterns = ExclusionUtils.get_comprehensive_exclusion_patterns(project_dir, exclusion_patterns)
        
        try:
            total_files = 0
            excluded_files = 0
            for md_file in project_dir.rglob('*.md'):
                total_files += 1
                # Skip if matches any exclusion pattern
                relative_path = md_file.relative_to(project_dir)
                should_exclude = False
                exclusion_reason = None
                
                # Check against all exclusion patterns
                for pattern in all_exclusion_patterns:
                    if ExclusionUtils.matches_exclusion_pattern(md_file, relative_path, pattern):
                        should_exclude = True
                        exclusion_reason = f"pattern: {pattern}"
                        break
                
                # Skip hidden files and directories by default
                if not should_exclude and ExclusionUtils.is_hidden_path(relative_path):
                    should_exclude = True
                    exclusion_reason = "hidden path"
                
                if should_exclude:
                    excluded_files += 1
                    # Log some excluded files for debugging
                    if excluded_files <= 10:
                        logger.info(f"Excluding: {relative_path} ({exclusion_reason})")
                else:
                    markdown_files.append(md_file)
            
            logger.info(f"Found {len(markdown_files)} markdown files (excluded {excluded_files} of {total_files} total)")
        
        except Exception as e:
            logger.warning(f"Error finding markdown files: {str(e)}")
        
        return markdown_files