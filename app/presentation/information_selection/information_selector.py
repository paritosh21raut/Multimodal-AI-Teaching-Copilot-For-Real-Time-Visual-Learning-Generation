"""
Information Selector

Selects slide-worthy information from semantic frames.

Key principles:
- Not summarization - pedagogical selection
- Preserve essential claims, relations, contrasts
- Avoid transcript repetition
- Every displayed item must have evidence
- Select focal claim + supporting units
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
import threading

from app.presentation.models.presentation_models import (
    SelectedInformation,
    ContentBlockType,
)


class InformationSelector:
    """
    Selects information for slide display.
    
    Uses:
    - Semantic propositions (what was said)
    - Relations (how concepts connect)
    - Definitions (what was defined)
    - Examples (what was exemplified)
    - Numbers (what quantities were given)
    - Formulas (what equations were stated)
    """
    
    def __init__(
        self,
        max_semantic_units: int = 6,
        max_definitions: int = 2,
        max_examples: int = 3,
        max_relations: int = 4,
        min_confidence: float = 0.5,
    ):
        self.max_semantic_units = max_semantic_units
        self.max_definitions = max_definitions
        self.max_examples = max_examples
        self.max_relations = max_relations
        self.min_confidence = min_confidence
        
        self._lock = threading.RLock()
        self._displayed_units: Set[str] = set()
    
    def select(
        self,
        frame: Any,
        important_concepts: List[str] = None,
    ) -> SelectedInformation:
        """
        Select slide-worthy information from a semantic frame.
        
        Args:
            frame: SemanticFrame with concepts, propositions, relations, acts
            important_concepts: List of important concept names
            
        Returns:
            SelectedInformation
        """
        with self._lock:
            important_concepts = important_concepts or []
            
            # Initialize selection
            selection = SelectedInformation()
            
            # ==========================================
            # 1. Select focal claim (most important proposition)
            # ==========================================
            focal = self._select_focal_claim(frame, important_concepts)
            selection.focal_claim = focal
            
            # ==========================================
            # 2. Select propositions (filtered)
            # ==========================================
            propositions = self._select_propositions(frame, important_concepts)
            selection.semantic_units = propositions
            
            # ==========================================
            # 3. Select definitions
            # ==========================================
            definitions = self._select_definitions(frame)
            selection.definitions = definitions[:self.max_definitions]
            
            # ==========================================
            # 4. Select examples
            # ==========================================
            examples = self._select_examples(frame)
            selection.examples = examples[:self.max_examples]
            
            # ==========================================
            # 5. Select relations
            # ==========================================
            relations = self._select_relations(frame)
            selection.relations = relations[:self.max_relations]
            
            # ==========================================
            # 6. Select numbers
            # ==========================================
            numbers = self._select_numbers(frame)
            selection.numbers = numbers
            
            # ==========================================
            # 7. Select formulas
            # ==========================================
            formulas = self._select_formulas(frame)
            selection.formula = formulas
            
            # ==========================================
            # 8. Collect evidence IDs
            # ==========================================
            selection.evidence_ids = self._collect_evidence(frame)
            
            # ==========================================
            # 9. Calculate priority and redundancy
            # ==========================================
            selection.priority = self._calculate_priority(
                selection, important_concepts
            )
            selection.redundancy_score = self._calculate_redundancy(selection)
            
            return selection
    
    def _select_focal_claim(
        self,
        frame: Any,
        important_concepts: List[str],
    ) -> str:
        """
        Select the most important claim as focal message.
        
        Priority:
        1. Definition of important concept
        2. Proposition involving important concept
        3. First proposition
        """
        if not frame or not hasattr(frame, 'propositions'):
            return ""
        
        propositions = frame.propositions
        
        if not propositions:
            return ""
        
        # Check for definition
        for prop in propositions:
            if (
                prop.subject
                and prop.subject.canonical_name in important_concepts
                and prop.predicate
                and prop.predicate.value == "DEFINED_AS"
            ):
                return f"{prop.subject.canonical_name} = {prop.object.canonical_name}"
        
        # Check for proposition involving important concept
        for prop in propositions:
            if (
                prop.subject
                and prop.subject.canonical_name in important_concepts
                and prop.predicate
                and prop.object
            ):
                return f"{prop.subject.canonical_name} {prop.predicate.value} {prop.object.canonical_name}"
        
        # Fallback: first proposition
        first = propositions[0]
        if first.subject and first.object and first.predicate:
            return f"{first.subject.canonical_name} {first.predicate.value} {first.object.canonical_name}"
        
        return ""
    
    def _select_propositions(
        self,
        frame: Any,
        important_concepts: List[str],
    ) -> List[str]:
        """
        Select propositions for display.
        
        Priority:
        1. Involve important concepts
        2. High confidence
        3. Not previously displayed
        """
        if not frame or not hasattr(frame, 'propositions'):
            return []
        
        selected = []
        
        # First pass: important concept propositions
        for prop in frame.propositions:
            if len(selected) >= self.max_semantic_units:
                break
            
            if not prop.subject or not prop.object or not prop.predicate:
                continue
            
            if prop.confidence < self.min_confidence:
                continue
            
            text = f"{prop.subject.canonical_name} {prop.predicate.value} {prop.object.canonical_name}"
            
            # Skip if already displayed
            if text in self._displayed_units:
                continue
            
            # Prioritize important concepts
            if (
                prop.subject.canonical_name in important_concepts
                or prop.object.canonical_name in important_concepts
            ):
                selected.append(text)
                self._displayed_units.add(text)
        
        # Second pass: other propositions
        for prop in frame.propositions:
            if len(selected) >= self.max_semantic_units:
                break
            
            if not prop.subject or not prop.object or not prop.predicate:
                continue
            
            if prop.confidence < self.min_confidence:
                continue
            
            text = f"{prop.subject.canonical_name} {prop.predicate.value} {prop.object.canonical_name}"
            
            if text in self._displayed_units:
                continue
            
            selected.append(text)
            self._displayed_units.add(text)
        
        return selected
    
    def _select_definitions(self, frame: Any) -> List[str]:
        """Select definitions from instructional acts"""
        if not frame or not hasattr(frame, 'instructional_acts'):
            return []
        
        definitions = []
        
        for act in frame.instructional_acts:
            if hasattr(act, 'act_type') and act.act_type.value == "DEFINITION":
                for ref in act.concept_refs:
                    definitions.append(ref.canonical_name)
        
        return definitions
    
    def _select_examples(self, frame: Any) -> List[str]:
        """Select examples from instructional acts"""
        if not frame or not hasattr(frame, 'instructional_acts'):
            return []
        
        examples = []
        
        for act in frame.instructional_acts:
            if hasattr(act, 'act_type') and act.act_type.value == "EXAMPLE":
                for ref in act.concept_refs:
                    examples.append(ref.canonical_name)
        
        return examples
    
    def _select_relations(self, frame: Any) -> List[str]:
        """Select relations for display"""
        if not frame or not hasattr(frame, 'relations'):
            return []
        
        relations = []
        
        for rel in frame.relations:
            if not rel.source or not rel.target or not rel.relation_type:
                continue
            
            if rel.confidence < self.min_confidence:
                continue
            
            text = f"{rel.source.canonical_name} {rel.relation_type.value} {rel.target.canonical_name}"
            relations.append(text)
        
        return relations
    
    def _select_numbers(self, frame: Any) -> List[Dict[str, Any]]:
        """Select numeric data"""
        if not frame or not hasattr(frame, 'propositions'):
            return []
        
        numbers = []
        
        for prop in frame.propositions:
            if prop.quantities:
                numbers.append({
                    "label": prop.subject.canonical_name if prop.subject else "",
                    "value": prop.quantities,
                })
        
        return numbers
    
    def _select_formulas(self, frame: Any) -> List[str]:
        """Select formulas"""
        if not frame or not hasattr(frame, 'instructional_acts'):
            return []
        
        formulas = []
        
        for act in frame.instructional_acts:
            if hasattr(act, 'act_type') and act.act_type.value == "FORMULA":
                formulas.append(act.act_type.value)
        
        return formulas
    
    def _collect_evidence(self, frame: Any) -> List[str]:
        """Collect evidence IDs"""
        if not frame:
            return []
        
        evidence_ids = []
        
        if hasattr(frame, 'propositions'):
            for prop in frame.propositions:
                evidence_ids.extend(prop.evidence_ids)
        
        return list(set(evidence_ids))
    
    def _calculate_priority(
        self,
        selection: SelectedInformation,
        important_concepts: List[str],
    ) -> float:
        """Calculate priority based on content richness"""
        score = 0.0
        
        if selection.focal_claim:
            score += 0.3
        
        score += min(0.3, len(selection.semantic_units) * 0.05)
        score += min(0.2, len(selection.definitions) * 0.1)
        score += min(0.2, len(selection.examples) * 0.07)
        
        return round(min(1.0, score), 3)
    
    def _calculate_redundancy(self, selection: SelectedInformation) -> float:
        """Calculate redundancy (how much information is repeated)"""
        if not selection.semantic_units:
            return 0.0
        
        # Simple redundancy: check if focal claim is repeated in units
        redundant = 0
        for unit in selection.semantic_units:
            if selection.focal_claim and selection.focal_claim in unit:
                redundant += 1
        
        return round(redundant / len(selection.semantic_units), 3)
    
    def reset_displayed_units(self):
        """Reset displayed units (e.g., new slide)"""
        with self._lock:
            self._displayed_units.clear()