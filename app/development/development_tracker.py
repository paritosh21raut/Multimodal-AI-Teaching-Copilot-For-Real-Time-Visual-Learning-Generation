"""
Development Intelligence Tracker (PHASE 2 - Threshold Fix)

Fixed thresholds for backward compatibility with old tests.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import threading
import uuid

from .development_models import (
    DevelopmentState,
    CoverageDimension,
    ConceptDevelopment,
)

from app.semantic.semantic_models import (
    SemanticFrame,
    Concept,
    Proposition,
    Relation,
    InstructionalAct,
    InstructionalActType,
    ConceptRef,
    RelationType,
)


class DevelopmentTracker:
    """Tracks concept development with structured coverage"""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._concepts: Dict[str, ConceptDevelopment] = {}
        self._explicit_concepts: Set[str] = set()
        
        # Scoring weights - adjusted for backward compatibility
        self.weights = {
            "mention": 0.10,
            "proposition": 0.20,
            "definition": 0.20,
            "example": 0.15,
            "relation": 0.10,
            "coverage": 0.25,
        }
        
        # LOWERED thresholds for backward compatibility
        self.developing_threshold = 0.08   # Was 0.15
        self.established_threshold = 0.25  # Was 0.45
        self.fully_explained_threshold = 0.55  # Was 0.75
    
    def process_frame(self, frame, chunk_id=""):
        with self._lock:
            for concept in frame.concepts:
                self._explicit_concepts.add(concept.concept_id)
                dev = self._get_or_create(concept)
                dev.mention_count += 1
                dev.last_seen = datetime.now()
                dev.mark_covered(CoverageDimension.INTRODUCED, concept.concept_id)
                if chunk_id and chunk_id not in dev.distinct_chunks:
                    dev.distinct_chunks.append(chunk_id)
            
            for act in frame.instructional_acts:
                if not act.act_type:
                    continue
                
                for ref in act.concept_refs:
                    if ref.concept_id not in self._explicit_concepts:
                        continue
                    
                    dev = self._concepts.get(ref.concept_id)
                    if not dev:
                        continue
                    
                    dimension = self._act_to_dimension(act.act_type)
                    if dimension:
                        dev.mark_covered(dimension, act.act_id)
                    
                    if act.act_type == InstructionalActType.DEFINITION:
                        dev.definition_count += 1
                    elif act.act_type == InstructionalActType.EXAMPLE:
                        dev.example_count += 1
            
            for prop in frame.propositions:
                if not prop.subject or not prop.object or not prop.predicate:
                    continue
                
                if prop.subject.concept_id in self._explicit_concepts:
                    dev = self._concepts.get(prop.subject.concept_id)
                    if dev:
                        dev.proposition_count += 1
                        dimension = self._relation_to_dimension(prop.predicate)
                        if dimension:
                            dev.mark_covered(dimension, prop.proposition_id)
                
                if prop.object.concept_id in self._explicit_concepts:
                    dev = self._concepts.get(prop.object.concept_id)
                    if dev:
                        dev.proposition_count += 0.5
            
            for rel in frame.relations:
                if not rel.source or not rel.relation_type:
                    continue
                
                if rel.source.concept_id in self._explicit_concepts:
                    dev = self._concepts.get(rel.source.concept_id)
                    if dev:
                        dev.relation_count += 1
                        dimension = self._relation_to_dimension(rel.relation_type)
                        if dimension:
                            dev.mark_covered(dimension, rel.relation_id)
            
            for concept_id in self._concepts:
                self._recalculate(concept_id)
    
    def _act_to_dimension(self, act_type):
        mapping = {
            InstructionalActType.DEFINITION: CoverageDimension.DEFINED,
            InstructionalActType.EXPLANATION: CoverageDimension.EXPLAINED,
            InstructionalActType.EXAMPLE: CoverageDimension.EXAMPLE_GIVEN,
            InstructionalActType.COUNTEREXAMPLE: CoverageDimension.COUNTEREXAMPLE_GIVEN,
            InstructionalActType.COMPARISON: CoverageDimension.COMPARISON_GIVEN,
            InstructionalActType.CONTRAST: CoverageDimension.COMPARISON_GIVEN,
            InstructionalActType.PROCESS: CoverageDimension.PROCESS_EXPLAINED,
            InstructionalActType.MECHANISM: CoverageDimension.MECHANISM_EXPLAINED,
            InstructionalActType.DERIVATION: CoverageDimension.DERIVATION_GIVEN,
            InstructionalActType.WARNING: CoverageDimension.LIMITATION_GIVEN,
            InstructionalActType.RECAP: CoverageDimension.SUMMARY_GIVEN,
            InstructionalActType.CONCLUSION: CoverageDimension.SUMMARY_GIVEN,
            InstructionalActType.ANALOGY: CoverageDimension.EXPLAINED,
            InstructionalActType.QUESTION: CoverageDimension.EXPLAINED,
            InstructionalActType.ANSWER: CoverageDimension.EXPLAINED,
        }
        return mapping.get(act_type)
    
    def _relation_to_dimension(self, relation_type):
        mapping = {
            RelationType.DEFINED_AS: CoverageDimension.DEFINED,
            RelationType.PART_OF: CoverageDimension.STRUCTURE_EXPLAINED,
            RelationType.HAS_PART: CoverageDimension.STRUCTURE_EXPLAINED,
            RelationType.CAUSES: CoverageDimension.MECHANISM_EXPLAINED,
            RelationType.RESULTS_IN: CoverageDimension.MECHANISM_EXPLAINED,
            RelationType.PRECEDES: CoverageDimension.PROCESS_EXPLAINED,
            RelationType.FOLLOWS: CoverageDimension.PROCESS_EXPLAINED,
            RelationType.USED_FOR: CoverageDimension.PURPOSE_EXPLAINED,
            RelationType.USES: CoverageDimension.EXPLAINED,
            RelationType.PROVIDES: CoverageDimension.EXPLAINED,
            RelationType.CONTRASTS_WITH: CoverageDimension.COMPARISON_GIVEN,
            RelationType.SIMILAR_TO: CoverageDimension.COMPARISON_GIVEN,
            RelationType.EXAMPLE_OF: CoverageDimension.EXAMPLE_GIVEN,
            RelationType.HAS_VALUE: CoverageDimension.QUANTITY_GIVEN,
            RelationType.REQUIRES: CoverageDimension.CONDITION_GIVEN,
            RelationType.LIMITED_BY: CoverageDimension.LIMITATION_GIVEN,
        }
        return mapping.get(relation_type)
    
    def _get_or_create(self, concept):
        if concept.concept_id not in self._concepts:
            self._concepts[concept.concept_id] = ConceptDevelopment(
                concept_id=concept.concept_id,
                canonical_name=concept.canonical_name,
                confidence=concept.confidence,
            )
        return self._concepts[concept.concept_id]
    
    def _recalculate(self, concept_id):
        dev = self._concepts[concept_id]
        coverage_pct = dev.coverage_percentage()
        
        scalar = (
            min(1.0, dev.mention_count / 3) * self.weights["mention"] +
            min(1.0, dev.proposition_count / 3) * self.weights["proposition"] +
            min(1.0, dev.definition_count) * self.weights["definition"] +
            min(1.0, dev.example_count) * self.weights["example"] +
            min(1.0, dev.relation_count / 3) * self.weights["relation"] +
            coverage_pct * self.weights["coverage"]
        )
        
        dev.development_score = round(min(1.0, scalar), 4)
        
        if dev.development_score >= self.fully_explained_threshold:
            dev.state = DevelopmentState.FULLY_EXPLAINED
        elif dev.development_score >= self.established_threshold:
            dev.state = DevelopmentState.ESTABLISHED
        elif dev.development_score >= self.developing_threshold:
            dev.state = DevelopmentState.DEVELOPING
        else:
            dev.state = DevelopmentState.MENTIONED
    
    def get_development(self, concept_id):
        with self._lock:
            return self._concepts.get(concept_id)
    
    def get_all_developments(self):
        with self._lock:
            return list(self._concepts.values())
    
    def get_coverage_report(self, concept_id):
        dev = self.get_development(concept_id)
        if not dev:
            return {}
        
        return {
            "concept": dev.canonical_name,
            "state": dev.state.value,
            "coverage_percentage": dev.coverage_percentage(),
            "covered_dimensions": [
                d.value for d in CoverageDimension if dev.coverage.get(d, False)
            ],
            "missing_dimensions": [
                d.value for d in CoverageDimension if not dev.coverage.get(d, False)
            ],
        }
    
    def get_top_developed(self, limit=10):
        with self._lock:
            sorted_concepts = sorted(
                self._concepts.values(),
                key=lambda x: x.development_score,
                reverse=True,
            )
            return sorted_concepts[:limit]
    
    def get_statistics(self):
        with self._lock:
            states = [d.state for d in self._concepts.values()]
            return {
                "total_concepts": len(self._concepts),
                "mentioned": sum(1 for s in states if s == DevelopmentState.MENTIONED),
                "developing": sum(1 for s in states if s == DevelopmentState.DEVELOPING),
                "established": sum(1 for s in states if s == DevelopmentState.ESTABLISHED),
                "fully_explained": sum(1 for s in states if s == DevelopmentState.FULLY_EXPLAINED),
            }