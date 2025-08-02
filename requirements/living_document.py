"""
Living requirements document management.

This module provides functionality to maintain and update the aimarkdowns/requirements.md
file as a living document that tracks all project requirements.
"""

from typing import List, Optional
from pathlib import Path
from datetime import datetime
import re

from .models import RequirementRecord, RequirementsChangeSet, RequirementStatus


class LivingRequirementsDocument:
    """
    Manages the living requirements document (aimarkdowns/requirements.md).
    
    This class handles reading, writing, and updating the markdown file
    that serves as the authoritative source for project requirements.
    """
    
    def __init__(self, file_path: Path):
        """Initialize the living document manager."""
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def exists(self) -> bool:
        """Check if the requirements document exists."""
        return self.file_path.exists()
    
    def create_initial_document(self, requirements: List[RequirementRecord], 
                              project_name: Optional[str] = None) -> None:
        """Create the initial requirements document."""
        project_name = project_name or self.file_path.parent.parent.name
        
        content = self._generate_document_header(project_name)
        content += self._generate_requirements_sections(requirements)
        content += self._generate_document_footer(requirements)
        
        self.file_path.write_text(content, encoding='utf-8')
    
    def update_document(self, changeset: RequirementsChangeSet, 
                       all_requirements: List[RequirementRecord]) -> None:
        """Update the document with a changeset."""
        if not self.exists():
            self.create_initial_document(all_requirements)
            return
        
        # For now, regenerate the entire document
        # TODO: In the future, we could implement smarter partial updates
        content = self.file_path.read_text(encoding='utf-8')
        
        # Extract the header (everything before the first requirement)
        header_match = re.search(r'^(.*?)(?=\n## REQ-\d+:)', content, re.DOTALL)
        header = header_match.group(1) if header_match else self._generate_document_header()
        
        # Regenerate the document
        new_content = header
        new_content += self._generate_requirements_sections(all_requirements)
        new_content += self._generate_document_footer(all_requirements)
        
        self.file_path.write_text(new_content, encoding='utf-8')
    
    def _generate_document_header(self, project_name: Optional[str] = None) -> str:
        """Generate the document header section."""
        project_name = project_name or "Project"
        
        return f"""# {project_name} Requirements

This is a living document that tracks all requirements discovered in the project. 
Requirements are automatically extracted from documentation, code, and commit messages,
then formatted in EARS (Easy Approach to Requirements Syntax) format.

**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Status Legend

- ✅ **Supported**: Requirement is implemented and working
- ⚠️ **Deprecated**: Requirement is deprecated but still functional  
- ❌ **Removed**: Requirement is no longer supported
- ❓ **Unknown**: Status cannot be determined

## Source Types

- **documentation**: Found in markdown documentation files
- **code_analysis**: Inferred from code structure and comments
- **commit_message**: Extracted from git commit messages
- **manual**: Manually added requirements

---

"""
    
    def _generate_requirements_sections(self, requirements: List[RequirementRecord]) -> str:
        """Generate the requirements sections."""
        if not requirements:
            return "## No Requirements Found\n\nNo requirements have been discovered yet.\n\n"
        
        # Sort requirements by ID
        sorted_requirements = sorted(requirements, key=lambda r: r.id)
        
        # Group by status for better organization
        implemented = [r for r in sorted_requirements if r.status == RequirementStatus.IMPLEMENTED]
        in_progress = [r for r in sorted_requirements if r.status == RequirementStatus.IN_PROGRESS]
        todo = [r for r in sorted_requirements if r.status == RequirementStatus.TODO]
        deprecated = [r for r in sorted_requirements if r.status == RequirementStatus.DEPRECATED]
        removed = [r for r in sorted_requirements if r.status == RequirementStatus.REMOVED]
        unknown = [r for r in sorted_requirements if r.status == RequirementStatus.UNKNOWN]
        
        content = ""
        
        # Add implemented requirements first  
        if implemented:
            content += "## Implemented Requirements\n\n"
            for req in implemented:
                content += req.to_markdown_section() + "\n"
        
        # Then in progress
        if in_progress:
            content += "## In Progress Requirements\n\n"
            for req in in_progress:
                content += req.to_markdown_section() + "\n"
                
        # Then todo
        if todo:
            content += "## Todo Requirements\n\n"
            for req in todo:
                content += req.to_markdown_section() + "\n"
        
        # Then deprecated
        if deprecated:
            content += "## Deprecated Requirements\n\n"
            for req in deprecated:
                content += req.to_markdown_section() + "\n"
        
        # Then removed
        if removed:
            content += "## Removed Requirements\n\n"
            for req in removed:
                content += req.to_markdown_section() + "\n"
        
        # Finally unknown
        if unknown:
            content += "## Requirements with Unknown Status\n\n"
            for req in unknown:
                content += req.to_markdown_section() + "\n"
        
        return content
    
    def _generate_document_footer(self, requirements: List[RequirementRecord]) -> str:
        """Generate the document footer with statistics."""
        if not requirements:
            return ""
        
        # Calculate statistics
        stats = {
            'total': len(requirements),
            'supported': len([r for r in requirements if r.status == RequirementStatus.SUPPORTED]),
            'deprecated': len([r for r in requirements if r.status == RequirementStatus.DEPRECATED]),
            'removed': len([r for r in requirements if r.status == RequirementStatus.REMOVED]),
            'unknown': len([r for r in requirements if r.status == RequirementStatus.UNKNOWN])
        }
        
        # Source statistics
        source_stats = {}
        for req in requirements:
            source = req.source_type.value
            source_stats[source] = source_stats.get(source, 0) + 1
        
        # Age statistics
        ages = [req.age_days for req in requirements]
        avg_age = sum(ages) / len(ages) if ages else 0
        oldest_req = max(requirements, key=lambda r: r.age_days) if requirements else None
        newest_req = min(requirements, key=lambda r: r.age_days) if requirements else None
        
        content = """---

## Document Statistics

### Status Summary
"""
        
        content += f"- **Total Requirements**: {stats['total']}\n"
        if stats['supported']:
            content += f"- **✅ Supported**: {stats['supported']} ({stats['supported']/stats['total']*100:.1f}%)\n"
        if stats['deprecated']:
            content += f"- **⚠️ Deprecated**: {stats['deprecated']} ({stats['deprecated']/stats['total']*100:.1f}%)\n"
        if stats['removed']:
            content += f"- **❌ Removed**: {stats['removed']} ({stats['removed']/stats['total']*100:.1f}%)\n"
        if stats['unknown']:
            content += f"- **❓ Unknown**: {stats['unknown']} ({stats['unknown']/stats['total']*100:.1f}%)\n"
        
        content += "\n### Source Summary\n"
        for source, count in sorted(source_stats.items()):
            percentage = count / stats['total'] * 100
            content += f"- **{source.replace('_', ' ').title()}**: {count} ({percentage:.1f}%)\n"
        
        content += "\n### Age Summary\n"
        content += f"- **Average Age**: {avg_age:.1f} days\n"
        if oldest_req:
            content += f"- **Oldest Requirement**: {oldest_req.id} ({oldest_req.age_days} days)\n"
        if newest_req:
            content += f"- **Newest Requirement**: {newest_req.id} ({newest_req.age_days} days)\n"
        
        content += f"\n---\n\n*Document generated automatically by gjalla requirements tracker on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}*\n"
        
        return content
    
    def _parse_requirement_section(self, req_id: str, content: str) -> Optional[RequirementRecord]:
        """Parse a requirement section from markdown content."""
        # This is similar to the method in RequirementsTracker, but simpler
        lines = content.strip().split('\n')
        
        metadata = {}
        ears_format = ""
        
        for line in lines:
            line = line.strip()
            if line.startswith('**EARS Format**:'):
                ears_format = line.split(':', 1)[1].strip()
            elif line.startswith('**Status**:'):
                status_text = line.split(':', 1)[1].strip()
                if '✅ Implemented' in status_text:
                    metadata['status'] = RequirementStatus.IMPLEMENTED
                elif '🚧 In_Progress' in status_text:
                    metadata['status'] = RequirementStatus.IN_PROGRESS
                elif '📝 Todo' in status_text:
                    metadata['status'] = RequirementStatus.TODO
                elif '⚠️' in status_text:
                    metadata['status'] = RequirementStatus.DEPRECATED
                elif '❌' in status_text:
                    metadata['status'] = RequirementStatus.REMOVED
                else:
                    metadata['status'] = RequirementStatus.UNKNOWN
            elif line.startswith('**Source**:'):
                metadata['source_location'] = line.split(':', 1)[1].strip()
            elif line.startswith('**Added**:'):
                added_text = line.split(':', 1)[1].strip()
                if '(' in added_text:
                    date_part, commit_part = added_text.split('(', 1)
                    try:
                        metadata['added_date'] = datetime.strptime(date_part.strip(), '%Y-%m-%d')
                        metadata['added_commit'] = commit_part.rstrip(')').strip()
                    except ValueError:
                        pass  # Skip if date parsing fails
        
        if not ears_format or 'status' not in metadata:
            return None
        
        from .models import RequirementSource
        
        try:
            return RequirementRecord(
                id=req_id,
                ears_format=ears_format,
                original_text=ears_format,
                status=metadata['status'],
                source_type=RequirementSource.DOCUMENTATION,  # Default
                source_location=metadata.get('source_location', 'unknown'),
                added_date=metadata.get('added_date', datetime.now()),
                added_commit=metadata.get('added_commit', 'unknown'),
                last_verified_date=datetime.now(),
                last_verified_commit='current'
            )
        except Exception:
            return None
    
    def get_all_requirements(self) -> List[RequirementRecord]:
        """Get all requirements from the document."""
        if not self.exists():
            return []
        
        content = self.file_path.read_text(encoding='utf-8')
        requirements = []
        
        # Find all requirement sections (including sub-requirements like REQ-1.1)
        pattern = r'\n## (REQ-[\d\.]+):.*?\n(.*?)(?=\n## REQ-[\d\.]+:|---|\Z)'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            req_id = match.group(1)
            section_content = match.group(2)
            
            req = self._parse_requirement_section(req_id, section_content)
            if req:
                requirements.append(req)
        
        return requirements