"""
Mention Extraction

Extracts literal mentions (noun phrases, technical terms) from transcript chunks
using regex patterns and basic NLP heuristics. No heavy dependencies required.
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
    
    # Technical term patterns
    TECHNICAL_PATTERNS = [
        r'\b[A-Z]{2,}\b',  # Acronyms (TCP, HTTP, CPU)
        r'\b[A-Z][a-z]+(?:[ -][A-Z][a-z]+)*\b',  # CamelCase (WiFi, JavaScript)
        r'\b[a-z]+(?:[- ][a-z]+){1,5}\b',  # Multi-word terms (data structure)
    ]
    
    # Patterns to extract noun phrases
    NOUN_PHRASE_PATTERNS = [
        # Adjective + Noun
        r'\b(?:[a-z]+ ){0,2}(?:[a-z]+)\b',
        # Noun + of + Noun
        r'\b[a-z]+ of [a-z]+\b',
        # Compound nouns
        r'\b[a-z]+ [a-z]+ [a-z]+\b',
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
        
        # Extract noun phrases (simplified)
        noun_phrases = self._extract_noun_phrases(text)
        
        for np_text, start, end in noun_phrases:
            span_key = (start, end)
            if span_key in seen_spans:
                continue
            seen_spans.add(span_key)
            
            mention = self._create_mention(
                surface_text=np_text,
                start_char=start,
                end_char=end,
                evidence=evidence,
                chunk_id=chunk_id
            )
            
            if mention:
                mentions.append(mention)
        
        # Extract "X of Y" patterns
        partitive_pattern = re.compile(
            r'\b([a-zA-Z]+(?:\s+[a-zA-Z]+){0,4})\s+of\s+'
            r'([a-zA-Z]+(?:\s+[a-zA-Z]+){0,4})\b'
        )
        
        for match in partitive_pattern.finditer(text):
            span_key = (match.start(), match.end())
            if span_key in seen_spans:
                continue
            seen_spans.add(span_key)
            
            full_text = match.group(0).strip()
            mention = self._create_mention(
                surface_text=full_text,
                start_char=match.start(),
                end_char=match.end(),
                evidence=evidence,
                chunk_id=chunk_id
            )
            
            if mention:
                mentions.append(mention)
        
        return self._deduplicate(mentions)
    
    def _extract_noun_phrases(self, text: str) -> List[Tuple[str, int, int]]:
        """Extract noun phrases using simple heuristics"""
        phrases = []
        words = text.split()
        
        i = 0
        while i < len(words):
            word = words[i].lower().strip('.,;:!?()')
            
            # Skip stopwords and short words
            if word in self.STOPWORDS or len(word) < 3:
                i += 1
                continue
            
            # Check for multi-word phrases
            phrase_start = i
            phrase_words = [words[i]]
            
            # Extend phrase while words are not stopwords
            j = i + 1
            while j < len(words) and j < i + 5:
                next_word = words[j].lower().strip('.,;:!?()')
                
                # Stop if we hit a verb or stopword
                if next_word in self.STOPWORDS:
                    break
                
                # Stop if next word is a common verb
                if next_word in {"is", "are", "was", "were", "provides", "uses", 
                                 "allows", "enables", "requires", "contains"}:
                    break
                
                phrase_words.append(words[j])
                j += 1
            
            if len(phrase_words) >= 1:
                phrase_text = " ".join(phrase_words).strip('.,;:!?()')
                
                if len(phrase_text) > 2:
                    # Calculate character positions
                    char_start = text.find(phrase_words[0], 
                                          sum(len(w) + 1 for w in words[:phrase_start]))
                    char_end = char_start + len(phrase_text)
                    
                    phrases.append((phrase_text, char_start, char_end))
            
            i = j
        
        return phrases
    
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
        
        # Skip pure stopwords
        if surface.lower() in self.STOPWORDS:
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
            confidence=0.7  # Base confidence for extracted mentions
        )
    
    def _normalize_mention(self, text: str) -> str:
        """Normalize mention text for comparison"""
        normalized = text.lower()
        
        # Remove articles
        normalized = re.sub(r'\b(the|a|an)\b', '', normalized)
        
        # Remove punctuation
        normalized = re.sub(r'[^\w\s-]', ' ', normalized)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Basic singularization
        if normalized.endswith('ies') and len(normalized) > 4:
            normalized = normalized[:-3] + 'y'
        elif normalized.endswith('es') and len(normalized) > 4:
            normalized = normalized[:-2]
        elif normalized.endswith('s') and len(normalized) > 3:
            # Don't singularize words ending in 'ss', 'us', 'is'
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