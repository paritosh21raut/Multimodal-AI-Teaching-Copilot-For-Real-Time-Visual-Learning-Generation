"""
Phase 6 Tests: Development + Importance Integration

Tests development tracking, importance scoring, and integration layer.
"""

from __future__ import annotations

import pytest

from app.semantic.semantic_models import (
    Concept,
    ConceptRef,
    Proposition,
    Relation,
    EvidenceSpan,
    GroundingStatus,
    PropositionLifecycle,
    RelationType,
    InstructionalAct,
    InstructionalActType
)

from app.semantic.development_tracker import DevelopmentTracker, DevelopmentScore
from app.semantic.importance_scorer import ImportanceScorer, ImportanceScore
from app.semantic.semantic_integration import SemanticIntegration, SemanticSummary
from app.semantic.semantic_intelligence import SemanticIntelligence


# ============================================================
# DEVELOPMENT TRACKER TESTS
# ============================================================

def test_development_tracker_basic():
    """Test basic development tracking"""
    tracker = DevelopmentTracker()
    
    concept = Concept(
        concept_id="c1",
        canonical_name="TCP",
        mention_count=3
    )
    
    tracker.update_from_frame(
        concepts=[concept],
        propositions=[],
        relations=[]
    )
    
    score = tracker.get_development_score("c1")
    
    assert score is not None
    assert score.mention_count == 3
    assert score.total_score > 0


def test_development_tracker_with_propositions():
    """Test development tracking with propositions"""
    tracker = DevelopmentTracker()
    
    concept = Concept(
        concept_id="c1",
        canonical_name="TCP",
        mention_count=1
    )
    
    prop = Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="c2", canonical_name="reliability")
    )
    
    tracker.update_from_frame(
        concepts=[concept],
        propositions=[prop],
        relations=[]
    )
    
    score = tracker.get_development_score("c1")
    
    assert score is not None
    assert score.proposition_count > 0
    assert score.total_score > 0.3  # Should be higher due to proposition


def test_development_levels():
    """Test development level classification"""
    tracker = DevelopmentTracker()
    
    # Low development
    concept1 = Concept(concept_id="c1", canonical_name="Concept 1", mention_count=1)
    tracker.update_from_frame([concept1], [], [])
    
    score1 = tracker.get_development_score("c1")
    assert score1.development_level == "low"
    
    # High development (many mentions and propositions)
    concept2 = Concept(concept_id="c2", canonical_name="Concept 2", mention_count=10)
    
    props = []
    for i in range(10):
        props.append(Proposition(
            subject=ConceptRef(concept_id="c2", canonical_name="Concept 2"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object {i}")
        ))
    
    tracker.update_from_frame([concept2], props, [])
    
    score2 = tracker.get_development_score("c2")
    assert score2.development_level in ["high", "very_high"]


def test_development_most_developed():
    """Test getting most developed concepts"""
    tracker = DevelopmentTracker()
    
    # Create concepts with different development levels
    for i in range(5):
        concept = Concept(
            concept_id=f"c{i}",
            canonical_name=f"Concept {i}",
            mention_count=i + 1
        )
        
        props = []
        for j in range(i + 1):
            props.append(Proposition(
                subject=ConceptRef(concept_id=f"c{i}", canonical_name=f"Concept {i}"),
                predicate=RelationType.PROVIDES,
                object=ConceptRef(concept_id=f"o{i}_{j}", canonical_name=f"Object {i}_{j}")
            ))
        
        tracker.update_from_frame([concept], props, [])
    
    most_developed = tracker.get_most_developed(limit=3)
    
    assert len(most_developed) == 3
    # Should be sorted by score (highest first)
    assert most_developed[0].total_score >= most_developed[1].total_score


# ============================================================
# IMPORTANCE SCORER TESTS
# ============================================================

def test_importance_scorer_basic():
    """Test basic importance scoring"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    concept = Concept(
        concept_id="c1",
        canonical_name="TCP",
        mention_count=3,
        confidence=0.9
    )
    
    score = scorer.score_concept(concept, [])
    
    assert score.importance >= 0.0
    assert score.importance <= 1.0
    assert score.entity_id == "c1"


def test_importance_with_development():
    """Test importance considers development"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    # Well-developed concept
    concept_developed = Concept(
        concept_id="c1",
        canonical_name="TCP",
        mention_count=10
    )
    
    props = []
    for i in range(10):
        props.append(Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object {i}")
        ))
    
    tracker.update_from_frame([concept_developed], props, [])
    
    # Less developed concept
    concept_less = Concept(
        concept_id="c2",
        canonical_name="UDP",
        mention_count=1
    )
    tracker.update_from_frame([concept_less], [], [])
    
    score_developed = scorer.score_concept(concept_developed, props)
    score_less = scorer.score_concept(concept_less, [])
    
    assert score_developed.importance > score_less.importance


def test_importance_ranking():
    """Test importance ranking"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    concepts = []
    for i in range(5):
        concept = Concept(
            concept_id=f"c{i}",
            canonical_name=f"Concept {i}",
            mention_count=i + 1,
            confidence=0.8
        )
        concepts.append(concept)
        
        props = [
            Proposition(
                subject=ConceptRef(concept_id=f"c{i}", canonical_name=f"Concept {i}"),
                predicate=RelationType.PROVIDES,
                object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object {i}")
            )
            for _ in range(i + 1)
        ]
        
        tracker.update_from_frame([concept], props, [])
    
    scores = scorer.score_all_concepts(concepts, [])
    
    assert len(scores) == 5
    # Should be ranked
    assert scores[0].rank == 1
    assert scores[4].rank == 5
    # First should be most important
    assert scores[0].importance >= scores[4].importance


# ============================================================
# SEMANTIC INTEGRATION TESTS
# ============================================================

def test_semantic_integration_basic():
    """Test semantic integration layer"""
    integration = SemanticIntegration()
    
    # Create a frame
    frame = __import__('app.semantic.semantic_models', fromlist=['SemanticFrame']).SemanticFrame(
        lecture_id="lecture_1",
        chunk_id="chunk_1"
    )
    
    concept = Concept(concept_id="c1", canonical_name="TCP", mention_count=2)
    prop = Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="c2", canonical_name="reliability"),
        grounding_status=GroundingStatus.EXPLICIT,
        lifecycle=PropositionLifecycle.ACTIVE
    )
    
    frame.concepts.append(concept)
    frame.propositions.append(prop)
    
    integration.process_frame(frame)
    
    # Get summary
    summary = integration.get_semantic_summary(
        concepts=[concept],
        propositions=[prop],
        active_concepts=[ConceptRef(concept_id="c1", canonical_name="TCP")]
    )
    
    assert summary is not None
    assert len(summary.active_concepts) == 1
    assert len(summary.top_developed_concepts) > 0


def test_semantic_integration_slide_ready():
    """Test getting concepts for slide generation"""
    integration = SemanticIntegration()
    
    concepts = []
    for i in range(5):
        concept = Concept(
            concept_id=f"c{i}",
            canonical_name=f"Concept {i}",
            mention_count=i + 1
        )
        concepts.append(concept)
        
        props = [
            Proposition(
                subject=ConceptRef(concept_id=f"c{i}", canonical_name=f"Concept {i}"),
                predicate=RelationType.PROVIDES,
                object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object {i}")
            )
            for _ in range(i + 1)
        ]
        
        integration.development_tracker.update_from_frame([concept], props, [])
    
    slide_concepts = integration.get_concepts_for_slide_generation(limit=3)
    
    assert len(slide_concepts) == 3


def test_semantic_integration_proposition_filtering():
    """Test filtering propositions for slides"""
    integration = SemanticIntegration()
    
    props = [
        Proposition(
            proposition_id="p1",
            confidence=0.8,
            grounding_status=GroundingStatus.EXPLICIT,
            lifecycle=PropositionLifecycle.ACTIVE
        ),
        Proposition(
            proposition_id="p2",
            confidence=0.3,
            grounding_status=GroundingStatus.UNSUPPORTED,
            lifecycle=PropositionLifecycle.ACTIVE
        ),
        Proposition(
            proposition_id="p3",
            confidence=0.9,
            grounding_status=GroundingStatus.EXPLICIT,
            lifecycle=PropositionLifecycle.SUPERSEDED
        ),
    ]
    
    filtered = integration.get_propositions_for_slide(
        props,
        min_confidence=0.5
    )
    
    assert len(filtered) == 1
    assert filtered[0].proposition_id == "p1"


# ============================================================
# FULL INTEGRATION TESTS
# ============================================================

def test_full_semantic_pipeline():
    """Test complete pipeline from semantic intelligence to integration"""
    si = SemanticIntelligence()
    integration = SemanticIntegration()
    
    # Process chunks
    chunks = [
        "TCP is a transport protocol",
        "TCP provides reliable delivery",
        "TCP uses acknowledgements for reliability",
        "For example, TCP uses a three-way handshake",
    ]
    
    for i, chunk in enumerate(chunks):
        frame = si.process(
            transcript_text=chunk,
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_test"
        )
        
        integration.process_frame(frame)
    
    # Get summary
    summary = integration.get_semantic_summary(
        concepts=si.get_all_concepts(),
        propositions=list(si.semantic_memory._propositions.values()),
        active_concepts=si.semantic_memory.active_context.get_concept_refs(
            si.semantic_memory.registry
        )
    )
    
    assert summary is not None
    assert len(summary.top_developed_concepts) > 0
    assert summary.statistics["total_concepts"] > 0


# ============================================================
# PERFORMANCE TESTS
# ============================================================

def test_development_tracker_performance():
    """Test development tracker performance"""
    import time
    
    tracker = DevelopmentTracker()
    
    start_time = time.time()
    
    for i in range(100):
        concept = Concept(
            concept_id=f"c{i}",
            canonical_name=f"Concept {i}",
            mention_count=1
        )
        
        tracker.update_from_frame([concept], [], [])
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    assert processing_time < 1.0


def test_integration_performance():
    """Test integration layer performance"""
    import time
    
    integration = SemanticIntegration()
    
    start_time = time.time()
    
    for i in range(50):
        frame = __import__('app.semantic.semantic_models', fromlist=['SemanticFrame']).SemanticFrame(
            chunk_id=f"chunk_{i}"
        )
        
        concept = Concept(concept_id=f"c{i}", canonical_name=f"Concept {i}")
        frame.concepts.append(concept)
        
        integration.process_frame(frame)
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    assert processing_time < 2.0