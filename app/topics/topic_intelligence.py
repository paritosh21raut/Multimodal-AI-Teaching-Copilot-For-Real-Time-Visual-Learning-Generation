from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


@dataclass
class TopicDecision:
    topic: str
    embedding: object

    is_relevant: bool
    is_new_topic: bool

    similarity: float
    confidence: float

    reason: str

    # ----------------------------------------------------------
    # Structural intelligence
    # ----------------------------------------------------------

    structural_heading: str = ""
    structural_type: str = "none"

    # True = meaningful section inside same broad topic.
    # False = continuation of existing section.
    is_subtopic: bool = False

    # True = strong enough to become a new slide.
    should_create_slide: bool = False


class TopicIntelligence:

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        new_topic_threshold: float = 0.55,
        irrelevant_threshold: float = 0.30,
    ):

        print(
            "[Topic] Loading embedding model..."
        )

        self.model = SentenceTransformer(
            model_name
        )

        self.new_topic_threshold = (
            new_topic_threshold
        )

        self.irrelevant_threshold = (
            irrelevant_threshold
        )

        print(
            "[Topic] Ready"
        )

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize(
        text: str,
    ) -> str:

        return " ".join(
            str(text or "")
            .strip()
            .split()
        )

    # ==========================================================
    # STRUCTURAL PHRASES
    # ==========================================================

    _STRUCTURAL_PATTERNS = (

        # ------------------------------------------------------
        # Definition
        # ------------------------------------------------------

        (
            "definition",
            (
                r"\bwhat\s+is\b",
                r"\bwhat\s+are\b",
                r"\bdefinition\s+of\b",
                r"\bdefined\s+as\b",
                r"\bmeans\b",
            ),
        ),

        # ------------------------------------------------------
        # Importance
        # ------------------------------------------------------

        (
            "importance",
            (
                r"\bwhy\s+is\b",
                r"\bwhy\s+are\b",
                r"\bwhy\s+is\s+it\s+important\b",
                r"\bimportance\s+of\b",
                r"\bimportant\b",
                r"\bwhy\s+.*important\b",
            ),
        ),

        # ------------------------------------------------------
        # Requirements
        # ------------------------------------------------------

        (
            "requirements",
            (
                r"\brequirements?\s+of\b",
                r"\brequirements?\s+for\b",
                r"\bneeded\s+for\b",
                r"\bthings\s+needed\b",
                r"\bconditions?\s+required\b",
            ),
        ),

        # ------------------------------------------------------
        # Working
        # ------------------------------------------------------

        (
            "working",
            (
                r"\bhow\s+does\b",
                r"\bhow\s+do\b",
                r"\bhow\s+it\s+works\b",
                r"\bhow\s+.*works\b",
                r"\bworking\s+of\b",
                r"\bworking\s+principle\b",
            ),
        ),

        # ------------------------------------------------------
        # Process
        # ------------------------------------------------------

        (
            "process",
            (
                r"\bprocess\s+of\b",
                r"\bprocess\b",
                r"\bstep\s+by\s+step\b",
                r"\bstages?\s+of\b",
                r"\bsteps?\s+in\b",
                r"\bsequence\s+of\b",
            ),
        ),

        # ------------------------------------------------------
        # Types
        # ------------------------------------------------------

        (
            "types",
            (
                r"\btypes?\s+of\b",
                r"\bkinds?\s+of\b",
                r"\bforms?\s+of\b",
                r"\bcategories?\s+of\b",
            ),
        ),

        # ------------------------------------------------------
        # Classification
        # ------------------------------------------------------

        (
            "classification",
            (
                r"\bclassification\s+of\b",
                r"\bclassified\s+by\b",
                r"\bclassification\s+based\s+on\b",
                r"\bclassified\s+based\s+on\b",
            ),
        ),

        # ------------------------------------------------------
        # Examples
        # ------------------------------------------------------

        (
            "examples",
            (
                r"\bexamples?\s+of\b",
                r"\bexamples?\s+include\b",
                r"\bsuch\s+as\b",
                r"\bfor\s+example\b",
            ),
        ),

        # ------------------------------------------------------
        # Applications / Uses
        # ------------------------------------------------------

        (
            "applications",
            (
                r"\bapplications?\s+of\b",
                r"\buses?\s+of\b",
                r"\bused\s+for\b",
                r"\bwhere\s+.*used\b",
                r"\breal[- ]world\s+applications?\b",
            ),
        ),

        # ------------------------------------------------------
        # Advantages
        # ------------------------------------------------------

        (
            "advantages",
            (
                r"\badvantages?\s+of\b",
                r"\bbenefits?\s+of\b",
                r"\badvantages?\b",
                r"\bbenefits?\b",
            ),
        ),

        # ------------------------------------------------------
        # Disadvantages
        # ------------------------------------------------------

        (
            "disadvantages",
            (
                r"\bdisadvantages?\s+of\b",
                r"\blimitations?\s+of\b",
                r"\bproblems?\s+with\b",
                r"\bchallenges?\s+of\b",
            ),
        ),

        # ------------------------------------------------------
        # Factors
        # ------------------------------------------------------

        (
            "factors",
            (
                r"\bfactors?\s+affecting\b",
                r"\bfactors?\s+that\s+affect\b",
                r"\bfactors?\s+of\b",
                r"\bthings\s+that\s+affect\b",
            ),
        ),

        # ------------------------------------------------------
        # Components / Architecture
        # ------------------------------------------------------

        (
            "architecture",
            (
                r"\barchitecture\s+of\b",
                r"\bcomponents?\s+of\b",
                r"\bparts?\s+of\b",
                r"\bstructure\s+of\b",
                r"\binternal\s+structure\b",
                r"\bmain\s+components?\b",
            ),
        ),

        # ------------------------------------------------------
        # Properties / Characteristics
        # ------------------------------------------------------

        (
            "properties",
            (
                r"\bproperties\s+of\b",
                r"\bcharacteristics?\s+of\b",
                r"\bfeatures?\s+of\b",
                r"\bkey\s+features?\b",
            ),
        ),

        # ------------------------------------------------------
        # Comparison
        # ------------------------------------------------------

        (
            "comparison",
            (
                r"\bcompare\b",
                r"\bcomparison\b",
                r"\bdifference\s+between\b",
                r"\bdifferences?\s+between\b",
                r"\bversus\b",
                r"\bvs\.?\b",
            ),
        ),

        # ------------------------------------------------------
        # Formula
        # ------------------------------------------------------

        (
            "formula",
            (
                r"\bformula\s+for\b",
                r"\bequation\s+for\b",
                r"\bcalculate\b",
                r"\bcalculation\b",
            ),
        ),
    )

    # ==========================================================
    # TRANSITION SIGNALS
    # ==========================================================

    _TRANSITION_PHRASES = (
        "now let's discuss",
        "now let us discuss",
        "now let's look at",
        "now let us look at",
        "now let's learn",
        "now let us learn",
        "now we will discuss",
        "now we'll discuss",
        "now we discuss",
        "let's discuss",
        "let us discuss",
        "let's look at",
        "let us look at",
        "let's learn about",
        "let us learn about",
        "moving on to",
        "moving on",
        "next let's discuss",
        "next let us discuss",
        "next we will discuss",
        "next we'll discuss",
        "next we discuss",
        "another topic",
        "another concept",
        "another type",
        "finally",
        "coming to",
        "let's understand",
        "let us understand",
        "now let's understand",
        "now let us understand",
    )

    # ==========================================================
    # MAJOR SLIDE SIGNALS
    # ==========================================================

    _MAJOR_SECTION_TYPES = {
        "definition",
        "working",
        "process",
        "types",
        "classification",
        "comparison",
        "architecture",
        "applications",
    }

    # ==========================================================
    # SUBTOPIC TYPES
    # ==========================================================

    _SUBTOPIC_TYPES = {
        "importance",
        "requirements",
        "examples",
        "advantages",
        "disadvantages",
        "factors",
        "properties",
        "formula",
    }

    # ==========================================================
    # TRANSITION DETECTION
    # ==========================================================

    @classmethod
    def _has_transition_signal(
        cls,
        text: str,
    ) -> bool:

        normalized = cls._normalize(
            text
        ).lower()

        return any(
            phrase in normalized
            for phrase in cls._TRANSITION_PHRASES
        )

    # ==========================================================
    # STRUCTURAL TYPE DETECTION
    # ==========================================================

    @classmethod
    def _detect_structural_type(
        cls,
        text: str,
    ) -> str:

        normalized = cls._normalize(
            text
        ).lower()

        if not normalized:
            return "none"

        # Check longer / more explicit patterns first.
        for structural_type, patterns in cls._STRUCTURAL_PATTERNS:

            for pattern in patterns:

                if re.search(
                    pattern,
                    normalized,
                    flags=re.IGNORECASE,
                ):

                    return structural_type

        return "none"

    # ==========================================================
    # STRUCTURAL HEADING CLEANUP
    # ==========================================================

    @classmethod
    def _extract_structural_heading(
        cls,
        text: str,
        structural_type: str,
    ) -> str:

        normalized = cls._normalize(
            text
        )

        if not normalized:
            return ""

        # ------------------------------------------------------
        # First sentence / clause.
        # ------------------------------------------------------

        first_clause = re.split(
            r"[.!?]",
            normalized,
            maxsplit=1,
        )[0].strip()

        # ------------------------------------------------------
        # Remove transition wording.
        # ------------------------------------------------------

        transition_patterns = (
            r"^now\s+let'?s\s+discuss\s+",
            r"^now\s+let\s+us\s+discuss\s+",
            r"^now\s+let'?s\s+look\s+at\s+",
            r"^now\s+let\s+us\s+look\s+at\s+",
            r"^now\s+let'?s\s+learn\s+about\s+",
            r"^now\s+let\s+us\s+learn\s+about\s+",
            r"^now\s+let'?s\s+understand\s+",
            r"^now\s+let\s+us\s+understand\s+",
            r"^let'?s\s+discuss\s+",
            r"^let\s+us\s+discuss\s+",
            r"^let'?s\s+look\s+at\s+",
            r"^let\s+us\s+look\s+at\s+",
            r"^let'?s\s+learn\s+about\s+",
            r"^let\s+us\s+learn\s+about\s+",
            r"^moving\s+on\s+to\s+",
            r"^moving\s+on\s+",
            r"^next\s+",
            r"^coming\s+to\s+",
        )

        for pattern in transition_patterns:

            first_clause = re.sub(
                pattern,
                "",
                first_clause,
                count=1,
                flags=re.IGNORECASE,
            ).strip()

        # ------------------------------------------------------
        # Explicit structural heading extraction.
        # ------------------------------------------------------

        heading_patterns = (
            r"^(?:what\s+is|what\s+are)\s+(.+)$",
            r"^(?:definition\s+of)\s+(.+)$",
            r"^(?:importance\s+of)\s+(.+)$",
            r"^(?:requirements?\s+(?:of|for))\s+(.+)$",
            r"^(?:working\s+of)\s+(.+)$",
            r"^(?:working\s+principle\s+of)\s+(.+)$",
            r"^(?:types?\s+of)\s+(.+)$",
            r"^(?:classification\s+of)\s+(.+)$",
            r"^(?:applications?\s+of)\s+(.+)$",
            r"^(?:uses?\s+of)\s+(.+)$",
            r"^(?:factors?\s+affecting)\s+(.+)$",
            r"^(?:properties\s+of)\s+(.+)$",
            r"^(?:characteristics?\s+of)\s+(.+)$",
            r"^(?:components?\s+of)\s+(.+)$",
            r"^(?:parts?\s+of)\s+(.+)$",
            r"^(?:structure\s+of)\s+(.+)$",
            r"^(?:comparison\s+of)\s+(.+)$",
            r"^(?:differences?\s+between)\s+(.+)$",
        )

        for pattern in heading_patterns:

            match = re.match(
                pattern,
                first_clause,
                flags=re.IGNORECASE,
            )

            if match:

                candidate = match.group(1).strip(
                    " ,:-"
                )

                if candidate:
                    return cls._title_case_heading(
                        candidate
                    )

        # ------------------------------------------------------
        # Classification / sub-classification wording.
        # ------------------------------------------------------

        classification_match = re.search(
            r"classification\s+of\s+(.+?)\s+based\s+on\s+(.+)",
            first_clause,
            flags=re.IGNORECASE,
        )

        if classification_match:

            subject = (
                classification_match
                .group(1)
                .strip()
            )

            basis = (
                classification_match
                .group(2)
                .strip()
            )

            if subject and basis:

                return (
                    cls._title_case_heading(
                        f"Classification of "
                        f"{subject} Based on "
                        f"{basis}"
                    )
                )

        # ------------------------------------------------------
        # Known generic heading fallbacks.
        # ------------------------------------------------------

        generic_headings = {
            "definition": "Definition",
            "importance": "Why It Is Important",
            "requirements": "Requirements",
            "working": "Working",
            "process": "Process",
            "types": "Types",
            "classification": "Classification",
            "examples": "Examples",
            "applications": "Applications",
            "advantages": "Advantages",
            "disadvantages": "Disadvantages",
            "factors": "Factors Affecting It",
            "architecture": "Architecture and Components",
            "properties": "Properties and Characteristics",
            "comparison": "Comparison",
            "formula": "Formula",
        }

        return generic_headings.get(
            structural_type,
            "",
        )

    # ==========================================================
    # TOPIC TITLE CLEANUP
    # ==========================================================

    @classmethod
    def _clean_topic_text(
        cls,
        text: str,
    ) -> str:

        normalized = cls._normalize(
            text
        )

        if not normalized:
            return ""

        # ------------------------------------------------------
        # Remove lecture-opening phrases.
        # ------------------------------------------------------

        opening_patterns = (
            r"^today\s+we\s+are\s+going\s+to\s+learn\s+about\s+",
            r"^today\s+we\s+will\s+learn\s+about\s+",
            r"^today\s+we'?ll\s+learn\s+about\s+",
            r"^we\s+are\s+going\s+to\s+learn\s+about\s+",
            r"^we\s+will\s+learn\s+about\s+",
            r"^we'?ll\s+learn\s+about\s+",
            r"^let'?s\s+learn\s+about\s+",
            r"^let\s+us\s+learn\s+about\s+",
            r"^now\s+let'?s\s+learn\s+about\s+",
            r"^now\s+let\s+us\s+learn\s+about\s+",
        )

        cleaned = normalized

        for pattern in opening_patterns:

            cleaned = re.sub(
                pattern,
                "",
                cleaned,
                count=1,
                flags=re.IGNORECASE,
            )

        # ------------------------------------------------------
        # Remove transition phrases.
        # ------------------------------------------------------

        transition_patterns = (
            r"^now\s+let'?s\s+discuss\s+",
            r"^now\s+let\s+us\s+discuss\s+",
            r"^now\s+let'?s\s+look\s+at\s+",
            r"^now\s+let\s+us\s+look\s+at\s+",
            r"^now\s+let'?s\s+understand\s+",
            r"^now\s+let\s+us\s+understand\s+",
            r"^let'?s\s+discuss\s+",
            r"^let\s+us\s+discuss\s+",
            r"^let'?s\s+look\s+at\s+",
            r"^let\s+us\s+look\s+at\s+",
            r"^moving\s+on\s+to\s+",
            r"^moving\s+on\s+",
            r"^next\s+",
            r"^coming\s+to\s+",
        )

        for pattern in transition_patterns:

            cleaned = re.sub(
                pattern,
                "",
                cleaned,
                count=1,
                flags=re.IGNORECASE,
            )

        # ------------------------------------------------------
        # Find obvious "X is..." / "X are..." topic starts.
        # ------------------------------------------------------

        definition_match = re.match(
            r"^(.{2,80}?)\s+is\s+(?:a|an|the)\s+",
            cleaned,
            flags=re.IGNORECASE,
        )

        if definition_match:

            candidate = (
                definition_match
                .group(1)
                .strip()
            )

            if candidate:

                # Reject generic junk.
                if len(candidate.split()) <= 8:

                    cleaned = candidate

        # ------------------------------------------------------
        # First sentence only.
        # ------------------------------------------------------

        cleaned = re.split(
            r"[.!?]",
            cleaned,
            maxsplit=1,
        )[0]

        # ------------------------------------------------------
        # Cut common explanation tails.
        # ------------------------------------------------------

        cleaned = re.split(
            r"\b(?:which|that|because|since|where|while|so\s+that)\b",
            cleaned,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        cleaned = cleaned.strip(
            " ,:-"
        )

        # ------------------------------------------------------
        # Reject obviously useless topic strings.
        # ------------------------------------------------------

        words = cleaned.split()

        banned_starts = {
            "today",
            "we",
            "now",
            "let's",
            "let",
            "the",
            "this",
            "it",
            "and",
            "but",
            "because",
            "then",
        }

        if (
            words
            and words[0].lower()
            in banned_starts
        ):

            if len(words) > 1:

                cleaned = " ".join(
                    words[1:]
                )

        # ------------------------------------------------------
        # Keep topic reasonably short.
        # ------------------------------------------------------

        words = cleaned.split()

        if len(words) > 8:

            cleaned = " ".join(
                words[:8]
            )

        if not cleaned:
            return ""

        return cls._title_case_heading(
            cleaned
        )

    # ==========================================================
    # TITLE CASE
    # ==========================================================

    @staticmethod
    def _title_case_heading(
        text: str,
    ) -> str:

        text = " ".join(
            str(text or "")
            .split()
        ).strip()

        if not text:
            return ""

        # Preserve common technical acronyms.
        acronyms = {
            "cpu",
            "gpu",
            "ram",
            "rom",
            "adc",
            "dac",
            "io",
            "i/o",
            "api",
            "fpga",
            "5g",
            "ai",
            "ml",
        }

        words = []

        for word in text.split():

            clean = word.strip(
                " ,.:;()[]{}"
            )

            if clean.lower() in acronyms:

                words.append(
                    clean.upper()
                )

            else:

                words.append(
                    clean.capitalize()
                )

        return " ".join(
            word
            for word in words
            if word
        )

    # ==========================================================
    # TOPIC NAME
    # ==========================================================

    def _extract_topic_name(
        self,
        text: str,
        fallback: Optional[str] = None,
    ) -> str:

        topic = self._clean_topic_text(
            text
        )

        if topic:
            return topic

        if fallback:
            return fallback

        # Last-resort short title.
        normalized = self._normalize(
            text
        )

        words = normalized.split()

        return self._title_case_heading(
            " ".join(
                words[:6]
            )
        )

    # ==========================================================
    # STRUCTURAL ANALYSIS
    # ==========================================================

    def analyze_structure(
        self,
        text: str,
    ) -> tuple[str, str, bool, bool]:

        normalized = self._normalize(
            text
        )

        if not normalized:

            return (
                "",
                "none",
                False,
                False,
            )

        structural_type = (
            self._detect_structural_type(
                normalized
            )
        )

        if structural_type == "none":

            return (
                "",
                "none",
                False,
                False,
            )

        heading = (
            self._extract_structural_heading(
                normalized,
                structural_type,
            )
        )

        is_subtopic = (
            structural_type
            in self._SUBTOPIC_TYPES
        )

        should_create_slide = (
            structural_type
            in self._MAJOR_SECTION_TYPES
        )

        # ------------------------------------------------------
        # A strong transition + structural section
        # is meaningful even when embeddings are similar.
        # ------------------------------------------------------

        if self._has_transition_signal(
            normalized
        ):

            if structural_type in {
                "working",
                "process",
                "types",
                "classification",
                "comparison",
                "architecture",
                "applications",
            }:

                should_create_slide = True

            else:

                is_subtopic = True

        return (
            heading,
            structural_type,
            is_subtopic,
            should_create_slide,
        )

    # ==========================================================
    # PROCESS
    # ==========================================================

    def process(
        self,
        latest_text: str,
        rolling_context: str,
        current_topic: Optional[str],
        current_embedding,
    ) -> TopicDecision:

        print(
            "[Topic] process() called"
        )

        text = self._normalize(
            latest_text
        )

        if not text:

            return TopicDecision(
                topic=current_topic or "",
                embedding=current_embedding,
                is_relevant=False,
                is_new_topic=False,
                similarity=1.0,
                confidence=0.0,
                reason="empty_text",
            )

        print(
            "[Topic] Encoding transcript..."
        )

        embedding = self.model.encode(
            text,
            convert_to_tensor=True,
        )

        print(
            "[Topic] Transcript encoded"
        )

        (
            structural_heading,
            structural_type,
            is_subtopic,
            structural_slide,
        ) = self.analyze_structure(
            text
        )

        transition_signal = (
            self._has_transition_signal(
                text
            )
        )

        # ==========================================================
        # FIRST TOPIC
        # ==========================================================

        if current_embedding is None:

            topic = (
                self._extract_topic_name(
                    text
                )
            )

            # A lecture-opening sentence should
            # establish the broad topic, not become
            # "Today We".
            if (
                topic.lower()
                in {
                    "today",
                    "today we",
                    "we",
                }
            ):

                words = text.split()

                if words:

                    topic = (
                        self._title_case_heading(
                            words[-1]
                            if len(words) == 1
                            else words[0]
                        )
                    )

            return TopicDecision(
                topic=topic,
                embedding=embedding,
                is_relevant=True,
                is_new_topic=True,
                similarity=1.0,
                confidence=1.0,
                reason="initial_topic",
                structural_heading=(
                    structural_heading
                ),
                structural_type=(
                    structural_type
                ),
                is_subtopic=False,
                should_create_slide=True,
            )

        # ==========================================================
        # SIMILARITY
        # ==========================================================

        similarity = float(
            cos_sim(
                current_embedding,
                embedding,
            ).item()
        )

        # ==========================================================
        # STRUCTURAL SUBTOPIC
        # ==========================================================

        # ------------------------------------------------------
        # A structural heading can be a subtopic even when the
        # embedding similarity is high.
        # ------------------------------------------------------

        if (
            structural_type != "none"
            and not structural_slide
            and similarity >= self.irrelevant_threshold
        ):

            print(
                f"[Topic] Similarity = "
                f"{similarity:.3f} | SUBTOPIC"
            )

            return TopicDecision(
                topic=(
                    current_topic
                    or self._extract_topic_name(
                        text
                    )
                ),
                embedding=embedding,
                is_relevant=True,
                is_new_topic=False,
                similarity=similarity,
                confidence=similarity,
                reason="structural_subtopic",
                structural_heading=(
                    structural_heading
                ),
                structural_type=(
                    structural_type
                ),
                is_subtopic=True,
                should_create_slide=False,
            )

        # ==========================================================
        # STRUCTURAL MAJOR SECTION
        # ==========================================================

        if (
            structural_slide
            and (
                transition_signal
                or structural_type
                in {
                    "working",
                    "process",
                    "types",
                    "classification",
                    "comparison",
                    "architecture",
                    "applications",
                }
            )
            and similarity >= self.irrelevant_threshold
        ):

            print(
                f"[Topic] Similarity = "
                f"{similarity:.3f} | STRUCTURAL SECTION"
            )

            section_topic = (
                structural_heading
                or self._extract_topic_name(
                    text
                )
            )

            return TopicDecision(
                topic=(
                    current_topic
                    or section_topic
                ),
                embedding=embedding,
                is_relevant=True,
                is_new_topic=False,
                similarity=similarity,
                confidence=max(
                    similarity,
                    0.75,
                ),
                reason="major_structural_section",
                structural_heading=(
                    structural_heading
                ),
                structural_type=(
                    structural_type
                ),
                is_subtopic=False,
                should_create_slide=True,
            )

        # ==========================================================
        # EXPLICIT NEW TOPIC
        # ==========================================================

        if transition_signal and similarity < 0.55:

            topic = self._extract_topic_name(
                structural_heading
                or text
            )

            print(
                f"[Topic] Similarity = "
                f"{similarity:.3f} | NEW TOPIC"
            )

            return TopicDecision(
                topic=topic,
                embedding=embedding,
                is_relevant=True,
                is_new_topic=True,
                similarity=similarity,
                confidence=max(
                    0.0,
                    min(
                        1.0,
                        1.0 - similarity,
                    ),
                ),
                reason="explicit_topic_transition",
                structural_heading=(
                    structural_heading
                ),
                structural_type=(
                    structural_type
                ),
                is_subtopic=False,
                should_create_slide=True,
            )

        # ==========================================================
        # SAME TOPIC
        # ==========================================================

        if (
            similarity
            >= self.new_topic_threshold
        ):

            print(
                f"[Topic] Similarity = "
                f"{similarity:.3f} | CONTINUE"
            )

            return TopicDecision(
                topic=current_topic or text,
                embedding=embedding,
                is_relevant=True,
                is_new_topic=False,
                similarity=similarity,
                confidence=similarity,
                reason="relevant_continuation",
                structural_heading=(
                    structural_heading
                ),
                structural_type=(
                    structural_type
                ),
                is_subtopic=(
                    is_subtopic
                ),
                should_create_slide=(
                    structural_slide
                ),
            )

        # ==========================================================
        # RELATED CONTENT
        # ==========================================================

        if (
            similarity
            >= self.irrelevant_threshold
        ):

            print(
                f"[Topic] Similarity = "
                f"{similarity:.3f} | RELATED"
            )

            return TopicDecision(
                topic=current_topic or text,
                embedding=embedding,
                is_relevant=True,
                is_new_topic=False,
                similarity=similarity,
                confidence=similarity,
                reason="related_content",
                structural_heading=(
                    structural_heading
                ),
                structural_type=(
                    structural_type
                ),
                is_subtopic=(
                    is_subtopic
                ),
                should_create_slide=(
                    structural_slide
                ),
            )

        # ==========================================================
        # IRRELEVANT
        # ==========================================================

        print(
            f"[Topic] Similarity = "
            f"{similarity:.3f} | IRRELEVANT"
        )

        return TopicDecision(
            topic=current_topic or text,
            embedding=current_embedding,
            is_relevant=False,
            is_new_topic=False,
            similarity=similarity,
            confidence=max(
                0.0,
                1.0 - similarity,
            ),
            reason="irrelevant_speech",
            structural_heading="",
            structural_type="none",
            is_subtopic=False,
            should_create_slide=False,
        )


topic_intelligence = TopicIntelligence()