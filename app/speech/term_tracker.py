"""
Technical Term Tracker (Fixed)

Tracks frequently occurring terms while preserving acronyms.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Tuple
import re
from difflib import SequenceMatcher


class TermTracker:
    """Tracks technical terms and corrects misrecognitions."""

    def __init__(
        self,
        min_occurrences_to_trust: int = 3,
        similarity_threshold: float = 0.80,
        max_terms: int = 200,
    ):
        self.min_occurrences = int(min_occurrences_to_trust)
        self.similarity_threshold = float(similarity_threshold)
        self.max_terms = int(max_terms)
        
        self._terms: Dict[str, int] = {}
        self._variants: Dict[str, List[str]] = {}
        self._recent_terms: deque = deque(maxlen=50)
        self._correction_count = 0
    
    def add_term(self, text: str) -> None:
        """Add a term, preserving original case for acronyms"""
        if not text or len(text) < 3:
            return
        
        # Preserve original for acronyms
        normalized = self._normalize(text)
        
        if not normalized:
            return
        
        existing_term = self._find_matching_term(normalized)
        
        if existing_term:
            self._terms[existing_term] = self._terms.get(existing_term, 0) + 1
            if normalized not in self._variants.get(existing_term, []):
                self._variants[existing_term].append(normalized)
        else:
            # Store with original casing for acronyms
            store_key = text if text.isupper() else normalized
            self._terms[store_key] = self._terms.get(store_key, 0) + 1
            self._variants[store_key] = [store_key]
        
        self._recent_terms.append(normalized)
    
    def add_terms_from_text(self, text: str) -> None:
        """Extract and add terms"""
        if not text:
            return
        
        words = text.split()
        
        for word in words:
            clean = word.strip('.,;:!?()')
            
            if len(clean) < 3:
                continue
            if clean.lower() in self._STOPWORDS:
                continue
            if self._is_technical(clean):
                self.add_term(clean)
    
    def correct(self, text: str) -> Tuple[str, List[Dict]]:
        """Correct misrecognized terms"""
        if not text:
            return text, []
        
        corrections = []
        words = text.split()
        corrected_words = []
        
        for word in words:
            clean = word.strip('.,;:!?()')
            
            if len(clean) < 3:
                corrected_words.append(word)
                continue
            
            match = self._find_trusted_term(clean)
            
            if match and match != clean:
                corrected = self._preserve_punctuation(word, match)
                corrected_words.append(corrected)
                self._correction_count += 1
                
                corrections.append({
                    "original": clean,
                    "replacement": match,
                    "confidence": self._confidence(clean, match),
                    "type": "term_correction",
                })
            else:
                corrected_words.append(word)
        
        return " ".join(corrected_words), corrections
    
    def get_trusted_terms(self) -> List[str]:
        """Get trusted terms"""
        return [
            term for term, count in self._terms.items()
            if count >= self.min_occurrences
        ]
    
    def get_statistics(self) -> Dict:
        """Get statistics"""
        return {
            "total_terms": len(self._terms),
            "trusted_terms": len(self.get_trusted_terms()),
            "total_corrections": self._correction_count,
        }
    
    def _find_matching_term(self, text: str) -> Optional[str]:
        """Find matching existing term"""
        best_match = None
        best_similarity = 0.0
        
        for term in self._terms:
            similarity = self._similarity(text, term)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = term
        
        if best_match and best_similarity >= self.similarity_threshold:
            return best_match
        
        return None
    
    def _find_trusted_term(self, text: str) -> Optional[str]:
        """Find trusted term that matches"""
        best_match = None
        best_similarity = 0.0
        
        for term, count in self._terms.items():
            if count < self.min_occurrences:
                continue
            
            similarity = self._similarity(text, term)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = term
        
        # Only correct if very similar
        if best_match and best_similarity >= self.similarity_threshold:
            return best_match
        
        return None
    
    def _confidence(self, original: str, corrected: str) -> float:
        """Calculate confidence"""
        similarity = self._similarity(original, corrected)
        count = self._terms.get(corrected, 0)
        confidence = similarity * min(1.0, count / 5.0)
        return round(confidence, 3)
    
    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Calculate similarity, case-sensitive for acronyms"""
        # For acronyms (all caps), use exact match
        if a.isupper() and b.isupper():
            return 1.0 if a == b else 0.0
        
        # For mixed case, use case-insensitive
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize term, preserving acronyms"""
        # Keep acronyms uppercase
        if text.isupper():
            return text
        return text.lower().strip()
    
    @staticmethod
    def _preserve_punctuation(original: str, replacement: str) -> str:
        """Preserve punctuation"""
        if original[0].isupper() and not replacement.isupper():
            replacement = replacement.capitalize()
        
        suffix = re.search(r'[^A-Za-z]*$', original)
        if suffix:
            replacement = replacement + suffix.group(0)
        
        return replacement
    
    @staticmethod
    def _is_technical(word: str) -> bool:
        """Check if word looks technical (GENERIC)"""
        if word.isupper() and len(word) <= 6:
            return True
        
        if word[0].isupper() and len(word) > 2:
            return True
        
        if word.lower().endswith(('tion', 'sion', 'ment', 'ity', 'ics', 'tor', 'ter')):
            return True
        
        if re.search(r'\d', word):
            return True
        
        return False
    
    _STOPWORDS = {
        "the", "and", "for", "are", "but", "not", "you", "all",
        "can", "had", "her", "was", "one", "our", "out", "has",
        "have", "this", "that", "these", "those", "with", "from",
        "they", "will", "would", "there", "their", "what", "about",
        "into", "than", "then", "them", "these", "some", "such",
        "when", "where", "which", "while", "who", "whom", "why",
        "how", "does", "did", "done", "doing", "being", "been",
    }