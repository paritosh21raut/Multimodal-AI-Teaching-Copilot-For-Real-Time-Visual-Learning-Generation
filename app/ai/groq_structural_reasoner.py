from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ai.llm_client import LLMError
from app.topics.structural_reasoner import (
    NodeView,
    StructuralProposal,
    StructuralReasoner,
    StructuralReasonerError,
)
from app.utils.logger import app_logger


_SYSTEM_PROMPT = (
    "You are a lecture-structure reasoner. "
    "Given a new transcript chunk and the current lecture structure, "
    "choose the single best structural relationship. "
    "Return exactly one JSON object matching the supplied schema. "
    "Do not invent node ids. Do not invent relations. "
    "Prefer CONTINUATION or DETAIL when the chunk is about the current node. "
    "Use SUBTOPIC only when the chunk introduces a distinct child of the "
    "current node. Use SIBLING only when the chunk introduces a peer of "
    "the current node at the same level. Use NEW_TOPIC only when the chunk "
    "is a distinct major topic that does not belong under the current root. "
    "Use RELATED when the chunk is about the broader lecture but does not "
    "create structural nodes. Use IRRELEVANT only for genuinely unrelated "
    "content."
)


def _build_prompt(
    *,
    chunk_text: str,
    context: str,
    current_node: Optional[NodeView],
    candidate_nodes: List[NodeView],
    allowed_relations: List[str],
    allow_return: bool,
    allow_new_root: bool,
) -> str:

    lines: List[str] = []

    lines.append("NEW CHUNK:")
    lines.append(chunk_text.strip())
    lines.append("")

    if context:
        trimmed = context.strip()
        if len(trimmed) > 600:
            trimmed = trimmed[-600:]
        lines.append("RECENT CONTEXT:")
        lines.append(trimmed)
        lines.append("")

    if current_node is not None:
        lines.append("CURRENT NODE:")
        lines.append(
            f"- id: {current_node.id} | label: {current_node.label} "
            f"| depth: {current_node.depth} "
            f"| parent: {current_node.parent_label or '-'}"
        )
        if current_node.child_labels:
            lines.append(
                "  children: " + ", ".join(current_node.child_labels)
            )
        lines.append("")

    lines.append("CANDIDATE NODES:")
    if not candidate_nodes:
        lines.append("- (none)")
    else:
        for node in candidate_nodes:
            lines.append(
                f"- id: {node.id} | label: {node.label} "
                f"| depth: {node.depth} "
                f"| parent: {node.parent_label or '-'}"
            )
    lines.append("")

    lines.append("ALLOWED RELATIONS:")
    lines.append(", ".join(allowed_relations))
    lines.append("")

    lines.append("RULES:")
    lines.append(
        "- target_node_id must be one of the candidate ids above, "
        "or null for NEW_TOPIC."
    )
    lines.append(
        "- concept_label is required only when creating a new node "
        "(SUBTOPIC, SIBLING, NEW_TOPIC). Maximum 5 words."
    )
    lines.append(
        "- For CONTINUATION, DETAIL, RELATED, RETURN, "
        "target_node_id must be a candidate id."
    )

    if not allow_return:
        lines.append("- RETURN is not available for this chunk.")
    if not allow_new_root:
        lines.append("- NEW_TOPIC is not available for this chunk.")

    lines.append("")
    lines.append("Return exactly one JSON object matching the schema.")

    return "\n".join(lines)


def _build_schema(
    *,
    allowed_relations: List[str],
    candidate_ids: List[str],
    allow_return: bool,
    allow_new_root: bool,
) -> Dict[str, Any]:

    relations = list(allowed_relations)

    if not allow_return and "return" in relations:
        relations.remove("return")

    if not allow_new_root and "new_topic" in relations:
        relations.remove("new_topic")

    target_enum_values: List[Any] = list(candidate_ids)

    if allow_new_root:
        target_enum_values.append(None)

    target_schema: Dict[str, Any] = {
        "type": ["string", "null"],
    }

    if target_enum_values:
        target_schema["enum"] = target_enum_values

    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "relation",
            "target_node_id",
            "concept_label",
            "confidence",
            "reason",
        ],
        "properties": {
            "relation": {
                "type": "string",
                "enum": relations,
            },
            "target_node_id": target_schema,
            "concept_label": {
                "type": ["string", "null"],
            },
            "confidence": {
                "type": "number",
            },
            "reason": {
                "type": "string",
            },
        },
    }


class GroqStructuralReasoner(StructuralReasoner):

    def __init__(
        self,
        client,
        *,
        max_tokens: int = 320,
        reasoning_effort: Optional[str] = "low",
    ) -> None:
        self._client = client
        self._max_tokens = int(max_tokens)
        self._reasoning_effort = reasoning_effort

    def reason(
        self,
        *,
        chunk_text: str,
        context: str,
        current_node: Optional[NodeView],
        candidate_nodes: List[NodeView],
        allowed_relations: List[str],
        allow_return: bool,
        allow_new_root: bool,
    ) -> StructuralProposal:

        if not allowed_relations:
            raise StructuralReasonerError(
                "no allowed relations supplied"
            )

        prompt = _build_prompt(
            chunk_text=chunk_text,
            context=context,
            current_node=current_node,
            candidate_nodes=candidate_nodes,
            allowed_relations=allowed_relations,
            allow_return=allow_return,
            allow_new_root=allow_new_root,
        )

        schema = _build_schema(
            allowed_relations=allowed_relations,
            candidate_ids=[node.id for node in candidate_nodes],
            allow_return=allow_return,
            allow_new_root=allow_new_root,
        )

        try:
            raw = self._client.generate_structured(
                prompt=prompt,
                system=_SYSTEM_PROMPT,
                schema=schema,
                schema_name="structural_decision",
                max_tokens=self._max_tokens,
                reasoning_effort=self._reasoning_effort,
            )
        except LLMError as error:
            app_logger.warning(
                f"[GroqStructuralReasoner] LLM failure: {error}"
            )
            raise StructuralReasonerError(str(error))
        except Exception as error:
            app_logger.warning(
                f"[GroqStructuralReasoner] unexpected error: {error}"
            )
            raise StructuralReasonerError(str(error))

        if not isinstance(raw, dict):
            raise StructuralReasonerError(
                "reasoner returned non-dict payload"
            )

        relation = raw.get("relation")
        target = raw.get("target_node_id")
        concept = raw.get("concept_label")
        confidence = raw.get("confidence")
        reason_text = raw.get("reason")

        if not isinstance(relation, str):
            raise StructuralReasonerError(
                "reasoner relation missing or wrong type"
            )

        if target is not None and not isinstance(target, str):
            raise StructuralReasonerError(
                "reasoner target_node_id wrong type"
            )

        if concept is not None and not isinstance(concept, str):
            raise StructuralReasonerError(
                "reasoner concept_label wrong type"
            )

        if not isinstance(confidence, (int, float)):
            raise StructuralReasonerError(
                "reasoner confidence wrong type"
            )

        if not isinstance(reason_text, str):
            raise StructuralReasonerError(
                "reasoner reason missing or wrong type"
            )

        return StructuralProposal(
            relation=relation,
            target_node_id=target,
            concept_label=concept,
            confidence=float(confidence),
            reason=reason_text,
            source="groq",
            raw=raw,
        )