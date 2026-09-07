"""
Semantic State Management

Thread-safe semantic state for the entire lecture.
No external dependencies beyond standard library.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Any
from datetime import datetime
import threading
import json

from .semantic_models import (
    Concept,
    Proposition,
    Relation,
    EvidenceSpan,
    Mention,
    SemanticEvent,
    SemanticEventType,
    PropositionLifecycle,
    GroundingStatus,
    ExtractionStatus,
    ConceptRef,
    RelationType
)


class SemanticState:
    """Thread-safe semantic state for the entire lecture"""

    def __init__(self, lecture_id: str = ""):
        self._lock = threading.RLock()
        self.lecture_id = lecture_id

        # Core registries
        self._concepts: Dict[str, Concept] = {}
        self._propositions: Dict[str, Proposition] = {}
        self._relations: Dict[str, Relation] = {}
        self._mentions: Dict[str, Mention] = {}

        # Alias index for fast concept lookup
        self._alias_index: Dict[str, str] = {}

        # Evidence index
        self._evidence_index: Dict[str, EvidenceSpan] = {}

        # Event log for replay
        self._event_log: List[SemanticEvent] = []

        # Active context (recent concepts)
        self._active_context: Dict[str, float] = {}

        # Topic-local memory
        self._topic_memory: Dict[str, Set[str]] = {}

        # Statistics
        self._stats = {
            "total_concepts": 0,
            "total_propositions": 0,
            "total_relations": 0,
            "total_mentions": 0,
            "total_events": 0,
            "total_evidence": 0
        }

    def apply_event(self, event: SemanticEvent) -> None:
        """Apply a semantic event to update state"""
        with self._lock:
            event_type = event.event_type
            payload = event.payload

            if event_type == SemanticEventType.CONCEPT_CREATED:
                self._handle_concept_created(payload)
            elif event_type == SemanticEventType.CONCEPT_MERGED:
                self._handle_concept_merged(payload)
            elif event_type == SemanticEventType.MENTION_LINKED:
                self._handle_mention_linked(payload)
            elif event_type == SemanticEventType.PROPOSITION_ADDED:
                self._handle_proposition_added(payload)
            elif event_type == SemanticEventType.PROPOSITION_SUPERSEDED:
                self._handle_proposition_superseded(payload)
            elif event_type == SemanticEventType.CONTRADICTION_DETECTED:
                self._handle_contradiction_detected(payload)

            self._event_log.append(event)
            self._stats["total_events"] += 1

    def _handle_concept_created(self, payload: Dict[str, Any]) -> None:
        concept_data = payload.get("concept", {})
        concept = Concept(
            concept_id=concept_data.get("concept_id", ""),
            canonical_name=concept_data.get("canonical_name", ""),
            aliases=concept_data.get("aliases", []),
            confidence=concept_data.get("confidence", 0.0),
            concept_type=concept_data.get("concept_type", "entity")
        )

        self._concepts[concept.concept_id] = concept

        for alias in concept.aliases:
            self._alias_index[self._normalize_key(alias)] = concept.concept_id

        self._stats["total_concepts"] += 1
        self._active_context[concept.concept_id] = 1.0

    def _handle_concept_merged(self, payload: Dict[str, Any]) -> None:
        source_id = payload.get("source_id", "")
        target_id = payload.get("target_id", "")

        if source_id in self._concepts and target_id in self._concepts:
            source_concept = self._concepts[source_id]
            target_concept = self._concepts[target_id]

            for alias in source_concept.aliases:
                if alias not in target_concept.aliases:
                    target_concept.aliases.append(alias)
                    self._alias_index[self._normalize_key(alias)] = target_id

            for prop in self._propositions.values():
                if prop.subject and prop.subject.concept_id == source_id:
                    prop.subject.concept_id = target_id
                if prop.object and prop.object.concept_id == source_id:
                    prop.object.concept_id = target_id

            del self._concepts[source_id]

            if source_id in self._active_context:
                activation = self._active_context.pop(source_id)
                self._active_context[target_id] = max(
                    self._active_context.get(target_id, 0.0),
                    activation
                )

    def _handle_mention_linked(self, payload: Dict[str, Any]) -> None:
        mention_data = payload.get("mention", {})
        mention = Mention(
            mention_id=mention_data.get("mention_id", ""),
            surface_text=mention_data.get("surface_text", ""),
            normalized_text=mention_data.get("normalized_text", ""),
            confidence=mention_data.get("confidence", 0.0)
        )

        self._mentions[mention.mention_id] = mention
        self._stats["total_mentions"] += 1

    def _handle_proposition_added(self, payload: Dict[str, Any]) -> None:
        prop_data = payload.get("proposition", {})
        proposition = Proposition(
            proposition_id=prop_data.get("proposition_id", ""),
            confidence=prop_data.get("confidence", 0.0),
            polarity=prop_data.get("polarity", True),
            modality=prop_data.get("modality", "fact"),
            evidence_ids=prop_data.get("evidence_ids", []),
            grounding_status=GroundingStatus(prop_data.get("grounding_status", "unsupported")),
            extraction_status=ExtractionStatus(prop_data.get("extraction_status", "uncertain")),
            lifecycle=PropositionLifecycle(prop_data.get("lifecycle", "active"))
        )

        if prop_data.get("subject"):
            proposition.subject = ConceptRef(**prop_data["subject"])
        if prop_data.get("object"):
            proposition.object = ConceptRef(**prop_data["object"])
        if prop_data.get("predicate"):
            proposition.predicate = RelationType(prop_data["predicate"])

        self._propositions[proposition.proposition_id] = proposition
        self._stats["total_propositions"] += 1

    def _handle_proposition_superseded(self, payload: Dict[str, Any]) -> None:
        old_id = payload.get("old_proposition_id", "")

        if old_id in self._propositions:
            self._propositions[old_id].lifecycle = PropositionLifecycle.SUPERSEDED
            self._propositions[old_id].updated_at = datetime.now()

    def _handle_contradiction_detected(self, payload: Dict[str, Any]) -> None:
        prop1_id = payload.get("proposition1_id", "")
        prop2_id = payload.get("proposition2_id", "")

        if prop1_id in self._propositions and prop2_id in self._propositions:
            self._propositions[prop1_id].lifecycle = PropositionLifecycle.CONTRADICTED
            self._propositions[prop2_id].lifecycle = PropositionLifecycle.CONTRADICTED

    def get_concept(self, concept_id: str) -> Optional[Concept]:
        with self._lock:
            return self._concepts.get(concept_id)

    def get_concept_by_alias(self, alias: str) -> Optional[Concept]:
        with self._lock:
            key = self._normalize_key(alias)
            concept_id = self._alias_index.get(key)
            if concept_id:
                return self._concepts.get(concept_id)
            return None

    def get_proposition(self, proposition_id: str) -> Optional[Proposition]:
        with self._lock:
            return self._propositions.get(proposition_id)

    def get_active_concepts(self, limit: int = 10) -> List[ConceptRef]:
        with self._lock:
            sorted_concepts = sorted(
                self._active_context.items(),
                key=lambda x: x[1],
                reverse=True
            )

            result = []
            for concept_id, activation in sorted_concepts[:limit]:
                concept = self._concepts.get(concept_id)
                if concept:
                    result.append(ConceptRef(
                        concept_id=concept_id,
                        canonical_name=concept.canonical_name,
                        confidence=activation
                    ))

            return result

    def get_concepts_by_topic(self, topic_path: str) -> List[Concept]:
        with self._lock:
            concept_ids = self._topic_memory.get(topic_path, set())
            return [self._concepts[cid] for cid in concept_ids if cid in self._concepts]

    def add_concept_to_topic(self, concept_id: str, topic_path: str) -> None:
        with self._lock:
            if topic_path not in self._topic_memory:
                self._topic_memory[topic_path] = set()
            self._topic_memory[topic_path].add(concept_id)

    def decay_active_context(self, decay_factor: float = 0.9) -> None:
        with self._lock:
            for concept_id in self._active_context:
                self._active_context[concept_id] *= decay_factor

            self._active_context = {
                cid: score for cid, score in self._active_context.items()
                if score > 0.1
            }

    def get_statistics(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "lecture_id": self.lecture_id,
                "concepts": {cid: c.to_dict() for cid, c in self._concepts.items()},
                "propositions": {pid: p.to_dict() for pid, p in self._propositions.items()},
                "active_context": self._active_context,
                "topic_memory": {k: list(v) for k, v in self._topic_memory.items()},
                "statistics": self._stats
            }

    def save_to_json(self, filepath: str) -> None:
        with self._lock:
            with open(filepath, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)

    def load_from_json(self, filepath: str) -> None:
        with self._lock:
            with open(filepath, 'r') as f:
                data = json.load(f)

            self.lecture_id = data.get("lecture_id", "")

            self._concepts.clear()
            for cid, cdata in data.get("concepts", {}).items():
                concept = Concept(
                    concept_id=cdata.get("concept_id", cid),
                    canonical_name=cdata.get("canonical_name", ""),
                    aliases=cdata.get("aliases", []),
                    confidence=cdata.get("confidence", 0.0),
                    concept_type=cdata.get("concept_type", "entity")
                )
                self._concepts[cid] = concept

                for alias in concept.aliases:
                    self._alias_index[self._normalize_key(alias)] = cid

            self._propositions.clear()
            for pid, pdata in data.get("propositions", {}).items():
                proposition = Proposition(
                    proposition_id=pdata.get("proposition_id", pid),
                    confidence=pdata.get("confidence", 0.0),
                    polarity=pdata.get("polarity", True),
                    modality=pdata.get("modality", "fact"),
                    grounding_status=GroundingStatus(pdata.get("grounding_status", "unsupported")),
                    extraction_status=ExtractionStatus(pdata.get("extraction_status", "uncertain")),
                    lifecycle=PropositionLifecycle(pdata.get("lifecycle", "active"))
                )
                self._propositions[pid] = proposition

            self._stats = data.get("statistics", self._stats)

    @staticmethod
    def _normalize_key(text: str) -> str:
        return text.lower().strip()