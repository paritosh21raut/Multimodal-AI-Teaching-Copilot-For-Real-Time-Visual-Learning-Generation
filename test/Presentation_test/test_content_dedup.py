"""
Regression: no duplicate visible text blocks on a single slide.

Root cause covered: PresentationPlanner emitted both a KEY_CLAIM block and an
EXPLANATION block with the same realized text when the focal claim proposition
was also present in semantic_units.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.information_selection.information_selector import InformationSelector
from app.presentation.planner.presentation_planner import PresentationPlanner
from app.presentation.models.presentation_models import (
    SlideAction, ContentBlockType,
)

from app.semantic.semantic_models import (
    SemanticFrame, Concept, ConceptRef, Proposition, RelationType,
)


def _frame_with_prop():
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="kernel", canonical_name="kernel", confidence=0.9))
    frame.concepts.append(Concept(concept_id="core", canonical_name="core program", confidence=0.9))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="kernel", canonical_name="kernel"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="core", canonical_name="core program"),
        confidence=0.9,
    ))
    return frame


def test_planner_emits_no_duplicate_text_blocks():
    selector = InformationSelector()
    planner = PresentationPlanner()
    frame = _frame_with_prop()

    selection = selector.select(frame, important_concepts=["kernel"])
    plan = planner.plan(
        slide_decision=SlideAction.CREATE_NEW,
        selected_info=selection,
        representation=None,
        topic_id="kernel",
    )

    texts = [b.text for b in plan.content_blocks if b.text]
    assert len(texts) == len(set(texts)), f"duplicate block text: {texts}"


def test_multiple_propositions_no_duplicate_text():
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="kernel", canonical_name="kernel", confidence=0.9))
    frame.concepts.append(Concept(concept_id="core", canonical_name="core program", confidence=0.9))
    frame.concepts.append(Concept(concept_id="syscall", canonical_name="system calls", confidence=0.9))

    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="kernel", canonical_name="kernel"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="core", canonical_name="core program"),
        confidence=0.9,
    ))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="kernel", canonical_name="kernel"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="syscall", canonical_name="system calls"),
        confidence=0.9,
    ))

    selector = InformationSelector()
    planner = PresentationPlanner()
    selection = selector.select(frame, important_concepts=["kernel"])
    plan = planner.plan(
        slide_decision=SlideAction.CREATE_NEW,
        selected_info=selection,
        representation=None,
        topic_id="kernel",
    )

    texts = [b.text for b in plan.content_blocks if b.text]
    assert len(texts) == len(set(texts)), f"duplicate block text: {texts}"
    assert len(texts) >= 2, "expected distinct blocks for distinct propositions"


def test_focal_claim_still_present_as_key_claim():
    selector = InformationSelector()
    planner = PresentationPlanner()
    frame = _frame_with_prop()

    selection = selector.select(frame, important_concepts=["kernel"])
    plan = planner.plan(
        slide_decision=SlideAction.CREATE_NEW,
        selected_info=selection,
        representation=None,
        topic_id="kernel",
    )

    key_claims = [b for b in plan.content_blocks if b.block_type == ContentBlockType.KEY_CLAIM]
    assert len(key_claims) == 1