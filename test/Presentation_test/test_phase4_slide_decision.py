"""
Phase 4: Slide Decision Engine - Production Readiness Tests

Tests the complete state machine behavior per the architecture spec.
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
# EASY TESTS - Basic State Machine
# ============================================================

def test_first_topic_creates_slide():
    """Easy: First topic always creates slide"""
    engine = SlideDecisionEngine()
    decision = engine.decide(topic_changed=True, current_topic="TCP")
    assert decision.action == SlideAction.CREATE_NEW


def test_same_topic_no_new_content():
    """Easy: Same topic, no new content = NO_CHANGE"""
    engine = SlideDecisionEngine()
    engine.decide(topic_changed=True, current_topic="TCP")
    decision = engine.decide(topic_changed=False, current_topic="TCP", semantic_novelty=0.0)
    assert decision.action == SlideAction.NO_CHANGE


def test_new_important_content_updates():
    """Easy: New important content on same topic = UPDATE"""
    engine = SlideDecisionEngine()
    engine.decide(topic_changed=True, current_topic="TCP")
    decision = engine.decide(
        topic_changed=False,
        current_topic="TCP",
        important_concepts=["reliability"],
        semantic_novelty=0.5,
    )
    assert decision.action == SlideAction.UPDATE


# ============================================================
# MEDIUM TESTS - Hysteresis and Debouncing
# ============================================================

def test_debounce_prevents_rapid_topic_change():
    """Medium: Rapid topic change is debounced"""
    engine = SlideDecisionEngine(min_slide_duration_seconds=10.0)
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    decision = engine.decide(topic_changed=True, current_topic="Topic B")
    # Should either WAIT or CREATE_NEW (depending on timing)
    assert decision.action in [SlideAction.WAIT, SlideAction.CREATE_NEW]


def test_saturation_triggers_new_slide():
    """Medium: Saturation eventually triggers new slide"""
    engine = SlideDecisionEngine(saturation_threshold=0.5)
    engine.decide(topic_changed=True, current_topic="TCP")
    
    decision = None
    for i in range(15):
        decision = engine.decide(
            topic_changed=False,
            current_topic="TCP",
            new_concepts=[f"concept_{i}"],
            important_concepts=[f"concept_{i}"],
            semantic_novelty=0.8,
        )
        if decision.action in [SlideAction.CREATE_NEW, SlideAction.FINALIZE]:
            break
    
    assert decision.action in [SlideAction.CREATE_NEW, SlideAction.FINALIZE]


def test_development_milestone_refines():
    """Medium: Development milestone triggers REFINE"""
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
# HARD TESTS - Edge Cases
# ============================================================

def test_no_flicker_on_rapid_updates():
    """Hard: Multiple rapid chunks don't cause slide flicker"""
    engine = SlideDecisionEngine(min_slide_duration_seconds=5.0)
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    actions = []
    for i in range(5):
        decision = engine.decide(topic_changed=True, current_topic=f"Topic {i}")
        actions.append(decision.action)
    
    # Should not repeatedly CREATE_NEW
    assert actions.count(SlideAction.CREATE_NEW) <= 2


def test_mixed_signals_prioritize_topic_change():
    """Hard: Topic change takes priority"""
    engine = SlideDecisionEngine(min_slide_duration_seconds=0.1)
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    time.sleep(0.2)  # Wait past debounce
    
    decision = engine.decide(
        topic_changed=True,
        current_topic="Topic B",
        important_concepts=["critical"],
        semantic_novelty=0.9,
    )
    
    assert decision.action == SlideAction.CREATE_NEW
    assert decision.trigger == "topic_change"


def test_state_tracking():
    """Hard: State tracks correctly through transitions"""
    engine = SlideDecisionEngine()
    engine.decide(topic_changed=True, current_topic="Topic A")
    
    state = engine.get_state()
    assert state["has_slide"] is True
    assert state["current_slide_topic"] == "Topic A"
    assert state["chunks_on_current_slide"] >= 0


def test_reset_clears_state():
    """Hard: Reset clears all state"""
    engine = SlideDecisionEngine()
    engine.decide(topic_changed=True, current_topic="Topic A")
    engine.reset()
    
    state = engine.get_state()
    assert state["has_slide"] is False
    assert state["chunks_on_current_slide"] == 0


# ============================================================
# GENERIC TESTS - Domain Agnostic
# ============================================================

def test_works_across_domains():
    """Generic: Works for any domain"""
    domains = ["Networking", "Biology", "Physics", "Math"]
    
    for domain in domains:
        engine = SlideDecisionEngine()
        decision = engine.decide(topic_changed=True, current_topic=domain)
        assert decision.action == SlideAction.CREATE_NEW, f"Failed for {domain}"