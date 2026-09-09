"""
Slide Decision Engine - Comprehensive Tests

Covers:
- Easy: Basic topic changes, accumulation
- Medium: Saturation, important content, debouncing
- Hard: Mixed signals, rapid changes, state transitions
"""

from __future__ import annotations

import sys
import os
import pytest
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.models.presentation_models import SlideAction
from app.presentation.slide_decision.slide_decision_engine import SlideDecisionEngine


# ============================================================
# EASY TESTS
# ============================================================

def test_first_topic_creates_slide():
    """Easy: First topic always creates a slide"""
    engine = SlideDecisionEngine()
    
    decision = engine.decide(
        topic_changed=True,
        current_topic="Computer Networks",
    )
    
    assert decision.action == SlideAction.CREATE_NEW
    assert decision.confidence == 1.0


def test_same_topic_no_change():
    """Easy: Same topic with no new content = no change"""
    engine = SlideDecisionEngine()
    
    engine.decide(topic_changed=True, current_topic="TCP")
    
    decision = engine.decide(
        topic_changed=False,
        current_topic="TCP",
        semantic_novelty=0.0,
    )
    
    assert decision.action == SlideAction.NO_CHANGE


def test_same_topic_important_content_updates():
    """Easy: New important content on same topic = update"""
    engine = SlideDecisionEngine()
    
    engine.decide(topic_changed=True, current_topic="TCP")
    
    decision = engine.decide(
        topic_changed=False,
        current_topic="TCP",
        important_concepts=["reliable delivery"],
        semantic_novelty=0.4,
    )
    
    assert decision.action == SlideAction.UPDATE


# ============================================================
# MEDIUM TESTS
# ============================================================

def test_topic_change_creates_new_slide_after_debounce():
    """Medium: Topic change creates new slide after debounce"""
    engine = SlideDecisionEngine(min_slide_duration_seconds=0.1)
    
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    # Wait past debounce
    time.sleep(0.2)
    
    decision = engine.decide(
        topic_changed=True,
        current_topic="Topic B",
    )
    
    assert decision.action == SlideAction.CREATE_NEW


def test_topic_change_debounced():
    """Medium: Rapid topic change is debounced"""
    engine = SlideDecisionEngine(min_slide_duration_seconds=10.0)
    
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    # Immediately change topic (no time passed)
    decision = engine.decide(
        topic_changed=True,
        current_topic="Topic B",
    )
    
    assert decision.action == SlideAction.WAIT


def test_slide_saturates_after_many_chunks():
    """Medium: Slide saturates after enough content"""
    engine = SlideDecisionEngine(
        saturation_threshold=0.5,
        min_slide_duration_seconds=0.0,
    )
    
    engine.decide(topic_changed=True, current_topic="TCP")
    
    decision = None
    # Feed many chunks with new concepts
    for i in range(15):
        decision = engine.decide(
            topic_changed=False,
            current_topic="TCP",
            new_concepts=[f"concept_{i}"],
            important_concepts=[f"concept_{i}"],
            semantic_novelty=0.6,
        )
        
        if decision.action in [SlideAction.CREATE_NEW, SlideAction.FINALIZE]:
            break
    
    assert decision.action in [SlideAction.CREATE_NEW, SlideAction.FINALIZE]


def test_development_milestone_refines():
    """Medium: Development milestone triggers refine"""
    engine = SlideDecisionEngine()
    
    engine.decide(topic_changed=True, current_topic="TCP")
    
    decision = engine.decide(
        topic_changed=False,
        current_topic="TCP",
        development_changed=True,
        semantic_novelty=0.3,
    )
    
    assert decision.action == SlideAction.REFINE


# ============================================================
# HARD TESTS
# ============================================================

def test_no_flicker_on_rapid_updates():
    """Hard: Multiple rapid chunks don't cause flicker"""
    engine = SlideDecisionEngine(min_slide_duration_seconds=5.0)
    
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    actions = []
    
    # Rapid topic changes within debounce period
    for i in range(5):
        decision = engine.decide(
            topic_changed=True,
            current_topic=f"Topic {i}",
        )
        actions.append(decision.action)
    
    # Should be mostly WAIT, not CREATE_NEW repeatedly
    assert SlideAction.WAIT in actions
    assert actions.count(SlideAction.CREATE_NEW) <= 1


def test_state_tracks_correctly():
    """Hard: State tracking across transitions"""
    engine = SlideDecisionEngine(min_slide_duration_seconds=0.0)
    
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    state = engine.get_state()
    assert state["current_slide_topic"] == "Topic A"
    assert state["has_slide"] is True
    
    time.sleep(0.01)
    engine.decide(topic_changed=True, current_topic="Topic B")
    
    state = engine.get_state()
    assert state["current_slide_topic"] == "Topic B"
    assert state["chunks_on_current_slide"] == 0  # Reset after new slide


def test_saturation_resets_on_new_slide():
    """Hard: Saturation resets when new slide created"""
    engine = SlideDecisionEngine(
        saturation_threshold=0.3,
        min_slide_duration_seconds=0.0,
    )
    
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    # Saturate
    for i in range(10):
        decision = engine.decide(
            topic_changed=False,
            current_topic="Topic A",
            new_concepts=[f"c{i}"],
            important_concepts=[f"c{i}"],
            semantic_novelty=0.8,
        )
    
    state = engine.get_state()
    assert state["saturation_score"] < 0.3  # Reset after new slide


def test_mixed_signals_prioritize_topic_change():
    """Hard: Topic change takes priority over other signals"""
    engine = SlideDecisionEngine(min_slide_duration_seconds=0.0)
    
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    time.sleep(0.01)
    
    # Topic change + important content + novelty
    decision = engine.decide(
        topic_changed=True,
        current_topic="Topic B",
        important_concepts=["critical_concept"],
        semantic_novelty=0.9,
    )
    
    assert decision.action == SlideAction.CREATE_NEW
    assert decision.trigger == "topic_change"


def test_engine_reset():
    """Hard: Reset clears all state"""
    engine = SlideDecisionEngine()
    
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    engine.reset()
    
    state = engine.get_state()
    assert state["has_slide"] is False
    assert state["chunks_on_current_slide"] == 0
    assert state["saturation_score"] == 0.0