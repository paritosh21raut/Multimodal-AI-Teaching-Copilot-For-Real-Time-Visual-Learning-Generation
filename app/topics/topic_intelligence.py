from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.ai.groq_structural_reasoner import (
    GroqStructuralReasoner,
)
from app.config import (
    LSI_REASONER_ENABLED,
    LSI_REASONER_MAX_TOKENS,
    LSI_REASONER_REASONING_EFFORT,
)
from app.topics.lsi import (
    LectureStructureIntelligence,
)
from app.topics.lecture_structure import (
    StructureDecision,
    StructureRelation,
)
from app.utils.logger import app_logger


@dataclass
class TopicDecision:
    topic: str
    embedding: Any
    is_relevant: bool
    is_new_topic: bool
    similarity: float
    confidence: float
    reason: str
    relation: Optional[str] = None
    node_id: Optional[str] = None
    parent_node_id: Optional[str] = None
    depth: Optional[int] = None
    is_return: bool = False
    is_new_subtopic: bool = False
    structure_evidence: Dict[str, Any] = field(default_factory=dict)


_RELATION_TO_REASON = {
    StructureRelation.CONTINUATION: "relevant_continuation",
    StructureRelation.DETAIL: "detail",
    StructureRelation.RELATED: "related_content",
    StructureRelation.SUBTOPIC: "subtopic",
    StructureRelation.SIBLING: "sibling",
    StructureRelation.NEW_TOPIC: "new_topic",
    StructureRelation.RETURN: "return_to_topic",
    StructureRelation.IRRELEVANT: "irrelevant_speech",
}

_IS_NEW_TOPIC_MAP = {
    StructureRelation.CONTINUATION: False,
    StructureRelation.DETAIL: False,
    StructureRelation.RELATED: False,
    StructureRelation.SUBTOPIC: False,
    StructureRelation.SIBLING: True,
    StructureRelation.NEW_TOPIC: True,
    StructureRelation.RETURN: False,
    StructureRelation.IRRELEVANT: False,
}


def _build_reasoner() -> Optional[GroqStructuralReasoner]:

    if not LSI_REASONER_ENABLED:
        app_logger.info(
            "[TopicIntelligence] LSI structural reasoner disabled"
        )
        return None

    from app.knowledge.content_generator import content_generator

    shared_client = getattr(content_generator, "ai", None)

    if shared_client is None:
        app_logger.warning(
            "[TopicIntelligence] ContentGenerator has no Groq client; "
            "LSI reasoner will be disabled"
        )
        return None

    app_logger.info(
        "[TopicIntelligence] LSI structural reasoner enabled "
        f"reasoning_effort={LSI_REASONER_REASONING_EFFORT} "
        f"max_tokens={LSI_REASONER_MAX_TOKENS}"
    )

    return GroqStructuralReasoner(
        shared_client,
        max_tokens=LSI_REASONER_MAX_TOKENS,
        reasoning_effort=LSI_REASONER_REASONING_EFFORT,
    )


class TopicIntelligence:

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        *,
        reasoner=None,
    ) -> None:

        print("[Topic] Loading embedding model...")

        effective_reasoner = (
            reasoner if reasoner is not None else _build_reasoner()
        )

        self.lsi = LectureStructureIntelligence(
            model_name=model_name,
            reasoner=effective_reasoner,
        )

        print("[Topic] Ready")

    def reset(self) -> None:
        self.lsi.reset()

    def process(
        self,
        latest_text: str,
        rolling_context: str = "",
        current_topic: Optional[str] = None,
        current_embedding=None,
    ) -> TopicDecision:

        print("[Topic] process() called")

        decision: StructureDecision = self.lsi.process(
            latest_text=latest_text,
            rolling_context=rolling_context,
            current_topic=current_topic,
            current_embedding=current_embedding,
        )

        relation = decision.relation
        is_relevant = relation is not StructureRelation.IRRELEVANT
        is_new_topic = _IS_NEW_TOPIC_MAP.get(relation, False)
        reason = _RELATION_TO_REASON.get(relation, decision.reason)
        topic = decision.topic_label or current_topic or ""

        embedding = current_embedding
        if decision.current_node_id:
            node = self.lsi._registry.get(decision.current_node_id)
            if node is not None:
                embedding = node.embedding

        return TopicDecision(
            topic=topic,
            embedding=embedding,
            is_relevant=is_relevant,
            is_new_topic=is_new_topic,
            similarity=decision.similarity,
            confidence=decision.confidence,
            reason=reason,
            relation=relation.value,
            node_id=decision.current_node_id,
            parent_node_id=decision.parent_node_id,
            depth=decision.depth,
            is_return=decision.is_return,
            is_new_subtopic=decision.is_new_subtopic,
            structure_evidence=decision.evidence,
        )


topic_intelligence = TopicIntelligence()