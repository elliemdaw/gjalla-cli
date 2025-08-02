"""
Requirements aggregator for extracting and processing requirements from documentation.

This module provides functionality to extract requirements from markdown documents,
classify them by type (EARS, general, user stories), and aggregate them into a
standardized format.
"""

import re
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from organize.models import (
    ExtractedRequirement, RequirementsAggregate, RequirementType,
    DiscoveredDocument, RequirementsExtractionError
)


# TODO check Kiro community, docs, website, etc to see if they link to any tooling for parsing the EARS format requirements or anything else.
class RequirementsAggregator:
    """
    Aggregates and processes requirements from discovered documentation files.
    
    This class provides methods to extract requirements from markdown content,
    classify them by type, format them in EARS format, and deduplicate similar
    requirements.
    """
    
    def __init__(self):
        """Initialize the requirements aggregator with pattern matchers."""
        self._ears_patterns = [
            # WHEN ... THEN ... SHALL pattern
            re.compile(r'WHEN\s+(.+?)\s+THEN\s+(.+?)\s+SHALL\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
            # IF ... THEN ... SHALL pattern  
            re.compile(r'IF\s+(.+?)\s+THEN\s+(.+?)\s+SHALL\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
            # GIVEN ... WHEN ... THEN pattern
            re.compile(r'GIVEN\s+(.+?)\s+WHEN\s+(.+?)\s+THEN\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
        ]
        
        self._general_requirement_patterns = [
            # Must/shall/should patterns
            re.compile(r'(?:system|application|feature|component|user)\s+(?:must|shall|should|will)\s+(.+?)(?:\.|$)', re.IGNORECASE),
            re.compile(r'(?:must|shall|should|will)\s+(?:be able to|support|provide|allow|enable)\s+(.+?)(?:\.|$)', re.IGNORECASE),
            re.compile(r'(?:it|this)\s+(?:must|shall|should|will)\s+(.+?)(?:\.|$)', re.IGNORECASE),
        ]
        
        self._user_story_patterns = [
            # As a ... I want ... so that pattern
            re.compile(r'As\s+a\s+(.+?),?\s+I\s+want\s+(.+?),?\s+so\s+that\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
            # As an ... I need ... to pattern
            re.compile(r'As\s+an?\s+(.+?),?\s+I\s+need\s+(.+?)\s+to\s+(.+?)(?:\.|$)', re.IGNORECASE | re.DOTALL),
        ]
    
    def generate_aggregate(self, files: List[DiscoveredDocument]) -> RequirementsAggregate:
        """
        Generate an aggregate requirements document from discovered files.
        
        Args:
            files: List of discovered documentation files
            
        Returns:
            RequirementsAggregate containing all extracted and processed requirements
            
        Raises:
            RequirementsExtractionError: If extraction fails
        """
        try:
            all_requirements = []
            source_files = []
            processing_errors = []
            
            for doc in files:
                if doc.path.suffix.lower() in ['.md', '.markdown']:
                    try:
                        content = doc.path.read_text(encoding='utf-8')
                        requirements = self.extract_requirements(content, doc.path)
                        all_requirements.extend(requirements)
                        if requirements:
                            source_files.append(doc.path)
                    except UnicodeDecodeError as e:
                        error_msg = f"Failed to read {doc.path} due to encoding issues: {e}"
                        processing_errors.append(error_msg)
                        print(f"Warning: {error_msg}")
                        continue
                    except Exception as e:
                        error_msg = f"Failed to extract requirements from {doc.path}: {e}"
                        processing_errors.append(error_msg)
                        print(f"Warning: {error_msg}")
                        continue
            
            # Deduplicate requirements
            original_count = len(all_requirements)
            deduplicated_requirements = self.deduplicate_requirements(all_requirements)
            duplicates_removed = original_count - len(deduplicated_requirements)
            
            # Create the aggregate with enhanced metadata
            aggregate = RequirementsAggregate(
                requirements=deduplicated_requirements,
                total_extracted=len(deduplicated_requirements),
                duplicates_removed=duplicates_removed,
                source_files=source_files,
                generation_timestamp=datetime.now()
            )
            
            # Log summary information
            if processing_errors:
                print(f"Processed {len(files)} files with {len(processing_errors)} errors")
            
            print(f"Extracted {original_count} requirements, removed {duplicates_removed} duplicates")
            print(f"Final aggregate contains {len(deduplicated_requirements)} unique requirements")
            
            return aggregate
            
        except Exception as e:
            raise RequirementsExtractionError(f"Failed to generate requirements aggregate: {e}")
    
    def write_aggregate_file(self, aggregate: RequirementsAggregate, output_path: Path) -> None:
        """
        Write the requirements aggregate to a markdown file.
        
        Args:
            aggregate: The requirements aggregate to write
            output_path: Path where to write the aggregate file
            
        Raises:
            RequirementsExtractionError: If writing fails
        """
        try:
            formatted_content = self.format_as_ears(aggregate.requirements)
            
            # Ensure the output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the formatted content
            output_path.write_text(formatted_content, encoding='utf-8')
            
            print(f"Requirements aggregate written to: {output_path}")
            
        except Exception as e:
            raise RequirementsExtractionError(f"Failed to write aggregate file to {output_path}: {e}")
    
    def extract_requirements(self, content: str, file_path: Path) -> List[ExtractedRequirement]:
        """
        Extract requirements from markdown content.
        
        Args:
            content: The markdown content to analyze
            file_path: Path to the source file
            
        Returns:
            List of extracted requirements with metadata
        """
        requirements = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # Try to extract EARS format requirements
            ears_req = self._extract_ears_requirement(line, file_path, line_num)
            if ears_req:
                requirements.append(ears_req)
                continue
            
            # Try to extract general requirements
            general_req = self._extract_general_requirement(line, file_path, line_num)
            if general_req:
                requirements.append(general_req)
                continue
            
            # Try to extract user stories
            user_story = self._extract_user_story(line, file_path, line_num)
            if user_story:
                requirements.append(user_story)
        
        return requirements
    
    def _extract_ears_requirement(self, line: str, file_path: Path, line_num: int) -> Optional[ExtractedRequirement]:
        """Extract EARS format requirements from a line."""
        for pattern in self._ears_patterns:
            match = pattern.search(line)
            if match:
                # Get context (surrounding text)
                context = self._get_context(line, 50)
                
                return ExtractedRequirement(
                    text=line.strip(),
                    source_file=file_path,
                    line_number=line_num,
                    requirement_type=RequirementType.EARS,
                    context=context
                )
        return None
    
    def _extract_general_requirement(self, line: str, file_path: Path, line_num: int) -> Optional[ExtractedRequirement]:
        """Extract general requirements from a line."""
        for pattern in self._general_requirement_patterns:
            match = pattern.search(line)
            if match:
                # Get context
                context = self._get_context(line, 50)
                
                return ExtractedRequirement(
                    text=line.strip(),
                    source_file=file_path,
                    line_number=line_num,
                    requirement_type=RequirementType.GENERAL,
                    context=context
                )
        return None
    
    def _extract_user_story(self, line: str, file_path: Path, line_num: int) -> Optional[ExtractedRequirement]:
        """Extract user stories from a line."""
        for pattern in self._user_story_patterns:
            match = pattern.search(line)
            if match:
                # Get context
                context = self._get_context(line, 50)
                
                return ExtractedRequirement(
                    text=line.strip(),
                    source_file=file_path,
                    line_number=line_num,
                    requirement_type=RequirementType.USER_STORY,
                    context=context
                )
        return None
    
    def _get_context(self, line: str, max_length: int = 100) -> str:
        """Get context around a requirement (truncated if too long)."""
        if len(line) <= max_length:
            return line
        return line[:max_length-3] + "..."
    
    def format_as_ears(self, requirements: List[ExtractedRequirement]) -> str:
        """
        Format requirements in EARS format.
        
        Args:
            requirements: List of requirements to format
            
        Returns:
            Formatted requirements string in EARS format
        """
        formatted_lines = [
            "# Requirements Aggregate",
            "",
            "This document contains all requirements extracted from the project documentation,",
            "formatted in EARS (Easy Approach to Requirements Syntax) format.",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Total Requirements:** {len(requirements)}",
            "",
            "## Source Files",
            "",
        ]
        
        # Add source file information
        source_files = sorted(set(req.source_file for req in requirements))
        for source_file in source_files:
            req_count = len([r for r in requirements if r.source_file == source_file])
            formatted_lines.append(f"- {source_file.name}: {req_count} requirements")
        
        formatted_lines.extend(["", "---", ""])
        
        # Group requirements by type
        ears_reqs = [r for r in requirements if r.requirement_type == RequirementType.EARS]
        general_reqs = [r for r in requirements if r.requirement_type == RequirementType.GENERAL]
        user_stories = [r for r in requirements if r.requirement_type == RequirementType.USER_STORY]
        
        # Add EARS requirements
        if ears_reqs:
            formatted_lines.extend([
                "## EARS Format Requirements",
                "",
                "These requirements are already in EARS format:",
                "",
            ])
            for i, req in enumerate(ears_reqs, 1):
                formatted_lines.extend([
                    f"### REQ-{i:03d}",
                    "",
                    f"**Text:** {req.text}",
                    f"**Source:** {req.source_file.name}:{req.line_number}",
                    f"**Context:** {req.context}",
                    "",
                ])
        
        # Add general requirements (convert to EARS format)
        if general_reqs:
            formatted_lines.extend([
                "## General Requirements (Converted to EARS)",
                "",
                "These requirements have been converted from general statements to EARS format:",
                "",
            ])
            for i, req in enumerate(general_reqs, 1):
                ears_formatted = self._convert_to_ears(req.text)
                formatted_lines.extend([
                    f"### REQ-{len(ears_reqs) + i:03d}",
                    "",
                    f"**Original:** {req.text}",
                    f"**EARS Format:** {ears_formatted}",
                    f"**Source:** {req.source_file.name}:{req.line_number}",
                    f"**Context:** {req.context}",
                    "",
                ])
        
        # Add user stories (convert to EARS format)
        if user_stories:
            formatted_lines.extend([
                "## User Stories (Converted to EARS)",
                "",
                "These user stories have been converted to EARS format:",
                "",
            ])
            for i, req in enumerate(user_stories, 1):
                ears_formatted = self._convert_user_story_to_ears(req.text)
                formatted_lines.extend([
                    f"### REQ-{len(ears_reqs) + len(general_reqs) + i:03d}",
                    "",
                    f"**User Story:** {req.text}",
                    f"**EARS Format:** {ears_formatted}",
                    f"**Source:** {req.source_file.name}:{req.line_number}",
                    f"**Context:** {req.context}",
                    "",
                ])
        
        # Add summary statistics
        formatted_lines.extend([
            "---",
            "",
            "## Summary",
            "",
            f"- **Total Requirements:** {len(requirements)}",
            f"- **EARS Format:** {len(ears_reqs)}",
            f"- **General Requirements:** {len(general_reqs)}",
            f"- **User Stories:** {len(user_stories)}",
            f"- **Source Files:** {len(source_files)}",
            "",
            f"**Generated on:** {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}",
        ])
        
        return "\n".join(formatted_lines)
    
    def _convert_to_ears(self, text: str) -> str:
        """Convert a general requirement to EARS format."""
        # Simple conversion - this could be enhanced with more sophisticated logic
        if "must" in text.lower() or "shall" in text.lower():
            return f"WHEN [condition] THEN the system SHALL {text.lower().replace('must', '').replace('shall', '').strip()}"
        elif "should" in text.lower():
            return f"WHEN [condition] THEN the system SHOULD {text.lower().replace('should', '').strip()}"
        else:
            return f"WHEN [condition] THEN the system SHALL {text.strip()}"
    
    def _convert_user_story_to_ears(self, text: str) -> str:
        """Convert a user story to EARS format."""
        # Extract components from user story
        user_story_match = re.search(r'As\s+a\s+(.+?),?\s+I\s+want\s+(.+?),?\s+so\s+that\s+(.+?)(?:\.|$)', text, re.IGNORECASE)
        if user_story_match:
            role, want, benefit = user_story_match.groups()
            return f"WHEN a {role.strip()} requests functionality THEN the system SHALL {want.strip()} so that {benefit.strip()}"
        else:
            return f"WHEN [user action] THEN the system SHALL support the user story: {text}"
    
    def deduplicate_requirements(self, requirements: List[ExtractedRequirement]) -> List[ExtractedRequirement]:
        """
        Remove duplicate requirements using similarity analysis.
        
        Args:
            requirements: List of requirements to deduplicate
            
        Returns:
            List of unique requirements
        """
        if not requirements:
            return []
        
        unique_requirements = []
        seen_texts = set()
        
        for req in requirements:
            # Normalize text for comparison
            normalized_text = self._normalize_text(req.text)
            
            # Check for exact duplicates first
            if normalized_text in seen_texts:
                continue
            
            # Check for similar requirements
            is_similar = False
            for existing_req in unique_requirements:
                if self._are_similar(req.text, existing_req.text):
                    is_similar = True
                    break
            
            if not is_similar:
                unique_requirements.append(req)
                seen_texts.add(normalized_text)
        
        return unique_requirements
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Remove extra whitespace, convert to lowercase, remove punctuation
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return normalized
    
    def _are_similar(self, text1: str, text2: str, threshold: float = 0.8) -> bool:
        """
        Check if two requirement texts are similar using simple similarity measure.
        
        Args:
            text1: First text to compare
            text2: Second text to compare
            threshold: Similarity threshold (0.0 to 1.0)
            
        Returns:
            True if texts are similar above threshold
        """
        # Normalize both texts
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        # Simple word-based similarity
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return False
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0.0
        return similarity >= threshold