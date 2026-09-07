"""
Instructional Act Detection (Enhanced)

Identifies pedagogical actions and links them to specific concepts.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, Tuple
import re

from .semantic_models import (
    InstructionalAct,
    InstructionalActType,
    EvidenceSpan,
    ConceptRef
)


class InstructionalDetector:
    """Detects instructional acts and links them to concepts"""
    
    # Patterns for different instructional acts
    ACT_PATTERNS = {
        InstructionalActType.DEFINITION: [
            (r'\b(?:is|are)\s+defined\s+as\b', 0.9),
            (r'\brefers\s+to\b', 0.85),
            (r'\bmeans\b', 0.8),
            (r'\bis\s+called\b', 0.85),
            (r'\bdefinition\s+of\b', 0.9),
        ],
        InstructionalActType.EXAMPLE: [
            (r'\bfor\s+example\b', 0.95),
            (r'\bfor\s+instance\b', 0.95),
            (r'\bsuch\s+as\b', 0.9),
            (r'\be\.g\.', 0.95),
            (r'\ban\s+example\s+of\b', 0.9),
        ],
        InstructionalActType.PROCESS: [
            (r'\bfirst\b.*\bthen\b', 0.85),
            (r'\bstep\s+\d+\b', 0.9),
            (r'\bthe\s+process\s+of\b', 0.85),
            (r'\bfollowed\s+by\b', 0.8),
        ],
        InstructionalActType.MECHANISM: [
            (r'\bhow\s+.*\bworks\b', 0.85),
            (r'\bmechanism\s+of\b', 0.9),
            (r'\bworks\s+by\b', 0.85),
        ],
        InstructionalActType.COMPARISON: [
            (r'\bcompared\s+to\b', 0.9),
            (r'\bsimilar\s+to\b', 0.85),
            (r'\bin\s+comparison\b', 0.85),
            (r'\bboth\s+.*\band\b.*\bshare\b', 0.8),
        ],
        InstructionalActType.CONTRAST: [
            (r'\bunlike\b', 0.9),
            (r'\bin\s+contrast\b', 0.85),
            (r'\bwhereas\b', 0.85),
            (r'\bon\s+the\s+other\s+hand\b', 0.85),
        ],
        InstructionalActType.WARNING: [
            (r'\bbe\s+careful\b', 0.9),
            (r'\bwatch\s+out\b', 0.9),
            (r'\bcommon\s+mistake\b', 0.9),
            (r'\bimportant\s+note\b', 0.85),
            (r'\bcaution\b', 0.85),
        ],
        InstructionalActType.QUESTION: [
            (r'\?\s*$', 0.9),
            (r'\bwhat\s+is\b.*\?', 0.9),
            (r'\bhow\s+does\b.*\?', 0.9),
            (r'\bwhy\s+is\b.*\?', 0.9),
        ],
        InstructionalActType.RECAP: [
            (r'\bto\s+summarize\b', 0.95),
            (r'\bin\s+summary\b', 0.95),
            (r'\bto\s+recap\b', 0.95),
            (r'\blet\s+me\s+summarize\b', 0.9),
        ],
        InstructionalActType.CONCLUSION: [
            (r'\bin\s+conclusion\b', 0.95),
            (r'\bto\s+conclude\b', 0.95),
            (r'\bas\s+a\s+result\b', 0.85),
            (r'\btherefore\b', 0.85),
        ],
        InstructionalActType.ANALOGY: [
            (r'\banalogy\b', 0.9),
            (r'\blike\s+a\b', 0.85),
            (r'\bsimilar\s+to\s+how\b', 0.85),
            (r'\bthink\s+of\s+it\s+as\b', 0.85),
        ],
    }
    
    def __init__(self):
        self._compiled_patterns = {}
        for act_type, patterns in self.ACT_PATTERNS.items():
            self._compiled_patterns[act_type] = [
                (re.compile(pattern, re.IGNORECASE | re.DOTALL), confidence)
                for pattern, confidence in patterns
            ]
    
    def detect(
        self,
        text: str,
        evidence: Optional[EvidenceSpan] = None,
        concept_refs: Optional[List[ConceptRef]] = None,
        active_concepts: Optional[List[ConceptRef]] = None
    ) -> List[InstructionalAct]:
        """
        Detect instructional acts in text with concept linking.
        
        Args:
            text: Transcript text
            evidence: Evidence span for grounding
            concept_refs: Concepts explicitly mentioned in text
            active_concepts: Currently active concepts
            
        Returns:
            List of InstructionalAct objects with linked concepts
        """
        if not text or not text.strip():
            return []
        
        acts = []
        
        for act_type, patterns in self._compiled_patterns.items():
            for pattern, base_confidence in patterns:
                match = pattern.search(text)
                
                if match:
                    # Determine which concepts are linked
                    linked_concepts = self._link_concepts(
                        text,
                        concept_refs,
                        active_concepts
                    )
                    
                    # Boost confidence if concepts are linked
                    confidence = base_confidence
                    if linked_concepts:
                        confidence = min(0.95, base_confidence + 0.05)
                    
                    act = InstructionalAct(
                        act_type=act_type,
                        concept_refs=linked_concepts or concept_refs or [],
                        evidence_ids=[evidence.evidence_id] if evidence else [],
                        confidence=confidence
                    )
                    acts.append(act)
                    break  # One act per type per chunk
        
        return acts
    
    def _link_concepts(
        self,
        text: str,
        concept_refs: Optional[List[ConceptRef]],
        active_concepts: Optional[List[ConceptRef]]
    ) -> List[ConceptRef]:
        """Link instructional act to relevant concepts"""
        linked = []
        text_lower = text.lower()
        
        # Check explicitly mentioned concepts
        if concept_refs:
            for ref in concept_refs:
                if ref.canonical_name.lower() in text_lower:
                    linked.append(ref)
        
        # If no explicit concepts found, use active concepts
        if not linked and active_concepts:
            linked = active_concepts[:3]  # Top 3 active concepts
        
        return linked