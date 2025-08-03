"""
Requirements tracking and management system.

This module provides the core RequirementsTracker class that coordinates
requirements discovery, analysis, and maintenance of the living document.
"""

import json
import re
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from .models import (
    RequirementRecord, RequirementsMetadata, RequirementsChangeSet,
    RequirementStatus, RequirementSource
)
from .git_integration import GitIntegration, extract_requirements_from_diff
from .requirements_aggregator import RequirementsAggregator
from organize.models import ExtractedRequirement, RequirementType


class RequirementsTracker:
    """
    Main class for tracking and managing project requirements.
    
    This class coordinates requirements discovery from multiple sources,
    maintains the living requirements document, and tracks changes over time.
    """
    
    def __init__(self, project_path: Path):
        """Initialize the requirements tracker for a project."""
        self.project_path = project_path
        self.gjalla_dir = project_path / '.gjalla'
        self.metadata_file = self.gjalla_dir / 'requirements_metadata.json'
        self.requirements_file = project_path / 'aimarkdowns' / 'requirements.md'
        
        # Initialize components
        self.git = GitIntegration(project_path)
        self.aggregator = RequirementsAggregator()
        
        # Ensure directories exist
        self.gjalla_dir.mkdir(exist_ok=True)
        self.requirements_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize metadata
        self.metadata = self._load_metadata()
        
        # Cache for requirements
        self._requirements_cache: Optional[Dict[str, RequirementRecord]] = None
    
    def _load_metadata(self) -> RequirementsMetadata:
        """Load metadata from file or create new if doesn't exist."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return RequirementsMetadata.from_dict(data)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Warning: Failed to load requirements metadata: {e}")
                print("Creating new metadata file.")
        
        # Create new metadata with current commit
        try:
            current_commit = self.git.get_current_commit()
        except Exception:
            current_commit = "unknown"
        
        return RequirementsMetadata(
            last_scan_commit=current_commit,
            last_scan_date=datetime.now()
        )
    
    def _save_metadata(self) -> None:
        """Save metadata to file."""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata.to_dict(), f, indent=2)
    
    def _load_existing_requirements(self) -> Dict[str, RequirementRecord]:
        """Load existing requirements from the living document."""
        if not self.requirements_file.exists():
            return {}
        
        try:
            content = self.requirements_file.read_text(encoding='utf-8')
            return self._parse_requirements_from_markdown(content)
        except Exception as e:
            print(f"Warning: Failed to parse existing requirements: {e}")
            return {}
    
    def _parse_requirements_from_markdown(self, content: str) -> Dict[str, RequirementRecord]:
        """Parse requirements from the markdown living document."""
        requirements = {}
        
        # Split into sections by requirement headers
        sections = re.split(r'\n## (REQ-\d+):', content)
        
        for i in range(1, len(sections), 2):
            if i + 1 >= len(sections):
                break
            
            req_id = f"REQ-{sections[i].strip()}"
            section_content = sections[i + 1]
            
            try:
                req = self._parse_requirement_section(req_id, section_content)
                if req:
                    requirements[req_id] = req
            except Exception as e:
                print(f"Warning: Failed to parse requirement {req_id}: {e}")
        
        return requirements
    
    def _parse_requirement_section(self, req_id: str, content: str) -> Optional[RequirementRecord]:
        """Parse a single requirement section from markdown."""
        lines = content.strip().split('\n')
        
        # Extract metadata from the section
        metadata = {}
        ears_format = ""
        title = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith('**EARS Format**:'):
                ears_format = line.split(':', 1)[1].strip()
            elif line.startswith('**Status**:'):
                status_text = line.split(':', 1)[1].strip()
                # Parse status emoji and text
                if '✅' in status_text:
                    metadata['status'] = RequirementStatus.SUPPORTED
                elif '⚠️' in status_text:
                    metadata['status'] = RequirementStatus.DEPRECATED
                elif '❌' in status_text:
                    metadata['status'] = RequirementStatus.REMOVED
                else:
                    metadata['status'] = RequirementStatus.UNKNOWN
            elif line.startswith('**Source**:'):
                metadata['source_location'] = line.split(':', 1)[1].strip()
            elif line.startswith('**Added**:'):
                # Parse date and commit: "2024-01-15 (abc123ef)"
                added_text = line.split(':', 1)[1].strip()
                if '(' in added_text:
                    date_part, commit_part = added_text.split('(', 1)
                    metadata['added_date'] = datetime.strptime(date_part.strip(), '%Y-%m-%d')
                    metadata['added_commit'] = commit_part.rstrip(')').strip()
            elif line.startswith('**Last Verified**:'):
                # Parse date and commit
                verified_text = line.split(':', 1)[1].strip()
                if '(' in verified_text:
                    date_part, commit_part = verified_text.split('(', 1)
                    metadata['last_verified_date'] = datetime.strptime(date_part.strip(), '%Y-%m-%d')
                    metadata['last_verified_commit'] = commit_part.rstrip(')').strip()
            elif line.startswith('**Deprecated**:'):
                # Parse deprecated info
                deprecated_text = line.split(':', 1)[1].strip()
                if '(' in deprecated_text and ')' in deprecated_text:
                    parts = deprecated_text.split('(', 1)
                    date_part = parts[0].strip()
                    rest = parts[1]
                    if ')' in rest:
                        commit_part, reason = rest.split(')', 1)
                        metadata['deprecated_date'] = datetime.strptime(date_part, '%Y-%m-%d')
                        metadata['deprecated_commit'] = commit_part.strip()
                        if ' - ' in reason:
                            metadata['deprecated_reason'] = reason.split(' - ', 1)[1].strip()
        
        # Extract title from first line after the requirement ID
        if lines and not lines[0].startswith('**'):
            title = lines[0].strip()
        
        # Validate required fields
        if not ears_format or 'status' not in metadata:
            return None
        
        # Create RequirementRecord
        try:
            return RequirementRecord(
                id=req_id,
                ears_format=ears_format,
                original_text=ears_format,  # Will be updated if we find original
                status=metadata['status'],
                source_type=RequirementSource.DOCUMENTATION,  # Default
                source_location=metadata.get('source_location', 'unknown'),
                added_date=metadata.get('added_date', datetime.now()),
                added_commit=metadata.get('added_commit', 'unknown'),
                last_verified_date=metadata.get('last_verified_date', datetime.now()),
                last_verified_commit=metadata.get('last_verified_commit', 'unknown'),
                deprecated_date=metadata.get('deprecated_date'),
                deprecated_commit=metadata.get('deprecated_commit'),
                deprecated_reason=metadata.get('deprecated_reason')
            )
        except Exception as e:
            print(f"Error creating RequirementRecord for {req_id}: {e}")
            return None
    
    def _generate_next_requirement_id(self, existing_requirements: Dict[str, RequirementRecord]) -> str:
        """Generate the next available requirement ID."""
        if not existing_requirements:
            return "REQ-001"
        
        # Find the highest existing number
        max_num = 0
        for req_id in existing_requirements.keys():
            if req_id.startswith('REQ-'):
                try:
                    num = int(req_id.split('-')[1])
                    max_num = max(max_num, num)
                except (ValueError, IndexError):
                    continue
        
        return f"REQ-{max_num + 1:03d}"
    
    def discover_requirements_from_documentation(self) -> List[RequirementRecord]:
        """Discover requirements from markdown documentation."""
        # Find all markdown files
        md_files = []
        for pattern in ['**/*.md', '**/*.markdown']:
            md_files.extend(self.project_path.glob(pattern))
        
        # Filter out the requirements file itself and common exclusions
        excluded_patterns = {
            'requirements.md', 'CHANGELOG.md', 'LICENSE.md', 'node_modules', 
            '.git', '__pycache__', '.pytest_cache'
        }
        
        filtered_files = []
        for file_path in md_files:
            relative_path = file_path.relative_to(self.project_path)
            if not any(pattern in str(relative_path) for pattern in excluded_patterns):
                filtered_files.append(file_path)
        
        # Extract requirements using the existing aggregator
        all_requirements = []
        current_commit = self.git.get_current_commit()
        
        for file_path in filtered_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                extracted = self.aggregator.extract_requirements(content, file_path)
                
                # Convert ExtractedRequirement to RequirementRecord
                for ext_req in extracted:
                    req_record = self._convert_extracted_to_record(
                        ext_req, current_commit, RequirementSource.DOCUMENTATION
                    )
                    all_requirements.append(req_record)
                    
            except Exception as e:
                print(f"Warning: Failed to process {file_path}: {e}")
        
        return all_requirements
    
    def discover_requirements_from_git_changes(self, since_commit: str) -> List[RequirementRecord]:
        """Discover requirements from git changes since a specific commit."""
        requirements = []
        current_commit = self.git.get_current_commit()
        
        # Handle case where there are no commits yet
        if current_commit == "0000000000000000000000000000000000000000":
            return []
        
        # Get changed files
        changed_files = self.git.get_changed_files_since_commit(since_commit)
        
        # Analyze commit messages
        commit_messages = self.git.get_commit_messages_since(since_commit)
        commit_requirements = self.git.extract_requirements_from_commit_messages(commit_messages)
        
        # Convert commit message requirements
        for req_text in commit_requirements:
            req_record = RequirementRecord(
                id="",  # Will be assigned later
                ears_format=self._convert_to_ears_format(req_text),
                original_text=req_text,
                status=RequirementStatus.SUPPORTED,
                source_type=RequirementSource.COMMIT_MESSAGE,
                source_location="git commit messages",
                added_date=datetime.now(),
                added_commit=current_commit,
                last_verified_date=datetime.now(),
                last_verified_commit=current_commit
            )
            requirements.append(req_record)
        
        # Analyze file diffs for requirements
        for file_change in changed_files:
            if file_change.is_markdown or file_change.is_source_code:
                diff_content = self.git.get_file_diff_since_commit(file_change.file_path, since_commit)
                diff_requirements = extract_requirements_from_diff(diff_content)
                
                for req_text in diff_requirements:
                    req_record = RequirementRecord(
                        id="",  # Will be assigned later
                        ears_format=self._convert_to_ears_format(req_text),
                        original_text=req_text,
                        status=RequirementStatus.SUPPORTED,
                        source_type=(RequirementSource.CODE_ANALYSIS if file_change.is_source_code 
                                   else RequirementSource.DOCUMENTATION),
                        source_location=f"{file_change.file_path} (diff)",
                        added_date=datetime.now(),
                        added_commit=current_commit,
                        last_verified_date=datetime.now(),
                        last_verified_commit=current_commit
                    )
                    requirements.append(req_record)
        
        return requirements
    
    def _convert_extracted_to_record(self, ext_req: ExtractedRequirement, 
                                   commit: str, source_type: RequirementSource) -> RequirementRecord:
        """Convert ExtractedRequirement to RequirementRecord."""
        # Convert to EARS format if needed
        ears_format = ext_req.text
        if ext_req.requirement_type != RequirementType.EARS:
            if ext_req.requirement_type == RequirementType.USER_STORY:
                ears_format = self.aggregator._convert_user_story_to_ears(ext_req.text)
            else:
                ears_format = self.aggregator._convert_to_ears(ext_req.text)
        
        return RequirementRecord(
            id="",  # Will be assigned later
            ears_format=ears_format,
            original_text=ext_req.text,
            status=RequirementStatus.SUPPORTED,
            source_type=source_type,
            source_location=f"{ext_req.source_file.name}:{ext_req.line_number}",
            added_date=datetime.now(),
            added_commit=commit,
            last_verified_date=datetime.now(),
            last_verified_commit=commit
        )
    
    def _convert_to_ears_format(self, text: str) -> str:
        """Convert general text to EARS format using the aggregator."""
        return self.aggregator._convert_to_ears(text)
    
    def perform_incremental_scan(self) -> RequirementsChangeSet:
        """Perform an incremental requirements scan since the last scan."""
        # Load existing requirements
        existing_requirements = self._load_existing_requirements()
        
        # Check if this is effectively a first scan
        current_commit = self.git.get_current_commit()
        if current_commit == "0000000000000000000000000000000000000000":
            # No commits yet - treat as first scan
            return self.perform_first_scan()
        
        # Discover new requirements from changes
        new_from_git = self.discover_requirements_from_git_changes(self.metadata.last_scan_commit)
        
        # Assign IDs to new requirements
        for req in new_from_git:
            req.id = self._generate_next_requirement_id(existing_requirements)
            existing_requirements[req.id] = req
        
        # Create changeset
        changeset = RequirementsChangeSet(
            added_requirements=new_from_git,
            from_commit=self.metadata.last_scan_commit,
            to_commit=current_commit,
            scan_date=datetime.now()
        )
        
        return changeset
    
    def perform_first_scan(self) -> RequirementsChangeSet:
        """Perform the first requirements scan for a project."""
        # For first scan, only look at documentation
        doc_requirements = self.discover_requirements_from_documentation()
        
        # Assign IDs
        existing_requirements = {}
        for i, req in enumerate(doc_requirements, 1):
            req.id = f"REQ-{i:03d}"
            existing_requirements[req.id] = req
        
        # Create changeset for initial scan
        changeset = RequirementsChangeSet(
            added_requirements=doc_requirements,
            from_commit="initial",
            to_commit="initial",  # No commits yet
            scan_date=datetime.now()
        )
        
        return changeset
    
    def perform_full_scan(self) -> RequirementsChangeSet:
        """Perform a full requirements scan of the project."""
        # Check if this is a repository with no commits
        current_commit = self.git.get_current_commit()
        if current_commit == "0000000000000000000000000000000000000000":
            return self.perform_first_scan()
        
        # Discover all requirements from documentation
        doc_requirements = self.discover_requirements_from_documentation()
        
        # Assign IDs
        existing_requirements = {}
        for i, req in enumerate(doc_requirements, 1):
            req.id = f"REQ-{i:03d}"
            existing_requirements[req.id] = req
        
        # Create changeset
        changeset = RequirementsChangeSet(
            added_requirements=doc_requirements,
            from_commit="initial",
            to_commit=current_commit,
            scan_date=datetime.now()
        )
        
        return changeset
    
    def update_metadata(self, changeset: RequirementsChangeSet) -> None:
        """Update metadata after a scan."""
        self.metadata.last_scan_commit = changeset.to_commit
        self.metadata.last_scan_date = changeset.scan_date
        self.metadata.total_requirements += len(changeset.added_requirements)
        
        # Update statistics
        for req in changeset.added_requirements:
            status_key = req.status.value
            source_key = req.source_type.value
            
            self.metadata.requirements_by_status[status_key] = (
                self.metadata.requirements_by_status.get(status_key, 0) + 1
            )
            self.metadata.requirements_by_source[source_key] = (
                self.metadata.requirements_by_source.get(source_key, 0) + 1
            )
        
        self._save_metadata()
    
    def is_first_scan(self) -> bool:
        """Check if this is the first requirements scan for the project."""
        return not self.requirements_file.exists() or self.metadata.total_requirements == 0