from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ai.llm_client import LLMError
from app.semantic.semantic_reasoner import (
    SemanticReasoner,
    SemanticReasonerError,
)
from app.semantic.semantic_types import (
    CandidateConcept,
    Certainty,
    ConceptProposal,
    ConceptType,
    InformationType,
    Polarity,
    RelationProposal,
    RelationToPrior,
    SemanticContextSnapshot,
    SemanticProposal,
    SemanticRole,
    is_valid_certainty,
    is_valid_concept_type,
    is_valid_information_type,
    is_valid_polarity,
    is_valid_relation_to_prior,
    is_valid_semantic_role,
)
from app.utils.logger import app_logger


_SYSTEM_PROMPT = (
    "You are a semantic extraction engine for educational lectures. "
    "Given a transcript chunk that has been split into sentences, extract "
    "semantic concepts and assertions. "
    "Return exactly one JSON object conforming to the supplied schema.\n"
    "\n"
    "Rules:\n"
    "- Use proposal-local ids of the form tmp_1, tmp_2, ... for concepts.\n"
    "- A relation's subject_tmp_id MUST reference a concept declared in this "
    "same response, or reference a retrieved candidate via existing_concept_id.\n"
    "- If a concept matches one of the retrieved candidates, set "
    "existing_concept_id to the matching candidate concept_id and do NOT "
    "create a duplicate.\n"
    "- predicate must be normalized snake_case, at most 4 words.\n"
    "- polarity in {positive, negated}. certainty in {asserted, uncertain, "
    "corrected}. relation_to_prior in {new, supports, contradicts, refines}.\n"
    "- information_type must be one of the allowed values.\n"
    "- semantic_role must be one of the allowed values.\n"
    "- concept_type MUST be one of: entity, class, process, quantity, unknown.\n"
    "- Do NOT use 'property', 'attribute', 'behavior', or any other value "
    "as concept_type. These are not valid concept_type values.\n"
    "- If a concept is best described as a property or behavior, choose "
    "the most appropriate allowed concept_type (usually 'entity' for the "
    "thing being described) or 'unknown' if none applies. Never invent a "
    "new concept_type.\n"
    "- Evidence is provided as (sentence_index, span_start, span_end) offsets "
    "into the chunk text. Do NOT supply evidence strings.\n"
    "- confidence_hint is optional. Use a number between 0 and 1, or null if "
    "you have no confidence estimate.\n"
    "- Do NOT invent facts. If the chunk contains no extractable semantics, "
    "return empty arrays.\n"
)


_CONCEPT_TYPE_VALUES = [t.value for t in ConceptType]
_POLARITY_VALUES = [p.value for p in Polarity]
_CERTAINTY_VALUES = [c.value for c in Certainty]
_RELATION_TO_PRIOR_VALUES = [r.value for r in RelationToPrior]
_INFO_TYPE_VALUES = [t.value for t in InformationType]
_SEMANTIC_ROLE_VALUES = [r.value for r in SemanticRole]


def _build_schema(candidate_ids: List[str]) -> Dict[str, Any]:
    existing_enum: List[Any] = list(candidate_ids) + [None]

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["concepts", "relations", "notes"],
        "properties": {
            "concepts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "tmp_id",
                        "canonical_label",
                        "aliases",
                        "concept_type",
                        "existing_concept_id",
                    ],
                    "properties": {
                        "tmp_id": {"type": "string"},
                        "canonical_label": {"type": "string"},
                        "aliases": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "concept_type": {
                            "type": "string",
                            "enum": _CONCEPT_TYPE_VALUES,
                        },
                        "existing_concept_id": {
                            "type": ["string", "null"],
                            "enum": existing_enum,
                        },
                    },
                },
            },
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "subject_tmp_id",
                        "predicate",
                        "object_tmp_id",
                        "object_literal",
                        "polarity",
                        "certainty",
                        "relation_to_prior",
                        "information_type",
                        "semantic_role",
                        "sentence_index",
                        "span_start",
                        "span_end",
                        "confidence_hint",
                    ],
                    "properties": {
                        "subject_tmp_id": {"type": "string"},
                        "predicate": {"type": "string"},
                        "object_tmp_id": {"type": ["string", "null"]},
                        "object_literal": {"type": ["string", "null"]},
                        "polarity": {
                            "type": "string",
                            "enum": _POLARITY_VALUES,
                        },
                        "certainty": {
                            "type": "string",
                            "enum": _CERTAINTY_VALUES,
                        },
                        "relation_to_prior": {
                            "type": "string",
                            "enum": _RELATION_TO_PRIOR_VALUES,
                        },
                        "information_type": {
                            "type": "string",
                            "enum": _INFO_TYPE_VALUES,
                        },
                        "semantic_role": {
                            "type": "string",
                            "enum": _SEMANTIC_ROLE_VALUES,
                        },
                        "sentence_index": {"type": "integer"},
                        "span_start": {"type": "integer"},
                        "span_end": {"type": "integer"},
                        "confidence_hint": {"type": ["number", "null"]},
                    },
                },
            },
            "notes": {"type": "string"},
        },
    }


def _build_prompt(snapshot: SemanticContextSnapshot) -> str:
    lines: List[str] = []
    lines.append("CHUNK TEXT (verbatim, do not modify):")
    lines.append(snapshot.chunk_text)
    lines.append("")

    if snapshot.sentences:
        lines.append("SENTENCES (0-based index, with character offsets):")
        for span in snapshot.sentences:
            lines.append(
                f"  [{span.index}] chars[{span.start}:{span.end}] {span.text}"
            )
        lines.append("")

    lines.append("LECTURE STRUCTURE CONTEXT:")
    lines.append(f"- relation: {snapshot.lsi_relation or 'unknown'}")
    lines.append(f"- current_node: {snapshot.lsi_node_label or '-'}")
    lines.append(f"- parent_node: {snapshot.lsi_parent_label or '-'}")
    lines.append(
        f"- depth: "
        f"{snapshot.lsi_depth if snapshot.lsi_depth is not None else '-'}"
    )
    lines.append("")

    if snapshot.recent_concept_labels:
        lines.append("RECENT CONCEPT LABELS:")
        for label in snapshot.recent_concept_labels:
            lines.append(f"- {label}")
        lines.append("")

    if snapshot.rolling_context:
        trimmed = snapshot.rolling_context.strip()
        if len(trimmed) > 400:
            trimmed = trimmed[-400:]
        lines.append("RECENT CONTEXT (for reference only):")
        lines.append(trimmed)
        lines.append("")

    lines.append("RETRIEVED CANDIDATE CONCEPTS:")
    if not snapshot.candidates:
        lines.append("- (none)")
    else:
        for c in snapshot.candidates:
            lines.append(
                f"- concept_id: {c.concept_id} | label: {c.label} | "
                f"embedding_score={c.embedding_score} "
                f"lexical_score={c.lexical_score}"
            )
    lines.append("")

    lines.append("Return the semantic proposal as JSON.")
    return "\n".join(lines)


class GroqSemanticReasoner(SemanticReasoner):

    def __init__(
        self,
        client,
        *,
        model: str,
        max_tokens: int = 1600,
        reasoning_effort: Optional[str] = None,
        schema_strict: bool = True,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = int(max_tokens)
        self._reasoning_effort = reasoning_effort
        self._schema_strict = bool(schema_strict)

    def reason(
        self,
        *,
        snapshot: SemanticContextSnapshot,
        candidate_concepts: List[CandidateConcept],
    ) -> SemanticProposal:

        candidate_ids = [
            c.concept_id for c in candidate_concepts if c.concept_id
        ]

        schema = _build_schema(candidate_ids)
        prompt = _build_prompt(snapshot)

        try:
            raw = self._client.generate_structured(
                prompt=prompt,
                system=_SYSTEM_PROMPT,
                schema=schema,
                schema_name="semantic_proposal",
                schema_strict=self._schema_strict,
                max_tokens=self._max_tokens,
                reasoning_effort=self._reasoning_effort,
                model=self._model,
            )
        except LLMError as error:
            raise SemanticReasonerError(str(error))
        except Exception as error:
            app_logger.warning(
                f"[GroqSemanticReasoner] unexpected error: {error}"
            )
            raise SemanticReasonerError(str(error))

        if not isinstance(raw, dict):
            raise SemanticReasonerError("non-dict payload")

        concepts_raw = raw.get("concepts", [])
        relations_raw = raw.get("relations", [])
        notes = raw.get("notes", "") or ""

        if not isinstance(concepts_raw, list):
            raise SemanticReasonerError("concepts not list")
        if not isinstance(relations_raw, list):
            raise SemanticReasonerError("relations not list")

        concepts: List[ConceptProposal] = []
        for c in concepts_raw:
            if not isinstance(c, dict):
                continue
            tmp_id = c.get("tmp_id")
            label = c.get("canonical_label")
            aliases = c.get("aliases", [])
            ctype = c.get("concept_type")
            existing_id = c.get("existing_concept_id")

            if not isinstance(tmp_id, str) or not isinstance(label, str):
                continue
            if not is_valid_concept_type(ctype):
                continue
            if not isinstance(aliases, list):
                aliases = []
            aliases = [a for a in aliases if isinstance(a, str)]
            if existing_id is not None and not isinstance(existing_id, str):
                existing_id = None

            concepts.append(
                ConceptProposal(
                    tmp_id=tmp_id,
                    canonical_label=label.strip(),
                    aliases=aliases,
                    concept_type=ctype,
                    existing_concept_id=existing_id,
                )
            )

        relations: List[RelationProposal] = []
        for r in relations_raw:
            if not isinstance(r, dict):
                continue

            sid = r.get("subject_tmp_id")
            predicate = r.get("predicate")
            oid = r.get("object_tmp_id")
            olit = r.get("object_literal")
            polarity = r.get("polarity")
            certainty = r.get("certainty")
            rtp = r.get("relation_to_prior")
            info_type = r.get("information_type")
            role = r.get("semantic_role")
            si = r.get("sentence_index")
            ss = r.get("span_start")
            se = r.get("span_end")
            conf = r.get("confidence_hint", 0.0)

            if not isinstance(sid, str) or not isinstance(predicate, str):
                continue
            if not is_valid_information_type(info_type):
                continue
            if not is_valid_semantic_role(role):
                continue
            if not isinstance(polarity, str) or not is_valid_polarity(polarity):
                continue
            if not isinstance(certainty, str) or not is_valid_certainty(certainty):
                continue
            if not isinstance(rtp, str) or not is_valid_relation_to_prior(rtp):
                continue
            if not isinstance(si, int):
                continue
            if not isinstance(ss, int) or not isinstance(se, int):
                continue

            if oid is not None and not isinstance(oid, str):
                oid = None
            if olit is not None and not isinstance(olit, str):
                olit = None

            if conf is None or not isinstance(conf, (int, float)):
                conf = 0.0

            relations.append(
                RelationProposal(
                    subject_tmp_id=sid,
                    predicate=predicate.strip(),
                    object_tmp_id=oid,
                    object_literal=olit,
                    polarity=polarity,
                    certainty=certainty,
                    relation_to_prior=rtp,
                    information_type=info_type,
                    semantic_role=role,
                    sentence_index=si,
                    span_start=ss,
                    span_end=se,
                    confidence_hint=float(conf),
                )
            )

        return SemanticProposal(
            concepts=concepts,
            relations=relations,
            notes=notes,
            source="groq",
        )