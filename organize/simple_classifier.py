"""
Simple NLP-based file classifier for name-only reorganization.

This module provides NLP-enhanced file classification capabilities using spaCy
for semantic understanding of filenames and categorization.
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging

try:
    from .models import ClassifiedFile, ClassificationError
except ImportError:
    # Fallback for direct execution
    from requirements.models import ClassifiedFile, ClassificationError

# Optional NLP dependencies
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

logger = logging.getLogger(__name__)


# Enhanced NLP patterns with high-confidence classification capabilities
NLP_CLASSIFICATION_PATTERNS = {
    "features": {
        "entities": ["PRODUCT", "ORG", "MONEY", "PERCENT"],  # Product names, organizations, metrics
        "pos_patterns": ["NOUN", "VERB", "ADJ"],  # Action-oriented and descriptive language
        "high_confidence_keywords": ["user_story", "user_stories", "feature_spec", "feature_specification", "requirements", "user_requirements", "acceptance_criteria", "user_acceptance", "feature_design", "functional_spec", "service", "roadmap", "architecture", "design", "flow"],
        "keywords": ["feature", "functionality", "requirement", "specification", "user story", "capability", "summary", "status", "phase", "contract", "product", "implementation", "plan", "design", "flow", "advanced", "epic", "story", "acceptance", "criteria", "persona", "journey", "workflow", "usecase", "scenario", "integration", "support", "usage", "instructions", "improvements", "setup", "streamlined", "enhancement", "migration", "demo"],
        "sentence_patterns": [
            r"as a .* i want",  # User story pattern
            r"the system shall",  # Requirements pattern
            r"given .* when .* then",  # BDD pattern
            r"feature:\s*",  # Feature declaration
            r"user story:\s*",  # User story declaration
            r"requirement:\s*",  # Requirement declaration
            r"acceptance criteria",  # Acceptance criteria
            r"functional requirement",  # Functional requirement
            r"the user can",  # User can pattern
        ],
        "content_patterns": [
            r"\b(user|customer|client)\s+(story|stories|requirement|need)",
            r"\b(acceptance|success)\s+criteria\b",
            r"\b(feature|functionality)\s+(specification|spec|description)\b",
            r"\b(business|functional)\s+requirement\b",
            r"\bepic:\s*",
            r"\bstory:\s*",
            r"\bas\s+a\s+.+\s+i\s+(want|need|expect)\b",
        ],
        "semantic_similarity": ["feature functionality requirement specification user story capability summary status phase contract product implementation plan design flow advanced epic acceptance criteria persona journey workflow usecase scenario"]
    },
    "fixes": {
        "entities": ["PRODUCT", "CARDINAL", "ORDINAL"],  # Bug numbers, versions, priorities
        "pos_patterns": ["VERB", "ADJ"],  # Action words and descriptive terms
        "high_confidence_keywords": ["bug_fix", "bug_report", "issue_resolution", "hotfix", "patch", "defect_report", "error_fix", "critical_fix", "urgent_fix", "production_fix"],
        "keywords": ["bug", "fix", "issue", "problem", "error", "defect", "resolved", "debug", "cleanup", "refactor", "consolidation", "patch", "hotfix", "repair", "resolve", "solution", "troubleshoot", "broken", "failure", "crash", "exception"],
        "sentence_patterns": [
            r"fixed .* bug",
            r"resolves? .*(issue|problem|bug)",
            r"error .* (occurred|fixed|resolved)",
            r"bug:\s*",  # Bug declaration
            r"issue:\s*",  # Issue declaration
            r"problem:\s*",  # Problem declaration
            r"(critical|urgent|high priority)\s+(bug|issue|fix)",
        ],
        "content_patterns": [
            r"\b(bug|issue|problem|defect)\s+(report|description|details)\b",
            r"\b(steps to reproduce|reproduction steps)\b",
            r"\b(expected|actual)\s+(behavior|result|outcome)\b",
            r"\b(error|exception|stack trace)\b",
            r"\b(workaround|temporary fix)\b",
            r"\b(root cause|cause analysis)\b",
            r"\bfixed\s+in\s+(version|release)\b",
        ],
        "semantic_similarity": ["bug fix issue problem error defect resolution debug cleanup refactor consolidation patch hotfix repair resolve solution troubleshoot broken failure crash exception"]
    },
    "reference": {
        "entities": ["PRODUCT", "ORG", "PERSON", "LOC", "DATE"],  # API names, authors, locations, dates
        "pos_patterns": ["NOUN", "ADJ"],  # Descriptive language
        "high_confidence_keywords": ["api_documentation", "user_guide", "developer_guide", "technical_reference", "architecture_overview", "system_architecture", "api_reference", "user_manual", "installation_guide", "configuration_guide", "todo"],
        "keywords": ["api", "documentation", "guide", "reference", "manual", "overview", "docs", "readme", "architecture", "technical", "installation", "configuration", "setup", "tutorial", "walkthrough", "explanation", "howto", "instructions", "glossary", "faq", "changelog", "release notes"],
        "sentence_patterns": [
            r"this document (describes|explains|covers)",
            r"api endpoint",
            r"usage example",
            r"(installation|setup|configuration)\s+(guide|instructions)",
            r"(getting started|quick start)",
            r"(user|developer|admin)\s+(guide|manual|documentation)",
        ],
        "content_patterns": [
            r"\b(api|endpoint|method|function)\s+(reference|documentation)\b",
            r"\b(installation|setup|configuration)\s+(instructions|steps|guide)\b",
            r"\b(getting started|quick start|tutorial)\b",
            r"\b(architecture|system design|technical overview)\b",
            r"\b(user|developer|administrator)\s+(guide|manual|documentation)\b",
            r"\b(changelog|release notes|version history)\b",
            r"\b(frequently asked questions|faq)\b",
        ],
        "semantic_similarity": ["documentation guide reference manual api overview docs readme architecture technical installation configuration setup tutorial walkthrough explanation howto instructions glossary faq changelog release notes"]
    }
}


class SimpleClassifier:
    """
    NLP-enhanced file classifier for filename-based classification.
    
    Uses spaCy for semantic understanding of filenames to categorize
    markdown files into features, fixes, or reference documentation.
    """
    
    def __init__(self, classification_patterns: Optional[Dict[str, Dict[str, List[str]]]] = None, filename_only: bool = False):
        """
        Initialize the NLP classifier.
        
        Args:
            classification_patterns: Custom patterns to use instead of defaults.
            filename_only: If False, use two-phase classification (filename + content analysis)
        """
        self.patterns = classification_patterns or NLP_CLASSIFICATION_PATTERNS.copy()
        self.filename_only = filename_only
        self.nlp = None
        
        # Confidence thresholds for two-phase classification
        self.HIGH_CONFIDENCE_THRESHOLD = 0.8  # Use filename result if above this
        self.LOW_CONFIDENCE_THRESHOLD = 0.2   # Use fallback if below this after content analysis
        self.CONTENT_ANALYSIS_CHAR_LIMIT = 1000  # Characters to read for content analysis
        
        # Feature template for enhanced feature detection
        self.feature_template = None
        self.feature_template_words = set()
        
        # Initialize NLP model if available
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("✓ Loaded spaCy model for NLP classification")
            except OSError:
                logger.warning("⚠️ spaCy model not found. Install with: python -m spacy download en_core_web_sm")
                self.nlp = None
        else:
            logger.warning("⚠️  spaCy not available. Install with: pip install spacy")
        
        # Load feature design template for enhanced feature detection
        self._load_feature_template()
        
    
    def classify_files(self, files: List[Path]) -> List[ClassifiedFile]:
        """
        Classify a list of markdown files using NLP-enhanced filename analysis.
        
        Args:
            files: List of file paths to classify
            
        Returns:
            List of ClassifiedFile objects with classification results
            
        Raises:
            ClassificationError: If classification fails
        """
        if not files:
            return []
        
        classified_files = []
        
        for file_path in files:
            try:
                classified_file = self._classify_single_file(file_path)
                classified_files.append(classified_file)
            except Exception as e:
                raise ClassificationError(f"Failed to classify file {file_path}: {str(e)}")
        
        return classified_files
    
    def _classify_single_file(self, file_path: Path) -> ClassifiedFile:
        """
        Classify a single file using two-phase NLP-enhanced analysis.
        
        Phase 1: Filename analysis
        - If confidence > 0.8, use that result
        Phase 2: Content analysis (if phase 1 confidence <= 0.8)
        - Read first 1000 characters and re-classify with filename + content
        - If still < 0.2, use fallback
        
        Args:
            file_path: Path to the file to classify
            
        Returns:
            ClassifiedFile with classification results
        """
        
        # Phase 1: Filename-based classification
        if self.nlp:
            phase1_result = self._classify_with_nlp(file_path)
        else:
            phase1_result = self._classify_with_keywords(file_path)
        
        # If filename_only mode or high confidence, return phase 1 result
        if self.filename_only or phase1_result.confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            if phase1_result.confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
                phase1_result.classification_reasons.append("High confidence from filename analysis")
            return phase1_result
        
        # Phase 2: Content + filename analysis for low confidence results
        try:
            content = self._read_file_content(file_path)
            if content:
                if self.nlp:
                    phase2_result = self._classify_with_content_nlp(file_path, content)
                else:
                    phase2_result = self._classify_with_content_keywords(file_path, content)
                
                # Use phase 2 result if it has higher confidence
                if phase2_result.confidence > phase1_result.confidence:
                    phase2_result.classification_reasons.append("Enhanced with content analysis")
                    return phase2_result
                
        except Exception as e:
            logger.error(f"Content analysis failed for {file_path.name}: {e}")
        
        # Fallback logic
        if phase1_result.confidence < self.LOW_CONFIDENCE_THRESHOLD:
            phase1_result.category = "reference"
            phase1_result.confidence = max(phase1_result.confidence, 0.2)
            phase1_result.classification_reasons.append("Low confidence, using fallback category")
        
        return phase1_result
    
    def _classify_with_nlp(self, file_path: Path) -> ClassifiedFile:
        """Classify using spaCy NLP analysis of filename."""
        filename = file_path.name
        
        # Remove file extension and process with spaCy
        name_without_ext = filename.replace('.md', '').replace('_', ' ').replace('-', ' ')
        doc = self.nlp(name_without_ext)
        
        # Extract NLP features
        features = self._extract_nlp_features(doc, file_path)
        category_scores = {}
        
        for category, patterns in self.patterns.items():
            score, reasons = self._score_category_nlp(features, patterns, category)
            category_scores[category] = score
        
        # Find best category
        if not category_scores:
            best_category = "reference"
            best_confidence = 0.1
            reasons = ["No patterns matched, using fallback"]
        else:
            best_category = max(category_scores.keys(), key=lambda k: category_scores[k])
            best_confidence = category_scores[best_category]
            reasons = [f"NLP analysis suggests '{best_category}' category"]
        
        # Apply confidence threshold and fallback logic
        if best_confidence < self.LOW_CONFIDENCE_THRESHOLD:
            best_category = "reference"  # Fallback
            best_confidence = max(best_confidence, 0.2)
            reasons.append("Low confidence, using fallback category")
        
        return ClassifiedFile(
            file_path=file_path,
            category=best_category,
            confidence=best_confidence,
            classification_reasons=reasons,
            content_preview=None
        )
    
    def _extract_nlp_features(self, doc, file_path: Path) -> Dict:
        """Extract NLP features from spaCy doc."""
        features = {
            'filename': file_path.name.lower(),
            'entities': [(ent.text.lower(), ent.label_) for ent in doc.ents],
            'pos_tags': [token.pos_ for token in doc if not token.is_stop],
            'tokens': [token.lemma_.lower() for token in doc if not token.is_stop and token.is_alpha],
            'sentences': [sent.text for sent in doc.sents],
        }
        
        return features
    
    def _score_category_nlp(self, features: Dict, patterns: Dict, category: str) -> Tuple[float, List[str]]:
        """Score a category using NLP features and patterns."""
        score = 0.0
        reasons = []
        
        # 1. Entity analysis
        relevant_entities = [ent for ent, label in features['entities'] 
                           if label in patterns.get('entities', [])]
        if relevant_entities:
            entity_score = min(len(relevant_entities) * 0.1, 0.3)
            score += entity_score
            reasons.append(f"Found relevant entities: {relevant_entities}")
        
        # 2. High confidence keyword matching
        high_conf_matches = 0
        for keyword in patterns.get('high_confidence_keywords', []):
            if keyword.lower() in features['filename']:
                high_conf_matches += 1
                score += 0.7  # Very high weight for high-confidence keywords
        
        if high_conf_matches > 0:
            reasons.append(f"Matched {high_conf_matches} high-confidence keywords")
        
        # 3. Regular keyword matching
        keyword_matches = 0
        for keyword in patterns.get('keywords', []):
            if keyword.lower() in features['filename']:
                keyword_matches += 1
                score += 0.4  # High weight for direct keyword matches
            
            # Check tokens for semantic similarity
            for token in features['tokens']:
                if keyword.lower() in token or token in keyword.lower():
                    score += 0.2
        
        if keyword_matches > 0:
            reasons.append(f"Matched {keyword_matches} regular keywords")
        
        # 3. POS tag analysis
        relevant_pos = sum(1 for pos in features['pos_tags'] 
                         if pos in patterns.get('pos_patterns', []))
        if relevant_pos > 0:
            pos_score = min(relevant_pos * 0.05, 0.2)
            score += pos_score
            reasons.append(f"Found {relevant_pos} relevant POS tags")
        
        # 4. Sentence pattern matching (for filename analysis, check if patterns exist in filename)
        pattern_matches = 0
        for pattern in patterns.get('sentence_patterns', []):
            if re.search(pattern, features['filename'], re.IGNORECASE):
                pattern_matches += 1
                score += 0.3
        
        if pattern_matches > 0:
            reasons.append(f"Matched {pattern_matches} sentence patterns")
        
        return min(score, 1.0), reasons
    
    def _load_feature_template(self):
        """Load feature design template for enhanced feature detection."""
        try:
            template_path = Path("templates/requirements.md")
            if template_path.exists():
                content = template_path.read_text(encoding='utf-8', errors='ignore')
                self.feature_template = self._clean_template_content(content)
                self.feature_template_words = set(self.feature_template.lower().split())
            else:
                logger.error("Feature template not found at templates/requirements.md")
        except Exception as e:
            logger.error(f"Error loading feature template: {e}")
    
    def _clean_template_content(self, content: str) -> str:
        """Clean template content to extract meaningful words."""
        import re
        
        # Remove markdown formatting
        content = re.sub(r'#+\s*', '', content)  # Headers
        content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)  # Code blocks
        content = re.sub(r'`.*?`', '', content)  # Inline code
        content = re.sub(r'\*\*?.*?\*\*?', '', content)  # Bold/italic
        content = re.sub(r'[_-]{3,}', '', content)  # Separators
        
        # Remove placeholder text and brackets
        content = re.sub(r'\[.*?\]', '', content)  # [placeholder]
        content = re.sub(r'\{.*?\}', '', content)  # {placeholder}
        content = re.sub(r'<.*?>', '', content)   # <placeholder>
        content = re.sub(r'\.{3,}', '', content)  # ...
        
        # Extract meaningful words
        words = []
        for line in content.split('\n'):
            line = line.strip()
            if line and len(line) > 3 and not line.startswith(('-', '*', '+')):
                # Split and filter words
                line_words = re.findall(r'\b[a-zA-Z]{3,}\b', line)
                words.extend(line_words)
        
        # Filter out common words and keep domain-specific terms
        stopwords = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 
            'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'how', 
            'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 
            'its', 'let', 'put', 'say', 'she', 'too', 'use', 'any', 'may', 'will'
        }
        
        filtered_words = [
            word.lower() for word in words 
            if len(word) > 2 and word.lower() not in stopwords
        ]
        
        return ' '.join(filtered_words)
    
    def _calculate_feature_template_similarity(self, text: str) -> float:
        """Calculate semantic similarity with feature template using spaCy if available."""
        if not self.feature_template or not text.strip():
            return 0.0
        
        # Simple word overlap similarity (fast and effective)
        text_words = set(text.lower().split())
        intersection = self.feature_template_words.intersection(text_words)
        
        if not self.feature_template_words:
            return 0.0
        
        # Jaccard similarity
        union = self.feature_template_words.union(text_words)
        jaccard_similarity = len(intersection) / len(union) if union else 0.0
        
        # If spaCy is available and has vectors, use semantic similarity
        if self.nlp and hasattr(self.nlp, 'vocab') and self.nlp.vocab.vectors.size > 0:
            try:
                doc1 = self.nlp(self.feature_template)
                doc2 = self.nlp(text)
                semantic_similarity = doc1.similarity(doc2)
                # Combine both similarities with more weight on semantic
                return (jaccard_similarity * 0.3) + (semantic_similarity * 0.7)
            except Exception:
                pass
        
        return jaccard_similarity
    
    def _expand_keywords_semantically(self, keywords: List[str], text: str) -> List[str]:
        """Expand keywords using spaCy semantic similarity if available."""
        if not self.nlp or not hasattr(self.nlp, 'vocab') or self.nlp.vocab.vectors.size == 0:
            return keywords
        
        expanded_keywords = set(keywords)
        
        try:
            doc = self.nlp(text)
            for token in doc:
                if (token.is_alpha and not token.is_stop and len(token.text) > 3 and 
                    token.has_vector):
                    
                    # Check semantic similarity with existing keywords
                    for keyword in keywords:
                        try:
                            keyword_token = self.nlp(keyword)[0]
                            if (keyword_token.has_vector and 
                                token.similarity(keyword_token) > 0.7):  # High similarity threshold
                                expanded_keywords.add(token.lemma_.lower())
                                break
                        except Exception:
                            continue
        except Exception:
            pass
        
        return list(expanded_keywords)
    
    def _classify_with_keywords(self, file_path: Path) -> ClassifiedFile:
        """Fallback classification using simple keyword matching."""
        filename = file_path.name.lower()
        category_scores = {}
        
        for category, patterns in self.patterns.items():
            score = 0.0
            matches = 0
            match_details = []
            
            # High confidence keyword matching
            for keyword in patterns.get("high_confidence_keywords", []):
                if keyword.lower() in filename:
                    score += 0.7  # Very high weight for high-confidence keywords
                    matches += 1
                    match_details.append(f"high_conf:{keyword}")
            
            # Regular keyword matching using enhanced patterns
            for keyword in patterns.get("keywords", []):
                if keyword.lower() in filename:
                    score += 0.4
                    matches += 1
                    match_details.append(f"keyword:{keyword}")
            
            # Check semantic similarity keywords
            for keyword in patterns.get("semantic_similarity", []):
                if keyword.lower() in filename:
                    score += 0.3
                    matches += 1
                    match_details.append(f"semantic:{keyword}")
            
            category_scores[category] = min(score, 1.0)
        
        # Find best category
        if not category_scores:
            best_category = "reference"
            best_confidence = 0.1
            reasons = ["No keywords matched, using fallback"]
        else:
            best_category = max(category_scores.keys(), key=lambda k: category_scores[k])
            best_confidence = category_scores[best_category]
            reasons = [f"Keyword analysis suggests '{best_category}' category"]
        
        # Apply fallback logic
        if best_confidence < self.LOW_CONFIDENCE_THRESHOLD:
            best_category = "reference"
            best_confidence = max(best_confidence, 0.2)
            reasons.append("Low confidence, using fallback category")
        
        return ClassifiedFile(
            file_path=file_path,
            category=best_category,
            confidence=best_confidence,
            classification_reasons=reasons,
            content_preview=None
        )
    
    def _read_file_content(self, file_path: Path) -> str:
        """
        Read the first portion of a file for content analysis.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            First 1000 characters of file content, or empty string if read fails
        """
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            return content[:self.CONTENT_ANALYSIS_CHAR_LIMIT]
        except Exception as e:
            logger.error(f"Failed to read content from {file_path.name}: {e}")
            return ""
    
    def _classify_with_content_nlp(self, file_path: Path, content: str) -> ClassifiedFile:
        """Classify using spaCy NLP analysis of filename + content."""
        filename = file_path.name
        # Combine filename and content for analysis
        combined_text = f"{filename.replace('.md', '').replace('_', ' ').replace('-', ' ')} {content}"
        doc = self.nlp(combined_text)
        
        # Extract NLP features from combined text
        features = self._extract_nlp_features_with_content(doc, file_path, content)
        # Calculate scores for each category using enhanced patterns
        category_scores = {}
        
        for category, patterns in self.patterns.items():
            score, reasons = self._score_category_with_content(features, patterns, category)
            
            # Add feature template similarity boost for features category
            if category == "features" and self.feature_template:
                template_similarity = self._calculate_feature_template_similarity(f"{filename} {content}")
                if template_similarity > 0.1:  # Only boost if there's meaningful similarity
                    template_boost = template_similarity * 0.3  # Moderate boost
                    score += template_boost
                    reasons.append(f"Feature template similarity: {template_similarity:.2f}")
            
            category_scores[category] = min(score, 1.0)  # Cap at 1.0

        # Find best category
        if not category_scores:
            best_category = "reference"
            best_confidence = 0.1
            reasons = ["No patterns matched in content analysis"]
        else:
            best_category = max(category_scores.keys(), key=lambda k: category_scores[k])
            best_confidence = category_scores[best_category]
            reasons = [f"Content+NLP analysis suggests '{best_category}' category"]
        
        return ClassifiedFile(
            file_path=file_path,
            category=best_category,
            confidence=best_confidence,
            classification_reasons=reasons,
            content_preview=content[:200] + "..." if len(content) > 200 else content
        )
    
    def _classify_with_content_keywords(self, file_path: Path, content: str) -> ClassifiedFile:
        """Classify using keyword matching on filename + content."""
        filename = file_path.name.lower()
        content_lower = content.lower()
        category_scores = {}
        
        for category, patterns in self.patterns.items():
            score = 0.0
            matches = 0
            match_details = []
            
            # High confidence keyword matching (filename + content)
            for keyword in patterns.get("high_confidence_keywords", []):
                keyword_lower = keyword.lower()
                if keyword_lower in filename:
                    score += 0.6  # Higher weight for high-confidence keywords in filename
                    matches += 1
                    match_details.append(f"filename:{keyword}")
                elif keyword_lower in content_lower:
                    score += 0.5  # High weight for high-confidence keywords in content
                    matches += 1
                    match_details.append(f"content:{keyword}")
            
            # Regular keyword matching
            for keyword in patterns.get("keywords", []):
                keyword_lower = keyword.lower()
                if keyword_lower in filename:
                    score += 0.4  # Standard weight for keywords in filename
                    matches += 1
                    match_details.append(f"filename:{keyword}")
                elif keyword_lower in content_lower:
                    score += 0.2  # Lower weight for keywords in content
                    matches += 1
                    match_details.append(f"content:{keyword}")
            
            # Content pattern matching
            import re
            for pattern in patterns.get("content_patterns", []):
                if re.search(pattern, content_lower, re.IGNORECASE):
                    score += 0.3  # Good weight for content patterns
                    matches += 1
                    match_details.append(f"pattern:{pattern}")
            
            # Sentence pattern matching in content
            for pattern in patterns.get("sentence_patterns", []):
                if re.search(pattern, content_lower, re.IGNORECASE):
                    score += 0.3  # Good weight for sentence patterns
                    matches += 1
                    match_details.append(f"sentence:{pattern}")
            
            # Add feature template similarity boost for features category
            if category == "features" and self.feature_template:
                template_similarity = self._calculate_feature_template_similarity(f"{filename} {content}")
                if template_similarity > 0.1:  # Only boost if there's meaningful similarity
                    template_boost = template_similarity * 0.3  # Moderate boost
                    score += template_boost
                    match_details.append(f"template:{template_similarity:.2f}")
            
            category_scores[category] = min(score, 1.0)

        # Find best category
        if not category_scores:
            best_category = "reference"
            best_confidence = 0.1
            reasons = ["No keywords matched in content analysis"]
        else:
            best_category = max(category_scores.keys(), key=lambda k: category_scores[k])
            best_confidence = category_scores[best_category]
            reasons = [f"Content+keyword analysis suggests '{best_category}' category"]

        return ClassifiedFile(
            file_path=file_path,
            category=best_category,
            confidence=best_confidence,
            classification_reasons=reasons,
            content_preview=content[:200] + "..." if len(content) > 200 else content
        )
    
    def _extract_nlp_features_with_content(self, doc, file_path: Path, content: str) -> Dict:
        """Extract enhanced NLP features from spaCy doc including content analysis."""
        features = {
            'filename': file_path.name.lower(),
            'entities': [(ent.text.lower(), ent.label_) for ent in doc.ents],
            'pos_tags': [token.pos_ for token in doc if not token.is_stop],
            'tokens': [token.lemma_.lower() for token in doc if not token.is_stop and token.is_alpha],
            'sentences': [sent.text for sent in doc.sents],
            'content': content.lower(),
            'content_tokens': [token.lemma_.lower() for token in doc[len(file_path.name.split()):] if not token.is_stop and token.is_alpha],
        }
        
        return features
    
    def _score_category_with_content(self, features: Dict, patterns: Dict, category: str) -> Tuple[float, List[str]]:
        """Score a category using enhanced NLP features including content analysis."""
        score = 0.0
        reasons = []
        
        # 1. Entity analysis (enhanced weight)
        relevant_entities = [ent for ent, label in features['entities'] 
                           if label in patterns.get('entities', [])]
        if relevant_entities:
            entity_score = min(len(relevant_entities) * 0.15, 0.4)
            score += entity_score
            reasons.append(f"Found relevant entities: {relevant_entities}")
        
        # 2. High confidence keyword matching
        high_conf_matches = 0
        for keyword in patterns.get('high_confidence_keywords', []):
            if keyword.lower() in features['filename']:
                high_conf_matches += 1
                score += 0.6  # Very high weight for high-confidence keywords in filename
            elif keyword.lower() in features['content']:
                high_conf_matches += 1
                score += 0.5  # High weight for high-confidence keywords in content
        
        if high_conf_matches > 0:
            reasons.append(f"Matched {high_conf_matches} high-confidence keywords")
        
        # 3. Regular keyword matching with semantic expansion
        keyword_matches = 0
        base_keywords = patterns.get('keywords', [])
        
        # Expand keywords semantically if possible
        if category == "features" and self.nlp:
            combined_text = f"{features['filename']} {features.get('content', '')}"
            expanded_keywords = self._expand_keywords_semantically(base_keywords, combined_text)
        else:
            expanded_keywords = base_keywords
        
        for keyword in expanded_keywords:
            if keyword.lower() in features['filename']:
                keyword_matches += 1
                # Give slightly lower weight to expanded keywords
                weight = 0.4 if keyword in base_keywords else 0.3
                score += weight
            elif keyword.lower() in features.get('content', ''):
                keyword_matches += 1
                weight = 0.2 if keyword in base_keywords else 0.15
                score += weight
            
            # Check tokens for semantic similarity
            for token in features['tokens']:
                if keyword.lower() in token or token in keyword.lower():
                    score += 0.1
        
        if keyword_matches > 0:
            reasons.append(f"Matched {keyword_matches} regular keywords")
        
        # 4. Content pattern matching
        import re
        content_pattern_matches = 0
        for pattern in patterns.get('content_patterns', []):
            if re.search(pattern, features['content'], re.IGNORECASE):
                content_pattern_matches += 1
                score += 0.3  # Good weight for content-specific patterns
        
        if content_pattern_matches > 0:
            reasons.append(f"Matched {content_pattern_matches} content patterns")
        
        # 5. POS tag analysis (enhanced)
        relevant_pos = sum(1 for pos in features['pos_tags'] 
                         if pos in patterns.get('pos_patterns', []))
        if relevant_pos > 0:
            pos_score = min(relevant_pos * 0.08, 0.3)
            score += pos_score
            reasons.append(f"Found {relevant_pos} relevant POS tags")
        
        # 6. Sentence pattern matching (enhanced for content)
        pattern_matches = 0
        for pattern in patterns.get('sentence_patterns', []):
            if re.search(pattern, features['filename'], re.IGNORECASE):
                pattern_matches += 1
                score += 0.4  # Higher weight for sentence patterns in filename
            elif re.search(pattern, features['content'], re.IGNORECASE):
                pattern_matches += 1
                score += 0.3  # Good weight for sentence patterns in content
        
        if pattern_matches > 0:
            reasons.append(f"Matched {pattern_matches} sentence patterns")
        
        return min(score, 1.0), reasons