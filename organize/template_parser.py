"""
Template parser for directory structure parsing.

This module provides functionality to parse directory structure templates
from markdown files and extract directory organization rules.
"""

import re
from pathlib import Path
from typing import Dict, Any, List

try:
    from .models import ParsedTemplate, TemplateParsingError
except ImportError:
    from requirements.models import ParsedTemplate, TemplateParsingError


class TemplateParser:
    """Parser for directory structure templates."""
    
    def __init__(self):
        """Initialize the template parser."""
        self.default_file_placement_rules = {
            "features": "aimarkdowns/features",
            "fixes": "aimarkdowns/fixes", 
            "reference": "aimarkdowns/reference",
            "resources": "aimarkdowns/resources"
        }
    
    def parse_template_file(self, template_file: Path) -> ParsedTemplate:
        """
        Parse a template file and return a ParsedTemplate object.
        
        Args:
            template_file: Path to the template file to parse
            
        Returns:
            ParsedTemplate object containing parsed structure and rules
            
        Raises:
            TemplateParsingError: If template parsing fails
        """
        try:
            if not template_file.exists():
                raise TemplateParsingError(f"Template file not found: {template_file}")
            
            content = template_file.read_text(encoding='utf-8')
            directory_structure = self.extract_directory_structure(content)
            file_placement_rules = self.parse_file_placement_rules(content)
            metadata = self._extract_metadata(content)
            
            return ParsedTemplate(
                template_name=template_file.stem,
                directory_structure=directory_structure,
                file_placement_rules=file_placement_rules,
                metadata=metadata
            )
            
        except Exception as e:
            if isinstance(e, TemplateParsingError):
                raise
            raise TemplateParsingError(f"Failed to parse template file {template_file}: {str(e)}")
    
    def extract_directory_structure(self, content: str) -> Dict[str, Any]:
        """
        Parse directory structure from path list format (in templates/directory.md).
        
        Args:
            content: Raw markdown content containing directory structure
            
        Returns:
            Nested dictionary representing directory structure
        """
        lines = content.strip().split('\n')
        structure = {}
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Remove trailing slash and split path
            path = line.rstrip('/')
            parts = path.split('/')
            
            # Build nested structure
            current = structure
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # Last part - directory (since our template only has directories)
                    if part not in current:
                        current[part] = {}
                else:
                    # Intermediate directory
                    if part not in current:
                        current[part] = {}
                    current = current[part]
        
        return structure
    
    def parse_file_placement_rules(self, content: str) -> Dict[str, str]:
        """
        Extract file categorization rules from template content.
        
        Args:
            content: Raw markdown content
            
        Returns:
            Dictionary mapping file categories to target directories
        """
        rules = self.default_file_placement_rules.copy()
        
        # Look for explicit file placement rules in comments or sections
        placement_patterns = [
            r'#\s*File\s+Placement\s*Rules?\s*\n(.*?)(?=\n#|\Z)',
            r'#\s*How\s+to\s+organize\s*\n(.*?)(?=\n#|\Z)',
            r'<!--\s*PLACEMENT\s*RULES\s*\n(.*?)\n\s*-->',
        ]
        
        for pattern in placement_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                rules_section = match.group(1)
                extracted_rules = self._parse_placement_rules_section(rules_section)
                rules.update(extracted_rules)
                break
        
        # Infer rules from directory structure if no explicit rules found
        explicit_rules_found = rules != self.default_file_placement_rules
        if not explicit_rules_found:
            inferred_rules = self._infer_placement_rules_from_structure(content)
            rules.update(inferred_rules)
        
        return rules
    
    def _parse_placement_rules_section(self, rules_section: str) -> Dict[str, str]:
        """Parse explicit file placement rules from a section."""
        rules = {}
        
        # Look for patterns like "features -> aimarkdowns/features"
        rule_patterns = [
            r'(\w+)\s*->\s*([^\n\r]+)',
            r'(\w+)\s*:\s*([^\n\r]+)',
            r'(\w+)\s*=\s*([^\n\r]+)',
        ]
        
        for pattern in rule_patterns:
            matches = re.findall(pattern, rules_section, re.IGNORECASE)
            for category, target in matches:
                rules[category.strip().lower()] = target.strip()
        
        return rules
    
    def _infer_placement_rules_from_structure(self, content: str) -> Dict[str, str]:
        """Infer file placement rules from directory structure."""
        rules = {}
        
        # Extract directory structure
        structure = self.extract_directory_structure(content)
        
        # Look for common directory patterns
        flat_paths = self._flatten_structure_paths(structure)
        
        for path in flat_paths:
            path_lower = path.lower()
            if 'feature' in path_lower:
                rules['features'] = path
            elif 'fix' in path_lower or 'bug' in path_lower:
                rules['fixes'] = path
            elif 'reference' in path_lower or 'ref' in path_lower:
                rules['reference'] = path
            elif 'resource' in path_lower:
                rules['resources'] = path
        
        return rules
    
    def _flatten_structure_paths(self, structure: Dict[str, Any], prefix: str = "") -> List[str]:
        """Flatten nested structure to list of paths."""
        paths = []
        
        for key, value in structure.items():
            current_path = f"{prefix}/{key}" if prefix else key
            
            if isinstance(value, dict):
                paths.append(current_path)
                paths.extend(self._flatten_structure_paths(value, current_path))
        
        return paths
    
    def _extract_metadata(self, content: str) -> Dict[str, str]:
        """Extract metadata from template content."""
        metadata = {}
        
        # Look for metadata in comments
        metadata_patterns = [
            r'<!--\s*TEMPLATE\s*:\s*([^\n]+)\s*-->',
            r'<!--\s*VERSION\s*:\s*([^\n]+)\s*-->',
            r'<!--\s*DESCRIPTION\s*:\s*([^\n]+)\s*-->',
        ]
        
        for pattern in metadata_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                key = pattern.split('\\s*')[1].lower()
                metadata[key] = match.group(1).strip()
        
        # Extract description from first comment or header
        desc_match = re.search(r'^#\s*(.+)$', content, re.MULTILINE)
        if desc_match and 'description' not in metadata:
            metadata['description'] = desc_match.group(1).strip()
        
        return metadata
    