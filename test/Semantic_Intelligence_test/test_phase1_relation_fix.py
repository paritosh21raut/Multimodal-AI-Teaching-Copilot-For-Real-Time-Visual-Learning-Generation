"""
Phase 1 Semantic Relation Fix - Regression Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.semantic.proposition_extractor import PropositionExtractor
from app.semantic.semantic_models import RelationType, EvidenceSpan


def extract_relations(text):
    """Helper to extract propositions and return list of (predicate, object)"""
    extractor = PropositionExtractor()
    props = extractor.extract_propositions(text)
    return [(p.predicate, p.object.canonical_name if p.object else "") for p in props]


def test_is_a_for_category():
    """TCP is a protocol → IS_A(protocol)"""
    relations = extract_relations("TCP is a protocol.")
    assert (RelationType.IS_A, "protocol") in relations


def test_has_attribute_for_property():
    """UDP is connectionless → HAS_ATTRIBUTE(connectionless)"""
    relations = extract_relations("UDP is connectionless.")
    assert (RelationType.HAS_ATTRIBUTE, "connectionless") in relations
    # Must NOT produce IS_A(connectionless)
    assert (RelationType.IS_A, "connectionless") not in relations


def test_combined_type_property():
    """UDP is a connectionless transport protocol → IS_A + HAS_ATTRIBUTE"""
    relations = extract_relations("UDP is a connectionless transport protocol.")
    
    # Must have IS_A with just the noun
    assert any(pred == RelationType.IS_A and "protocol" in obj for pred, obj in relations)
    
    # Must have HAS_ATTRIBUTE with the adjective
    assert any(pred == RelationType.HAS_ATTRIBUTE and "connectionless" in obj for pred, obj in relations)
    
    # Must NOT have IS_A with full phrase
    assert not any(pred == RelationType.IS_A and "connectionless transport protocol" in obj for pred, obj in relations)


def test_comparison_while_detected():
    """TCP is connection-oriented while UDP is connectionless → CONTRASTS_WITH"""
    relations = extract_relations("TCP is connection-oriented while UDP is connectionless.")
    
    # Must have HAS_ATTRIBUTE for both
    assert any(pred == RelationType.HAS_ATTRIBUTE and "connection-oriented" in obj for pred, obj in relations)
    assert any(pred == RelationType.HAS_ATTRIBUTE and "connectionless" in obj for pred, obj in relations)
    
    # Must have CONTRASTS_WITH
    assert any(pred == RelationType.CONTRASTS_WITH for pred, obj in relations)


def test_provides_no_regression():
    """TCP provides reliable delivery → PROVIDES"""
    relations = extract_relations("TCP provides reliable delivery.")
    assert any(pred == RelationType.PROVIDES and "reliable delivery" in obj for pred, obj in relations)


def test_is_an_regression():
    """TCP is an important protocol → IS_A(protocol)"""
    relations = extract_relations("TCP is an important protocol.")
    assert any(pred == RelationType.IS_A and "protocol" in obj for pred, obj in relations)


def test_is_the_regression():
    """TCP is the primary protocol → IS_A(protocol)"""
    relations = extract_relations("TCP is the primary protocol.")
    assert any(pred == RelationType.IS_A and "protocol" in obj for pred, obj in relations)