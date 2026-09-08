"""
Representation Engine

Maps semantic relations and instructional acts to visual representations.

Key mapping:
- DEFINED_AS → DEFINITION
- CONTRASTS_WITH → COMPARISON
- EXAMPLE_OF → EXAMPLE_GRID
- PART_OF/HAS_PART → HIERARCHY
- PRECEDES/FOLLOWS → SEQUENCE/FLOWCHART
- CAUSES/RESULTS_IN → CAUSAL_CHAIN
- HAS_VALUE/numeric → NUMBER_STATISTIC or DATA_CHART
- FORMULA act → FORMULA
- PROCESS act → FLOWCHART
- CLASSIFICATION → HIERARCHY
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
import threading

from app.presentation.models.presentation_models import (
    RepresentationType,
    RepresentationDecision,
    SelectedInformation,
)
from app.semantic.semantic_models import RelationType, InstructionalActType


class RepresentationEngine:
    """
    Determines visual representation from semantic structure.
    
    Deterministic mapping from relations to representation.
    No LLM needed for basic cases.
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._recent_representations: List[RepresentationType] = []
        self._max_recent = 10
    
    def decide(
        self,
        frame: Any,
        selected_info: Optional[SelectedInformation] = None,
    ) -> RepresentationDecision:
        """
        Decide representation for a semantic frame.
        
        Args:
            frame: SemanticFrame with relations, instructional acts, propositions
            selected_info: Optional SelectedInformation
            
        Returns:
            RepresentationDecision
        """
        with self._lock:
            # Collect signals
            signals = self._analyze_signals(frame)
            
            # Determine representation
            representation, confidence, reason = self._determine(signals, frame)
            
            # Check for monotony (avoid same representation repeatedly)
            representation = self._apply_rhythm(representation)
            
            # Build decision
            decision = RepresentationDecision(
                representation_type=representation,
                confidence=confidence,
                reason=reason,
                visual_need=self._visual_need(representation),
                supporting_visuals=self._supporting_visuals(representation),
            )
            
            # Track recent
            self._recent_representations.append(representation)
            if len(self._recent_representations) > self._max_recent:
                self._recent_representations = self._recent_representations[-self._max_recent:]
            
            return decision
    
    def _analyze_signals(self, frame: Any) -> Dict[str, int]:
        """Analyze signals in frame"""
        signals = {
            "definition": 0,
            "example": 0,
            "comparison": 0,
            "contrast": 0,
            "process": 0,
            "hierarchy": 0,
            "causal": 0,
            "numeric": 0,
            "formula": 0,
            "classification": 0,
        }
        
        # Count relations
        if hasattr(frame, 'relations'):
            for rel in frame.relations:
                if not rel.relation_type:
                    continue
                
                if rel.relation_type == RelationType.DEFINED_AS:
                    signals["definition"] += 1
                elif rel.relation_type == RelationType.CONTRASTS_WITH:
                    signals["contrast"] += 1
                    signals["comparison"] += 1
                elif rel.relation_type == RelationType.SIMILAR_TO:
                    signals["comparison"] += 1
                elif rel.relation_type in [RelationType.PART_OF, RelationType.HAS_PART]:
                    signals["hierarchy"] += 1
                elif rel.relation_type in [RelationType.PRECEDES, RelationType.FOLLOWS]:
                    signals["process"] += 1
                elif rel.relation_type in [RelationType.CAUSES, RelationType.RESULTS_IN]:
                    signals["causal"] += 1
                elif rel.relation_type == RelationType.EXAMPLE_OF:
                    signals["example"] += 1
                elif rel.relation_type == RelationType.HAS_VALUE:
                    signals["numeric"] += 1
        
        # Count instructional acts
        if hasattr(frame, 'instructional_acts'):
            for act in frame.instructional_acts:
                if not act.act_type:
                    continue
                
                if act.act_type == InstructionalActType.DEFINITION:
                    signals["definition"] += 1
                elif act.act_type == InstructionalActType.EXAMPLE:
                    signals["example"] += 1
                elif act.act_type in [InstructionalActType.COMPARISON, InstructionalActType.CONTRAST]:
                    signals["comparison"] += 1
                elif act.act_type in [InstructionalActType.PROCESS, InstructionalActType.MECHANISM]:
                    signals["process"] += 1
                elif act.act_type == InstructionalActType.FORMULA:
                    signals["formula"] += 1
        
        # Check for numeric data in propositions
        if hasattr(frame, 'propositions'):
            for prop in frame.propositions:
                if prop.quantities:
                    signals["numeric"] += 1
        
        return signals
    
    def _determine(
        self,
        signals: Dict[str, int],
        frame: Any,
    ) -> tuple:
        """Determine representation from signals"""
        
        # Priority order: most specific first
        
        # 1. Formula
        if signals["formula"] > 0:
            return RepresentationType.FORMULA, 0.9, "Formula detected"
        
        # 2. Definition
        if signals["definition"] > 0 and signals["comparison"] == 0:
            return RepresentationType.DEFINITION, 0.85, "Definition detected"
        
        # 3. Comparison/Contrast
        if signals["comparison"] > 0:
            if signals["contrast"] > 0:
                return RepresentationType.CONTRAST, 0.8, "Contrasting concepts detected"
            return RepresentationType.COMPARISON, 0.75, "Comparison detected"
        
        # 4. Process/Sequence
        if signals["process"] > 0:
            return RepresentationType.FLOWCHART, 0.8, "Process/sequence detected"
        
        # 5. Causal chain
        if signals["causal"] > 0:
            return RepresentationType.CAUSAL_CHAIN, 0.75, "Causal relationship detected"
        
        # 6. Hierarchy/Classification
        if signals["hierarchy"] > 0:
            return RepresentationType.HIERARCHY, 0.75, "Hierarchical structure detected"
        
        # 7. Examples
        if signals["example"] > 0:
            return RepresentationType.EXAMPLE_GRID, 0.7, "Multiple examples detected"
        
        # 8. Numeric data
        if signals["numeric"] > 0:
            return RepresentationType.NUMBER_STATISTIC, 0.65, "Numeric data detected"
        
        # 9. Default: explanation
        return RepresentationType.EXPLANATION, 0.5, "General explanation"
    
    def _apply_rhythm(
        self,
        representation: RepresentationType,
    ) -> RepresentationType:
        """
        Avoid monotony - if same representation used 3+ times recently,
        try alternative if available.
        
        But content semantics always wins - only change if confidence is low.
        """
        if not self._recent_representations:
            return representation
        
        # Count recent same-type
        recent_count = sum(
            1 for r in self._recent_representations[-3:]
            if r == representation
        )
        
        # If 3 in a row, still keep (semantics wins)
        # Rhythm adjustment would only apply for EXPLANATION
        if representation == RepresentationType.EXPLANATION and recent_count >= 3:
            return RepresentationType.KEY_CONCEPT
        
        return representation
    
    def _visual_need(self, representation: RepresentationType) -> str:
        """Determine visual need"""
        needs = {
            RepresentationType.DEFINITION: "optional_diagram",
            RepresentationType.COMPARISON: "none",
            RepresentationType.CONTRAST: "none",
            RepresentationType.FLOWCHART: "none",
            RepresentationType.CAUSAL_CHAIN: "none",
            RepresentationType.HIERARCHY: "none",
            RepresentationType.EXAMPLE_GRID: "optional_icons",
            RepresentationType.NUMBER_STATISTIC: "none",
            RepresentationType.FORMULA: "none",
            RepresentationType.EXPLANATION: "optional_image",
            RepresentationType.KEY_CONCEPT: "optional_image",
        }
        return needs.get(representation, "none")
    
    def _supporting_visuals(self, representation: RepresentationType) -> List[str]:
        """Determine supporting visuals"""
        return []
    
    def get_recent_representations(self) -> List[RepresentationType]:
        with self._lock:
            return list(self._recent_representations)