"""
Development Intelligence Tracker (PHASE 3)

Structured pedagogical coverage drives stage.
Legacy scalar (development_score) preserved with Phase 2 formula for
backward compatibility with importance scorer.

Changes from Phase 2:
- New field `development_index` = structured coverage + gated evidence.
- `state` derived from `development_index`, not `development_score`.
- Repetition dedup: identical (subject,predicate,object) counted once.
- Low-confidence gating: 0 < confidence < 0.30 is ignored.
- Contradiction gating: lifecycle in {CONTRADICTED, SUPERSEDED, RETRACTED} ignored.
- Trajectory log per concept.
- Topic anchor (LSI node_id) propagated from caller.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import threading

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
    PropositionLifecycle,
)


class DevelopmentTracker:

    MIN_EVIDENCE_CONFIDENCE = 0.30
    CONTRADICTED_LIFECYCLES = {
        PropositionLifecycle.CONTRADICTED,
        PropositionLifecycle.SUPERSEDED,
        PropositionLifecycle.RETRACTED,
    }

    # Structured index weights (drive stage)
    IDX_MENTION = 0.10
    IDX_PROP = 0.075
    IDX_DEF = 0.15
    IDX_EXAMPLE = 0.15
    IDX_RELATION = 0.075

    CAP_MENTION = 0.30
    CAP_PROP = 0.15
    CAP_DEF = 0.15
    CAP_EXAMPLE = 0.15
    CAP_RELATION = 0.15

    DEVELOPING_THRESHOLD = 0.15
    ESTABLISHED_THRESHOLD = 0.40
    FULLY_EXPLAINED_THRESHOLD = 0.70

    # Legacy Phase 2 scalar weights (for development_score compatibility)
    W_MENTION = 0.20
    W_PROPOSITION = 0.25
    W_DEFINITION = 0.25
    W_EXAMPLE = 0.25
    W_RELATION = 0.10
    W_COVERAGE = 0.25

    def __init__(self):
        self._lock = threading.RLock()
        self._concepts: Dict[str, ConceptDevelopment] = {}
        self._explicit_concepts: Set[str] = set()

        self.weights = {
            "mention": self.W_MENTION,
            "proposition": self.W_PROPOSITION,
            "definition": self.W_DEFINITION,
            "example": self.W_EXAMPLE,
            "relation": self.W_RELATION,
            "coverage": self.W_COVERAGE,
        }
        self.developing_threshold = self.DEVELOPING_THRESHOLD
        self.established_threshold = self.ESTABLISHED_THRESHOLD
        self.fully_explained_threshold = self.FULLY_EXPLAINED_THRESHOLD

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(
        self,
        frame: SemanticFrame,
        chunk_id: str = "",
        topic_node_id: Optional[int] = None,
    ) -> None:
        with self._lock:
            self._process_concepts(frame, chunk_id, topic_node_id)
            self._process_instructional_acts(frame, chunk_id)
            self._process_propositions(frame, chunk_id)
            self._process_relations(frame, chunk_id)

            for concept_id in self._concepts:
                self._recalculate(concept_id)

    def get_development(self, concept_id: str) -> Optional[ConceptDevelopment]:
        with self._lock:
            return self._concepts.get(concept_id)

    def get_all_developments(self) -> List[ConceptDevelopment]:
        with self._lock:
            return list(self._concepts.values())

    def get_coverage_report(self, concept_id: str) -> Dict[str, Any]:
        dev = self.get_development(concept_id)
        if not dev:
            return {}
        return {
            "concept": dev.canonical_name,
            "state": dev.state.value,
            "development_score": dev.development_score,
            "development_index": dev.development_index,
            "coverage_percentage": dev.coverage_percentage(),
            "covered_dimensions": [d.value for d in dev.covered_dimensions()],
            "missing_dimensions": [d.value for d in dev.missing_dimensions()],
            "evidence_ids": list(dev.evidence_ids),
            "trajectory": list(dev.trajectory),
            "topic_node_id": dev.topic_node_id,
        }

    def get_gaps(self, concept_id: str) -> List[str]:
        dev = self.get_development(concept_id)
        if not dev:
            return []
        return [d.value for d in dev.missing_dimensions()]

    def get_trajectory(self, concept_id: str) -> List[Dict[str, str]]:
        dev = self.get_development(concept_id)
        if not dev:
            return []
        return list(dev.trajectory)

    def get_top_developed(self, limit: int = 10) -> List[ConceptDevelopment]:
        with self._lock:
            sorted_concepts = sorted(
                self._concepts.values(),
                key=lambda x: (x.development_index, x.development_score),
                reverse=True,
            )
            return sorted_concepts[:limit]

    def get_statistics(self) -> Dict[str, int]:
        with self._lock:
            states = [d.state for d in self._concepts.values()]
            return {
                "total_concepts": len(self._concepts),
                "mentioned": sum(1 for s in states if s == DevelopmentState.MENTIONED),
                "developing": sum(1 for s in states if s == DevelopmentState.DEVELOPING),
                "established": sum(1 for s in states if s == DevelopmentState.ESTABLISHED),
                "fully_explained": sum(1 for s in states if s == DevelopmentState.FULLY_EXPLAINED),
            }

    def reset(self) -> None:
        with self._lock:
            self._concepts.clear()
            self._explicit_concepts.clear()

    # ------------------------------------------------------------------
    # Internal processing
    # ------------------------------------------------------------------

    def _process_concepts(
        self,
        frame: SemanticFrame,
        chunk_id: str,
        topic_node_id: Optional[int],
    ) -> None:
        for concept in frame.concepts:
            self._explicit_concepts.add(concept.concept_id)
            dev = self._get_or_create(concept, topic_node_id=topic_node_id)
            dev.mention_count += 1
            dev.last_seen = datetime.now()
            if topic_node_id is not None:
                dev.last_seen_topic_id = topic_node_id
            newly = dev.mark_covered(CoverageDimension.INTRODUCED, concept.concept_id)
            if newly and chunk_id:
                dev.trajectory.append({
                    "dimension": CoverageDimension.INTRODUCED.value,
                    "chunk_id": chunk_id,
                    "timestamp": datetime.now().isoformat(),
                })
            if chunk_id and chunk_id not in dev.distinct_chunks:
                dev.distinct_chunks.append(chunk_id)

    def _process_instructional_acts(self, frame: SemanticFrame, chunk_id: str) -> None:
        for act in frame.instructional_acts:
            if not act.act_type:
                continue
            if not self._evidence_confidence_ok(act.confidence):
                continue

            for ref in act.concept_refs:
                if ref.concept_id not in self._explicit_concepts:
                    continue
                dev = self._concepts.get(ref.concept_id)
                if not dev:
                    continue

                dimension = self._act_to_dimension(act.act_type)
                if dimension:
                    evidence_id = act.act_id or (act.evidence_ids[0] if act.evidence_ids else "")
                    newly = dev.mark_covered(dimension, evidence_id)
                    if newly and chunk_id:
                        dev.trajectory.append({
                            "dimension": dimension.value,
                            "chunk_id": chunk_id,
                            "timestamp": datetime.now().isoformat(),
                        })

                if act.act_type == InstructionalActType.DEFINITION:
                    dev.definition_count += 1
                elif act.act_type == InstructionalActType.EXAMPLE:
                    dev.example_count += 1

    def _process_propositions(self, frame: SemanticFrame, chunk_id: str) -> None:
        for prop in frame.propositions:
            if not prop.subject or not prop.object or not prop.predicate:
                continue
            if prop.lifecycle in self.CONTRADICTED_LIFECYCLES:
                continue
            if not self._evidence_confidence_ok(prop.confidence):
                continue

            signature = self._proposition_signature(prop)

            if prop.subject.concept_id in self._explicit_concepts:
                dev = self._concepts.get(prop.subject.concept_id)
                if dev and signature not in dev.seen_proposition_signatures:
                    dev.seen_proposition_signatures.add(signature)
                    dev.proposition_count += 1
                    dimension = self._relation_to_dimension(prop.predicate)
                    if dimension:
                        newly = dev.mark_covered(dimension, prop.proposition_id)
                        if newly and chunk_id:
                            dev.trajectory.append({
                                "dimension": dimension.value,
                                "chunk_id": chunk_id,
                                "timestamp": datetime.now().isoformat(),
                            })

            if prop.object.concept_id in self._explicit_concepts:
                dev = self._concepts.get(prop.object.concept_id)
                if dev and signature not in dev.seen_proposition_signatures:
                    dev.seen_proposition_signatures.add(signature)
                    dev.proposition_count += 0.5

    def _process_relations(self, frame: SemanticFrame, chunk_id: str) -> None:
        for rel in frame.relations:
            if not rel.source or not rel.relation_type:
                continue
            if not self._evidence_confidence_ok(rel.confidence):
                continue

            signature = self._relation_signature(rel)

            if rel.source.concept_id in self._explicit_concepts:
                dev = self._concepts.get(rel.source.concept_id)
                if dev and signature not in dev.seen_relation_signatures:
                    dev.seen_relation_signatures.add(signature)
                    dev.relation_count += 1
                    dimension = self._relation_to_dimension(rel.relation_type)
                    if dimension:
                        newly = dev.mark_covered(dimension, rel.relation_id)
                        if newly and chunk_id:
                            dev.trajectory.append({
                                "dimension": dimension.value,
                                "chunk_id": chunk_id,
                                "timestamp": datetime.now().isoformat(),
                            })

    # ------------------------------------------------------------------
    # Evidence gating
    # ------------------------------------------------------------------

    def _evidence_confidence_ok(self, confidence: Optional[float]) -> bool:
        if confidence is None:
            return True
        if confidence == 0.0:
            return True
        return confidence >= self.MIN_EVIDENCE_CONFIDENCE

    @staticmethod
    def _proposition_signature(prop: Proposition) -> str:
        subj = prop.subject.concept_id if prop.subject else ""
        obj = prop.object.concept_id if prop.object else ""
        pred = prop.predicate.value if prop.predicate else ""
        return f"{subj}|{pred}|{obj}"

    @staticmethod
    def _relation_signature(rel: Relation) -> str:
        src = rel.source.concept_id if rel.source else ""
        tgt = rel.target.concept_id if rel.target else ""
        rt = rel.relation_type.value if rel.relation_type else ""
        return f"{src}|{rt}|{tgt}"

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def _act_to_dimension(self, act_type: InstructionalActType) -> Optional[CoverageDimension]:
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

    def _relation_to_dimension(self, relation_type: RelationType) -> Optional[CoverageDimension]:
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

    # ------------------------------------------------------------------
    # State creation / recalculation
    # ------------------------------------------------------------------

    def _get_or_create(
        self,
        concept: Concept,
        topic_node_id: Optional[int] = None,
    ) -> ConceptDevelopment:
        existing = self._concepts.get(concept.concept_id)
        if existing is None:
            dev = ConceptDevelopment(
                concept_id=concept.concept_id,
                canonical_name=concept.canonical_name,
                confidence=concept.confidence,
                topic_node_id=topic_node_id,
                first_seen_topic_id=topic_node_id,
                last_seen_topic_id=topic_node_id,
            )
            self._concepts[concept.concept_id] = dev
            return dev

        if topic_node_id is not None:
            if existing.first_seen_topic_id is None:
                existing.first_seen_topic_id = topic_node_id
            existing.last_seen_topic_id = topic_node_id
            existing.topic_node_id = topic_node_id
        return existing

    def _recalculate(self, concept_id: str) -> None:
        dev = self._concepts[concept_id]

        # Phase 2 scalar (compatibility)
        coverage_pct = dev.coverage_percentage()
        scalar = (
            min(1.0, dev.mention_count / 3) * self.W_MENTION +
            min(1.0, dev.proposition_count / 3) * self.W_PROPOSITION +
            min(1.0, dev.definition_count) * self.W_DEFINITION +
            min(1.0, dev.example_count) * self.W_EXAMPLE +
            min(1.0, dev.relation_count / 3) * self.W_RELATION +
            coverage_pct * self.W_COVERAGE
        )
        dev.development_score = round(min(1.0, scalar), 4)

        # Structured index (drives stage)
        mention_component = min(self.CAP_MENTION, dev.mention_count * self.IDX_MENTION)
        prop_component = min(self.CAP_PROP, dev.proposition_count * self.IDX_PROP)
        def_component = min(self.CAP_DEF, dev.definition_count * self.IDX_DEF)
        ex_component = min(self.CAP_EXAMPLE, dev.example_count * self.IDX_EXAMPLE)
        rel_component = min(self.CAP_RELATION, dev.relation_count * self.IDX_RELATION)

        index = mention_component + prop_component + def_component + ex_component + rel_component
        dev.development_index = round(min(1.0, index), 4)

        non_intro = dev.non_introduced_coverage_count()

        if dev.development_index >= self.FULLY_EXPLAINED_THRESHOLD and non_intro >= 3:
            dev.state = DevelopmentState.FULLY_EXPLAINED
        elif dev.development_index >= self.ESTABLISHED_THRESHOLD and non_intro >= 1:
            dev.state = DevelopmentState.ESTABLISHED
        elif dev.development_index >= self.DEVELOPING_THRESHOLD:
            dev.state = DevelopmentState.DEVELOPING
        else:
            dev.state = DevelopmentState.MENTIONED