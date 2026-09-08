"""
Visual Asset Engine

Manages image retrieval and selection for slides.

Key principles:
- Multi-source retrieval (Pixabay as fallback, not primary)
- Educational value scoring
- Semantic relevance (keyword + conceptual match)
- Quality checks
- NO image if confidence is low (native diagram preferred)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading


@dataclass
class VisualAssetCandidate:
    """A candidate image for slide"""
    source: str
    url: str
    thumbnail_url: str = ""
    title: str = ""
    tags: List[str] = field(default_factory=list)
    license: str = ""
    width: int = 0
    height: int = 0
    relevance_score: float = 0.0
    educational_score: float = 0.0
    quality_score: float = 0.0
    overall_score: float = 0.0


@dataclass
class VisualAssetResult:
    """Result of visual asset selection"""
    selected: bool
    reason: str
    asset: Optional[VisualAssetCandidate] = None
    confidence: float = 0.0
    use_native_diagram: bool = False


class VisualAssetEngine:
    """
    Selects visual assets for slides.
    
    Decision flow:
    1. Determine if visual is needed
    2. Generate search query from concepts
    3. Retrieve candidates from sources
    4. Score candidates (semantic, educational, quality)
    5. Select best or reject all
    6. Fall back to native diagram if no good image
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._cache: Dict[str, List[VisualAssetCandidate]] = {}
        
        # Scoring weights
        self.weights = {
            "relevance": 0.45,
            "educational": 0.30,
            "quality": 0.15,
            "source_trust": 0.10,
        }
        
        # Source trust scores (higher = more reliable)
        self.source_trust = {
            "wikimedia": 0.9,
            "nasa": 0.95,
            "openverse": 0.85,
            "unsplash": 0.7,
            "pexels": 0.7,
            "pixabay": 0.5,  # Lowest trust
        }
        
        # Minimum confidence to select image
        self.min_confidence = 0.65
    
    def decide(
        self,
        concepts: List[str],
        representation_type: str,
        visual_need: str = "",
    ) -> VisualAssetResult:
        """
        Decide if a visual asset is needed and select one.
        
        Args:
            concepts: Key concepts for the slide
            representation_type: Type of representation
            visual_need: What kind of visual would help
            
        Returns:
            VisualAssetResult
        """
        with self._lock:
            # ==========================================
            # Step 1: Is visual needed?
            # ==========================================
            if not self._should_use_visual(representation_type, visual_need):
                return VisualAssetResult(
                    selected=False,
                    reason=f"No visual needed for {representation_type}",
                    use_native_diagram=False,
                )
            
            if not concepts:
                return VisualAssetResult(
                    selected=False,
                    reason="No concepts for query",
                    use_native_diagram=True,  # Use native diagram instead
                )
            
            # ==========================================
            # Step 2: Generate query
            # ==========================================
            query = self._build_query(concepts)
            
            # ==========================================
            # Step 3: Check cache
            # ==========================================
            if query in self._cache:
                candidates = self._cache[query]
            else:
                candidates = self._retrieve_candidates(query)
                self._cache[query] = candidates
            
            # ==========================================
            # Step 4: Score candidates
            # ==========================================
            scored = self._score_candidates(candidates, concepts)
            
            # ==========================================
            # Step 5: Select best or reject
            # ==========================================
            if not scored:
                return VisualAssetResult(
                    selected=False,
                    reason="No candidates found",
                    use_native_diagram=True,
                )
            
            best = scored[0]
            
            if best.overall_score < self.min_confidence:
                return VisualAssetResult(
                    selected=False,
                    reason=f"Best score {best.overall_score:.2f} below confidence threshold",
                    use_native_diagram=True,  # Use native diagram instead
                )
            
            return VisualAssetResult(
                selected=True,
                reason=f"Selected {best.source} image (score: {best.overall_score:.2f})",
                asset=best,
                confidence=best.overall_score,
                use_native_diagram=False,
            )
    
    def _should_use_visual(
        self,
        representation_type: str,
        visual_need: str,
    ) -> bool:
        """
        Determine if a visual asset would help.
        
        Some representations don't need external images:
        - comparison → native table
        - flowchart → native diagram
        - hierarchy → native tree
        - formula → native equation
        """
        no_visual_types = {
            "comparison",
            "contrast",
            "flowchart",
            "process",
            "hierarchy",
            "timeline",
            "concept_map",
            "causal_chain",
            "formula",
            "number_statistic",
        }
        
        if representation_type in no_visual_types:
            return False
        
        # Visual need must be explicitly requested
        if not visual_need or visual_need == "none":
            return False
        
        return True
    
    def _build_query(self, concepts: List[str]) -> str:
        """Build search query from concepts"""
        # Use first 3 concepts as query terms
        terms = [c.lower().strip() for c in concepts[:3] if c.strip()]
        return " ".join(terms)
    
    def _retrieve_candidates(self, query: str) -> List[VisualAssetCandidate]:
        """
        Retrieve candidates from sources.
        
        This is a STUB - actual retrieval would call APIs.
        For now, returns empty list (no network calls in tests).
        """
        # TODO: Implement actual retrieval
        # - Wikimedia Commons API
        # - Openverse API
        # - Pixabay API (fallback)
        return []
    
    def _score_candidates(
        self,
        candidates: List[VisualAssetCandidate],
        concepts: List[str],
    ) -> List[VisualAssetCandidate]:
        """Score candidates and sort by overall score"""
        concept_set = set(c.lower() for c in concepts)
        
        for candidate in candidates:
            # Semantic relevance (keyword match)
            candidate.relevance_score = self._calculate_relevance(
                candidate, concept_set
            )
            
            # Educational value
            candidate.educational_score = self._calculate_educational_value(
                candidate
            )
            
            # Quality
            candidate.quality_score = self._calculate_quality(candidate)
            
            # Source trust
            source_score = self.source_trust.get(candidate.source, 0.5)
            
            # Overall score
            candidate.overall_score = (
                candidate.relevance_score * self.weights["relevance"] +
                candidate.educational_score * self.weights["educational"] +
                candidate.quality_score * self.weights["quality"] +
                source_score * self.weights["source_trust"]
            )
        
        # Sort by overall score
        candidates.sort(key=lambda c: c.overall_score, reverse=True)
        
        return candidates
    
    def _calculate_relevance(
        self,
        candidate: VisualAssetCandidate,
        concept_set: set,
    ) -> float:
        """Calculate semantic relevance"""
        tag_set = set(t.lower() for t in candidate.tags)
        title_words = set(candidate.title.lower().split())
        
        # Keyword match
        matched_tags = concept_set.intersection(tag_set)
        matched_title = concept_set.intersection(title_words)
        
        # Simple relevance: matched tags / total concepts
        if not concept_set:
            return 0.0
        
        relevance = (len(matched_tags) * 2 + len(matched_title)) / (len(concept_set) * 3)
        
        return min(1.0, relevance)
    
    def _calculate_educational_value(
        self,
        candidate: VisualAssetCandidate,
    ) -> float:
        """
        Calculate educational value.
        
        Educational images typically:
        - Are diagrams or illustrations
        - Have descriptive titles
        - Are from trusted educational sources
        """
        score = 0.5  # Base score
        
        # Title quality
        if candidate.title:
            score += 0.1
        
        # Tags quality
        if len(candidate.tags) >= 3:
            score += 0.1
        
        # Source trust boost
        if candidate.source in ["wikimedia", "nasa"]:
            score += 0.2
        
        # License information
        if candidate.license:
            score += 0.1
        
        return min(1.0, score)
    
    def _calculate_quality(self, candidate: VisualAssetCandidate) -> float:
        """Calculate image quality"""
        score = 0.5  # Base score
        
        # Resolution
        if candidate.width >= 1920 and candidate.height >= 1080:
            score += 0.3
        elif candidate.width >= 1280 and candidate.height >= 720:
            score += 0.2
        elif candidate.width >= 800 and candidate.height >= 600:
            score += 0.1
        
        # Aspect ratio (prefer landscape for slides)
        if candidate.width > candidate.height:
            score += 0.2
        
        return min(1.0, score)