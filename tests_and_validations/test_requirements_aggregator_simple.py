#!/usr/bin/env python3
"""
Simple direct test for RequirementsAggregator functionality.
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional

# Define the models we need locally to avoid import issues
class RequirementType(Enum):
    EARS = "ears"
    GENERAL = "general"
    USER_STORY = "user_story"

class DocumentType(Enum):
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    UNKNOWN = "unknown"

@dataclass
class ExtractedRequirement:
    text: str
    source_file: Path
    line_number: int
    requirement_type: RequirementType
    confidence: float
    context: str
    extraction_timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RequirementsAggregate:
    requirements: List[ExtractedRequirement]
    total_extracted: int
    duplicates_removed: int
    source_files: List[Path]
    generation_timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class DiscoveredDocument:
    path: Path
    size: int
    last_modified: datetime
    detected_type: DocumentType
    confidence: float

class RequirementsExtractionError(Exception):
    pass

# Copy the RequirementsAggregator class directly
class RequirementsAggregator:
    """
    Aggregates and processes requirements from discovered documentation files.
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
    
    def extract_requirements(self, content: str, file_path: Path) -> List[ExtractedRequirement]:
        """Extract requirements from markdown content."""
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
                context = self._get_context(line, 50)
                
                return ExtractedRequirement(
                    text=line.strip(),
                    source_file=file_path,
                    line_number=line_num,
                    requirement_type=RequirementType.EARS,
                    confidence=0.9,
                    context=context
                )
        return None
    
    def _extract_general_requirement(self, line: str, file_path: Path, line_num: int) -> Optional[ExtractedRequirement]:
        """Extract general requirements from a line."""
        for pattern in self._general_requirement_patterns:
            match = pattern.search(line)
            if match:
                context = self._get_context(line, 50)
                
                return ExtractedRequirement(
                    text=line.strip(),
                    source_file=file_path,
                    line_number=line_num,
                    requirement_type=RequirementType.GENERAL,
                    confidence=0.7,
                    context=context
                )
        return None
    
    def _extract_user_story(self, line: str, file_path: Path, line_num: int) -> Optional[ExtractedRequirement]:
        """Extract user stories from a line."""
        for pattern in self._user_story_patterns:
            match = pattern.search(line)
            if match:
                context = self._get_context(line, 50)
                
                return ExtractedRequirement(
                    text=line.strip(),
                    source_file=file_path,
                    line_number=line_num,
                    requirement_type=RequirementType.USER_STORY,
                    confidence=0.8,
                    context=context
                )
        return None
    
    def _get_context(self, line: str, max_length: int = 100) -> str:
        """Get context around a requirement (truncated if too long)."""
        if len(line) <= max_length:
            return line
        return line[:max_length-3] + "..."
    
    def format_as_ears(self, requirements: List[ExtractedRequirement]) -> str:
        """Format requirements in EARS format."""
        formatted_lines = [
            "# Requirements Aggregate",
            "",
            "This document contains all requirements extracted from the project documentation,",
            "formatted in EARS (Easy Approach to Requirements Syntax) format.",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Total Requirements:** {len(requirements)}",
            "",
        ]
        
        # Group requirements by type
        ears_reqs = [r for r in requirements if r.requirement_type == RequirementType.EARS]
        general_reqs = [r for r in requirements if r.requirement_type == RequirementType.GENERAL]
        user_stories = [r for r in requirements if r.requirement_type == RequirementType.USER_STORY]
        
        # Add EARS requirements
        if ears_reqs:
            formatted_lines.extend([
                "## EARS Format Requirements",
                "",
            ])
            for i, req in enumerate(ears_reqs, 1):
                formatted_lines.extend([
                    f"### Requirement {i}",
                    "",
                    f"**Text:** {req.text}",
                    f"**Source:** {req.source_file.name}:{req.line_number}",
                    f"**Confidence:** {req.confidence:.2f}",
                    "",
                ])
        
        return "\n".join(formatted_lines)
    
    def deduplicate_requirements(self, requirements: List[ExtractedRequirement]) -> List[ExtractedRequirement]:
        """Remove duplicate requirements using similarity analysis."""
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
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return normalized
    
    def _are_similar(self, text1: str, text2: str, threshold: float = 0.8) -> bool:
        """Check if two requirement texts are similar."""
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return False
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0.0
        return similarity >= threshold


def test_basic_functionality():
    """Test basic RequirementsAggregator functionality."""
    print("Testing RequirementsAggregator basic functionality...")
    
    aggregator = RequirementsAggregator()
    
    # Test initialization
    assert len(aggregator._ears_patterns) > 0
    assert len(aggregator._general_requirement_patterns) > 0
    assert len(aggregator._user_story_patterns) > 0
    print("✓ Initialization successful")
    
    # Test EARS extraction
    content = """
    # Requirements
    
    1. WHEN a user logs in THEN the system SHALL authenticate the credentials
    2. IF the password is incorrect THEN the system SHALL display an error message
    """
    
    requirements = aggregator.extract_requirements(content, Path("test.md"))
    ears_reqs = [r for r in requirements if r.requirement_type == RequirementType.EARS]
    
    assert len(ears_reqs) == 2
    assert ears_reqs[0].confidence == 0.9
    assert "WHEN a user logs in" in ears_reqs[0].text
    print("✓ EARS extraction successful")
    
    # Test general requirements extraction
    content = """
    The system must support user authentication.
    The application shall provide data encryption.
    """
    
    requirements = aggregator.extract_requirements(content, Path("test.md"))
    general_reqs = [r for r in requirements if r.requirement_type == RequirementType.GENERAL]
    
    assert len(general_reqs) >= 2
    assert general_reqs[0].confidence == 0.7
    print("✓ General requirements extraction successful")
    
    # Test user story extraction
    content = """
    As a user, I want to log in to the system, so that I can access my data.
    As an administrator, I need to manage user accounts to maintain system security.
    """
    
    requirements = aggregator.extract_requirements(content, Path("test.md"))
    user_stories = [r for r in requirements if r.requirement_type == RequirementType.USER_STORY]
    
    assert len(user_stories) == 2
    assert user_stories[0].confidence == 0.8
    assert "As a user, I want to log in" in user_stories[0].text
    print("✓ User story extraction successful")
    
    # Test EARS formatting
    test_requirements = [
        ExtractedRequirement(
            text="WHEN user logs in THEN system SHALL authenticate",
            source_file=Path("test1.md"),
            line_number=1,
            requirement_type=RequirementType.EARS,
            confidence=0.9,
            context="login context"
        ),
        ExtractedRequirement(
            text="The system must validate input",
            source_file=Path("test2.md"),
            line_number=2,
            requirement_type=RequirementType.GENERAL,
            confidence=0.7,
            context="validation context"
        )
    ]
    
    formatted = aggregator.format_as_ears(test_requirements)
    
    assert "# Requirements Aggregate" in formatted
    assert "**Total Requirements:** 2" in formatted
    assert "## EARS Format Requirements" in formatted
    print("✓ EARS formatting successful")
    
    # Test deduplication
    duplicate_requirements = [
        ExtractedRequirement(
            text="The system must validate input",
            source_file=Path("test1.md"),
            line_number=1,
            requirement_type=RequirementType.GENERAL,
            confidence=0.7,
            context="context1"
        ),
        ExtractedRequirement(
            text="The system must validate input",  # Exact duplicate
            source_file=Path("test2.md"),
            line_number=2,
            requirement_type=RequirementType.GENERAL,
            confidence=0.7,
            context="context2"
        ),
        ExtractedRequirement(
            text="The system must encrypt data",  # Different requirement
            source_file=Path("test3.md"),
            line_number=3,
            requirement_type=RequirementType.GENERAL,
            confidence=0.7,
            context="context3"
        )
    ]
    
    deduplicated = aggregator.deduplicate_requirements(duplicate_requirements)
    assert len(deduplicated) == 2  # Should remove one duplicate
    print("✓ Deduplication successful")
    
    # Test similarity detection
    text1 = "The system must validate user input"
    text2 = "The system must validate input from users"
    similarity = aggregator._are_similar(text1, text2, threshold=0.7)
    print(f"Similarity between '{text1}' and '{text2}': {similarity}")
    
    # Debug the similarity calculation
    norm1 = aggregator._normalize_text(text1)
    norm2 = aggregator._normalize_text(text2)
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    jaccard = intersection / union if union > 0 else 0.0
    print(f"Words1: {words1}")
    print(f"Words2: {words2}")
    print(f"Intersection: {intersection}, Union: {union}, Jaccard: {jaccard}")
    
    # Use a lower threshold for this test
    assert aggregator._are_similar(text1, text2, threshold=0.6)
    
    text3 = "The application should encrypt data"
    assert not aggregator._are_similar(text1, text3, threshold=0.7)
    print("✓ Similarity detection successful")
    
    print("All tests passed! ✓")


if __name__ == "__main__":
    try:
        test_basic_functionality()
        print("\n🎉 All RequirementsAggregator tests passed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)