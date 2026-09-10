"""
Topic Intelligence - LECTURE STRUCTURE HARDENED

Changes:
- Clean topic labels (remove signposting completely)
- Extract core noun phrases for topic names
- Preserve partitive "X of Y" structure (including internal articles)
- Strip leading articles from topic names
- Improved concept extraction
- Stable topic identity
"""

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
        r"^okay$",
        r"^ok$",
        r"^right$",
        r"^so$",
        r"^um$",
        r"^uh$",
        r"^let's see$",
    )

    _STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "of", "to", "in", "on",
        "for", "with", "from", "by", "is", "are", "was", "were", "be",
        "been", "being", "this", "that", "these", "those", "we", "you",
        "they", "it", "as", "at", "into", "about", "now", "then", "also",
        "very", "just", "can", "will", "would", "could", "should",
        "have", "has", "had", "do", "does", "did", "used", "using",
        "use", "lets", "let", "there", "their", "its", "which", "who",
        "what", "how", "today",
    }

    _LEADING_ARTICLES = ("the ", "a ", "an ")

    _SIGNPOST_PATTERNS = (
        r"^(?:now\s+)?(?:let'?s|we\s+will|we'll)\s+"
        r"(?:discuss|look\s+at|talk\s+about|consider|examine|explore)\s+",

        r"^(?:today\s+)?(?:we\s+are|we're|we\s+will|we'll)\s+"
        r"(?:going\s+to\s+)?(?:learning|learn|studying|study|covering|cover|"
        r"discussing|discuss|examining|examine|exploring|explore|"
        r"talking\s+about)\s+"
        r"(?:about\s+|on\s+|the\s+topic\s+of\s+)?",

        r"^(?:moving\s+on\s+to|turning\s+to|next\s+up|finally)\s+",

        r"^(?:in\s+this\s+(?:lecture|lesson|section|module))\s+"
        r"(?:we\s+will\s+|we'll\s+)?(?:discuss|cover|learn|study)\s+",
    )

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        new_topic_threshold: float = 0.55,
        irrelevant_threshold: float = 0.25,
        subtopic_threshold: float = 0.35,
        centroid_update_weight: float = 0.15,
    ) -> None:
        self._lock = RLock()
        self.model = SentenceTransformer(model_name)
        self.new_topic_threshold = float(new_topic_threshold)
        self.irrelevant_threshold = float(irrelevant_threshold)
        self.subtopic_threshold = float(subtopic_threshold)
        self.centroid_update_weight = float(centroid_update_weight)

        self._nodes: Dict[int, TopicNode] = {}
        self._next_node_id = 1
        self._active_node_id: Optional[int] = None
        self._active_stack: List[int] = []
        self._topic_history: List[TopicNode] = []
        self._recent_chunks: List[str] = []
        self._concept_history: List[str] = []
        self._compiled_signposts = [re.compile(p, re.IGNORECASE) for p in self._SIGNPOST_PATTERNS]

    def process(
        self,
        latest_text: str,
        rolling_context: str = "",
        current_topic: Optional[str] = None,
        current_embedding: Optional[torch.Tensor] = None,
    ) -> TopicDecision:
        with self._lock:
            text = self._normalize_text(latest_text)
            if not text:
                return self._irrelevant("", self._zero_embedding(), "empty transcript")

            discourse = self._detect_discourse(text)
            embedding = self._encode(text)

            if discourse.classroom_chatter:
                return self._irrelevant(text, embedding, "classroom chatter")

            concept = self._extract_concept(text)

            if not self._active_stack:
                topic_name = self._clean_topic_name(concept.text if concept else text)
                node = self._create_node(name=topic_name, embedding=embedding, parent_id=None, concept=concept)
                self._activate(node.node_id)
                self._remember(text, concept)
                return TopicDecision(
                    topic=node.name, embedding=embedding, is_relevant=True,
                    is_new_topic=True, similarity=1.0, confidence=1.0,
                    reason="initial lecture concept",
                    structural_decision=StructuralDecision.INITIAL_TOPIC,
                    node_id=node.node_id, parent_node_id=None,
                    transition_signal=discourse.explicit_boundary,
                    evidence={"concept": concept},
                )

            active = self._nodes[self._active_stack[-1]]
            active_similarity = self._similarity(embedding, active.centroid_embedding)

            if discourse.explicit_return:
                historical = self._find_return_target(embedding, concept)
                if historical is not None:
                    self._activate(historical.node_id)
                    self._update_node(historical, embedding)
                    self._remember(text, concept)
                    return TopicDecision(
                        topic=historical.name, embedding=embedding, is_relevant=True,
                        is_new_topic=False, similarity=self._similarity(embedding, historical.centroid_embedding),
                        confidence=0.92, reason="returned to previously discussed concept",
                        structural_decision=StructuralDecision.RETURN_TO_PREVIOUS,
                        node_id=historical.node_id, parent_node_id=historical.parent_id,
                        transition_signal=True, evidence={"concept": concept, "return_target": historical.node_id},
                    )

            if discourse.explicit_boundary:
                relation = self._classify_boundary(concept=concept, embedding=embedding, active=active, active_similarity=active_similarity)

                if relation == StructuralDecision.CONTINUE_CURRENT:
                    self._update_node(active, embedding)
                    self._remember(text, concept)
                    return TopicDecision(
                        topic=active.name, embedding=embedding, is_relevant=True,
                        is_new_topic=False, similarity=active_similarity, confidence=0.90,
                        reason="explicit transition refers to current concept",
                        structural_decision=StructuralDecision.CONTINUE_CURRENT,
                        node_id=active.node_id, parent_node_id=active.parent_id,
                        transition_signal=True, evidence={"concept": concept},
                    )

                if relation == StructuralDecision.CREATE_SUBTOPIC:
                    parent_id = self._get_boundary_parent(concept=concept, active=active, embedding=embedding)
                    node = self._create_node(
                        name=self._clean_topic_name(concept.text if concept else text),
                        embedding=embedding, parent_id=parent_id, concept=concept,
                    )
                    self._activate(node.node_id)
                    self._remember(text, concept)
                    return TopicDecision(
                        topic=node.name, embedding=embedding, is_relevant=True,
                        is_new_topic=True, similarity=active_similarity, confidence=0.90,
                        reason="explicit boundary introduces a new structural concept",
                        structural_decision=StructuralDecision.CREATE_SUBTOPIC,
                        node_id=node.node_id, parent_node_id=parent_id,
                        transition_signal=True, evidence={"concept": concept, "parent_node_id": parent_id},
                    )

                if relation == StructuralDecision.NEW_MAJOR_TOPIC:
                    clean_concept_text = concept.text if concept else text
                    node = self._create_node(
                        name=self._clean_topic_name(clean_concept_text),
                        embedding=embedding, parent_id=None, concept=concept,
                    )
                    self._activate(node.node_id)
                    self._remember(text, concept)
                    return TopicDecision(
                        topic=node.name, embedding=embedding, is_relevant=True,
                        is_new_topic=True, similarity=active_similarity, confidence=0.88,
                        reason="explicit boundary introduces a new major concept",
                        structural_decision=StructuralDecision.NEW_MAJOR_TOPIC,
                        node_id=node.node_id, parent_node_id=None,
                        transition_signal=True, evidence={"concept": concept},
                    )

                if relation == StructuralDecision.RELATED_CONTENT:
                    self._update_node(active, embedding)
                    self._remember(text, concept)
                    return TopicDecision(
                        topic=active.name, embedding=embedding, is_relevant=True,
                        is_new_topic=False, similarity=active_similarity, confidence=0.70,
                        reason="boundary but related to current topic",
                        structural_decision=StructuralDecision.RELATED_CONTENT,
                        node_id=active.node_id, parent_node_id=active.parent_id,
                        transition_signal=True, evidence={"concept": concept},
                    )

            if self._is_same_concept(concept, active):
                self._update_node(active, embedding)
                self._remember(text, concept)
                return TopicDecision(
                    topic=active.name, embedding=embedding, is_relevant=True,
                    is_new_topic=False, similarity=active_similarity, confidence=0.95,
                    reason="same concept continues",
                    structural_decision=StructuralDecision.CONTINUE_CURRENT,
                    node_id=active.node_id, parent_node_id=active.parent_id,
                )

            if active_similarity >= 0.45:
                self._update_node(active, embedding)
                self._remember(text, concept)
                return TopicDecision(
                    topic=active.name, embedding=embedding, is_relevant=True,
                    is_new_topic=False, similarity=active_similarity, confidence=0.82,
                    reason="semantic continuity without structural boundary",
                    structural_decision=StructuralDecision.CONTINUE_CURRENT,
                    node_id=active.node_id, parent_node_id=active.parent_id,
                )

            lecture_signal = self._has_lecture_signal(text, discourse)
            self._remember(text, concept)

            if active_similarity < self.irrelevant_threshold:
                if not lecture_signal:
                    return self._irrelevant(text, embedding, "low similarity and no lecture signal", active.node_id)

            return TopicDecision(
                topic=active.name, embedding=embedding, is_relevant=True,
                is_new_topic=False, similarity=active_similarity, confidence=0.55,
                reason="related content without enough structural evidence",
                structural_decision=StructuralDecision.RELATED_CONTENT,
                node_id=active.node_id, parent_node_id=active.parent_id,
            )

    # ============================================================
    # CLEAN TOPIC NAME - strips leading articles, preserves partitives
    # ============================================================

    def _clean_topic_name(self, text: str) -> str:
        """Clean topic name by removing signposting and extracting core phrase.

        - Strips leading articles ("the ", "a ", "an ").
        - Preserves "X of Y" partitive structure with internal articles intact.
        """
        cleaned = self._normalize_text(text)

        for pattern in self._compiled_signposts:
            cleaned = pattern.sub("", cleaned)

        cleaned = re.sub(
            r"^(?:now|today|so|okay|right|um|uh|hello|hi|hey)\s+",
            "", cleaned, flags=re.IGNORECASE,
        )
        cleaned = cleaned.strip(" .,;:!?")
        cleaned = self._normalize_text(cleaned)

        if not cleaned:
            return ""

        # Partitive "X of Y": strip leading article from head, keep internal articles
        partitive_match = re.match(
            r"^(?P<head>.+?)\s+of\s+(?P<object>.+)$",
            cleaned, flags=re.IGNORECASE,
        )
        if partitive_match:
            head = self._strip_leading_article(
                partitive_match.group("head").strip(" .,;:!?")
            )
            obj = partitive_match.group("object").strip(" .,;:!?")
            if head and obj:
                return f"{head} of {obj}".strip(" .,;:!?")
            return cleaned.strip(" .,;:!?")

        # Non-partitive: strip leading article, then extract content words
        stripped = self._strip_leading_article(cleaned)
        words = [w for w in stripped.split() if w.lower() not in self._STOPWORDS]
        if not words:
            return stripped

        core = " ".join(words[:5])
        while core and core.split()[-1].lower() in self._STOPWORDS:
            core = " ".join(core.split()[:-1])

        return core.strip(" .,;:!?") if core else stripped

    @staticmethod
    def _strip_leading_article(phrase: str) -> str:
        lowered = phrase.lower()
        for art in ("the ", "a ", "an "):
            if lowered.startswith(art):
                return phrase[len(art):].strip()
        return phrase

    # ============================================================
    # CONCEPT EXTRACTION - preserves partitive with articles
    # ============================================================

    def _extract_concept(self, text: str) -> Optional[_Concept]:
        cleaned = self._strip_prefix(text)
        if not cleaned:
            return None

        for pattern in self._compiled_signposts:
            cleaned = pattern.sub("", cleaned)
        cleaned = self._normalize_text(cleaned).strip(" .,;:!?")

        if not cleaned:
            return None

        partitive_match = re.match(
            r"^(?P<head>.+?)\s+of\s+(?P<object>.+)$",
            cleaned, flags=re.IGNORECASE,
        )
        if partitive_match:
            head_raw = self._strip_leading_article(
                partitive_match.group("head").strip(" .,;:!?")
            )
            obj_raw = partitive_match.group("object").strip(" .,;:!?")
            head_clean = self._normalize_phrase(
                re.sub(r"\b(the|a|an)\s+", "", head_raw, flags=re.IGNORECASE)
            )
            obj_clean = self._normalize_phrase(
                re.sub(r"\b(the|a|an)\s+", "", obj_raw, flags=re.IGNORECASE)
            )
            text_form = f"{head_raw} of {obj_raw}"
            normalized = f"{head_clean} of {obj_clean}"
            return _Concept(
                text=text_form,
                normalized=self._normalize_phrase(normalized),
                head=head_clean,
                modifier="",
                object_term=obj_clean,
                terms=self._content_terms(normalized),
                is_partitive=True,
            )

        words = [w for w in cleaned.split() if w.lower() not in self._STOPWORDS]
        if not words:
            return None

        phrase = " ".join(words[:8])
        return _Concept(
            text=phrase, normalized=self._normalize_phrase(phrase),
            head=words[-1], modifier=" ".join(words[:-1]), object_term="",
            terms=self._content_terms(phrase), is_partitive=False,
        )

    # ============================================================
    # REST OF METHODS
    # ============================================================

    def _detect_discourse(self, text: str) -> _Discourse:
        return _Discourse(
            explicit_boundary=self._matches(text, self._BOUNDARY_PATTERNS),
            explicit_return=self._matches(text, self._RETURN_PATTERNS),
            summary_signal=self._matches(text, self._SUMMARY_PATTERNS),
            development_signal=self._matches(text, self._DEVELOPMENT_PATTERNS),
            classroom_chatter=self._is_classroom_chatter(text),
        )

    def _is_classroom_chatter(self, text: str) -> bool:
        if not self._matches(text, self._CHATTER_PATTERNS):
            return False
        return len(text.split()) <= 5

    def _has_lecture_signal(self, text: str, discourse: _Discourse) -> bool:
        if discourse.development_signal or discourse.summary_signal:
            return True
        if len(text.split()) < 5:
            return False
        return self._matches(text, self._DEVELOPMENT_PATTERNS)

    @staticmethod
    def _matches(text: str, patterns) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _classify_boundary(self, concept, embedding, active, active_similarity):
        if self._is_same_concept(concept, active):
            return StructuralDecision.CONTINUE_CURRENT
        if concept and concept.is_partitive and self._scope_matches_active(concept, active):
            return StructuralDecision.CREATE_SUBTOPIC
        if active.parent_id is not None:
            parent = self._nodes.get(active.parent_id)
            if parent:
                parent_sim = self._similarity(embedding, parent.centroid_embedding)
                if parent_sim >= 0.30:
                    return StructuralDecision.CREATE_SUBTOPIC
                return StructuralDecision.NEW_MAJOR_TOPIC
        if active.parent_id is None:
            if concept and self._head_relation(concept, active):
                return StructuralDecision.CREATE_SUBTOPIC
        if active_similarity < 0.40:
            return StructuralDecision.NEW_MAJOR_TOPIC
        if active_similarity >= 0.25:
            return StructuralDecision.RELATED_CONTENT
        return StructuralDecision.UNCERTAIN

    def _get_boundary_parent(self, concept, active, embedding):
        if concept and concept.is_partitive and self._scope_matches_active(concept, active):
            return active.node_id
        if active.parent_id is not None:
            return active.parent_id
        if concept and self._head_relation(concept, active):
            return active.node_id
        return active.parent_id

    def _find_return_target(self, embedding, concept):
        best_node = None
        best_sim = -1.0
        for node in self._topic_history:
            if concept and self._is_same_concept(concept, node):
                return node
            sim = self._similarity(embedding, node.centroid_embedding)
            if sim > best_sim:
                best_sim = sim
                best_node = node
        return best_node if best_node and best_sim >= 0.62 else None

    def _is_same_concept(self, concept, node):
        if concept is None:
            return False
        a = concept.normalized
        b = self._normalize_phrase(node.name)
        if not a or not b:
            return False
        if a == b:
            return True
        aliases = {self._normalize_phrase(x) for x in node.aliases}
        if a in aliases:
            return True
        a_terms = set(concept.terms)
        b_terms = set(node.concept_terms)
        if not a_terms or not b_terms:
            return False
        overlap = a_terms & b_terms
        if not overlap:
            return False
        smaller = min(len(a_terms), len(b_terms))
        return len(overlap) / smaller >= 0.85 if smaller > 1 else a_terms == b_terms

    def _scope_matches_active(self, concept, active):
        if not concept.is_partitive:
            return False
        obj_terms = set(self._content_terms(concept.object_term))
        active_terms = set(self._content_terms(active.name))
        if not obj_terms or not active_terms:
            return False
        overlap = obj_terms & active_terms
        if not overlap:
            return False
        return len(overlap) / min(len(obj_terms), len(active_terms)) >= 0.50

    def _head_relation(self, concept, active):
        if self._is_same_concept(concept, active):
            return False
        c_terms = set(concept.terms)
        a_terms = set(active.concept_terms)
        return bool(c_terms & a_terms) if c_terms and a_terms else False

    def _create_node(self, name, embedding, parent_id, concept):
        node_id = self._next_node_id
        self._next_node_id += 1
        clean_name = self._clean_topic_name(name)
        anchor = embedding.detach().clone()
        centroid = embedding.detach().clone()
        node = TopicNode(
            node_id=node_id, name=clean_name, parent_id=parent_id,
            level=(self._nodes[parent_id].level + 1 if parent_id is not None else 0),
            anchor_embedding=anchor, centroid_embedding=centroid,
            concept_terms=list(concept.terms) if concept else self._content_terms(clean_name),
            concept_head=concept.head if concept else "",
            concept_modifier=concept.modifier if concept else "",
            concept_object=concept.object_term if concept else "",
        )
        self._nodes[node_id] = node
        if parent_id is not None:
            parent = self._nodes.get(parent_id)
            if parent and node_id not in parent.children_ids:
                parent.children_ids.append(node_id)
        return node

    def _update_node(self, node, embedding):
        alpha = self.centroid_update_weight
        updated = (1.0 - alpha) * node.centroid_embedding + alpha * embedding
        norm = torch.norm(updated)
        if norm > 0:
            updated = updated / norm
        node.centroid_embedding = updated.detach().clone()
        node.mention_count += 1
        node.updated_at = datetime.now()

    def _activate(self, node_id):
        if node_id not in self._nodes:
            return
        if node_id in self._active_stack:
            idx = self._active_stack.index(node_id)
            self._active_stack = self._active_stack[:idx + 1]
        else:
            self._active_stack.append(node_id)
        self._active_node_id = node_id
        node = self._nodes[node_id]
        if all(n.node_id != node_id for n in self._topic_history):
            self._topic_history.append(node)

    def _remember(self, text, concept):
        if text:
            self._recent_chunks.append(text)
            self._recent_chunks = self._recent_chunks[-20:]
        if concept:
            self._concept_history.append(concept.normalized)
            self._concept_history = self._concept_history[-50:]

    def _irrelevant(self, topic, embedding, reason, node_id=None):
        parent_id = self._nodes[node_id].parent_id if node_id and node_id in self._nodes else None
        return TopicDecision(
            topic=topic, embedding=embedding, is_relevant=False, is_new_topic=False,
            similarity=0.0, confidence=0.90, reason=reason,
            structural_decision=StructuralDecision.IRRELEVANT,
            node_id=node_id, parent_node_id=parent_id,
        )

    def get_active_node(self):
        with self._lock:
            return self._nodes.get(self._active_node_id) if self._active_node_id else None

    def get_active_path(self):
        with self._lock:
            return [self._nodes[nid] for nid in self._active_stack if nid in self._nodes]

    def get_active_path_ids(self):
        with self._lock:
            return list(self._active_stack)

    def get_topic_history(self):
        with self._lock:
            return list(self._topic_history)

    def get_nodes(self):
        with self._lock:
            return dict(self._nodes)

    def get_node(self, node_id):
        with self._lock:
            return self._nodes.get(node_id)

    def get_current_topic(self):
        node = self.get_active_node()
        return node.name if node else None

    def reset(self):
        with self._lock:
            self._nodes.clear()
            self._next_node_id = 1
            self._active_node_id = None
            self._active_stack.clear()
            self._topic_history.clear()
            self._recent_chunks.clear()
            self._concept_history.clear()

    def _encode(self, text):
        emb = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return torch.tensor(emb, dtype=torch.float32)

    @staticmethod
    def _similarity(a, b):
        a = a.detach().cpu().numpy().astype(np.float32)
        b = b.detach().cpu().numpy().astype(np.float32)
        an, bn = np.linalg.norm(a), np.linalg.norm(b)
        if an == 0 or bn == 0:
            return 0.0
        return float(np.dot(a, b) / (an * bn))

    def _zero_embedding(self):
        try:
            dim = int(self.model.get_sentence_embedding_dimension())
        except Exception:
            dim = 384
        return torch.zeros(dim, dtype=torch.float32)

    @staticmethod
    def _normalize_text(text):
        return " ".join(str(text or "").strip().split())

    @staticmethod
    def _normalize_phrase(text):
        t = str(text or "").lower()
        t = re.sub(r"[^\w\s-]", " ", t)
        return " ".join(t.split()).strip()

    def _content_terms(self, text):
        normalized = self._normalize_phrase(text)
        terms = []
        for token in normalized.split():
            if token in self._STOPWORDS:
                continue
            if len(token) > 4 and token.endswith("ies"):
                token = token[:-3] + "y"
            elif len(token) > 4 and token.endswith("s"):
                token = token[:-1]
            if token:
                terms.append(token)
        return list(dict.fromkeys(terms))

    def _strip_prefix(self, text):
        result = text.strip()
        for pattern in self._compiled_signposts:
            result = pattern.sub("", result)
        return result.strip()