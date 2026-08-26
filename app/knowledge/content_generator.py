from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.llm.llm_orchestrator import (
    LLMOrchestrator,
)

from app.slides.slide_models import (
    BulletPoint,
    ContentType,
    DiagramAsset,
    SlideContent,
    SlideSection,
    VisualType,
)


SUBTOPIC_MARKER = "__SUBTOPIC__:"
LEAD_MARKER = "__LEAD__:"


class ContentGenerator:

    def __init__(
        self,
        llm: LLMOrchestrator | None = None,
    ) -> None:

        self.llm = llm or LLMOrchestrator()

    # ==========================================================
    # BASIC NORMALIZATION
    # ==========================================================

    @staticmethod
    def _safe_string(
        value: Any,
        default: str = "",
    ) -> str:

        if value is None:
            return default

        if isinstance(
            value,
            (dict, list),
        ):
            return default

        return str(
            value
        ).strip()

    @staticmethod
    def _normalize_text(
        value: Any,
    ) -> str:

        return " ".join(
            str(value or "")
            .strip()
            .split()
        )

    # ==========================================================
    # BULLETS
    # ==========================================================

    @staticmethod
    def _normalize_bullets(
        values: Any,
    ) -> List[BulletPoint]:

        if not isinstance(
            values,
            list,
        ):
            return []

        bullets: List[BulletPoint] = []

        for value in values[:8]:

            if isinstance(
                value,
                dict,
            ):
                text = value.get(
                    "text",
                    "",
                )
                level = int(
                    value.get(
                        "level",
                        0,
                    )
                    or 0
                )
            else:

                text = value
                level = 0

            text = str(
                text or ""
            ).strip()

            if text:

                bullets.append(
                    BulletPoint(
                        text=text,
                        level=level,
                    )
                )

        return bullets

    # ==========================================================
    # CONTENT TYPE
    # ==========================================================

    @staticmethod
    def _normalize_content_type(
        content_type: Any,
    ) -> str:

        value = (
            str(
                content_type
                or ContentType.EXPLANATION.value
            )
            .strip()
            .lower()
        )

        aliases = {

            "educational": "explanation",

            "info": "explanation",

            "information": "explanation",

            "concept": "explanation",

            "overview": "explanation",

            "definition_slide": "definition",

            "example": "examples",

            "comparison_table": "comparison",

            "table": "comparison",

            "process_flow": "process",

            "flow": "process",

            "architecture": "explanation",

            "numeric": "data",

            "numbers": "data",
        }

        value = aliases.get(
            value,
            value,
        )

        valid = {
            item.value
            for item in ContentType
        }

        return (
            value
            if value in valid
            else ContentType.EXPLANATION.value
        )

    # ==========================================================
    # VISUAL TYPE
    # ==========================================================

    @staticmethod
    def _normalize_visual_type(
        visual_type: Any,
    ) -> str:

        value = (
            str(
                visual_type
                or VisualType.NONE.value
            )
            .strip()
            .lower()
        )

        aliases = {

            "slide": "none",

            "educational": "none",

            "visual": "image",

            "photo": "image",

            "photograph": "image",

            "picture": "image",

            "flow": "flowchart",

            "process": "flowchart",

            "table": "comparison_table",

            "comparison": "comparison_table",

            "map": "concept_map",

            "concept": "concept_map",

            "examples": "example_grid",

            "grid": "example_grid",

            "architecture": "diagram",

            "components": "diagram",

            "structure": "diagram",

            "data_chart": "chart",

            "bar_chart": "chart",

            "plot": "chart",
        }

        value = aliases.get(
            value,
            value,
        )

        valid = {
            item.value
            for item in VisualType
        }

        return (
            value
            if value in valid
            else VisualType.NONE.value
        )

    # ==========================================================
    # VISUAL SPEC
    # ==========================================================

    @staticmethod
    def _normalize_visual_spec(
        spec: Any,
    ) -> Dict[str, Any]:

        if not isinstance(
            spec,
            dict,
        ):
            return {}

        return dict(spec)

    # ==========================================================
    # CONTEXT
    # ==========================================================

    @staticmethod
    def _context_lower(
        context: str,
    ) -> str:

        return " ".join(
            str(context or "")
            .lower()
            .split()
        )

    # ==========================================================
    # MAJOR SUBTOPIC DETECTION
    # ==========================================================

    @staticmethod
    def detect_major_subtopic(
        text: str,
    ) -> str:

        normalized = " ".join(
            str(text or "")
            .strip()
            .split()
        )

        lower = normalized.lower()

        patterns = (
            (
                r"\bworking\s+of\s+(?:a\s+)?microcontroller\b",
                "Working of Microcontroller",
            ),
            (
                r"\bhow\s+(?:a\s+)?microcontroller\s+works\b",
                "Working of Microcontroller",
            ),
            (
                r"\btypes?\s+of\s+microcontrollers?\b",
                "Types of Microcontrollers",
            ),
            (
                r"\bapplications?\s+of\s+microcontrollers?\b",
                "Applications of Microcontrollers",
            ),
            (
                r"\buses?\s+of\s+microcontrollers?\b",
                "Uses of Microcontrollers",
            ),
            (
                r"\badvantages?\s+(?:and|&)\s+disadvantages?\b",
                "Advantages and Disadvantages",
            ),
            (
                r"\blimitations?\s+of\s+microcontrollers?\b",
                "Limitations of Microcontrollers",
            ),
            (
                r"\bproblems?\s+(?:in|of)\s+microcontrollers?\b",
                "Problems in Microcontrollers",
            ),
            (
                r"\bissues?\s+(?:in|with)\s+microcontrollers?\b",
                "Issues in Microcontrollers",
            ),
            (
                r"\barchitecture\s+of\s+microcontrollers?\b",
                "Microcontroller Architecture",
            ),
            (
                r"\bcomponents?\s+of\s+microcontrollers?\b",
                "Components of Microcontroller",
            ),
            (
                r"\bmicrocontroller\s+vs\.?\s+microprocessor\b",
                "Microcontroller vs Microprocessor",
            ),
            (
                r"\bmicrocontroller\s+versus\s+microprocessor\b",
                "Microcontroller vs Microprocessor",
            ),
        )

        for pattern, heading in patterns:

            if re.search(
                pattern,
                normalized,
                flags=re.IGNORECASE,
            ):
                return heading

        # Useful normalized shorthand.

        if "types of microcontroller" in lower:
            return "Types of Microcontrollers"

        if "working of microcontroller" in lower:
            return "Working of Microcontroller"

        if "applications of microcontroller" in lower:
            return "Applications of Microcontrollers"

        return ""

    # ==========================================================
    # MAJOR SECTION SPLITTING
    # ==========================================================

    @classmethod
    def split_major_sections(
        cls,
        text: str,
    ) -> List[
        Tuple[str, str]
    ]:
        """
        Returns:

            [
                ("", opening_definition),
                ("Types of Microcontrollers", types_text),
                ("Applications of Microcontrollers", applications_text),
            ]

        The first entry can have an empty heading.
        """

        text = cls._normalize_text(
            text
        )

        if not text:
            return []

        markers = [
            (
                r"\bworking\s+of\s+(?:a\s+)?microcontroller\b",
                "Working of Microcontroller",
            ),
            (
                r"\bhow\s+(?:a\s+)?microcontroller\s+works\b",
                "Working of Microcontroller",
            ),
            (
                r"\btypes?\s+of\s+microcontrollers?\b",
                "Types of Microcontrollers",
            ),
            (
                r"\bapplications?\s+of\s+microcontrollers?\b",
                "Applications of Microcontrollers",
            ),
            (
                r"\buses?\s+of\s+microcontrollers?\b",
                "Uses of Microcontrollers",
            ),
            (
                r"\badvantages?\s+(?:and|&)\s+disadvantages?\b",
                "Advantages and Disadvantages",
            ),
            (
                r"\blimitations?\s+of\s+microcontrollers?\b",
                "Limitations of Microcontrollers",
            ),
            (
                r"\bproblems?\s+(?:in|of)\s+microcontrollers?\b",
                "Problems in Microcontrollers",
            ),
            (
                r"\bissues?\s+(?:in|with)\s+microcontrollers?\b",
                "Issues in Microcontrollers",
            ),
            (
                r"\barchitecture\s+of\s+microcontrollers?\b",
                "Microcontroller Architecture",
            ),
            (
                r"\bcomponents?\s+of\s+microcontrollers?\b",
                "Components of Microcontroller",
            ),
            (
                r"\bmicrocontroller\s+(?:vs\.?|versus)\s+microprocessor\b",
                "Microcontroller vs Microprocessor",
            ),
        ]

        matches = []

        for pattern, heading in markers:

            for match in re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):

                matches.append(
                    (
                        match.start(),
                        match.end(),
                        heading,
                    )
                )

        if not matches:
            return [
                (
                    "",
                    text,
                )
            ]

        matches.sort(
            key=lambda item: item[0]
        )

        # Remove overlapping markers.

        cleaned = []

        last_end = -1

        for match in matches:

            if match[0] < last_end:
                continue

            cleaned.append(
                match
            )

            last_end = match[1]

        sections: List[
            Tuple[str, str]
        ] = []

        first_start = cleaned[0][0]

        if first_start > 0:

            opening = text[
                :first_start
            ].strip()

            if opening:

                sections.append(
                    (
                        "",
                        opening,
                    )
                )

        for index, current in enumerate(
            cleaned
        ):

            start = current[0]
            end = (
                cleaned[index + 1][0]
                if index + 1 < len(cleaned)
                else len(text)
            )

            content = text[
                start:end
            ].strip()

            if content:

                sections.append(
                    (
                        current[2],
                        content,
                    )
                )

        return sections

    # ==========================================================
    # SUBTOPIC EXTRACTION
    # ==========================================================

    @staticmethod
    def _classification_heading(
        text: str,
    ) -> str:

        lower = text.lower()

        patterns = (

            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"based\s+on\s+number\s+of\s+bits",
                "Classification by Number of Bits",
            ),

            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"by\s+number\s+of\s+bits",
                "Classification by Number of Bits",
            ),

            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"based\s+on\s+memory\s+type",
                "Classification by Memory Type",
            ),

            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"by\s+memory\s+type",
                "Classification by Memory Type",
            ),

            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"based\s+on\s+instruction\s+set",
                "Classification by Instruction Set",
            ),

            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"by\s+instruction\s+set",
                "Classification by Instruction Set",
            ),

            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"based\s+on\s+memory\s+architecture",
                "Classification by Memory Architecture",
            ),

            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"by\s+memory\s+architecture",
                "Classification by Memory Architecture",
            ),
        )

        for pattern, heading in patterns:

            if re.search(
                pattern,
                lower,
            ):

                return heading

        return ""

    @classmethod
    def _extract_subtopic_sections(
        cls,
        context: str,
    ) -> List[SlideSection]:

        text = cls._normalize_text(
            context
        )

        if not text:
            return []

        classification_markers = [
            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"(?:based\s+on|by)\s+number\s+of\s+bits",
                "Classification by Number of Bits",
            ),
            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"(?:based\s+on|by)\s+memory\s+type",
                "Classification by Memory Type",
            ),
            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"(?:based\s+on|by)\s+instruction\s+set",
                "Classification by Instruction Set",
            ),
            (
                r"classification\s+of\s+microcontrollers?\s+"
                r"(?:based\s+on|by)\s+memory\s+architecture",
                "Classification by Memory Architecture",
            ),
        ]

        matches = []

        for pattern, heading in classification_markers:

            for match in re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):

                matches.append(
                    (
                        match.start(),
                        match.end(),
                        heading,
                    )
                )

        matches.sort(
            key=lambda item: item[0]
        )

        if not matches:
            return []

        sections = []

        for index, match in enumerate(
            matches
        ):

            start = match[1]

            end = (
                matches[index + 1][0]
                if index + 1 < len(matches)
                else len(text)
            )

            content = text[
                start:end
            ].strip(
                " .,:;-"
            )

            bullets = []

            # --------------------------------------------------
            # Number-bit classification
            # --------------------------------------------------

            heading = match[2]

            if heading == "Classification by Number of Bits":

                found = re.findall(
                    r"\b(?:8|16|32|64)\s*-\s*bit"
                    r"\s+microcontrollers?\b",
                    content,
                    flags=re.IGNORECASE,
                )

                if not found:

                    found = re.findall(
                        r"\b(?:8|16|32|64)\s+bit"
                        r"\s+microcontrollers?\b",
                        content,
                        flags=re.IGNORECASE,
                    )

                for item in found:

                    bullets.append(
                        BulletPoint(
                            text=(
                                " ".join(
                                    item.split()
                                )
                            )
                        )
                    )

            # --------------------------------------------------
            # Memory classification
            # --------------------------------------------------

            elif heading == "Classification by Memory Type":

                memory_patterns = (
                    (
                        r"embedded\s+memory"
                        r"(?:\s+microcontrollers?)?",
                        "Embedded memory microcontroller",
                    ),
                    (
                        r"external\s+memory"
                        r"(?:\s+microcontrollers?)?",
                        "External memory microcontroller",
                    ),
                )

                for pattern, fallback in memory_patterns:

                    if re.search(
                        pattern,
                        content,
                        flags=re.IGNORECASE,
                    ):

                        bullets.append(
                            BulletPoint(
                                text=fallback
                            )
                        )

            # --------------------------------------------------
            # Instruction set
            # --------------------------------------------------

            elif heading == "Classification by Instruction Set":

                terms = (
                    (
                        r"\bCISC\b|complex\s+instruction\s+set",
                        "Complex Instruction Set Computer (CISC)",
                    ),
                    (
                        r"\bRISC\b|reduced\s+instruction\s+set",
                        "Reduced Instruction Set Computer (RISC)",
                    ),
                )

                for pattern, label in terms:

                    if re.search(
                        pattern,
                        content,
                        flags=re.IGNORECASE,
                    ):

                        bullets.append(
                            BulletPoint(
                                text=label
                            )
                        )

            # --------------------------------------------------
            # Memory architecture
            # --------------------------------------------------

            elif heading == "Classification by Memory Architecture":

                if re.search(
                    r"\bharvard\b",
                    content,
                    flags=re.IGNORECASE,
                ):

                    bullets.append(
                        BulletPoint(
                            text="Harvard Memory Architecture"
                        )
                    )

                if re.search(
                    r"\bvon\s+neumann\b",
                    content,
                    flags=re.IGNORECASE,
                ) or re.search(
                    r"\bone\s+memory\b",
                    content,
                    flags=re.IGNORECASE,
                ):

                    bullets.append(
                        BulletPoint(
                            text="Von Neumann Memory Architecture"
                        )
                    )

            if not bullets and content:

                # Generic fallback:
                # turn comma-separated short concepts into bullets.

                parts = re.split(
                    r",|;\s*|\band\b",
                    content,
                    flags=re.IGNORECASE,
                )

                for part in parts:

                    part = part.strip(
                        " .,:;-"
                    )

                    if (
                        part
                        and len(part.split()) <= 12
                    ):

                        bullets.append(
                            BulletPoint(
                                text=part
                            )
                        )

                bullets = bullets[:6]

            if bullets:

                sections.append(
                    SlideSection(
                        heading=heading,
                        bullets=bullets,
                        level=0,
                    )
                )

        return sections

    # ==========================================================
    # FALLBACK GENERAL SUBSECTIONS
    # ==========================================================

    @staticmethod
    def _fallback_definition(
        context: str,
        topic: str,
    ) -> List[BulletPoint]:

        sentences = re.findall(
            r"[^.!?]+[.!?]+",
            context,
        )

        cleaned = [
            " ".join(
                sentence.split()
            ).strip()
            for sentence in sentences
            if sentence.strip()
        ]

        if cleaned:

            return [
                BulletPoint(
                    text=sentence
                )
                for sentence in cleaned[:5]
            ]

        return [
            BulletPoint(
                text=context[:250]
            )
        ]

    @staticmethod
    def _make_lead_bullet(
        topic: str,
        summary: str,
    ) -> BulletPoint:

        summary = " ".join(
            summary.split()
        ).strip()

        if not summary:

            summary = (
                f"{topic} is an important concept "
                "used in embedded systems."
            )

        return BulletPoint(
            text=(
                f"{LEAD_MARKER}"
                f"{topic}: {summary}"
            )
        )

    # ==========================================================
    # EXAMPLES
    # ==========================================================

    @staticmethod
    def _extract_examples(
        context: str,
    ) -> list[str]:

        text = ContentGenerator._normalize_text(
            context
        )

        patterns = [

            r"examples?\s+(?:include|are|such as)\s+"
            r"(.+?)(?:\.|$)",

            r"examples?\s+(?:of|like)\s+"
            r"(.+?)(?:\.|$)",

            r"such as\s+(.+?)(?:\.|$)",
        ]

        extracted = None

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:

                extracted = (
                    match.group(1)
                )

                break

        if not extracted:
            return []

        extracted = extracted.replace(
            " and ",
            ",",
        )

        parts = [
            item.strip(
                " .,:;()"
            )
            for item
            in extracted.split(",")
        ]

        return [
            item
            for item in parts
            if item
        ][:6]

    # ==========================================================
    # NUMERIC
    # ==========================================================

    @staticmethod
    def _extract_numeric_series(
        context: str,
    ) -> tuple[list[str], list[float]]:

        text = str(
            context or ""
        )

        labels: list[str] = []

        values: list[float] = []

        pattern = re.compile(
            r"([A-Za-z][A-Za-z0-9 _-]{0,30}?)"
            r"(?:operates at|runs at|has|is)\s*"
            r"(\d+(?:\.\d+)?)",
            flags=re.IGNORECASE,
        )

        for match in pattern.finditer(
            text
        ):

            label = match.group(1).strip(
                " ,.-:"
            )

            try:

                value = float(
                    match.group(2)
                )

            except ValueError:

                continue

            if not label:
                continue

            labels.append(
                label
            )

            values.append(
                value
            )

        if len(values) < 2:

            measurement_pattern = re.compile(
                r"(\d+(?:\.\d+)?)\s*"
                r"(mhz|ghz|khz|hz|ms|s|us|ns|%)",
                flags=re.IGNORECASE,
            )

            matches = list(
                measurement_pattern.finditer(
                    text
                )
            )

            if len(matches) >= 2:

                labels = [
                    f"Value {index + 1}"
                    for index in range(
                        len(matches)
                    )
                ]

                values = [
                    float(
                        match.group(1)
                    )
                    for match in matches
                ]

        return (
            labels[:6],
            values[:6],
        )

    @staticmethod
    def _has_numeric_data(
        context: str,
    ) -> bool:

        text = str(
            context or ""
        )

        pattern = re.compile(
            r"\b\d+(?:\.\d+)?\s*"
            r"(?:mhz|ghz|khz|hz|ms|s|us|ns|kb|mb|gb|tb|%)\b",
            flags=re.IGNORECASE,
        )

        return (
            len(
                pattern.findall(text)
            )
            >= 2
        )

    # ==========================================================
    # ARCHITECTURE
    # ==========================================================

    @staticmethod
    def _extract_architecture_components(
        context: str,
    ) -> list[str]:

        text = ContentGenerator._normalize_text(
            context
        )

        known = [
            "CPU",
            "RAM",
            "ROM",
            "Flash",
            "program memory",
            "memory",
            "input/output peripherals",
            "I/O peripherals",
            "I/O ports",
            "input/output ports",
            "timers",
            "counters",
            "communication peripherals",
            "communication interface",
            "ADC",
            "DAC",
            "sensors",
            "actuators",
        ]

        components = []

        lower_text = text.lower()

        for item in known:

            if item.lower() in lower_text:

                if item not in components:

                    components.append(
                        item
                    )

        match = re.search(
            r"(?:contains|consists of|includes)\s+"
            r"(.+?)(?:\.|$)",
            text,
            flags=re.IGNORECASE,
        )

        if match:

            raw = match.group(
                1
            )

            raw = raw.replace(
                " and ",
                ",",
            )

            for part in raw.split(
                ","
            ):

                part = re.sub(
                    r"^(a|an|the)\s+",
                    "",
                    part.strip(
                        " .,:;()"
                    ),
                    flags=re.IGNORECASE,
                )

                if (
                    part
                    and len(
                        part.split()
                    )
                    <= 5
                ):

                    components.append(
                        part
                    )

        unique = []

        for item in components:

            normalized = item.strip()

            if not normalized:
                continue

            if not any(
                normalized.lower()
                == existing.lower()
                for existing
                in unique
            ):

                unique.append(
                    normalized
                )

        return unique[:8]

    # ==========================================================
    # COMPARISON
    # ==========================================================

    @staticmethod
    def _extract_comparison_spec(
        context: str,
    ) -> Dict[str, Any]:

        text = ContentGenerator._normalize_text(
            context
        )

        if (
            "microcontroller"
            in text.lower()
            and "microprocessor"
            in text.lower()
        ):

            return {
                "columns": [
                    "Feature",
                    "Microcontroller",
                    "Microprocessor",
                ],
                "rows": [

                    {
                        "label": "Integration",
                        "values": [
                            "CPU, memory and peripherals on one chip",
                            "Mainly CPU; external components usually required",
                        ],
                    },

                    {
                        "label": "Primary use",
                        "values": [
                            "Dedicated embedded control",
                            "General-purpose computing",
                        ],
                    },

                    {
                        "label": "Power",
                        "values": [
                            "Typically lower power",
                            "Typically higher system power",
                        ],
                    },
                ],
            }

        return {}

    # ==========================================================
    # VISUAL REPAIR
    # ==========================================================

    def _repair_visual_decision(
        self,
        requested_visual: str,
        requested_spec: Dict[str, Any],
        content_type: str,
        context: str,
    ) -> tuple[
        str,
        Dict[str, Any],
        str,
    ]:

        spec = dict(
            requested_spec
        )

        context_text = self._context_lower(
            context
        )

        # ------------------------------------------------------
        # Numeric
        # ------------------------------------------------------

        if self._has_numeric_data(
            context
        ):

            labels, values = (
                self._extract_numeric_series(
                    context
                )
            )

            if (
                len(labels) >= 2
                and len(values) >= 2
            ):

                return (
                    VisualType.CHART.value,
                    {
                        "chart_type": "bar",
                        "x": labels,
                        "y": values,
                    },
                    "Actual numeric measurements detected; repaired to chart.",
                )

        # ------------------------------------------------------
        # Examples
        # ------------------------------------------------------

        examples = self._extract_examples(
            context
        )

        if (
            content_type
            == ContentType.EXAMPLES.value
            or len(examples) >= 2
        ):

            existing = spec.get(
                "examples",
                spec.get(
                    "items",
                    [],
                ),
            )

            if (
                isinstance(
                    existing,
                    list,
                )
                and len(existing) >= 2
            ):

                examples = [
                    str(item).strip()
                    for item in existing[:6]
                    if str(item).strip()
                ]

            if len(examples) >= 2:

                return (
                    VisualType.EXAMPLE_GRID.value,
                    {
                        "examples":
                            examples[:6]
                    },
                    "Multiple concrete examples detected; repaired to example grid.",
                )

        # ------------------------------------------------------
        # Comparison
        # ------------------------------------------------------

        if (
            content_type
            == ContentType.COMPARISON.value
        ):

            columns = spec.get(
                "columns",
                [],
            )

            rows = spec.get(
                "rows",
                [],
            )

            if (
                isinstance(
                    columns,
                    list,
                )
                and len(columns) >= 2
                and isinstance(
                    rows,
                    list,
                )
                and rows
            ):

                clean_rows = []

                for row in rows:

                    if not isinstance(
                        row,
                        dict,
                    ):
                        continue

                    label = str(
                        row.get(
                            "label",
                            "",
                        )
                    ).strip()

                    values = row.get(
                        "values",
                        [],
                    )

                    if (
                        label
                        and isinstance(
                            values,
                            list,
                        )
                    ):

                        clean_rows.append(
                            {
                                "label": label,
                                "values": [
                                    str(item)
                                    for item
                                    in values
                                ],
                            }
                        )

                if clean_rows:

                    return (
                        VisualType.COMPARISON_TABLE.value,
                        {
                            "columns": [
                                str(item)
                                for item in columns[:4]
                            ],
                            "rows": clean_rows[:6],
                        },
                        "Comparison specification normalized.",
                    )

            repaired = (
                self._extract_comparison_spec(
                    context
                )
            )

            if repaired:

                return (
                    VisualType.COMPARISON_TABLE.value,
                    repaired,
                    "Comparison detected from lecture text and repaired to table.",
                )

        # ------------------------------------------------------
        # Process
        # ------------------------------------------------------

        if content_type in {
            ContentType.PROCESS.value,
            ContentType.SEQUENCE.value,
        }:

            nodes = spec.get(
                "nodes",
                [],
            )

            if (
                isinstance(
                    nodes,
                    list,
                )
                and len(nodes) >= 2
            ):

                return (
                    VisualType.FLOWCHART.value,
                    {
                        "nodes": [
                            str(x)
                            for x
                            in nodes[:8]
                            if str(x).strip()
                        ],
                        "edges": spec.get(
                            "edges",
                            [],
                        ),
                    },
                    "Sequential content repaired to flowchart.",
                )

        # ------------------------------------------------------
        # Architecture
        # ------------------------------------------------------

        architecture_signal = any(
            word in context_text
            for word in (
                "architecture",
                "components",
                "contains",
                "consists of",
                "internal",
                "parts",
                "modules",
            )
        )

        components = (
            self._extract_architecture_components(
                context
            )
        )

        if (
            requested_visual
            == VisualType.DIAGRAM.value
            or architecture_signal
        ):

            center = str(
                spec.get(
                    "center",
                    "",
                )
            ).strip()

            if not center:

                if "microcontroller" in context_text:
                    center = "Microcontroller"

                elif "microprocessor" in context_text:
                    center = "Microprocessor"

                else:
                    center = "System"

            existing_components = spec.get(
                "components",
                [],
            )

            if (
                isinstance(
                    existing_components,
                    list,
                )
                and len(existing_components) >= 2
            ):

                components = [
                    str(item)
                    for item
                    in existing_components[:8]
                    if str(item).strip()
                ]

            if len(components) >= 2:

                return (
                    VisualType.DIAGRAM.value,
                    {
                        "center": center,
                        "components": components,
                        "relationships":
                            spec.get(
                                "relationships",
                                [
                                    [
                                        center,
                                        item,
                                    ]
                                    for item
                                    in components
                                ],
                            ),
                    },
                    "Component relationships detected; repaired to diagram.",
                )

        # ------------------------------------------------------
        # Existing valid visual types
        # ------------------------------------------------------

        if (
            requested_visual
            == VisualType.FLOWCHART.value
        ):

            nodes = spec.get(
                "nodes",
                [],
            )

            if (
                isinstance(
                    nodes,
                    list,
                )
                and len(nodes) >= 2
            ):

                return (
                    VisualType.FLOWCHART.value,
                    {
                        "nodes": nodes[:8],
                        "edges": spec.get(
                            "edges",
                            [],
                        ),
                    },
                    "Flowchart specification validated.",
                )

        if (
            requested_visual
            == VisualType.EXAMPLE_GRID.value
        ):

            existing = spec.get(
                "examples",
                spec.get(
                    "items",
                    [],
                ),
            )

            if isinstance(
                existing,
                list,
            ) and existing:

                return (
                    VisualType.EXAMPLE_GRID.value,
                    {
                        "examples": [
                            str(item)
                            for item
                            in existing[:6]
                            if str(item).strip()
                        ]
                    },
                    "Example grid specification validated.",
                )

        if (
            requested_visual
            == VisualType.CHART.value
        ):

            x_values = spec.get(
                "x",
                [],
            )

            y_values = spec.get(
                "y",
                [],
            )

            if (
                isinstance(
                    x_values,
                    list,
                )
                and isinstance(
                    y_values,
                    list,
                )
                and len(x_values)
                == len(y_values)
                and len(x_values) >= 2
            ):

                try:

                    values = [
                        float(v)
                        for v
                        in y_values
                    ]

                    return (
                        VisualType.CHART.value,
                        {
                            "chart_type":
                                spec.get(
                                    "chart_type",
                                    "bar",
                                ),
                            "x": [
                                str(x)
                                for x
                                in x_values
                            ],
                            "y": values,
                        },
                        "Chart specification validated.",
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    pass

        if (
            requested_visual
            == VisualType.HIERARCHY.value
        ):

            root = str(
                spec.get(
                    "root",
                    "",
                )
            ).strip()

            levels = spec.get(
                "levels",
                [],
            )

            if root and levels:

                return (
                    VisualType.HIERARCHY.value,
                    {
                        "root": root,
                        "levels": levels[:6],
                    },
                    "Hierarchy specification validated.",
                )

        if (
            requested_visual
            == VisualType.CONCEPT_MAP.value
        ):

            center = str(
                spec.get(
                    "center",
                    "",
                )
            ).strip()

            concepts = spec.get(
                "concepts",
                [],
            )

            if (
                center
                and isinstance(
                    concepts,
                    list,
                )
                and len(concepts) >= 2
            ):

                return (
                    VisualType.CONCEPT_MAP.value,
                    {
                        "center": center,
                        "concepts": concepts[:6],
                    },
                    "Concept map specification validated.",
                )

        if (
            requested_visual
            == VisualType.FORMULA.value
        ):

            formula = str(
                spec.get(
                    "formula",
                    "",
                )
            ).strip()

            if formula:

                return (
                    VisualType.FORMULA.value,
                    {
                        "formula": formula,
                    },
                    "Formula specification validated.",
                )

        if (
            requested_visual
            == VisualType.IMAGE.value
        ):

            return (
                VisualType.IMAGE.value,
                {},
                "Educational image selected.",
            )

        return (
            VisualType.NONE.value,
            {},
            "No valid structured visual specification was available.",
        )

    # ==========================================================
    # VISUAL VALIDATION
    # ==========================================================

    def _validate_visual(
        self,
        visual_type: str,
        visual_spec: Dict[str, Any],
    ) -> tuple[
        str,
        Dict[str, Any],
        str,
    ]:

        if visual_type == "none":

            return (
                "none",
                {},
                "No structured visual is required.",
            )

        if visual_type == "image":

            return (
                "image",
                {},
                "Educational image selected.",
            )

        if visual_type == "comparison_table":

            columns = visual_spec.get(
                "columns",
                [],
            )

            rows = visual_spec.get(
                "rows",
                [],
            )

            if (
                not isinstance(
                    columns,
                    list,
                )
                or len(columns) < 2
                or not isinstance(
                    rows,
                    list,
                )
                or not rows
            ):

                return (
                    "none",
                    {},
                    "Invalid comparison specification.",
                )

            return (
                "comparison_table",
                visual_spec,
                "Comparison data validated.",
            )

        if visual_type == "flowchart":

            nodes = visual_spec.get(
                "nodes",
                [],
            )

            if (
                not isinstance(
                    nodes,
                    list,
                )
                or len(nodes) < 2
            ):

                return (
                    "none",
                    {},
                    "Flowchart needs at least two nodes.",
                )

            return (
                "flowchart",
                visual_spec,
                "Ordered process validated.",
            )

        if visual_type == "diagram":

            center = str(
                visual_spec.get(
                    "center",
                    "",
                )
            ).strip()

            components = visual_spec.get(
                "components",
                [],
            )

            if (
                not center
                or not isinstance(
                    components,
                    list,
                )
                or len(components) < 2
            ):

                return (
                    "none",
                    {},
                    "Diagram requires a center and components.",
                )

            return (
                "diagram",
                visual_spec,
                "Architecture/components validated.",
            )

        if visual_type == "hierarchy":

            root = str(
                visual_spec.get(
                    "root",
                    "",
                )
            ).strip()

            levels = visual_spec.get(
                "levels",
                [],
            )

            if (
                not root
                or not isinstance(
                    levels,
                    list,
                )
                or not levels
            ):

                return (
                    "none",
                    {},
                    "Hierarchy specification invalid.",
                )

            return (
                "hierarchy",
                visual_spec,
                "Classification structure validated.",
            )

        if visual_type == "chart":

            x_values = visual_spec.get(
                "x",
                [],
            )

            y_values = visual_spec.get(
                "y",
                [],
            )

            if (
                not isinstance(
                    x_values,
                    list,
                )
                or not isinstance(
                    y_values,
                    list,
                )
                or len(x_values)
                != len(y_values)
                or not x_values
            ):

                return (
                    "none",
                    {},
                    "Chart requires matching data arrays.",
                )

            try:

                clean_y = [
                    float(value)
                    for value
                    in y_values
                ]

            except (
                TypeError,
                ValueError,
            ):

                return (
                    "none",
                    {},
                    "Chart data is not numeric.",
                )

            return (
                "chart",
                {
                    **visual_spec,
                    "x": [
                        str(x)
                        for x
                        in x_values
                    ],
                    "y": clean_y,
                },
                "Real numeric data validated.",
            )

        if visual_type == "example_grid":

            examples = visual_spec.get(
                "examples",
                visual_spec.get(
                    "items",
                    [],
                ),
            )

            if (
                not isinstance(
                    examples,
                    list,
                )
                or not examples
            ):

                return (
                    "none",
                    {},
                    "Examples were not provided.",
                )

            return (
                "example_grid",
                {
                    "examples":
                        examples[:6]
                },
                "Concrete examples validated.",
            )

        if visual_type == "timeline":

            events = visual_spec.get(
                "events",
                visual_spec.get(
                    "steps",
                    [],
                ),
            )

            if (
                not isinstance(
                    events,
                    list,
                )
                or len(events) < 2
            ):

                return (
                    "none",
                    {},
                    "Timeline requires at least two events.",
                )

            return (
                "timeline",
                {
                    "events":
                        events[:6]
                },
                "Chronological events validated.",
            )

        if visual_type == "formula":

            formula = str(
                visual_spec.get(
                    "formula",
                    "",
                )
            ).strip()

            if not formula:

                return (
                    "none",
                    {},
                    "Formula was empty.",
                )

            return (
                "formula",
                {
                    "formula":
                        formula
                },
                "Formula validated.",
            )

        if visual_type == "concept_map":

            center = str(
                visual_spec.get(
                    "center",
                    "",
                )
            ).strip()

            concepts = visual_spec.get(
                "concepts",
                [],
            )

            if (
                not center
                or not isinstance(
                    concepts,
                    list,
                )
                or len(concepts) < 2
            ):

                return (
                    "none",
                    {},
                    "Concept map is invalid.",
                )

            return (
                "concept_map",
                {
                    "center":
                        center,
                    "concepts":
                        concepts[:6],
                },
                "Concept relationships validated.",
            )

        return (
            "none",
            {},
            "Unsupported visual type.",
        )

    # ==========================================================
    # STRUCTURED CONTENT
    # ==========================================================

    def _build_structured_content(
        self,
        topic: str,
        context: str,
        result: Dict[str, Any],
        content_type: str,
    ) -> tuple[
        List[BulletPoint],
        List[SlideSection],
    ]:

        bullets = self._normalize_bullets(
            result.get(
                "bullets",
                [],
            )
        )

        sections: List[
            SlideSection
        ] = []

        # ------------------------------------------------------
        # Classification sections have deterministic structure.
        # ------------------------------------------------------

        classification_sections = (
            self._extract_subtopic_sections(
                context
            )
        )

        if classification_sections:

            sections.extend(
                classification_sections
            )

            flattened = []

            for section in sections:

                flattened.append(
                    BulletPoint(
                        text=(
                            f"{SUBTOPIC_MARKER}"
                            f"{section.heading}"
                        ),
                        level=0,
                    )
                )

                for item in section.bullets:

                    flattened.append(
                        BulletPoint(
                            text=item.text,
                            level=1,
                        )
                    )

            return (
                flattened[:14],
                sections,
            )

        # ------------------------------------------------------
        # Definition
        # ------------------------------------------------------

        if (
            content_type
            == ContentType.DEFINITION.value
        ):

            summary = self._safe_string(
                result.get(
                    "summary",
                    "",
                )
            )

            if summary:

                structured = [
                    self._make_lead_bullet(
                        topic,
                        summary,
                    )
                ]

                for bullet in bullets:

                    if (
                        bullet.text
                        and bullet.text.lower()
                        not in summary.lower()
                    ):

                        structured.append(
                            bullet
                        )

                return (
                    structured[:6],
                    [],
                )

            if not bullets:

                bullets = (
                    self._fallback_definition(
                        context,
                        topic,
                    )
                )

            if bullets:

                first = bullets[0]

                first.text = (
                    f"{LEAD_MARKER}"
                    f"{topic}: "
                    f"{first.text}"
                )

            return (
                bullets[:6],
                [],
            )

        # ------------------------------------------------------
        # LLM can provide sections in future.
        # ------------------------------------------------------

        raw_sections = result.get(
            "sections",
            [],
        )

        if isinstance(
            raw_sections,
            list,
        ):

            for raw in raw_sections:

                if not isinstance(
                    raw,
                    dict,
                ):
                    continue

                heading = self._safe_string(
                    raw.get(
                        "heading",
                        "",
                    )
                )

                raw_bullets = (
                    self._normalize_bullets(
                        raw.get(
                            "bullets",
                            [],
                        )
                    )
                )

                if heading and raw_bullets:

                    sections.append(
                        SlideSection(
                            heading=heading,
                            bullets=raw_bullets,
                        )
                    )

        if sections:

            flattened = []

            for section in sections:

                flattened.append(
                    BulletPoint(
                        text=(
                            f"{SUBTOPIC_MARKER}"
                            f"{section.heading}"
                        ),
                        level=section.level,
                    )
                )

                for item in section.bullets:

                    flattened.append(
                        BulletPoint(
                            text=item.text,
                            level=item.level + 1,
                        )
                    )

            return (
                flattened[:14],
                sections,
            )

        return (
            bullets[:8],
            [],
        )

    # ==========================================================
    # MAIN GENERATION
    # ==========================================================

    def generate(
        self,
        topic: str,
        context: str,
    ) -> SlideContent:

        context = self._normalize_text(
            context
        )

        result = self.llm.generate_slide(
            topic=topic,
            context=context,
        )

        if not isinstance(
            result,
            dict,
        ):
            result = {}

        title = self._safe_string(
            result.get(
                "title",
                topic,
            ),
            default=topic,
        )

        content_type = (
            self._normalize_content_type(
                result.get(
                    "content_type",
                    ContentType.EXPLANATION.value,
                )
            )
        )

        requested_visual = (
            self._normalize_visual_type(
                result.get(
                    "visual_type",
                    VisualType.NONE.value,
                )
            )
        )

        requested_spec = (
            self._normalize_visual_spec(
                result.get(
                    "visual_spec",
                    {},
                )
            )
        )

        bullets, sections = (
            self._build_structured_content(
                topic=topic,
                context=context,
                result=result,
                content_type=content_type,
            )
        )

        (
            repaired_visual,
            repaired_spec,
            repair_reason,
        ) = self._repair_visual_decision(
            requested_visual=requested_visual,
            requested_spec=requested_spec,
            content_type=content_type,
            context=context,
        )

        (
            visual_type,
            visual_spec,
            validation_reason,
        ) = self._validate_visual(
            repaired_visual,
            repaired_spec,
        )

        llm_reason = self._safe_string(
            result.get(
                "visual_reason",
                "",
            )
        )

        reasons = []

        if llm_reason:
            reasons.append(
                llm_reason
            )

        if repair_reason:
            reasons.append(
                repair_reason
            )

        if validation_reason:
            reasons.append(
                validation_reason
            )

        visual_reason = " ".join(
            reasons
        ).strip()

        image_query = self._safe_string(
            result.get(
                "image_query",
                "",
            )
        )

        if visual_type != "image":

            image_query = None

        diagram = None

        if visual_type in {
            "diagram",
            "flowchart",
            "hierarchy",
            "concept_map",
        }:

            diagram = DiagramAsset(
                title=title,
                description=self._safe_string(
                    result.get(
                        "diagram",
                        "",
                    )
                ),
                diagram_type=visual_type,
                data=visual_spec,
            )

        print(
            "=" * 60
        )

        print(
            "[ContentGenerator]"
        )

        print(
            "Provider      :",
            self.llm.last_provider,
        )

        print(
            "Content Type  :",
            content_type,
        )

        print(
            "Requested     :",
            requested_visual,
        )

        print(
            "Final Visual  :",
            visual_type,
        )

        print(
            "Visual Reason :",
            visual_reason,
        )

        print(
            "Visual Spec   :",
            visual_spec,
        )

        print(
            "Structured Sections:",
            [
                section.heading
                for section
                in sections
            ],
        )

        self.llm.print_status()

        print(
            "=" * 60
        )

        return SlideContent(
            title=title,
            bullets=bullets,
            sections=sections,
            summary=result.get(
                "summary"
            ),
            image_query=image_query,
            keywords=(
                result.get(
                    "keywords",
                    [],
                )
                if isinstance(
                    result.get(
                        "keywords",
                        [],
                    ),
                    list,
                )
                else []
            ),
            diagram=diagram,
            content_type=content_type,
            visual_type=visual_type,
            visual_reason=visual_reason,
            visual_spec=visual_spec,
            metadata={
                "content_type":
                    content_type,
                "requested_visual_type":
                    requested_visual,
                "visual_type":
                    visual_type,
                "visual_validation":
                    validation_reason,
                "llm_provider":
                    self.llm.last_provider,
                "structured_sections": [
                    section.heading
                    for section
                    in sections
                ],
            },
        )


content_generator = ContentGenerator()