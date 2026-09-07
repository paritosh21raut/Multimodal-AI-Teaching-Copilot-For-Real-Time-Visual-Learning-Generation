"""
Semantic Validator

Validates extracted semantic content against evidence.
Ensures no hallucination - every proposition must be grounded.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
import re

from .semantic_models import (
    Proposition,
    Concept,
    Relation,
    EvidenceSpan,
    GroundingStatus,
    ExtractionStatus,
    Confidence
)


class SemanticValidator:
    """Validates semantic extractions for quality and grounding"""
    
    def __init__(self):
        self.min_evidence_coverage = 0.5
        self.min_extraction_confidence = 0.4
        self.max_unsupported_propositions = 0.3  # 30% max unsupported
    
    def validate_proposition(
        self,
        proposition: Proposition,
        evidence: Optional[EvidenceSpan] = None
    ) -> Tuple[bool, float, str]:
        """
        Validate a proposition.
        
        Returns:
            (is_valid, confidence, reason)
        """
        # Check subject and object exist
        if not proposition.subject or not proposition.object:
            return False, 0.0, "missing subject or object"
        
        # Check predicate is valid
        if proposition.predicate is None:
            return False, 0.0, "missing predicate"
        
        # Check evidence grounding
        if not proposition.evidence_ids:
            proposition.grounding_status = GroundingStatus.UNSUPPORTED
            return False, 0.1, "no evidence grounding"
        
        # Check grounding status
        if proposition.grounding_status == GroundingStatus.UNSUPPORTED:
            return False, 0.2, "unsupported proposition"
        
        # Check extraction status
        if proposition.extraction_status == ExtractionStatus.REJECTED:
            return False, 0.0, "rejected extraction"
        
        # Basic confidence check
        if proposition.confidence < self.min_extraction_confidence:
            return False, proposition.confidence, "low confidence"
        
        return True, proposition.confidence, "valid"
    
    def validate_frame(
        self,
        frame_concepts: List[Concept],
        frame_propositions: List[Proposition],
        evidence_spans: List[EvidenceSpan]
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Validate entire semantic frame.
        
        Returns:
            (is_valid, confidence, validation_report)
        """
        report = {
            "total_concepts": len(frame_concepts),
            "total_propositions": len(frame_propositions),
            "valid_propositions": 0,
            "invalid_propositions": 0,
            "unsupported_propositions": 0,
            "evidence_coverage": 0.0,
            "issues": []
        }
        
        if not evidence_spans:
            return False, 0.0, report
        
        # Validate propositions
        for prop in frame_propositions:
            is_valid, confidence, reason = self.validate_proposition(prop)
            
            if is_valid:
                report["valid_propositions"] += 1
            else:
                report["invalid_propositions"] += 1
                report["issues"].append({
                    "proposition_id": prop.proposition_id,
                    "reason": reason
                })
            
            if prop.grounding_status == GroundingStatus.UNSUPPORTED:
                report["unsupported_propositions"] += 1
        
        # Calculate evidence coverage
        if frame_propositions:
            evidence_coverage = report["valid_propositions"] / len(frame_propositions)
            report["evidence_coverage"] = evidence_coverage
        
        # Frame is valid if enough propositions are valid
        if frame_propositions:
            valid_ratio = report["valid_propositions"] / len(frame_propositions)
            frame_valid = valid_ratio >= self.min_evidence_coverage
        else:
            frame_valid = len(frame_concepts) > 0
        
        # Calculate overall confidence
        if frame_valid:
            confidence = report["evidence_coverage"] if frame_propositions else 0.5
        else:
            confidence = 0.0
        
        return frame_valid, confidence, report
    
    def validate_relation(
        self,
        relation: Relation
    ) -> Tuple[bool, float, str]:
        """Validate a relation"""
        if not relation.source or not relation.target:
            return False, 0.0, "missing source or target"
        
        if relation.relation_type is None:
            return False, 0.0, "missing relation type"
        
        if not relation.evidence_ids:
            return False, 0.1, "no evidence grounding"
        
        return True, relation.confidence, "valid"
    
    def check_hallucination_risk(
        self,
        proposition: Proposition,
        evidence_text: str
    ) -> Tuple[bool, float]:
        """
        Check if proposition might be hallucinated.
        
        Returns:
            (is_safe, risk_score)
        """
        if not evidence_text:
            return False, 1.0
        
        # Check if subject appears in evidence
        subject_name = proposition.subject.canonical_name.lower() if proposition.subject else ""
        object_name = proposition.object.canonical_name.lower() if proposition.object else ""
        
        evidence_lower = evidence_text.lower()
        
        risk_factors = []
        
        # Subject not in evidence
        if subject_name and subject_name not in evidence_lower:
            risk_factors.append(0.5)
        
        # Object not in evidence
        if object_name and object_name not in evidence_lower:
            risk_factors.append(0.5)
        
        # Neither subject nor object in evidence
        if not risk_factors:
            return True, 0.0
        
        risk_score = sum(risk_factors) / len(risk_factors)
        
        return risk_score < 0.8, risk_score