"""
Evidence Management

Handles evidence span creation, tracking, and grounding validation.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import hashlib
import uuid

from .semantic_models import EvidenceSpan, GroundingStatus


class EvidenceManager:
    """Manages evidence spans and grounding validation"""

    def __init__(self):
        self._evidence_spans: Dict[str, EvidenceSpan] = {}
        self._proposition_evidence: Dict[str, List[str]] = {}
        self._concept_evidence: Dict[str, List[str]] = {}

    def create_evidence(
        self,
        chunk_id: str,
        text: str,
        start_char: int = 0,
        end_char: int = 0,
        transcript_id: str = "",
        sentence_id: str = "",
        timestamp: Optional[float] = None,
        asr_confidence: Optional[float] = None
    ) -> EvidenceSpan:
        """Create a new evidence span"""
        evidence = EvidenceSpan(
            evidence_id=str(uuid.uuid4()),
            chunk_id=chunk_id,
            transcript_id=transcript_id,
            sentence_id=sentence_id,
            start_char=start_char,
            end_char=end_char if end_char > 0 else len(text),
            text=text,
            timestamp=timestamp,
            asr_confidence=asr_confidence
        )

        self._evidence_spans[evidence.evidence_id] = evidence
        return evidence

    def link_proposition_evidence(self, proposition_id: str, evidence_ids: List[str]) -> None:
        """Link evidence to proposition"""
        if proposition_id not in self._proposition_evidence:
            self._proposition_evidence[proposition_id] = []
        self._proposition_evidence[proposition_id].extend(evidence_ids)

    def link_concept_evidence(self, concept_id: str, evidence_ids: List[str]) -> None:
        """Link evidence to concept"""
        if concept_id not in self._concept_evidence:
            self._concept_evidence[concept_id] = []
        self._concept_evidence[concept_id].extend(evidence_ids)

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceSpan]:
        """Get evidence span by ID"""
        return self._evidence_spans.get(evidence_id)

    def get_proposition_evidence(self, proposition_id: str) -> List[EvidenceSpan]:
        """Get all evidence for a proposition"""
        evidence_ids = self._proposition_evidence.get(proposition_id, [])
        return [self._evidence_spans[eid] for eid in evidence_ids if eid in self._evidence_spans]

    def get_concept_evidence(self, concept_id: str) -> List[EvidenceSpan]:
        """Get all evidence for a concept"""
        evidence_ids = self._concept_evidence.get(concept_id, [])
        return [self._evidence_spans[eid] for eid in evidence_ids if eid in self._evidence_spans]

    def validate_grounding(
        self,
        evidence_ids: List[str],
        extraction_confidence: float,
        asr_confidence: Optional[float] = None
    ) -> Tuple[GroundingStatus, float]:
        """Validate grounding status and calculate grounding confidence"""

        if not evidence_ids:
            return GroundingStatus.UNSUPPORTED, 0.0

        evidence_quality = []
        for eid in evidence_ids:
            evidence = self._evidence_spans.get(eid)
            if evidence:
                quality = 1.0
                if evidence.asr_confidence is not None:
                    quality *= evidence.asr_confidence
                evidence_quality.append(quality)

        if not evidence_quality:
            return GroundingStatus.UNSUPPORTED, 0.0

        avg_quality = sum(evidence_quality) / len(evidence_quality)

        if len(evidence_ids) == 1 and avg_quality > 0.8:
            status = GroundingStatus.EXPLICIT
        elif len(evidence_ids) >= 2:
            status = GroundingStatus.SUPPORTED
        elif avg_quality > 0.5:
            status = GroundingStatus.EXPLICIT
        else:
            status = GroundingStatus.UNSUPPORTED

        grounding_confidence = min(1.0, avg_quality * extraction_confidence)

        return status, grounding_confidence

    def compute_evidence_hash(self, text: str) -> str:
        """Compute a stable hash for evidence text"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()