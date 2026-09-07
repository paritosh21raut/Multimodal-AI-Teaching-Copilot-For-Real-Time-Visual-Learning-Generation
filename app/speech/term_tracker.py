"""
Technical Term Tracker

Tracks frequently occurring terms from the lecture and uses them
to correct later misrecognitions. Domain-agnostic - learns from
the lecture content itself.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Tuple
import re
from difflib import SequenceMatcher


class TermTracker:
    """
    Tracks technical terms and corrects misrecognitions.
    
    Strategy:
    1. When a term appears multiple times with consistent spelling,
       it becomes a "trusted" term.
    2. Later occurrences with slightly different spelling are
       corrected to match the trusted term.
    3. This handles Whisper errors like:
       - "Portional" → "Proportional" (after seeing "Proportional" multiple times)
       - "mos fed" → "MOSFET" (after seeing "MOSFET" multiple times)
       - "you are tee" → "UART" (after seeing "UART" multiple times)
    """

    def __init__(
        self,
        min_occurrences_to_trust: int = 3,
        similarity_threshold: float = 0.75,
        max_terms: int = 200,
    ):
        self.min_occurrences = int(min_occurrences_to_trust)
        self.similarity_threshold = float(similarity_threshold)
        self.max_terms = int(max_terms)
        
        # term -> count
        self._terms: Dict[str, int] = {}
        
        # term -> list of variants seen
        self._variants: Dict[str, List[str]] = {}
        
        # Recent terms for context
        self._recent_terms: deque = deque(maxlen=50)
    
    def add_term(self, text: str) -> None:
        """
        Add a term from transcript.
        
        Args:
            text: Cleaned text (single word or short phrase)
        """
        if not text or len(text) < 3:
            return
        
        normalized = self._normalize(text)
        
        if not normalized:
            return
        
        # Check if this is a variant of existing term
        existing_term = self._find_matching_term(normalized)
        
        if existing_term:
            # This is a variant of existing term
            self._terms[existing_term] = self._terms.get(existing_term, 0) + 1
            
            if normalized not in self._variants.get(existing_term, []):
                self._variants[existing_term].append(normalized)
        else:
            # New term
            self._terms[normalized] = self._terms.get(normalized, 0) + 1
            self._variants[normalized] = [normalized]
        
        self._recent_terms.append(normalized)
    
    def add_terms_from_text(self, text: str) -> None:
        """Extract and add terms from a transcript chunk"""
        if not text:
            return
        
        # Extract potential technical terms
        # Acronyms, proper nouns, technical words
        words = text.split()
        
        for word in words:
            clean = word.strip('.,;:!?()')
            
            # Skip short words and stopwords
            if len(clean) < 3:
                continue
            if clean.lower() in self._STOPWORDS:
                continue
            
            # Add if it looks technical
            if self._is_technical(clean):
                self.add_term(clean)
    
    def correct(self, text: str) -> Tuple[str, List[Dict]]:
        """
        Correct misrecognized terms in text.
        
        Returns:
            (corrected_text, corrections_list)
        """
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
            
            # Check if this looks like a misrecognition
            match = self._find_trusted_term(clean)
            
            if match and match != clean:
                # Correct the word
                corrected = self._preserve_punctuation(word, match)
                corrected_words.append(corrected)
                
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
        """Get terms that have been seen multiple times"""
        return [
            term for term, count in self._terms.items()
            if count >= self.min_occurrences
        ]
    
    def get_statistics(self) -> Dict:
        """Get tracker statistics"""
        return {
            "total_terms": len(self._terms),
            "trusted_terms": len(self.get_trusted_terms()),
            "total_corrections": self._correction_count,
        }
    
    def _find_matching_term(self, text: str) -> Optional[str]:
        """Find if text is a variant of an existing term"""
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
        """Find if text matches a trusted term (seen 3+ times)"""
        best_match = None
        best_similarity = 0.0
        
        for term, count in self._terms.items():
            if count < self.min_occurrences:
                continue
            
            similarity = self._similarity(text, term)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = term
        
        # Only correct if similarity is high enough
        if best_match and best_similarity >= 0.80:
            return best_match
        
        return None
    
    def _confidence(self, original: str, corrected: str) -> float:
        """Calculate correction confidence"""
        similarity = self._similarity(original, corrected)
        count = self._terms.get(corrected, 0)
        
        # Higher confidence if term seen many times
        confidence = similarity * min(1.0, count / 5.0)
        
        return round(confidence, 3)
    
    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Calculate string similarity"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize term"""
        return text.lower().strip()
    
    @staticmethod
    def _preserve_punctuation(original: str, replacement: str) -> str:
        """Preserve original capitalization and punctuation"""
        # Check if original was capitalized
        if original[0].isupper():
            replacement = replacement.capitalize()
        
        # Preserve trailing punctuation
        suffix = re.search(r'[^A-Za-z]*$', original)
        if suffix:
            replacement = replacement + suffix.group(0)
        
        return replacement
    
    @staticmethod
    def _is_technical(word: str) -> bool:
        """Check if word looks technical"""
        # Acronyms
        if word.isupper() and len(word) <= 6:
            return True
        
        # Proper nouns
        if word[0].isupper() and len(word) > 2:
            return True
        
        # Technical suffixes
        if word.lower().endswith(('tion', 'sion', 'ment', 'ity', 'ics', 'tor', 'ter')):
            return True
        
        # Words with numbers
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