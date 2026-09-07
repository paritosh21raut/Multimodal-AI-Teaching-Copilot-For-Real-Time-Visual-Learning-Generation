"""
Confidence Calculator

Calculates multi-dimensional confidence scores for semantic extractions.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
import math

from .semantic_models import (
    Proposition,
    Concept,
    EvidenceSpan,
    Confidence,
    GroundingStatus,
    ExtractionStatus
)


class ConfidenceCalculator:
    """Calculates confidence scores for semantic content"""
    
    def __init__(self):
        # Weights for different confidence components
        self.weights = {
            "asr_quality": 0.15,
            "extraction_confidence": 0.25,
            "entity_resolution_confidence": 0.20,
            "grounding_confidence": 0.20,
            "validation_confidence": 0.10,
            "consistency_confidence": 0.10
        }
    
    def calculate_proposition_confidence(
        self,
        proposition: Proposition,
        asr_confidence: Optional[float] = None,
        evidence_quality: float = 0.8,
        validation_confidence: float = 0.7
    ) -> float:
        """Calculate confidence for a proposition"""
        confidence = 0.0
        
        # Base extraction confidence
        confidence += 0.3 * proposition.confidence
        
        # ASR quality
        if asr_confidence is not None:
            confidence += 0.2 * asr_confidence
        else:
            confidence += 0.2 * 0.8  # Default ASR quality
        
        # Evidence grounding
        if proposition.grounding_status == GroundingStatus.EXPLICIT:
            confidence += 0.25 * evidence_quality
        elif proposition.grounding_status == GroundingStatus.SUPPORTED:
            confidence += 0.20 * evidence_quality
        elif proposition.grounding_status == GroundingStatus.INFERRED:
            confidence += 0.10 * evidence_quality
        else:
            confidence += 0.0  # Unsupported
        
        # Validation
        confidence += 0.25 * validation_confidence
        
        return min(1.0, confidence)
    
    def calculate_frame_confidence(
        self,
        concepts: List[Concept],
        propositions: List[Proposition],
        evidence_spans: List[EvidenceSpan],
        asr_confidence: Optional[float] = None,
        validation_report: Optional[Dict[str, Any]] = None
    ) -> Confidence:
        """Calculate multi-dimensional confidence for a frame"""
        
        # ASR quality
        asr_quality = asr_confidence if asr_confidence is not None else 0.8
        
        # Extraction confidence
        if propositions:
            extraction_confidence = 0.8
        elif concepts:
            extraction_confidence = 0.6
        else:
            extraction_confidence = 0.0
        
        # Entity resolution confidence
        if concepts:
            resolved_count = sum(1 for c in concepts if c.mention_count > 1)
            entity_resolution_confidence = 0.7 + (0.2 * min(1.0, resolved_count / max(1, len(concepts))))
        else:
            entity_resolution_confidence = 0.0
        
        # Grounding confidence
        if evidence_spans and propositions:
            grounded_count = sum(
                1 for p in propositions
                if p.grounding_status in [GroundingStatus.EXPLICIT, GroundingStatus.SUPPORTED]
            )
            grounding_confidence = grounded_count / len(propositions)
        elif evidence_spans:
            grounding_confidence = 0.9
        else:
            grounding_confidence = 0.0
        
        # Validation confidence
        if validation_report:
            validation_confidence = validation_report.get("evidence_coverage", 0.0)
        else:
            validation_confidence = 0.5
        
        # Consistency confidence (placeholder for now)
        consistency_confidence = 0.5
        
        return Confidence(
            asr_quality=asr_quality,
            extraction_confidence=extraction_confidence,
            entity_resolution_confidence=entity_resolution_confidence,
            grounding_confidence=grounding_confidence,
            validation_confidence=validation_confidence,
            consistency_confidence=consistency_confidence
        )
    
    def calibrate_confidence(self, confidence: float) -> float:
        """Calibrate confidence score"""
        # Apply logistic calibration
        # This maps raw confidence to calibrated confidence
        if confidence <= 0:
            return 0.0
        if confidence >= 1:
            return 1.0
        
        # Simple calibration curve
        calibrated = 1.0 / (1.0 + math.exp(-8 * (confidence - 0.5)))
        
        return min(1.0, max(0.0, calibrated))
    
    def get_overall_confidence(self, confidence: Confidence) -> float:
        """Calculate overall confidence from components"""
        overall = (
            confidence.asr_quality * self.weights["asr_quality"] +
            confidence.extraction_confidence * self.weights["extraction_confidence"] +
            confidence.entity_resolution_confidence * self.weights["entity_resolution_confidence"] +
            confidence.grounding_confidence * self.weights["grounding_confidence"] +
            confidence.validation_confidence * self.weights["validation_confidence"] +
            confidence.consistency_confidence * self.weights["consistency_confidence"]
        )
        
        return self.calibrate_confidence(overall)