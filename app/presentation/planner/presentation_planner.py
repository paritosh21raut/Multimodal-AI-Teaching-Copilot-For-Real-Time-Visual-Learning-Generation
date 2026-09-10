"""PresentationPlanner with deterministic language realization.

Deduplicates visible text blocks: one semantic claim/evidence unit must not
produce multiple identical visible text blocks on the same slide.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any

from app.presentation.models.presentation_models import (
    SlidePlan, ContentBlock, ContentBlockType, LayoutFamily,
    RepresentationDecision, SelectedInformation, SemanticEvidence,
)


class PresentationPlanner:
    """Composes SlidePlan and realizes display text deterministically."""

    def __init__(self):
        self._slide_counter = 0

    def plan(self, slide_decision, selected_info, representation=None, topic_id=""):
        self._slide_counter += 1

        action = slide_decision
        if hasattr(slide_decision, 'action'):
            action = slide_decision.action

        focal_text = self._realize_evidence(selected_info.focal_claim) if selected_info.focal_claim else ""

        plan = SlidePlan(
            slide_id=f"slide_{self._slide_counter}",
            topic_id=topic_id,
            purpose=self._determine_purpose(action),
            focal_message=focal_text,
            content_blocks=self._build_blocks(selected_info),
            representation=representation,
            evidence_ids=selected_info.evidence_ids,
            density=self._determine_density(selected_info),
            layout_family=self._determine_layout(representation),
        )

        return plan

    def _realize_evidence(self, evidence: SemanticEvidence) -> str:
        mapping = {
            "IS_A": f"{evidence.subject} is a {evidence.object}",
            "HAS_ATTRIBUTE": f"{evidence.subject} is {evidence.object}",
            "PROVIDES": f"{evidence.subject} provides {evidence.object}",
            "USES": f"{evidence.subject} uses {evidence.object}",
            "CONTRASTS_WITH": f"{evidence.subject} contrasts with {evidence.object}",
            "PART_OF": f"{evidence.subject} is part of {evidence.object}",
            "HAS_PART": f"{evidence.subject} has {evidence.object}",
            "CAUSES": f"{evidence.subject} causes {evidence.object}",
            "DEFINED_AS": f"{evidence.subject} is defined as {evidence.object}",
        }
        return mapping.get(evidence.predicate, f"{evidence.subject} {evidence.predicate} {evidence.object}")

    def _build_blocks(self, selected_info):
        blocks = []
        seen_text = set()

        def _add(block_type, text, semantic_ids=None, priority=1.0):
            if not text:
                return
            if text in seen_text:
                return
            seen_text.add(text)
            blocks.append(ContentBlock(
                block_type=block_type,
                text=text,
                semantic_ids=semantic_ids or [],
                priority=priority,
            ))

        if selected_info.focal_claim:
            _add(
                ContentBlockType.KEY_CLAIM,
                self._realize_evidence(selected_info.focal_claim),
                semantic_ids=[selected_info.focal_claim.evidence_id] if selected_info.focal_claim.evidence_id else [],
                priority=1.0,
            )

        for ev in selected_info.semantic_units:
            _add(
                ContentBlockType.EXPLANATION,
                self._realize_evidence(ev),
                semantic_ids=[ev.evidence_id] if ev.evidence_id else [],
                priority=0.6,
            )

        for d in selected_info.definitions:
            _add(ContentBlockType.DEFINITION, d, priority=0.5)

        blocks.sort(key=lambda b: b.priority, reverse=True)
        return blocks

    def _determine_purpose(self, action):
        purposes = {
            "create_new": "Introduce new concept",
            "update": "Expand current concept",
            "refine": "Refine explanation",
            "finalize": "Complete current concept",
            "no_change": "Accumulate content",
            "wait": "Waiting for more information",
        }
        return purposes.get(action.value if hasattr(action, 'value') else str(action), "General content")

    def _determine_density(self, selected_info):
        total = len(selected_info.semantic_units) + len(selected_info.definitions)
        if total <= 2: return 0.3
        if total <= 4: return 0.5
        if total <= 6: return 0.7
        return 0.9

    def _determine_layout(self, representation):
        if not representation:
            return LayoutFamily.TEXT_LEFT_VISUAL_RIGHT
        mapping = {
            "definition": LayoutFamily.HERO_DEFINITION,
            "comparison": LayoutFamily.FULL_WIDTH_COMPARISON,
            "contrast": LayoutFamily.TWO_COLUMN_CONTRAST,
            "flowchart": LayoutFamily.FULL_WIDTH_PROCESS,
            "hierarchy": LayoutFamily.HIERARCHY_CENTERED,
        }
        rt = representation.representation_type
        rt_val = rt.value if hasattr(rt, 'value') else str(rt)
        return mapping.get(rt_val, LayoutFamily.TEXT_LEFT_VISUAL_RIGHT)