# app/topics/topic_intelligence.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import RLock
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from sentence_transformers import SentenceTransformer


class StructuralDecision(str, Enum):
    INITIAL_TOPIC = "initial_topic"
    CONTINUE_CURRENT = "continue_current"
    RELATED_CONTENT = "related_content"
    CREATE_SUBTOPIC = "create_subtopic"
    NEW_MAJOR_TOPIC = "new_major_topic"
    RETURN_TO_PREVIOUS = "return_to_previous"
    IRRELEVANT = "irrelevant"
    UNCERTAIN = "uncertain"


@dataclass
class TopicNode:
    node_id: int
    name: str
    parent_id: Optional[int]
    level: int

    anchor_embedding: torch.Tensor
    centroid_embedding: torch.Tensor

    aliases: List[str] = field(default_factory=list)
    mention_count: int = 1
    development_score: float = 0.0
    importance_score: float = 0.0

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    children_ids: List[int] = field(default_factory=list)
    status: str = "active"

    concept_terms: List[str] = field(default_factory=list)
    concept_head: str = ""
    concept_modifier: str = ""
    concept_object: str = ""

    @property
    def children(self) -> List[int]:
        return self.children_ids


@dataclass
class TopicDecision:
    topic: str
    embedding: torch.Tensor
    is_relevant: bool
    is_new_topic: bool
    similarity: float
    confidence: float
    reason: str
    structural_decision: StructuralDecision
    node_id: Optional[int] = None
    parent_node_id: Optional[int] = None
    transition_signal: bool = False
    evidence: Dict[str, object] = field(default_factory=dict)


@dataclass
class _Concept:
    text: str
    normalized: str
    head: str
    modifier: str
    object_term: str
    terms: List[str]
    is_partitive: bool


@dataclass
class _Discourse:
    explicit_boundary: bool = False
    explicit_return: bool = False
    summary_signal: bool = False
    development_signal: bool = False
    classroom_chatter: bool = False


class TopicIntelligence:

    # ================================================================
    # DISCOURSE SIGNALS
    # ================================================================

    _BOUNDARY_PATTERNS = (
        r"\bnow\s+(?:let'?s|we'?ll|we\s+will)\b",
        r"\bnext\b",
        r"\bmoving\s+on\b",
        r"\blet'?s\s+(?:discuss|look\s+at|talk\s+about|consider)\b",
        r"\bwe\s+(?:will|are\s+going\s+to)\s+(?:discuss|look\s+at|consider)\b",
        r"\bturning\s+to\b",
        r"\banother\s+(?:topic|aspect|concept|point)\b",
        r"\bfinally\b",
    )

    _RETURN_PATTERNS = (
        r"\bback\s+to\b",
        r"\breturn(?:ing)?\s+to\b",
        r"\bcoming\s+back\s+to\b",
        r"\bas\s+we\s+(?:saw|discussed)\s+earlier\b",
        r"\bgoing\s+back\s+to\b",
        r"\brevisit\b",
    )

    _SUMMARY_PATTERNS = (
        r"\bto\s+summarize\b",
        r"\bin\s+summary\b",
        r"\bto\s+sum\s+up\b",
        r"\bin\s+short\b",
        r"\brecap\b",
    )

    _DEVELOPMENT_PATTERNS = (
        r"\bused\s+to\b",
        r"\bused\s+for\b",
        r"\bconsists\s+of\b",
        r"\bcontains\b",
        r"\bincludes\b",
        r"\bprovides\b",
        r"\ballows\b",
        r"\bcontrols\b",
        r"\bstores\b",
        r"\bexecutes\b",
        r"\bcommunicates\b",
        r"\bworks\s+by\b",
        r"\bmeans\b",
        r"\brefers\s+to\b",
        r"\bdefines\b",
        r"\bcalled\b",
        r"\bknown\s+as\b",
        r"\bcomposed\s+of\b",
        r"\bmade\s+of\b",
    )

    _CHATTER_PATTERNS = (
        r"\bcan\s+you\s+hear\s+me\b",
        r"\bcan\s+you\s+hear\s+us\b",
        r"\bis\s+the\s+(?:mic|microphone)\b",
        r"\bwait\s+a\s+(?:second|moment)\b",
        r"\bjust\s+a\s+second\b",
        r"\bhold\s+on\b",
        r"^sorry$",
        r"^thanks?$",
    )

    # ================================================================
    # GENERIC STOPWORDS
    # ================================================================

    _STOPWORDS = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "from",
        "by",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "this",
        "that",
        "these",
        "those",
        "we",
        "you",
        "they",
        "it",
        "as",
        "at",
        "into",
        "about",
        "now",
        "then",
        "also",
        "very",
        "just",
        "can",
        "will",
        "would",
        "could",
        "should",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "used",
        "using",
        "use",
        "lets",
        "let",
        "there",
        "their",
        "its",
        "which",
        "who",
        "what",
        "how",
        "today",
    }

    # ================================================================
    # INITIALIZATION
    # ================================================================

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        new_topic_threshold: float = 0.55,
        irrelevant_threshold: float = 0.30,
        subtopic_threshold: float = 0.45,
        centroid_update_weight: float = 0.15,
    ) -> None:

        self._lock = RLock()

        self.model = SentenceTransformer(model_name)

        self.new_topic_threshold = float(
            new_topic_threshold
        )
        self.irrelevant_threshold = float(
            irrelevant_threshold
        )
        self.subtopic_threshold = float(
            subtopic_threshold
        )
        self.centroid_update_weight = float(
            centroid_update_weight
        )

        self._nodes: Dict[int, TopicNode] = {}
        self._next_node_id = 1

        self._active_node_id: Optional[int] = None
        self._active_stack: List[int] = []

        self._topic_history: List[TopicNode] = []

        self._recent_chunks: List[str] = []
        self._concept_history: List[str] = []

    # ================================================================
    # MAIN PROCESS
    # ================================================================

    def process(
        self,
        latest_text: str,
        rolling_context: str = "",
        current_topic: Optional[str] = None,
        current_embedding: Optional[torch.Tensor] = None,
    ) -> TopicDecision:

        with self._lock:

            text = self._normalize_text(
                latest_text
            )

            if not text:
                return self._irrelevant(
                    "",
                    self._zero_embedding(),
                    "empty transcript",
                )

            discourse = self._detect_discourse(
                text
            )

            embedding = self._encode(text)

            if discourse.classroom_chatter:
                return self._irrelevant(
                    text,
                    embedding,
                    "classroom chatter",
                )

            concept = self._extract_concept(
                text
            )

            # ========================================================
            # INITIAL TOPIC
            # ========================================================

            if not self._active_stack:

                topic_name = (
                    concept.text
                    if concept is not None
                    else self._clean_topic_name(text)
                )

                node = self._create_node(
                    name=topic_name,
                    embedding=embedding,
                    parent_id=None,
                    concept=concept,
                )

                self._activate(
                    node.node_id
                )

                self._remember(
                    text,
                    concept,
                )

                return TopicDecision(
                    topic=node.name,
                    embedding=embedding,
                    is_relevant=True,
                    is_new_topic=True,
                    similarity=1.0,
                    confidence=1.0,
                    reason="initial lecture concept",
                    structural_decision=(
                        StructuralDecision.INITIAL_TOPIC
                    ),
                    node_id=node.node_id,
                    parent_node_id=None,
                    transition_signal=(
                        discourse.explicit_boundary
                    ),
                    evidence={
                        "concept": concept,
                    },
                )

            active = self._nodes[
                self._active_stack[-1]
            ]

            active_similarity = self._similarity(
                embedding,
                active.centroid_embedding,
            )

            # ========================================================
            # EXPLICIT RETURN
            # ========================================================

            if discourse.explicit_return:

                historical = self._find_return_target(
                    embedding,
                    concept,
                )

                if historical is not None:

                    self._activate(
                        historical.node_id
                    )

                    self._update_node(
                        historical,
                        embedding,
                    )

                    self._remember(
                        text,
                        concept,
                    )

                    return TopicDecision(
                        topic=historical.name,
                        embedding=embedding,
                        is_relevant=True,
                        is_new_topic=False,
                        similarity=self._similarity(
                            embedding,
                            historical.centroid_embedding,
                        ),
                        confidence=0.92,
                        reason=(
                            "returned to previously "
                            "discussed concept"
                        ),
                        structural_decision=(
                            StructuralDecision.RETURN_TO_PREVIOUS
                        ),
                        node_id=historical.node_id,
                        parent_node_id=historical.parent_id,
                        transition_signal=True,
                        evidence={
                            "concept": concept,
                            "return_target": historical.node_id,
                        },
                    )

                return TopicDecision(
                    topic=active.name,
                    embedding=embedding,
                    is_relevant=True,
                    is_new_topic=False,
                    similarity=active_similarity,
                    confidence=0.35,
                    reason=(
                        "return signal detected but "
                        "target is uncertain"
                    ),
                    structural_decision=(
                        StructuralDecision.UNCERTAIN
                    ),
                    node_id=active.node_id,
                    parent_node_id=active.parent_id,
                    transition_signal=True,
                    evidence={
                        "concept": concept,
                    },
                )

            # ========================================================
            # EXPLICIT STRUCTURAL BOUNDARY
            # ========================================================

            if discourse.explicit_boundary:

                relation = self._classify_boundary(
                    concept=concept,
                    embedding=embedding,
                    active=active,
                    active_similarity=active_similarity,
                )

                if (
                    relation
                    == StructuralDecision.CONTINUE_CURRENT
                ):

                    self._update_node(
                        active,
                        embedding,
                    )

                    self._remember(
                        text,
                        concept,
                    )

                    return TopicDecision(
                        topic=active.name,
                        embedding=embedding,
                        is_relevant=True,
                        is_new_topic=False,
                        similarity=active_similarity,
                        confidence=0.90,
                        reason=(
                            "explicit transition refers "
                            "to current concept"
                        ),
                        structural_decision=(
                            StructuralDecision.CONTINUE_CURRENT
                        ),
                        node_id=active.node_id,
                        parent_node_id=active.parent_id,
                        transition_signal=True,
                        evidence={
                            "concept": concept,
                        },
                    )

                if (
                    relation
                    == StructuralDecision.CREATE_SUBTOPIC
                ):

                    parent_id = self._get_boundary_parent(
                        concept=concept,
                        active=active,
                        embedding=embedding,
                    )

                    node = self._create_node(
                        name=(
                            concept.text
                            if concept is not None
                            else self._clean_topic_name(text)
                        ),
                        embedding=embedding,
                        parent_id=parent_id,
                        concept=concept,
                    )

                    self._activate(
                        node.node_id
                    )

                    self._remember(
                        text,
                        concept,
                    )

                    return TopicDecision(
                        topic=node.name,
                        embedding=embedding,
                        is_relevant=True,
                        is_new_topic=True,
                        similarity=active_similarity,
                        confidence=0.90,
                        reason=(
                            "explicit boundary introduces "
                            "a new structural concept"
                        ),
                        structural_decision=(
                            StructuralDecision.CREATE_SUBTOPIC
                        ),
                        node_id=node.node_id,
                        parent_node_id=parent_id,
                        transition_signal=True,
                        evidence={
                            "concept": concept,
                            "parent_node_id": parent_id,
                        },
                    )

                if (
                    relation
                    == StructuralDecision.NEW_MAJOR_TOPIC
                ):

                    node = self._create_node(
                        name=(
                            concept.text
                            if concept is not None
                            else self._clean_topic_name(text)
                        ),
                        embedding=embedding,
                        parent_id=None,
                        concept=concept,
                    )

                    self._activate(
                        node.node_id
                    )

                    self._remember(
                        text,
                        concept,
                    )

                    return TopicDecision(
                        topic=node.name,
                        embedding=embedding,
                        is_relevant=True,
                        is_new_topic=True,
                        similarity=active_similarity,
                        confidence=0.88,
                        reason=(
                            "explicit boundary introduces "
                            "a new major concept"
                        ),
                        structural_decision=(
                            StructuralDecision.NEW_MAJOR_TOPIC
                        ),
                        node_id=node.node_id,
                        parent_node_id=None,
                        transition_signal=True,
                        evidence={
                            "concept": concept,
                        },
                    )

                self._remember(
                    text,
                    concept,
                )

                return TopicDecision(
                    topic=active.name,
                    embedding=embedding,
                    is_relevant=True,
                    is_new_topic=False,
                    similarity=active_similarity,
                    confidence=0.45,
                    reason=(
                        "structural boundary detected "
                        "but relationship is uncertain"
                    ),
                    structural_decision=(
                        StructuralDecision.UNCERTAIN
                    ),
                    node_id=active.node_id,
                    parent_node_id=active.parent_id,
                    transition_signal=True,
                    evidence={
                        "concept": concept,
                    },
                )

            # ========================================================
            # NO EXPLICIT BOUNDARY
            # ========================================================

            if self._is_same_concept(
                concept,
                active,
            ):

                self._update_node(
                    active,
                    embedding,
                )

                self._remember(
                    text,
                    concept,
                )

                return TopicDecision(
                    topic=active.name,
                    embedding=embedding,
                    is_relevant=True,
                    is_new_topic=False,
                    similarity=active_similarity,
                    confidence=0.95,
                    reason="same concept continues",
                    structural_decision=(
                        StructuralDecision.CONTINUE_CURRENT
                    ),
                    node_id=active.node_id,
                    parent_node_id=active.parent_id,
                )

            if active_similarity >= 0.45:

                self._update_node(
                    active,
                    embedding,
                )

                self._remember(
                    text,
                    concept,
                )

                return TopicDecision(
                    topic=active.name,
                    embedding=embedding,
                    is_relevant=True,
                    is_new_topic=False,
                    similarity=active_similarity,
                    confidence=0.82,
                    reason=(
                        "semantic continuity without "
                        "structural boundary"
                    ),
                    structural_decision=(
                        StructuralDecision.CONTINUE_CURRENT
                    ),
                    node_id=active.node_id,
                    parent_node_id=active.parent_id,
                )

            if active_similarity < self.irrelevant_threshold:

                lecture_signal = (
                    self._has_lecture_signal(
                        text,
                        discourse,
                    )
                )

                self._remember(
                    text,
                    concept,
                )

                if not lecture_signal:

                    return self._irrelevant(
                        text,
                        embedding,
                        (
                            "low similarity and no "
                            "lecture signal"
                        ),
                        active.node_id,
                    )

                return TopicDecision(
                    topic=active.name,
                    embedding=embedding,
                    is_relevant=True,
                    is_new_topic=False,
                    similarity=active_similarity,
                    confidence=0.30,
                    reason=(
                        "lecture-like content but "
                        "structural relation is uncertain"
                    ),
                    structural_decision=(
                        StructuralDecision.UNCERTAIN
                    ),
                    node_id=active.node_id,
                    parent_node_id=active.parent_id,
                )

            self._remember(
                text,
                concept,
            )

            return TopicDecision(
                topic=active.name,
                embedding=embedding,
                is_relevant=True,
                is_new_topic=False,
                similarity=active_similarity,
                confidence=0.55,
                reason=(
                    "related content without enough "
                    "structural evidence"
                ),
                structural_decision=(
                    StructuralDecision.RELATED_CONTENT
                ),
                node_id=active.node_id,
                parent_node_id=active.parent_id,
            )

    # ================================================================
    # DISCOURSE
    # ================================================================

    def _detect_discourse(
        self,
        text: str,
    ) -> _Discourse:

        return _Discourse(
            explicit_boundary=self._matches(
                text,
                self._BOUNDARY_PATTERNS,
            ),
            explicit_return=self._matches(
                text,
                self._RETURN_PATTERNS,
            ),
            summary_signal=self._matches(
                text,
                self._SUMMARY_PATTERNS,
            ),
            development_signal=self._matches(
                text,
                self._DEVELOPMENT_PATTERNS,
            ),
            classroom_chatter=self._is_classroom_chatter(
                text
            ),
        )

    def _is_classroom_chatter(
        self,
        text: str,
    ) -> bool:

        if not self._matches(
            text,
            self._CHATTER_PATTERNS,
        ):
            return False

        return len(text.split()) <= 12

    def _has_lecture_signal(
        self,
        text: str,
        discourse: _Discourse,
    ) -> bool:

        if discourse.development_signal:
            return True

        if discourse.summary_signal:
            return True

        if len(text.split()) < 5:
            return False

        explanatory_patterns = (
            r"\brefers\s+to\b",
            r"\bdefined\s+as\b",
            r"\bknown\s+as\b",
            r"\bcalled\b",
            r"\bused\s+for\b",
            r"\bused\s+to\b",
            r"\bconsists\s+of\b",
            r"\bmade\s+of\b",
            r"\bcomposed\s+of\b",
            r"\bcontains\b",
            r"\bincludes\b",
            r"\bprovides\b",
            r"\ballows\b",
            r"\bcontrols\b",
            r"\bstores\b",
            r"\bexecutes\b",
            r"\bcommunicates\b",
            r"\bworks\s+by\b",
            r"\bmeans\b",
            r"\brepresents\b",
            r"\bdefines\b",
        )

        return self._matches(
            text,
            explanatory_patterns,
        )

    @staticmethod
    def _matches(
        text: str,
        patterns: Tuple[str, ...],
    ) -> bool:

        return any(
            re.search(
                pattern,
                text,
                re.IGNORECASE,
            )
            for pattern in patterns
        )

    # ================================================================
    # CONCEPT EXTRACTION
    # ================================================================

    def _extract_concept(
        self,
        text: str,
    ) -> Optional[_Concept]:

        cleaned = self._strip_prefix(
            text
        )

        if not cleaned:
            return None

        introduction_patterns = (
            r"^(?:today\s+)?"
            r"(?:we\s+are|we're|we\s+will|we'll)\s+"
            r"(?:learning|studying|covering|discussing|"
            r"examining|exploring)\s+"
            r"(?:about\s+|on\s+|the\s+topic\s+of\s+)?"
            r"(?P<concept>.+)$",

            r"^(?:today\s+)?"
            r"(?:the\s+)?"
            r"(?:topic|subject)\s+"
            r"(?:is|will\s+be)\s+"
            r"(?P<concept>.+)$",

            r"^(?:today\s+)?"
            r"(?:our\s+)?"
            r"(?:topic|subject)\s+(?:for\s+today\s+)?"
            r"(?:is|will\s+be)\s+"
            r"(?P<concept>.+)$",
        )

        for pattern in introduction_patterns:

            match = re.match(
                pattern,
                cleaned,
                flags=re.IGNORECASE,
            )

            if match:

                candidate = (
                    match.group("concept")
                    .strip(" .,:;!?")
                )

                candidate = self._clean_concept_candidate(
                    candidate
                )

                if candidate:
                    return self._make_concept(
                        candidate,
                        is_partitive=False,
                    )

        # ------------------------------------------------------------
        # Generic X-of-Y structure.
        # ------------------------------------------------------------

        cleaned_for_structure = re.sub(
            r"[,:;.!?]+",
            " ",
            cleaned,
        )

        cleaned_for_structure = re.sub(
            r"\s+",
            " ",
            cleaned_for_structure,
        ).strip()

        cleaned_for_structure = (
            self._clean_concept_candidate(
                cleaned_for_structure
            )
        )

        match = re.match(
            r"^(?P<head>[\w-]+(?:\s+[\w-]+){0,4}?)\s+of\s+"
            r"(?P<object>[\w-]+(?:\s+[\w-]+){0,5})$",
            cleaned_for_structure,
            flags=re.IGNORECASE,
        )

        if match:

            head = self._normalize_phrase(
                match.group("head")
            )

            object_term = self._normalize_phrase(
                match.group("object")
            )

            normalized_text = (
                f"{head} of {object_term}"
            )

            return _Concept(
                text=normalized_text,
                normalized=self._normalize_phrase(
                    normalized_text
                ),
                head=head,
                modifier="",
                object_term=object_term,
                terms=self._content_terms(
                    normalized_text
                ),
                is_partitive=True,
            )

        # ------------------------------------------------------------
        # Generic content phrase.
        # ------------------------------------------------------------

        words = [
            word
            for word in cleaned.split()
            if word.lower()
            not in self._STOPWORDS
        ]

        if not words:
            return None

        phrase = " ".join(
            words[:8]
        )

        return _Concept(
            text=phrase,
            normalized=self._normalize_phrase(
                phrase
            ),
            head=words[-1],
            modifier=" ".join(
                words[:-1]
            ),
            object_term="",
            terms=self._content_terms(
                phrase
            ),
            is_partitive=False,
        )

    def _make_concept(
        self,
        text: str,
        is_partitive: bool,
    ) -> Optional[_Concept]:

        normalized = self._normalize_phrase(
            text
        )

        terms = self._content_terms(
            text
        )

        if not normalized or not terms:
            return None

        words = normalized.split()

        return _Concept(
            text=text,
            normalized=normalized,
            head=words[-1],
            modifier=" ".join(
                words[:-1]
            ),
            object_term="",
            terms=terms,
            is_partitive=is_partitive,
        )

    def _clean_concept_candidate(
        self,
        candidate: str,
    ) -> str:

        candidate = re.sub(
            r"^(?:the|a|an)\s+",
            "",
            candidate,
            flags=re.IGNORECASE,
        )

        candidate = re.sub(
            r"\s+",
            " ",
            candidate,
        )

        return candidate.strip(
            " .,:;!?"
        )

    def _strip_prefix(
        self,
        text: str,
    ) -> str:

        result = text.strip()

        patterns = (
            r"^(?:now\s+)?let'?s\s+"
            r"(?:discuss|look\s+at|talk\s+about|consider)\s+",

            r"^(?:now\s+)?we\s+"
            r"(?:will|are\s+going\s+to)\s+"
            r"(?:discuss|look\s+at|consider)\s+",

            r"^(?:moving\s+on\s+to|turning\s+to)\s+",

            r"^(?:next|finally)\s+",

            r"^(?:let'?s\s+)?move\s+to\s+",
        )

        for pattern in patterns:

            result = re.sub(
                pattern,
                "",
                result,
                flags=re.IGNORECASE,
            )

        return result.strip()

    # ================================================================
    # STRUCTURAL CLASSIFICATION
    # ================================================================

    def _classify_boundary(
        self,
        concept: Optional[_Concept],
        embedding: torch.Tensor,
        active: TopicNode,
        active_similarity: float,
    ) -> StructuralDecision:

        # ------------------------------------------------------------
        # 1. Same concept.
        # ------------------------------------------------------------

        if self._is_same_concept(
            concept,
            active,
        ):
            return StructuralDecision.CONTINUE_CURRENT

        # ------------------------------------------------------------
        # 2. Explicit X-of-Y scope.
        # ------------------------------------------------------------

        if (
            concept is not None
            and concept.is_partitive
            and self._scope_matches_active(
                concept,
                active,
            )
        ):
            return StructuralDecision.CREATE_SUBTOPIC

        # ------------------------------------------------------------
        # 3. Active child - EXPLICIT BOUNDARY ALWAYS CREATES NEW NODE
        #
        # When active is a child and we have an explicit boundary,
        # this is a sibling. The parent relationship should be
        # determined by checking against the parent.
        # ------------------------------------------------------------

        if active.parent_id is not None:

            parent = self._nodes[
                active.parent_id
            ]

            parent_similarity = self._similarity(
                embedding,
                parent.centroid_embedding,
            )

            # Check if this concept relates to the parent
            # If it does, create as sibling (subtopic of parent)
            if parent_similarity >= 0.35:
                return StructuralDecision.CREATE_SUBTOPIC

            # Even if similarity to parent is low, check if we should
            # create a new major topic or still keep as subtopic
            # Check against the grandparent if it exists
            if parent.parent_id is not None:
                grandparent = self._nodes[
                    parent.parent_id
                ]
                
                grandparent_similarity = self._similarity(
                    embedding,
                    grandparent.centroid_embedding,
                )
                
                if grandparent_similarity >= 0.40:
                    # This belongs to the grandparent level
                    return StructuralDecision.CREATE_SUBTOPIC

            # If no strong relationship with parent, but we have
            # explicit boundary, create as new major topic
            return StructuralDecision.NEW_MAJOR_TOPIC

        # ------------------------------------------------------------
        # 4. Root + explicit boundary.
        # ------------------------------------------------------------

        if active.parent_id is None:

            if concept is not None:

                if (
                    concept.is_partitive
                    and self._scope_matches_active(
                        concept,
                        active,
                    )
                ):
                    return StructuralDecision.CREATE_SUBTOPIC

                if self._head_relation(
                    concept,
                    active,
                ):
                    return StructuralDecision.CREATE_SUBTOPIC

        # ------------------------------------------------------------
        # 5. Related content.
        # ------------------------------------------------------------

        if (
            active_similarity
            >= self.subtopic_threshold
        ):
            return StructuralDecision.RELATED_CONTENT

        # ------------------------------------------------------------
        # 6. New major topic.
        # ------------------------------------------------------------

        if active_similarity < 0.50:
            return StructuralDecision.NEW_MAJOR_TOPIC

        return StructuralDecision.UNCERTAIN

    def _get_boundary_parent(
        self,
        concept: Optional[_Concept],
        active: TopicNode,
        embedding: torch.Tensor,
    ) -> Optional[int]:

        # ------------------------------------------------------------
        # Explicit X-of-Y always belongs under the active concept
        # when its object matches the active node.
        # ------------------------------------------------------------

        if (
            concept is not None
            and concept.is_partitive
            and self._scope_matches_active(
                concept,
                active,
            )
        ):
            return active.node_id

        # ------------------------------------------------------------
        # If active is a child, a new explicit-boundary concept is
        # normally a sibling, so attach it to the active node's parent.
        # ------------------------------------------------------------

        if active.parent_id is not None:
            # Check if we should attach to parent or grandparent
            parent = self._nodes[active.parent_id]
            
            parent_similarity = self._similarity(
                embedding,
                parent.centroid_embedding,
            )
            
            # If strong relationship with parent, attach there
            if parent_similarity >= 0.35:
                return active.parent_id
            
            # Check grandparent if parent has one
            if parent.parent_id is not None:
                grandparent = self._nodes[parent.parent_id]
                
                grandparent_similarity = self._similarity(
                    embedding,
                    grandparent.centroid_embedding,
                )
                
                if grandparent_similarity >= 0.40:
                    return parent.parent_id
            
            # Default to parent
            return active.parent_id

        # ------------------------------------------------------------
        # Otherwise the active root is the natural parent only when
        # generic concept evidence supports the relationship.
        # ------------------------------------------------------------

        if (
            concept is not None
            and self._head_relation(
                concept,
                active,
            )
        ):
            return active.node_id

        return active.parent_id

    # ================================================================
    # HISTORICAL RETURN
    # ================================================================

    def _find_return_target(
        self,
        embedding: torch.Tensor,
        concept: Optional[_Concept],
    ) -> Optional[TopicNode]:

        best_node: Optional[TopicNode] = None
        best_similarity = -1.0

        for node in self._topic_history:

            if concept is not None:

                if self._is_same_concept(
                    concept,
                    node,
                ):
                    return node

            similarity = self._similarity(
                embedding,
                node.centroid_embedding,
            )

            if similarity > best_similarity:

                best_similarity = similarity
                best_node = node

        if (
            best_node is not None
            and best_similarity >= 0.62
        ):
            return best_node

        return None

    # ================================================================
    # CONCEPT RELATIONSHIPS
    # ================================================================

    def _is_same_concept(
        self,
        concept: Optional[_Concept],
        node: TopicNode,
    ) -> bool:

        if concept is None:
            return False

        a = concept.normalized

        b = self._normalize_phrase(
            node.name
        )

        if not a or not b:
            return False

        if a == b:
            return True

        aliases = {
            self._normalize_phrase(alias)
            for alias in node.aliases
        }

        if a in aliases:
            return True

        a_terms = set(
            concept.terms
        )

        b_terms = set(
            node.concept_terms
        )

        if not a_terms or not b_terms:
            return False

        overlap = (
            a_terms & b_terms
        )

        if not overlap:
            return False

        smaller = min(
            len(a_terms),
            len(b_terms),
        )

        if smaller <= 1:
            return a_terms == b_terms

        return (
            len(overlap)
            / float(smaller)
        ) >= 0.85

    def _scope_matches_active(
        self,
        concept: _Concept,
        active: TopicNode,
    ) -> bool:

        if not concept.is_partitive:
            return False

        object_terms = set(
            self._content_terms(
                concept.object_term
            )
        )

        active_terms = set(
            self._content_terms(
                active.name
            )
        )

        if not object_terms or not active_terms:
            return False

        overlap = (
            object_terms & active_terms
        )

        if not overlap:
            return False

        ratio = (
            len(overlap)
            / float(
                min(
                    len(object_terms),
                    len(active_terms),
                )
            )
        )

        return ratio >= 0.50

    def _head_relation(
        self,
        concept: _Concept,
        active: TopicNode,
    ) -> bool:

        if self._is_same_concept(
            concept,
            active,
        ):
            return False

        concept_terms = set(
            concept.terms
        )

        active_terms = set(
            active.concept_terms
        )

        if not concept_terms or not active_terms:
            return False

        overlap = (
            concept_terms & active_terms
        )

        return len(overlap) >= 1

    # ================================================================
    # GRAPH MUTATION
    # ================================================================

    def _create_node(
        self,
        name: str,
        embedding: torch.Tensor,
        parent_id: Optional[int],
        concept: Optional[_Concept],
    ) -> TopicNode:

        node_id = self._next_node_id
        self._next_node_id += 1

        clean_name = self._clean_topic_name(
            name
        )

        anchor = embedding.detach().clone()
        centroid = embedding.detach().clone()

        node = TopicNode(
            node_id=node_id,
            name=clean_name,
            parent_id=parent_id,
            level=(
                self._nodes[parent_id].level + 1
                if parent_id is not None
                else 0
            ),
            anchor_embedding=anchor,
            centroid_embedding=centroid,
            concept_terms=(
                list(concept.terms)
                if concept is not None
                else self._content_terms(
                    clean_name
                )
            ),
            concept_head=(
                concept.head
                if concept is not None
                else ""
            ),
            concept_modifier=(
                concept.modifier
                if concept is not None
                else ""
            ),
            concept_object=(
                concept.object_term
                if concept is not None
                else ""
            ),
        )

        self._nodes[node_id] = node

        if parent_id is not None:

            parent = self._nodes[
                parent_id
            ]

            if node_id not in parent.children_ids:
                parent.children_ids.append(
                    node_id
                )

            parent.updated_at = datetime.now()

        return node

    def _update_node(
        self,
        node: TopicNode,
        embedding: torch.Tensor,
    ) -> None:

        previous = (
            node.centroid_embedding
            .detach()
            .clone()
        )

        incoming = (
            embedding
            .detach()
            .clone()
        )

        alpha = (
            self.centroid_update_weight
        )

        updated = (
            (1.0 - alpha)
            * previous
            + alpha
            * incoming
        )

        norm = torch.norm(
            updated
        )

        if norm > 0:
            updated = (
                updated / norm
            )

        node.centroid_embedding = (
            updated.detach().clone()
        )

        node.mention_count += 1
        node.development_score += 1.0
        node.updated_at = datetime.now()

    def _activate(
        self,
        node_id: int,
    ) -> None:

        if node_id not in self._nodes:
            return

        if node_id in self._active_stack:

            index = self._active_stack.index(
                node_id
            )

            self._active_stack = (
                self._active_stack[
                    : index + 1
                ]
            )

        else:

            self._active_stack.append(
                node_id
            )

        self._active_node_id = node_id

        node = self._nodes[
            node_id
        ]

        if all(
            existing.node_id != node_id
            for existing in self._topic_history
        ):

            self._topic_history.append(
                node
            )

    # ================================================================
    # ACCESSORS
    # ================================================================

    def get_active_node(
        self,
    ) -> Optional[TopicNode]:

        with self._lock:

            if self._active_node_id is None:
                return None

            return self._nodes.get(
                self._active_node_id
            )

    def get_active_path(
        self,
    ) -> List[TopicNode]:

        with self._lock:

            return [
                self._nodes[node_id]
                for node_id in self._active_stack
                if node_id in self._nodes
            ]

    def get_active_path_ids(
        self,
    ) -> List[int]:

        with self._lock:
            return list(
                self._active_stack
            )

    def get_topic_history(
        self,
    ) -> List[TopicNode]:

        with self._lock:
            return list(
                self._topic_history
            )

    def get_nodes(
        self,
    ) -> Dict[int, TopicNode]:

        with self._lock:
            return dict(
                self._nodes
            )

    def get_node(
        self,
        node_id: int,
    ) -> Optional[TopicNode]:

        with self._lock:
            return self._nodes.get(
                node_id
            )

    def get_current_topic(
        self,
    ) -> Optional[str]:

        node = self.get_active_node()

        if node is None:
            return None

        return node.name

    def reset(
        self,
    ) -> None:

        with self._lock:

            self._nodes.clear()
            self._next_node_id = 1
            self._active_node_id = None
            self._active_stack.clear()
            self._topic_history.clear()
            self._recent_chunks.clear()
            self._concept_history.clear()

    # ================================================================
    # EMBEDDINGS
    # ================================================================

    def _encode(
        self,
        text: str,
    ) -> torch.Tensor:

        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        return torch.tensor(
            embedding,
            dtype=torch.float32,
        )

    @staticmethod
    def _similarity(
        first: torch.Tensor,
        second: torch.Tensor,
    ) -> float:

        a = (
            first.detach()
            .cpu()
            .numpy()
            .astype(np.float32)
        )

        b = (
            second.detach()
            .cpu()
            .numpy()
            .astype(np.float32)
        )

        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)

        if (
            a_norm == 0.0
            or b_norm == 0.0
        ):
            return 0.0

        value = float(
            np.dot(a, b)
            / (a_norm * b_norm)
        )

        return max(
            -1.0,
            min(1.0, value),
        )

    def _zero_embedding(
        self,
    ) -> torch.Tensor:

        try:

            dimension = int(
                self.model.get_sentence_embedding_dimension()
            )

        except Exception:

            dimension = 384

        return torch.zeros(
            dimension,
            dtype=torch.float32,
        )

    # ================================================================
    # TEXT UTILITIES
    # ================================================================

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:

        text = str(
            text or ""
        ).strip()

        return re.sub(
            r"\s+",
            " ",
            text,
        )

    @staticmethod
    def _normalize_phrase(
        text: str,
    ) -> str:

        text = str(
            text or ""
        ).lower()

        text = re.sub(
            r"[^\w\s-]",
            " ",
            text,
        )

        return re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

    def _content_terms(
        self,
        text: str,
    ) -> List[str]:

        normalized = self._normalize_phrase(
            text
        )

        terms: List[str] = []

        for token in normalized.split():

            if token in self._STOPWORDS:
                continue

            if (
                len(token) > 4
                and token.endswith("ies")
            ):
                token = (
                    token[:-3]
                    + "y"
                )

            elif (
                len(token) > 4
                and token.endswith("s")
            ):
                token = token[:-1]

            if token:
                terms.append(
                    token
                )

        return list(
            dict.fromkeys(
                terms
            )
        )

    def _clean_topic_name(
        self,
        text: str,
    ) -> str:

        text = self._normalize_text(
            text
        )

        text = re.sub(
            r"^(?:now\s+)?let'?s\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"^(?:next|finally)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = self._clean_concept_candidate(
            text
        )

        return text.strip(
            " .,:;!?"
        )

    # ================================================================
    # MEMORY
    # ================================================================

    def _remember(
        self,
        text: str,
        concept: Optional[_Concept],
    ) -> None:

        if text:
            self._recent_chunks.append(
                text
            )

        if len(
            self._recent_chunks
        ) > 20:

            self._recent_chunks = (
                self._recent_chunks[
                    -20:
                ]
            )

        if concept is not None:

            self._concept_history.append(
                concept.normalized
            )

        if len(
            self._concept_history
        ) > 50:

            self._concept_history = (
                self._concept_history[
                    -50:
                ]
            )

    # ================================================================
    # IRRELEVANT DECISION
    # ================================================================

    def _irrelevant(
        self,
        topic: str,
        embedding: torch.Tensor,
        reason: str,
        node_id: Optional[int] = None,
    ) -> TopicDecision:

        parent_id = None

        if (
            node_id is not None
            and node_id in self._nodes
        ):

            parent_id = (
                self._nodes[
                    node_id
                ].parent_id
            )

        return TopicDecision(
            topic=topic,
            embedding=embedding,
            is_relevant=False,
            is_new_topic=False,
            similarity=0.0,
            confidence=0.90,
            reason=reason,
            structural_decision=(
                StructuralDecision.IRRELEVANT
            ),
            node_id=node_id,
            parent_node_id=parent_id,
        )