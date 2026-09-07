"""
Instructional Act Detection

Identifies pedagogical actions in lecture transcript (definitions,
examples, processes, comparisons, etc.) using pattern matching.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
import re

from .semantic_models import (
    InstructionalAct,
    InstructionalActType,
    EvidenceSpan,
    ConceptRef
)


class InstructionalDetector:
    """Detects instructional acts from transcript text"""
    
    # Patterns for different instructional acts
    ACT_PATTERNS = {
        InstructionalActType.DEFINITION: [
            r'\bis\s+defined\s+as\b',
            r'\brefers\s+to\b',
            r'\bmeans\b',
            r'\bis\s+called\b',
            r'\bdefinition\s+of\b',
            r'\bdefined\s+as\b',
        ],
        InstructionalActType.EXAMPLE: [
            r'\bfor\s+example\b',
            r'\bfor\s+instance\b',
            r'\bsuch\s+as\b',
            r'\be\.g\.',
            r'\ban\s+example\s+of\b',
            r'\bconsider\s+the\s+example\b',
        ],
        InstructionalActType.PROCESS: [
            r'\bfirst\b.*\bthen\b.*\bfinally\b',
            r'\bstep\s+\d+\b',
            r'\bthe\s+process\s+of\b',
            r'\bfirst\b.*\bthen\b',
            r'\bfollowed\s+by\b',
        ],
        InstructionalActType.MECHANISM: [
            r'\bhow\s+.*\bworks\b',
            r'\bmechanism\s+of\b',
            r'\bworks\s+by\b',
            r'\bthrough\s+the\s+process\b',
        ],
        InstructionalActType.COMPARISON: [
            r'\bcompared\s+to\b',
            r'\bsimilar\s+to\b',
            r'\bin\s+comparison\b',
            r'\bboth\s+.*\band\b.*\bshare\b',
            r'\blike\b.*\balso\b',
        ],
        InstructionalActType.CONTRAST: [
            r'\bunlike\b',
            r'\bin\s+contrast\b',
            r'\bhowever\b.*\bdifferent\b',
            r'\bwhereas\b',
            r'\bon\s+the\s+other\s+hand\b',
        ],
        InstructionalActType.WARNING: [
            r'\bbe\s+careful\b',
            r'\bwatch\s+out\b',
            r'\bcommon\s+mistake\b',
            r'\bimportant\s+note\b',
            r'\bcaution\b',
            r'\bdo\s+not\s+confuse\b',
        ],
        InstructionalActType.QUESTION: [
            r'\?\s*$',
            r'\bwhat\s+is\b.*\?',
            r'\bhow\s+does\b.*\?',
            r'\bwhy\s+is\b.*\?',
        ],
        InstructionalActType.RECAP: [
            r'\bto\s+summarize\b',
            r'\bin\s+summary\b',
            r'\bto\s+recap\b',
            r'\blet\s+me\s+summarize\b',
            r'\breview\s+what\b',
        ],
        InstructionalActType.CONCLUSION: [
            r'\bin\s+conclusion\b',
            r'\bto\s+conclude\b',
            r'\bfinally\b.*\bwe\b',
            r'\bas\s+a\s+result\b',
            r'\btherefore\b',
        ],
        InstructionalActType.ANALOGY: [
            r'\banalogy\b',
            r'\blike\s+a\b',
            r'\bsimilar\s+to\s+how\b',
            r'\bthink\s+of\s+it\s+as\b',
            r'\bjust\s+like\b',
        ],
        InstructionalActType.DERIVATION: [
            r'\bderive\b',
            r'\bderivation\b',
            r'\bfrom\s+the\s+equation\b',
            r'\bmathematically\b',
        ],
        InstructionalActType.OBSERVATION: [
            r'\bwe\s+observe\b',
            r'\bnotice\s+that\b',
            r'\bit\s+can\s+be\s+seen\b',
            r'\bexperimentally\b',
            r'\bempirically\b',
        ],
    }
    
    def __init__(self):
        self._compiled_patterns = {}
        for act_type, patterns in self.ACT_PATTERNS.items():
            self._compiled_patterns[act_type] = [
                re.compile(pattern, re.IGNORECASE | re.DOTALL)
                for pattern in patterns
            ]
    
    def detect(
        self,
        text: str,
        evidence: Optional[EvidenceSpan] = None,
        concept_refs: Optional[List[ConceptRef]] = None
    ) -> List[InstructionalAct]:
        """
        Detect instructional acts in text.
        
        Args:
            text: Transcript text
            evidence: Evidence span for grounding
            concept_refs: Concepts referenced in text
            
        Returns:
            List of InstructionalAct objects
        """
        if not text or not text.strip():
            return []
        
        acts = []
        
        for act_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    act = InstructionalAct(
                        act_type=act_type,
                        concept_refs=concept_refs or [],
                        evidence_ids=[evidence.evidence_id] if evidence else [],
                        confidence=0.7
                    )
                    acts.append(act)
                    break  # One act per type per chunk
        
        return acts