"""
Slide Grounder

Prepares semantic content for slide generation.
Bridges Semantic Intelligence and ContentGenerator.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from .semantic_models import (
    Concept,
    Proposition,
    Relation,
    InstructionalAct,
    ConceptRef,
    GroundingStatus,
    PropositionLifecycle,
    RelationType,
    InstructionalActType
)


@dataclass
class SlideContent:
    """Prepared content for a slide"""
    topic: str
    title: str
    key_concepts: List[str]
    definitions: List[str]
    propositions: List[str]
    examples: List[str]
    relations: List[Tuple[str, str, str]]
    importance: float
    confidence: float
    evidence_ids: List[str]


class SlideGrounder:
    """Prepares semantic content for slide generation"""
    
    def __init__(self):
        self.min_confidence = 0.6
        self.max_concepts = 5
        self.max_propositions = 5
        self.max_definitions = 3
        self.max_examples = 3
    
    def prepare_slide_content(
        self,
        topic: str,
        concepts: List[Concept],
        propositions: List[Proposition],
        instructional_acts: List[InstructionalAct] = None,
        relations: List[Relation] = None
    ) -> SlideContent:
        """
        Prepare semantic content for slide generation.
        
        Filters and organizes content into slide-ready format.
        """
        # Filter concepts by confidence
        active_concepts = [
            c for c in concepts
            if c.confidence >= self.min_confidence
        ]
        
        # Limit concepts
        top_concepts = active_concepts[:self.max_concepts]
        
        # Filter propositions
        active_propositions = [
            p for p in propositions
            if p.confidence >= self.min_confidence and
            p.lifecycle == PropositionLifecycle.ACTIVE and
            p.grounding_status in [GroundingStatus.EXPLICIT, GroundingStatus.SUPPORTED]
        ]
        
        # Extract definitions
        definitions = self._extract_definitions(
            active_propositions,
            instructional_acts
        )
        definitions = definitions[:self.max_definitions]
        
        # Extract examples
        examples = self._extract_examples(
            active_propositions,
            instructional_acts
        )
        examples = examples[:self.max_examples]
        
        # Format propositions
        proposition_texts = self._format_propositions(
            active_propositions[:self.max_propositions]
        )
        
        # Format relations
        relation_tuples = self._format_relations(
            relations or [],
            top_concepts
        )
        
        # Calculate importance and confidence
        importance = self._calculate_importance(
            top_concepts,
            active_propositions
        )
        
        confidence = self._calculate_confidence(
            top_concepts,
            active_propositions
        )
        
        # Extract evidence IDs
        evidence_ids = self._extract_evidence_ids(
            active_propositions,
            instructional_acts
        )
        
        # Generate title
        title = self._generate_title(topic, top_concepts)
        
        return SlideContent(
            topic=topic,
            title=title,
            key_concepts=[c.canonical_name for c in top_concepts],
            definitions=definitions,
            propositions=proposition_texts,
            examples=examples,
            relations=relation_tuples,
            importance=importance,
            confidence=confidence,
            evidence_ids=evidence_ids
        )
    
    def _extract_definitions(
        self,
        propositions: List[Proposition],
        instructional_acts: List[InstructionalAct] = None
    ) -> List[str]:
        """Extract definitions from propositions and acts"""
        definitions = []
        
        # From propositions
        for prop in propositions:
            if prop.predicate == RelationType.DEFINED_AS:
                if prop.subject and prop.object:
                    definitions.append(
                        f"{prop.subject.canonical_name} = {prop.object.canonical_name}"
                    )
        
        # From instructional acts
        if instructional_acts:
            for act in instructional_acts:
                if act.act_type == InstructionalActType.DEFINITION:
                    for ref in act.concept_refs:
                        definitions.append(f"Definition: {ref.canonical_name}")
        
        return definitions
    
    def _extract_examples(
        self,
        propositions: List[Proposition],
        instructional_acts: List[InstructionalAct] = None
    ) -> List[str]:
        """Extract examples from propositions and acts"""
        examples = []
        
        # From propositions with example modality
        for prop in propositions:
            if prop.modality == "example":
                if prop.subject and prop.object:
                    examples.append(
                        f"{prop.subject.canonical_name} → {prop.object.canonical_name}"
                    )
        
        # From instructional acts
        if instructional_acts:
            for act in instructional_acts:
                if act.act_type == InstructionalActType.EXAMPLE:
                    for ref in act.concept_refs:
                        examples.append(f"Example: {ref.canonical_name}")
        
        return examples
    
    def _format_propositions(self, propositions: List[Proposition]) -> List[str]:
        """Format propositions into readable text"""
        formatted = []
        
        for prop in propositions:
            if prop.subject and prop.object and prop.predicate:
                text = f"{prop.subject.canonical_name} {prop.predicate.value} {prop.object.canonical_name}"
                formatted.append(text)
        
        return formatted
    
    def _format_relations(
        self,
        relations: List[Relation],
        concepts: List[Concept]
    ) -> List[Tuple[str, str, str]]:
        """Format relations into tuples"""
        formatted = []
        concept_ids = {c.concept_id for c in concepts}
        
        for rel in relations:
            if rel.source and rel.target and rel.relation_type:
                # Only include relations involving key concepts
                if (rel.source.concept_id in concept_ids or
                    rel.target.concept_id in concept_ids):
                    formatted.append((
                        rel.source.canonical_name,
                        rel.relation_type.value,
                        rel.target.canonical_name
                    ))
        
        return formatted
    
    def _calculate_importance(
        self,
        concepts: List[Concept],
        propositions: List[Proposition]
    ) -> float:
        """Calculate overall importance"""
        if not concepts:
            return 0.0
        
        importance = 0.0
        
        # Concept confidence
        importance += sum(c.confidence for c in concepts) / len(concepts) * 0.4
        
        # Proposition count
        importance += min(1.0, len(propositions) / 10) * 0.3
        
        # Grounding quality
        grounded = sum(
            1 for p in propositions
            if p.grounding_status == GroundingStatus.EXPLICIT
        )
        importance += min(1.0, grounded / max(1, len(propositions))) * 0.3
        
        return min(1.0, importance)
    
    def _calculate_confidence(
        self,
        concepts: List[Concept],
        propositions: List[Proposition]
    ) -> float:
        """Calculate overall confidence"""
        if not concepts and not propositions:
            return 0.0
        
        confidences = []
        
        for c in concepts:
            confidences.append(c.confidence)
        
        for p in propositions:
            confidences.append(p.confidence)
        
        return sum(confidences) / len(confidences) if confidences else 0.0
    
    def _extract_evidence_ids(
        self,
        propositions: List[Proposition],
        instructional_acts: List[InstructionalAct] = None
    ) -> List[str]:
        """Extract evidence IDs from content"""
        evidence_ids = []
        
        for prop in propositions:
            evidence_ids.extend(prop.evidence_ids)
        
        if instructional_acts:
            for act in instructional_acts:
                evidence_ids.extend(act.evidence_ids)
        
        return list(set(evidence_ids))
    
    def _generate_title(self, topic: str, concepts: List[Concept]) -> str:
        """Generate slide title from topic and concepts"""
        if concepts:
            # Use topic + top concept
            return f"{topic}: {concepts[0].canonical_name}"
        else:
            return topic