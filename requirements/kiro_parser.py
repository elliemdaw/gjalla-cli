"""
Kiro requirements parser for structured .kiro directory files.

This module provides regex-based parsing for well-structured requirements
files found in .kiro directories that already follow EARS format patterns.
"""

import re
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from .models import RequirementRecord, RequirementStatus, RequirementSource


class KiroRequirementsParser:
    """
    Parser for structured .kiro directory requirements files.
    
    This parser is optimized for files that already follow structured patterns
    like EARS format, user stories with acceptance criteria, etc.
    """
    
    def __init__(self):
        """Initialize the Kiro parser with specialized patterns."""
        # Enhanced EARS patterns for structured documents
        self._ears_patterns = [
            # Standard EARS: WHEN ... THEN ... SHALL
            re.compile(r'WHEN\s+(.+?)\s+THEN\s+(.+?)\s+SHALL\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
            # Alternative: IF ... THEN ... SHALL  
            re.compile(r'IF\s+(.+?)\s+THEN\s+(.+?)\s+SHALL\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
            # BDD style: GIVEN ... WHEN ... THEN
            re.compile(r'GIVEN\s+(.+?)\s+WHEN\s+(.+?)\s+THEN\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
            # Numbered acceptance criteria with WHEN/THEN
            re.compile(r'\d+\.\s+WHEN\s+(.+?)\s+THEN\s+(.+?)\s+SHALL\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
        ]
        
        # User story patterns with structured format
        self._user_story_patterns = [
            # Standard: As a ... I want ... so that
            re.compile(r'(?:\*\*User Story:\*\*|\*User Story:\*)?\s*As\s+a\s+(.+?),?\s+I\s+want\s+(.+?),?\s+so\s+that\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
            # Alternative: As an ... I need ... to
            re.compile(r'(?:\*\*User Story:\*\*|\*User Story:\*)?\s*As\s+an?\s+(.+?),?\s+I\s+need\s+(.+?)\s+to\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
        ]
        
        # Requirement section headers
        self._requirement_header_pattern = re.compile(r'^###?\s*Requirement\s+(\d+|[A-Z]+)', re.IGNORECASE | re.MULTILINE)
        
        # Acceptance criteria section
        self._acceptance_criteria_pattern = re.compile(r'(?:####?\s*Acceptance Criteria|Acceptance Criteria:)', re.IGNORECASE)
    
    def parse_kiro_directory(self, kiro_path: Path, current_commit: str) -> List[RequirementRecord]:
        """
        Parse all requirements files in a .kiro directory structure.
        
        Args:
            kiro_path: Path to the .kiro directory
            current_commit: Current git commit hash
            
        Returns:
            List of parsed requirement records
        """
        requirements = []
        
        # Look for requirements files in .kiro structure
        requirements_files = self._find_requirements_files(kiro_path)
        
        for file_path in requirements_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                file_requirements = self.parse_requirements_file(content, file_path, current_commit)
                requirements.extend(file_requirements)
            except Exception as e:
                print(f"Warning: Failed to parse {file_path}: {e}")
        
        return requirements
    
    def _find_requirements_files(self, kiro_path: Path) -> List[Path]:
        """Find all requirements-related files in .kiro directory."""
        requirements_files = []
        
        # Common patterns for requirements files in .kiro structure
        patterns = [
            '**/requirements.md',
            '**/requirements/*.md',
            '**/specs/**/requirements.md',
            '**/acceptance_criteria.md',
            '**/user_stories.md'
        ]
        
        for pattern in patterns:
            requirements_files.extend(kiro_path.glob(pattern))
        
        return list(set(requirements_files))  # Remove duplicates
    
    def parse_requirements_file(self, content: str, file_path: Path, current_commit: str) -> List[RequirementRecord]:
        """
        Parse a structured requirements file.
        
        Args:
            content: File content to parse
            file_path: Path to the source file
            current_commit: Current git commit hash
            
        Returns:
            List of requirement records
        """
        requirements = []
        
        # Extract source folder name (parent directory of requirements file)
        source_folder = self._get_source_folder_name(file_path)
        
        # Parse tasks.md in same directory to determine implementation status
        task_status_map = self._parse_tasks_file(file_path.parent)
        
        # Split content into requirement sections
        sections = self._split_into_requirement_sections(content)
        
        for section_id, section_content in sections.items():
            section_requirements = self._parse_requirement_section(
                section_id, section_content, file_path, current_commit, source_folder, task_status_map
            )
            requirements.extend(section_requirements)
        
        return requirements
    
    def _split_into_requirement_sections(self, content: str) -> Dict[str, str]:
        """Split content into individual requirement sections."""
        sections = {}
        
        # Find requirement headers
        header_matches = list(self._requirement_header_pattern.finditer(content))
        
        if not header_matches:
            # If no structured headers, treat entire content as one section
            return {"general": content}
        
        for i, match in enumerate(header_matches):
            section_id = match.group(1)
            start_pos = match.start()
            
            # Find end position (start of next section or end of content)
            if i + 1 < len(header_matches):
                end_pos = header_matches[i + 1].start()
            else:
                end_pos = len(content)
            
            section_content = content[start_pos:end_pos]
            sections[section_id] = section_content
        
        return sections
    
    def _parse_requirement_section(self, section_id: str, content: str, 
                                 file_path: Path, current_commit: str, source_folder: str, 
                                 task_status_map: Dict[str, bool]) -> List[RequirementRecord]:
        """Parse an individual requirement section."""
        requirements = []
        
        # Extract user story if present
        user_story = self._extract_user_story(content)
        
        # Extract acceptance criteria (EARS format requirements)
        acceptance_criteria = self._extract_acceptance_criteria(content)
        
        # Create main user story requirement record if user story exists
        if user_story:
            # Determine status for acceptance criteria first
            ac_statuses = []
            for i in range(1, len(acceptance_criteria) + 1):
                ac_status = self._determine_acceptance_criteria_status(section_id, i, task_status_map)
                ac_statuses.append(ac_status)
            
            # Determine user story status based on acceptance criteria aggregate
            user_story_status = self._determine_user_story_status(ac_statuses)
            
            user_story_req = RequirementRecord(
                id=f"REQ-{section_id}",
                ears_format=user_story,  # User story goes in EARS format field
                original_text=user_story,
                status=user_story_status,
                source_type=RequirementSource.DOCUMENTATION,
                source_location=source_folder,
                added_date=datetime.now(),
                added_commit=current_commit,
                last_verified_date=datetime.now(),
                last_verified_commit=current_commit,
                tags=["kiro", "user-story", "structured"]
            )
            requirements.append(user_story_req)
        
        # Generate acceptance criteria requirement records
        for i, criteria in enumerate(acceptance_criteria, 1):
            req_id = f"REQ-{section_id}.{i}"
            
            # Determine status from tasks.md parsing
            status = self._determine_acceptance_criteria_status(section_id, i, task_status_map)
            
            req_record = RequirementRecord(
                id=req_id,
                ears_format=criteria,
                original_text=criteria,
                status=status,
                source_type=RequirementSource.DOCUMENTATION,
                source_location=source_folder,
                added_date=datetime.now(),
                added_commit=current_commit,
                last_verified_date=datetime.now(),
                last_verified_commit=current_commit,
                tags=["kiro", "acceptance-criteria", "structured"]
            )
            
            requirements.append(req_record)
        
        return requirements
    
    def _extract_user_story(self, content: str) -> Optional[str]:
        """Extract user story from section content."""
        for pattern in self._user_story_patterns:
            match = pattern.search(content)
            if match:
                # Extract just the user story content without the preamble
                # Reconstruct the user story from captured groups (role, want, benefit)
                if len(match.groups()) >= 3:
                    role = match.group(1).strip()
                    want = match.group(2).strip()
                    benefit = match.group(3).strip()
                    
                    # Check if this is an "I want" or "I need" pattern
                    original_text = match.group(0)
                    if "I need" in original_text:
                        return f"As a {role}, I need {want} to {benefit}."
                    else:
                        return f"As a {role}, I want {want}, so that {benefit}."
                
                # Fallback to full match if groups don't work as expected
                return match.group(0).strip()
        return None
    
    def _extract_acceptance_criteria(self, content: str) -> List[str]:
        """Extract acceptance criteria (EARS format) from section content."""
        criteria = []
        
        # Find acceptance criteria section
        ac_match = self._acceptance_criteria_pattern.search(content)
        if ac_match:
            # Extract content after acceptance criteria header
            ac_content = content[ac_match.end():]
        else:
            # Use entire content if no specific AC section
            ac_content = content
        
        # Extract EARS format statements
        for pattern in self._ears_patterns:
            matches = pattern.finditer(ac_content)
            for match in matches:
                ears_statement = match.group(0).strip()
                # Clean up the EARS statement by removing leading/trailing numbers
                cleaned_statement = self._clean_ears_statement(ears_statement)
                if cleaned_statement:  # Only add non-empty cleaned statements
                    criteria.append(cleaned_statement)
        
        # If no EARS patterns found, look for numbered list items that might be requirements
        if not criteria:
            criteria = self._extract_numbered_requirements(ac_content)
        
        return criteria
    
    def _clean_ears_statement(self, statement: str) -> str:
        """Clean up EARS statements by removing leading/trailing numbers and extra whitespace."""
        # Remove leading numbers (e.g., "1. WHEN..." -> "WHEN...")
        cleaned = re.sub(r'^\d+\.\s*', '', statement.strip())
        
        # Remove trailing numbers (e.g., "...SHALL do something 2." -> "...SHALL do something")
        cleaned = re.sub(r'\s+\d+\.$', '', cleaned)
        
        # Remove other trailing numbers without period (e.g., "...SHALL do something 2" -> "...SHALL do something")
        cleaned = re.sub(r'\s+\d+$', '', cleaned)
        
        # Clean up any extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def _extract_numbered_requirements(self, content: str) -> List[str]:
        """Extract numbered list items that look like requirements."""
        requirements = []
        
        # Pattern for numbered lists with requirement-like content
        numbered_pattern = re.compile(r'^\d+\.\s+(.+?)(?=\n\d+\.|\n[^0-9]|\Z)', re.MULTILINE | re.DOTALL)
        
        matches = numbered_pattern.finditer(content)
        for match in matches:
            requirement_text = match.group(1).strip()
            
            # Check if it looks like a requirement (contains SHALL, MUST, SHOULD, etc.)
            if any(keyword in requirement_text.upper() for keyword in ['SHALL', 'MUST', 'SHOULD', 'WILL']):
                # Clean up the text using the same method as EARS statements
                cleaned_text = self._clean_ears_statement(requirement_text)
                if cleaned_text:
                    requirements.append(cleaned_text)
        
        return requirements
    
    def validate_kiro_structure(self, kiro_path: Path) -> Dict[str, List[str]]:
        """
        Validate the .kiro directory structure for requirements parsing.
        
        Returns:
            Dictionary with 'found' and 'missing' lists
        """
        result = {"found": [], "missing": [], "invalid": []}
        
        if not kiro_path.exists():
            result["missing"].append(f".kiro directory not found at {kiro_path}")
            return result
        
        # Check for requirements files
        requirements_files = self._find_requirements_files(kiro_path)
        
        if requirements_files:
            for file_path in requirements_files:
                try:
                    content = file_path.read_text(encoding='utf-8')
                    # Quick validation - check if it contains structured content
                    if (self._requirement_header_pattern.search(content) or 
                        any(pattern.search(content) for pattern in self._ears_patterns)):
                        result["found"].append(str(file_path.relative_to(kiro_path)))
                    else:
                        result["invalid"].append(f"{file_path.relative_to(kiro_path)} - no structured requirements found")
                except Exception as e:
                    result["invalid"].append(f"{file_path.relative_to(kiro_path)} - {e}")
        else:
            result["missing"].append("No requirements files found in .kiro directory")
        
        return result
    
    def generate_summary_report(self, requirements: List[RequirementRecord]) -> str:
        """Generate a summary report of parsed .kiro requirements."""
        if not requirements:
            return "No requirements found in .kiro directory structure."
        
        # Basic statistics
        total = len(requirements)
        files = set(req.source_location for req in requirements)
        
        report = ""
        report += f"Total Requirements: {total}\n"
        report += f"Source Files: {len(files)}\n\n"
        
        # Group by source file
        by_file = {}
        for req in requirements:
            file_name = req.source_location
            if file_name not in by_file:
                by_file[file_name] = []
            by_file[file_name].append(req)
        
        report += "Requirements by File:\n"
        for file_name, file_reqs in by_file.items():
            report += f"  {file_name}: {len(file_reqs)} requirements"
        
        return report
    
    def _get_source_folder_name(self, file_path: Path) -> str:
        """Extract the source folder name from the file path."""
        # For path like .kiro/specs/onboarding/requirements.md, return "onboarding"
        parts = file_path.parts
        
        # Find the index of 'specs' and get the next part
        try:
            specs_index = parts.index('specs')
            if specs_index + 1 < len(parts):
                return parts[specs_index + 1]
        except ValueError:
            pass
        
        # Fallback to parent directory name
        return file_path.parent.name
    
    def _parse_tasks_file(self, directory: Path) -> Dict[str, bool]:
        """
        Parse tasks.md file to determine implementation status.
        
        Returns a mapping of requirement patterns to completion status.
        """
        tasks_file = directory / 'tasks.md'
        if not tasks_file.exists():
            return {}
        
        try:
            content = tasks_file.read_text(encoding='utf-8')
            return self._extract_task_completion_status(content)
        except Exception as e:
            print(f"Warning: Failed to parse tasks.md in {directory}: {e}")
            return {}
    
    def _extract_task_completion_status(self, content: str) -> Dict[str, bool]:
        """
        Extract task completion status and map to requirements.
        
        Uses a robust regex approach to parse patterns like:
        - [x] Task description...
          - _Requirements: 1.1, 1.2, 1.3_
        - [ ] Task description...
          - _Requirements: 2.1, 2.2_
        """
        status_map = {}
        
        # Split content into sections that start with checkbox and contain requirements
        # This approach is more reliable than complex AST parsing for this structured format
        sections = re.split(r'\n(?=- \[[x\s]\])', content)
        
        for section in sections:
            if not section.strip():
                continue
                
            # Check for checkbox at the start of the section
            checkbox_match = re.match(r'- \[([x\s])\]', section.strip())
            if checkbox_match:
                checkbox_state = checkbox_match.group(1).strip().lower()
                is_completed = checkbox_state == 'x'
                
                # Look for requirements pattern anywhere in this section
                req_pattern = re.compile(r'_Requirements:\s*([^_]+)_', re.IGNORECASE)
                req_match = req_pattern.search(section)
                
                if req_match:
                    requirements_text = req_match.group(1).strip()
                    # Parse requirement references like "1.1, 1.2, 1.3"
                    req_refs = [req.strip() for req in requirements_text.split(',')]
                    
                    for req_ref in req_refs:
                        req_ref = req_ref.strip()
                        if req_ref:
                            status_map[req_ref] = is_completed
        
        return status_map
    
    def _determine_acceptance_criteria_status(self, section_id: str, req_index: int, 
                                            task_status_map: Dict[str, bool]) -> RequirementStatus:
        """
        Determine acceptance criteria status based on task completion.
        
        Maps requirement section and index to task completion status.
        Acceptance criteria can only be IMPLEMENTED or TODO.
        """
        # For section_id like "1", "2", "3" and req_index like 1, 2, 3
        # Create format like "1.1", "1.2", "2.1", etc.
        if section_id.isdigit():
            requirement_ref = f"{section_id}.{req_index}"
        elif section_id == "general":
            # For general section, try different formats
            requirement_ref = str(req_index)
        else:
            # For non-numeric section IDs, try various formats
            requirement_ref = f"{section_id}.{req_index}"
        
        # Check if this requirement reference is in the task status map
        if requirement_ref in task_status_map:
            return RequirementStatus.IMPLEMENTED if task_status_map[requirement_ref] else RequirementStatus.TODO
        
        # Also try without the section (just the index)
        simple_ref = str(req_index)
        if simple_ref in task_status_map:
            return RequirementStatus.IMPLEMENTED if task_status_map[simple_ref] else RequirementStatus.TODO
        
        # Default to TODO if no tasks.md or no matching task found
        return RequirementStatus.TODO
    
    def _determine_user_story_status(self, acceptance_criteria_statuses: List[RequirementStatus]) -> RequirementStatus:
        """
        Determine user story status based on aggregate of acceptance criteria statuses.
        
        Logic:
        - If all acceptance criteria are IMPLEMENTED → IMPLEMENTED
        - If some are IMPLEMENTED and some are TODO → IN_PROGRESS  
        - If all are TODO → TODO
        """
        if not acceptance_criteria_statuses:
            return RequirementStatus.TODO
        
        implemented_count = sum(1 for status in acceptance_criteria_statuses if status == RequirementStatus.IMPLEMENTED)
        total_count = len(acceptance_criteria_statuses)
        
        if implemented_count == total_count:
            return RequirementStatus.IMPLEMENTED
        elif implemented_count > 0:
            return RequirementStatus.IN_PROGRESS
        else:
            return RequirementStatus.TODO