"""
InformationSelector — Fixed to preserve structured semantic evidence.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Set
import threading

from app.presentation.models.presentation_models import SelectedInformation, SemanticEvidence


class InformationSelector:
    """Selects WHAT goes on screen. Does NOT generate display text."""
    
    def __init__(self, max_semantic_units=6, min_confidence=0.5):
        self.max_semantic_units = max_semantic_units
        self.min_confidence = min_confidence
        self._lock = threading.RLock()
        self._displayed_units: Set[str] = set()
    
    def select(self, frame, important_concepts=None):
        with self._lock:
            important_concepts = important_concepts or []
            selection = SelectedInformation()
            
            # Select focal claim (structured)
            selection.focal_claim = self._select_focal_claim(frame, important_concepts)
            
            # Select structured semantic evidence (NOT display text)
            selection.semantic_units = self._select_evidence(frame, important_concepts)
            
            # Collect definitions, examples as references
            selection.definitions = self._select_definitions(frame)
            selection.examples = self._select_examples(frame)
            
            selection.evidence_ids = self._collect_evidence(frame)
            selection.priority = self._calculate_priority(selection)
            
            return selection
    
    def _select_focal_claim(self, frame, important_concepts):
        """Return SemanticEvidence, not string."""
        if not frame or not hasattr(frame, 'propositions'):
            return None
        
        for prop in frame.propositions:
            if prop.subject and prop.predicate and prop.object:
                if prop.subject.canonical_name in important_concepts:
                    return SemanticEvidence(
                        subject=prop.subject.canonical_name,
                        predicate=prop.predicate.value,
                        object=prop.object.canonical_name,
                        evidence_id=prop.evidence_ids[0] if prop.evidence_ids else "",
                        confidence=prop.confidence,
                    )
        
        # Fallback: first proposition
        for prop in frame.propositions:
            if prop.subject and prop.predicate and prop.object:
                return SemanticEvidence(
                    subject=prop.subject.canonical_name,
                    predicate=prop.predicate.value,
                    object=prop.object.canonical_name,
                    evidence_id=prop.evidence_ids[0] if prop.evidence_ids else "",
                    confidence=prop.confidence,
                )
        
        return None
    
    def _select_evidence(self, frame, important_concepts):
        """Return List[SemanticEvidence], not List[str]."""
        evidence_list = []
        
        if not hasattr(frame, 'propositions'):
            return evidence_list
        
        for prop in frame.propositions:
            if len(evidence_list) >= self.max_semantic_units:
                break
            
            if not prop.subject or not prop.object or not prop.predicate:
                continue
            
            if prop.confidence < self.min_confidence:
                continue
            
            key = f"{prop.subject.canonical_name}_{prop.predicate.value}_{prop.object.canonical_name}"
            if key in self._displayed_units:
                continue
            
            self._displayed_units.add(key)
            
            evidence_list.append(SemanticEvidence(
                subject=prop.subject.canonical_name,
                predicate=prop.predicate.value,
                object=prop.object.canonical_name,
                evidence_id=prop.evidence_ids[0] if prop.evidence_ids else "",
                confidence=prop.confidence,
            ))
        
        return evidence_list
    
    def _select_definitions(self, frame):
        definitions = []
        if hasattr(frame, 'instructional_acts'):
            for act in frame.instructional_acts:
                if act.act_type and act.act_type.value == "DEFINITION":
                    for ref in act.concept_refs:
                        definitions.append(ref.canonical_name)
        return definitions
    
    def _select_examples(self, frame):
        examples = []
        if hasattr(frame, 'instructional_acts'):
            for act in frame.instructional_acts:
                if act.act_type and act.act_type.value == "EXAMPLE":
                    for ref in act.concept_refs:
                        examples.append(ref.canonical_name)
        return examples
    
    def _collect_evidence(self, frame):
        ids = []
        if hasattr(frame, 'propositions'):
            for prop in frame.propositions:
                ids.extend(prop.evidence_ids)
        return list(set(ids))
    
    def _calculate_priority(self, selection):
        score = 0.0
        if selection.focal_claim:
            score += 0.4
        score += min(0.3, len(selection.semantic_units) * 0.05)
        return min(1.0, score)
    
    def reset_displayed_units(self):
        with self._lock:
            self._displayed_units.clear()