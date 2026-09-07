"""
Mention Extraction (Fixed)

Extracts literal mentions (noun phrases, technical terms) from transcript chunks
using regex patterns and basic NLP heuristics.
Filters common words to reduce noise in concepts.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, Tuple
import re

from .semantic_models import Mention, EvidenceSpan


class MentionExtractor:
    """Extracts mentions from transcript text using deterministic patterns"""
    
    # Common stopwords to avoid extracting as mentions
    STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "of", "to", "in", "on",
        "for", "with", "from", "by", "is", "are", "was", "were", "be",
        "been", "being", "this", "that", "these", "those", "we", "you",
        "they", "it", "as", "at", "into", "about", "now", "then", "also",
        "very", "just", "can", "will", "would", "could", "should",
        "have", "has", "had", "do", "does", "did", "used", "using",
        "use", "lets", "let", "there", "their", "its", "which", "who",
        "what", "how", "today", "here", "there", "when", "where", "why"
    }
    
    # Common verbs that shouldn't be extracted as concepts
    VERBS = {
        "is", "are", "was", "were", "provides", "uses", "allows", "enables",
        "requires", "causes", "contains", "includes", "has", "have", "had",
        "do", "does", "did", "make", "makes", "made", "get", "gets", "got",
        "take", "takes", "took", "give", "gives", "gave", "go", "goes", "went",
        "connects", "connected", "connecting", "deals", "handles", "ensures",
        "guarantees", "maintains", "manages", "processes", "transmits",
        "receives", "sends", "links", "routes", "forwards", "delivers",
    }
    
    # Common words that should NEVER be concepts
    _COMMON_WORDS = {
        "all", "through", "discuss", "look", "if", "one", "only",
        "using", "uses", "used", "connect", "connects", "connected",
        "provide", "provides", "provided", "layer", "layers",
        "device", "devices", "model", "models", "process", "processes",
        "let", "lets", "look", "looking", "see", "seen", "example",
        "examples", "learning", "learn", "learns", "discuss", "discussion",
        "talking", "talk", "talks", "going", "go", "goes",
        "like", "unlike", "without", "within", "between", "among",
    }
    
    # Technical term patterns
    TECHNICAL_PATTERNS = [
        r'\b[A-Z]{2,}\b',  # Acronyms (TCP, HTTP, CPU)
        r'\b[A-Z][a-z]+(?:[ -][A-Z][a-z]+)*\b',  # CamelCase (WiFi, JavaScript)
    ]
    
    def __init__(self):
        self._compiled_technical = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.TECHNICAL_PATTERNS
        ]
    
    def extract_mentions(
        self,
        text: str,
        evidence: Optional[EvidenceSpan] = None,
        chunk_id: str = ""
    ) -> List[Mention]:
        """
        Extract mentions from text.
        
        Args:
            text: Transcript text
            evidence: Evidence span for grounding
            chunk_id: Current chunk ID
            
        Returns:
            List of Mention objects
        """
        if not text or not text.strip():
            return []
        
        mentions = []
        seen_spans = set()
        
        # Extract technical terms (acronyms, CamelCase)
        for pattern in self._compiled_technical:
            for match in pattern.finditer(text):
                surface = match.group(0).strip()
                
                if not surface or len(surface) < 2:
                    continue
                
                # Skip if it's a verb or common word
                if surface.lower() in self.VERBS:
                    continue
                if surface.lower() in self._COMMON_WORDS:
                    continue
                
                span_key = (match.start(), match.end())
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)
                
                mention = self._create_mention(
                    surface_text=surface,
                    start_char=match.start(),
                    end_char=match.end(),
                    evidence=evidence,
                    chunk_id=chunk_id
                )
                
                if mention:
                    mentions.append(mention)
        
        # Extract "X of Y" patterns
        partitive_pattern = re.compile(
            r'\b([a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})\s+of\s+'
            r'([a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})\b'
        )
        
        for match in partitive_pattern.finditer(text):
            span_key = (match.start(), match.end())
            if span_key in seen_spans:
                continue
            seen_spans.add(span_key)
            
            full_text = match.group(0).strip()
            
            # Validate that this is a meaningful phrase
            if self._is_valid_phrase(full_text):
                mention = self._create_mention(
                    surface_text=full_text,
                    start_char=match.start(),
                    end_char=match.end(),
                    evidence=evidence,
                    chunk_id=chunk_id
                )
                
                if mention:
                    mentions.append(mention)
        
        # Extract individual technical terms
        individual_terms = self._extract_individual_terms(text, seen_spans)
        mentions.extend(individual_terms)
        
        return self._deduplicate(mentions)
    
    def _extract_individual_terms(
        self,
        text: str,
        seen_spans: set
    ) -> List[Mention]:
        """Extract individual technical terms"""
        mentions = []
        words = text.split()
        
        char_position = 0
        for word in words:
            word_start = text.find(word, char_position)
            word_end = word_start + len(word)
            char_position = word_end
            
            clean_word = word.strip('.,;:!?()')
            word_lower = clean_word.lower()
            
            # Skip stopwords, verbs, common words, short words
            if word_lower in self.STOPWORDS:
                continue
            if word_lower in self.VERBS:
                continue
            if word_lower in self._COMMON_WORDS:
                continue
            if len(clean_word) < 3:
                continue
            
            # Check if this word is already part of a mention
            span_key = (word_start, word_end)
            if span_key in seen_spans:
                continue
            
            # Skip if word is part of a larger phrase we already extracted
            is_part_of_larger = False
            for existing_start, existing_end in seen_spans:
                if existing_start <= word_start and word_end <= existing_end:
                    is_part_of_larger = True
                    break
            
            if is_part_of_larger:
                continue
            
            # Only extract if it looks technical
            if self._is_technical_term(clean_word):
                mention = self._create_mention(
                    surface_text=clean_word,
                    start_char=word_start,
                    end_char=word_end,
                    evidence=None,
                    chunk_id=""
                )
                
                if mention:
                    mentions.append(mention)
                    seen_spans.add(span_key)
        
        return mentions
    
    def _is_technical_term(self, word: str) -> bool:
        """Check if word looks like a technical term"""
        # Skip common words
        if word.lower() in self._COMMON_WORDS:
            return False
        if word.lower() in self.VERBS:
            return False
        
        # Acronyms
        if word.isupper() and len(word) <= 5:
            return True
        
        # Proper nouns (first letter uppercase, not at sentence start)
        if word[0].isupper() and len(word) > 2:
            return True
        
        # Words with numbers
        if re.search(r'\d', word):
            return True
        
        # Technical suffixes
        if word.lower().endswith(('tion', 'sion', 'ment', 'ity', 'ism', 'ics')):
            return True
        
        return False
    
    def _is_valid_phrase(self, phrase: str) -> bool:
        """Check if phrase is a valid concept"""
        words = phrase.lower().split()
        
        # Must have at least 2 content words
        content_words = [
            w for w in words
            if w not in self.STOPWORDS
            and w not in self.VERBS
            and w not in self._COMMON_WORDS
        ]
        if len(content_words) < 2:
            return False
        
        # Should not start or end with a verb
        if words[0] in self.VERBS or words[-1] in self.VERBS:
            return False
        
        return True
    
    def _create_mention(
        self,
        surface_text: str,
        start_char: int,
        end_char: int,
        evidence: Optional[EvidenceSpan],
        chunk_id: str
    ) -> Optional[Mention]:
        """Create a Mention object"""
        surface = surface_text.strip()
        
        if not surface or len(surface) < 2:
            return None
        
        # Skip pure stopwords, verbs, common words
        if surface.lower() in self.STOPWORDS:
            return None
        if surface.lower() in self.VERBS:
            return None
        if surface.lower() in self._COMMON_WORDS:
            return None
        
        normalized = self._normalize_mention(surface)
        
        if not normalized:
            return None
        
        return Mention(
            surface_text=surface,
            normalized_text=normalized,
            evidence=evidence,
            start_char=start_char,
            end_char=end_char,
            confidence=0.7
        )
    
    def _normalize_mention(self, text: str) -> str:
        """Normalize mention text for comparison"""
        normalized = text.lower()
        normalized = re.sub(r'\b(the|a|an)\b', '', normalized)
        normalized = re.sub(r'[^\w\s-]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Basic singularization
        if normalized.endswith('ies') and len(normalized) > 4:
            normalized = normalized[:-3] + 'y'
        elif normalized.endswith('es') and len(normalized) > 4:
            normalized = normalized[:-2]
        elif normalized.endswith('s') and len(normalized) > 3:
            if not normalized.endswith(('ss', 'us', 'is')):
                normalized = normalized[:-1]
        
        return normalized
    
    def _deduplicate(self, mentions: List[Mention]) -> List[Mention]:
        """Remove duplicate mentions"""
        deduplicated = []
        seen = set()
        
        for mention in mentions:
            key = (mention.normalized_text, mention.start_char, mention.end_char)
            if key not in seen:
                seen.add(key)
                deduplicated.append(mention)
        
        return deduplicated