"""
Phase 8 Tests: Slide Grounding

Tests preparation of semantic content for slide generation.
"""

from __future__ import annotations

import pytest

from app.semantic.semantic_models import (
    Concept,
    ConceptRef,
    Proposition,
    Relation,
    InstructionalAct,
    GroundingStatus,
    PropositionLifecycle,
    RelationType,
    InstructionalActType
)

from app.semantic.slide_grounder import SlideGrounder, SlideContent
from app.semantic.semantic_integration import SemanticIntegration


# ============================================================
# SLIDE GROUNDER TESTS
# ============================================================

def test_prepare_basic_slide():
    """Test basic slide content preparation"""
    grounder = SlideGrounder()
    
    concepts = [
        Concept(concept_id="c1", canonical_name="TCP", confidence=0.9),
        Concept(concept_id="c2", canonical_name="UDP", confidence=0.85)
    ]
    
    propositions = [
        Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id="c3", canonical_name="reliability"),
            confidence=0.8,
            grounding_status=GroundingStatus.EXPLICIT,
            lifecycle=PropositionLifecycle.ACTIVE
        )
    ]
    
    content = grounder.prepare_slide_content(
        topic="Transport Protocols",
        concepts=concepts,
        propositions=propositions
    )
    
    assert content is not None
    assert content.topic == "Transport Protocols"
    assert len(content.key_concepts) > 0
    assert len(content.propositions) > 0


def test_prepare_slide_with_definitions():
    """Test slide content with definitions"""
    grounder = SlideGrounder()
    
    concepts = [
        Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    ]
    
    propositions = [
        Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.DEFINED_AS,
            object=ConceptRef(concept_id="c2", canonical_name="Transmission Control Protocol"),
            confidence=0.9,
            grounding_status=GroundingStatus.EXPLICIT,
            lifecycle=PropositionLifecycle.ACTIVE
        )
    ]
    
    content = grounder.prepare_slide_content(
        topic="TCP",
        concepts=concepts,
        propositions=propositions
    )
    
    assert len(content.definitions) > 0
    assert "TCP" in content.definitions[0]


def test_prepare_slide_filters_low_confidence():
    """Test that low confidence content is filtered"""
    grounder = SlideGrounder()
    
    concepts = [
        Concept(concept_id="c1", canonical_name="High", confidence=0.9),
        Concept(concept_id="c2", canonical_name="Low", confidence=0.3)
    ]
    
    content = grounder.prepare_slide_content(
        topic="Test",
        concepts=concepts,
        propositions=[]
    )
    
    # Only high confidence concept should be included
    assert "High" in content.key_concepts
    assert "Low" not in content.key_concepts


def test_prepare_slide_limits_content():
    """Test that content is limited to max values"""
    grounder = SlideGrounder()
    grounder.max_concepts = 3
    grounder.max_propositions = 2
    
    concepts = [
        Concept(concept_id=f"c{i}", canonical_name=f"Concept {i}", confidence=0.9)
        for i in range(10)
    ]
    
    propositions = [
        Proposition(
            subject=ConceptRef(concept_id=f"c{i}", canonical_name=f"Concept {i}"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object {i}"),
            confidence=0.8,
            grounding_status=GroundingStatus.EXPLICIT,
            lifecycle=PropositionLifecycle.ACTIVE
        )
        for i in range(10)
    ]
    
    content = grounder.prepare_slide_content(
        topic="Test",
        concepts=concepts,
        propositions=propositions
    )
    
    assert len(content.key_concepts) <= 3
    assert len(content.propositions) <= 2


def test_prepare_slide_importance():
    """Test importance calculation"""
    grounder = SlideGrounder()
    
    concepts = [
        Concept(concept_id="c1", canonical_name="TCP", confidence=0.95)
    ]
    
    propositions = [
        Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id="c2", canonical_name="reliability"),
            confidence=0.9,
            grounding_status=GroundingStatus.EXPLICIT,
            lifecycle=PropositionLifecycle.ACTIVE
        )
    ]
    
    content = grounder.prepare_slide_content(
        topic="TCP",
        concepts=concepts,
        propositions=propositions
    )
    
    assert content.importance > 0.5
    assert content.confidence > 0.5


# ============================================================
# SEMANTIC INTEGRATION WITH SLIDE GROUNDING TESTS
# ============================================================

def test_integration_prepare_slide():
    """Test integration layer with slide grounding"""
    integration = SemanticIntegration()
    
    concepts = [
        Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    ]
    
    propositions = [
        Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.IS_A,
            object=ConceptRef(concept_id="c2", canonical_name="protocol"),
            confidence=0.85,
            grounding_status=GroundingStatus.EXPLICIT,
            lifecycle=PropositionLifecycle.ACTIVE
        )
    ]
    
    content = integration.prepare_slide_content(
        topic="Networking",
        concepts=concepts,
        propositions=propositions
    )
    
    assert content is not None
    assert content.topic == "Networking"
    assert "TCP" in content.key_concepts


def test_integration_full_pipeline():
    """Test full pipeline from SI to slide content"""
    from app.semantic.semantic_intelligence import SemanticIntelligence
    
    si = SemanticIntelligence(enable_llm=False)
    integration = SemanticIntegration()
    
    # Process chunks
    chunks = [
        "TCP is a transport protocol",
        "TCP provides reliable delivery",
        "TCP uses acknowledgements",
    ]
    
    all_concepts = []
    all_propositions = []
    
    for i, chunk in enumerate(chunks):
        frame = si.process(
            transcript_text=chunk,
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_test",
            generate_embeddings=False
        )
        
        integration.process_frame(frame)
        all_concepts.extend(frame.concepts)
        all_propositions.extend(frame.propositions)
    
    # Prepare slide content
    content = integration.prepare_slide_content(
        topic="TCP",
        concepts=all_concepts,
        propositions=all_propositions,
        instructional_acts=[],
        relations=[]
    )
    
    assert content is not None
    assert len(content.key_concepts) > 0
    assert len(content.propositions) > 0


# ============================================================
# PERFORMANCE TESTS
# ============================================================

def test_slide_grounder_performance():
    """Test slide grounder performance"""
    import time
    
    grounder = SlideGrounder()
    
    concepts = [
        Concept(concept_id=f"c{i}", canonical_name=f"Concept {i}", confidence=0.9)
        for i in range(20)
    ]
    
    propositions = [
        Proposition(
            subject=ConceptRef(concept_id=f"c{i}", canonical_name=f"Concept {i}"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object {i}"),
            confidence=0.8,
            grounding_status=GroundingStatus.EXPLICIT,
            lifecycle=PropositionLifecycle.ACTIVE
        )
        for i in range(20)
    ]
    
    start_time = time.time()
    
    for _ in range(100):
        grounder.prepare_slide_content(
            topic="Test",
            concepts=concepts,
            propositions=propositions
        )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    # Should be very fast (pure Python filtering)
    assert processing_time < 2.0
