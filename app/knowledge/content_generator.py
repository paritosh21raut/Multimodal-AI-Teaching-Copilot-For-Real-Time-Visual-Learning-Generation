from __future__ import annotations

import re
from typing import Any, Dict, List

from app.llm.llm_orchestrator import LLMOrchestrator

from app.slides.slide_models import (
    BulletPoint,
    ContentType,
    DiagramAsset,
    SlideContent,
    VisualType,
)


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

        if isinstance(value, (dict, list)):
            return default

        return str(value).strip()

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

        if not isinstance(values, list):
            return []

        bullets: List[BulletPoint] = []

        for value in values[:6]:

            if isinstance(value, dict):
                text = value.get("text", "")
            else:
                text = value

            text = str(
                text or ""
            ).strip()

            if text:
                bullets.append(
                    BulletPoint(text=text)
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

        if not isinstance(spec, dict):
            return {}

        return dict(spec)

    # ==========================================================
    # CONTEXT HELPERS
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
    # EXAMPLE EXTRACTION
    # ==========================================================

    @staticmethod
    def _extract_examples(
        context: str,
    ) -> list[str]:

        text = ContentGenerator._normalize_text(
            context
        )

        patterns = [
            r"examples?\s+(?:include|are|such as)\s+(.+?)(?:\.|$)",
            r"examples?\s+(?:of|like)\s+(.+?)(?:\.|$)",
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
                extracted = match.group(1)
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
            for item in extracted.split(",")
        ]

        return [
            item
            for item in parts
            if item
        ][:6]

    # ==========================================================
    # NUMERIC EXTRACTION
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

        # Example:
        # Controller A operates at 16 MHz
        # Controller B operates at 32 MHz
        pattern = re.compile(
            r"([A-Za-z][A-Za-z0-9 _-]{0,30}?)"
            r"(?:operates at|runs at|has|is)\s*"
            r"(\d+(?:\.\d+)?)",
            flags=re.IGNORECASE,
        )

        for match in pattern.finditer(text):

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

            labels.append(label)
            values.append(value)

        # Fallback for:
        # 16 MHz, 32 MHz, 80 MHz
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

    # ==========================================================
    # NUMERIC DETECTION
    # ==========================================================

    @staticmethod
    def _has_numeric_data(
        context: str,
    ) -> bool:

        text = str(
            context or ""
        )

        patterns = (
            r"\b\d+(?:\.\d+)?\s*(?:mhz|ghz|khz|hz)\b",
            r"\b\d+(?:\.\d+)?\s*%",
            r"\b\d+(?:\.\d+)?\s*(?:ms|s|us|ns)\b",
            r"\b\d+(?:\.\d+)?\s*(?:kb|mb|gb|tb)\b",
        )

        count = 0

        for pattern in patterns:

            count += len(
                re.findall(
                    pattern,
                    text,
                    flags=re.IGNORECASE,
                )
            )

        return count >= 2

    # ==========================================================
    # ARCHITECTURE EXTRACTION
    # ==========================================================

    @staticmethod
    def _extract_architecture_components(
        context: str,
    ) -> list[str]:

        text = ContentGenerator._normalize_text(
            context
        )

        components: list[str] = []

        # ------------------------------------------------------
        # Explicit known technical components
        # ------------------------------------------------------

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

        lower_text = text.lower()

        for item in known:

            if item.lower() in lower_text:

                if item not in components:
                    components.append(item)

        # ------------------------------------------------------
        # Detect list after "contains"
        # ------------------------------------------------------

        match = re.search(
            r"(?:contains|consists of|includes)\s+(.+?)(?:\.|$)",
            text,
            flags=re.IGNORECASE,
        )

        if match:

            raw = match.group(1)

            raw = raw.replace(
                " and ",
                ",",
            )

            parts = [
                re.sub(
                    r"^(a|an|the)\s+",
                    "",
                    item.strip(" .,:;()"),
                    flags=re.IGNORECASE,
                )
                for item in raw.split(",")
            ]

            for part in parts:

                if (
                    part
                    and len(part.split()) <= 5
                ):
                    components.append(
                        part
                    )

        # Deduplicate while preserving order.
        unique = []

        for item in components:

            normalized = item.strip()

            if not normalized:
                continue

            duplicate = any(
                normalized.lower()
                == existing.lower()
                for existing in unique
            )

            if not duplicate:
                unique.append(
                    normalized
                )

        return unique[:8]

    # ==========================================================
    # COMPARISON EXTRACTION
    # ==========================================================

    @staticmethod
    def _extract_comparison_spec(
        context: str,
    ) -> Dict[str, Any]:

        text = ContentGenerator._normalize_text(
            context
        )

        # Basic microcontroller/microprocessor
        # repair for our lecture domain.
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
                        "label": "Main Integration",
                        "values": [
                            "CPU + memory + peripherals",
                            "Primarily CPU",
                        ],
                    },
                    {
                        "label": "Memory",
                        "values": [
                            "Integrated",
                            "Usually external",
                        ],
                    },
                    {
                        "label": "Peripherals",
                        "values": [
                            "Integrated",
                            "Usually external",
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
    ) -> tuple[str, Dict[str, Any], str]:

        spec = dict(
            requested_spec
        )

        context_text = self._context_lower(
            context
        )

        # ------------------------------------------------------
        # Recover type accidentally placed inside spec.
        # ------------------------------------------------------

        embedded_type = spec.get(
            "type",
            "",
        )

        if (
            requested_visual == "none"
            and embedded_type
        ):

            recovered = (
                self._normalize_visual_type(
                    embedded_type
                )
            )

            if recovered != "none":
                requested_visual = recovered

        # ------------------------------------------------------
        # NUMERIC DATA
        # Highest-priority deterministic repair.
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
        # EXAMPLES
        # ------------------------------------------------------

        examples = self._extract_examples(
            context
        )

        if (
            content_type
            == ContentType.EXAMPLES.value
            or len(examples) >= 2
        ):

            existing_examples = spec.get(
                "examples",
                spec.get(
                    "items",
                    [],
                ),
            )

            if (
                isinstance(
                    existing_examples,
                    list,
                )
                and len(existing_examples) >= 2
            ):

                examples = [
                    str(item).strip()
                    for item in existing_examples[:6]
                    if str(item).strip()
                ]

            if len(examples) >= 2:

                return (
                    VisualType.EXAMPLE_GRID.value,
                    {
                        "examples": examples[:6],
                    },
                    "Multiple concrete examples detected; repaired to example grid.",
                )

        # ------------------------------------------------------
        # COMPARISON
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

            normalized_rows = []

            if isinstance(
                rows,
                list,
            ):

                for row in rows:

                    if isinstance(
                        row,
                        dict,
                    ):

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

                            normalized_rows.append(
                                {
                                    "label": label,
                                    "values": [
                                        str(v)
                                        for v in values
                                    ],
                                }
                            )

                    elif isinstance(
                        row,
                        list,
                    ) and len(row) >= 2:

                        normalized_rows.append(
                            {
                                "label": str(
                                    row[0]
                                ),
                                "values": [
                                    str(v)
                                    for v in row[1:]
                                ],
                            }
                        )

            if (
                isinstance(
                    columns,
                    list,
                )
                and len(columns) >= 2
                and normalized_rows
            ):

                return (
                    VisualType.COMPARISON_TABLE.value,
                    {
                        "columns": [
                            str(c)
                            for c in columns[:4]
                        ],
                        "rows": normalized_rows[:6],
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
        # PROCESS / SEQUENCE
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
                            for x in nodes[:6]
                            if str(x).strip()
                        ],
                        "edges": spec.get(
                            "edges",
                            [],
                        ),
                    },
                    "Sequential content repaired to flowchart.",
                )

            # Deterministic sensor-pipeline repair.
            if (
                "sensor" in context_text
                and "adc" in context_text
                and "cpu" in context_text
                and "actuator" in context_text
            ):

                return (
                    VisualType.FLOWCHART.value,
                    {
                        "nodes": [
                            "Sensor",
                            "ADC",
                            "CPU",
                            "Actuator",
                        ],
                        "edges": [
                            [
                                "Sensor",
                                "ADC",
                            ],
                            [
                                "ADC",
                                "CPU",
                            ],
                            [
                                "CPU",
                                "Actuator",
                            ],
                        ],
                    },
                    "Sensor → ADC → CPU → actuator sequence detected.",
                )

        # ------------------------------------------------------
        # ARCHITECTURE / COMPONENTS
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
                    for item in existing_components[:8]
                    if str(item).strip()
                ]

            if len(components) >= 2:

                return (
                    VisualType.DIAGRAM.value,
                    {
                        "center": center,
                        "components": components,
                        "relationships": spec.get(
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
        # VALID FLOWCHART SPEC
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
                        "nodes": [
                            str(x)
                            for x in nodes[:6]
                        ],
                        "edges": spec.get(
                            "edges",
                            [],
                        ),
                    },
                    "Flowchart specification validated.",
                )

        # ------------------------------------------------------
        # VALID EXAMPLE GRID
        # ------------------------------------------------------

        if (
            requested_visual
            == VisualType.EXAMPLE_GRID.value
        ):

            existing_examples = spec.get(
                "examples",
                spec.get(
                    "items",
                    [],
                ),
            )

            if (
                isinstance(
                    existing_examples,
                    list,
                )
                and len(existing_examples) >= 1
            ):

                return (
                    VisualType.EXAMPLE_GRID.value,
                    {
                        "examples": [
                            str(x)
                            for x in existing_examples[:6]
                            if str(x).strip()
                        ]
                    },
                    "Example grid specification validated.",
                )

        # ------------------------------------------------------
        # VALID CHART
        # ------------------------------------------------------

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

                    clean_y = [
                        float(v)
                        for v in y_values
                    ]

                    return (
                        VisualType.CHART.value,
                        {
                            "chart_type": spec.get(
                                "chart_type",
                                "bar",
                            ),
                            "x": [
                                str(x)
                                for x in x_values
                            ],
                            "y": clean_y,
                        },
                        "Chart specification validated.",
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    pass

        # ------------------------------------------------------
        # VALID HIERARCHY
        # ------------------------------------------------------

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

            if (
                root
                and isinstance(
                    levels,
                    list,
                )
                and levels
            ):

                return (
                    VisualType.HIERARCHY.value,
                    {
                        "root": root,
                        "levels": levels[:6],
                    },
                    "Hierarchy specification validated.",
                )

        # ------------------------------------------------------
        # VALID FORMULA
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # VALID CONCEPT MAP
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # IMAGE
        # ------------------------------------------------------

        if (
            requested_visual
            == VisualType.IMAGE.value
        ):

            return (
                VisualType.IMAGE.value,
                {},
                "Educational image selected.",
            )

        # ------------------------------------------------------
        # NONE
        # ------------------------------------------------------

        return (
            VisualType.NONE.value,
            {},
            "No valid structured visual specification was available.",
        )

    # ==========================================================
    # FINAL VALIDATION
    # ==========================================================

    def _validate_visual(
        self,
        visual_type: str,
        visual_spec: Dict[str, Any],
    ) -> tuple[str, Dict[str, Any], str]:

        if visual_type == VisualType.NONE.value:
            return (
                "none",
                {},
                "No structured visual is required.",
            )

        if visual_type == VisualType.IMAGE.value:
            return (
                "image",
                {},
                "Educational image selected.",
            )

        if visual_type == VisualType.COMPARISON_TABLE.value:

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

        if visual_type == VisualType.FLOWCHART.value:

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

        if visual_type == VisualType.DIAGRAM.value:

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

        if visual_type == VisualType.HIERARCHY.value:

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

        if visual_type == VisualType.CHART.value:

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
                or not x_values
                or len(x_values)
                != len(y_values)
            ):

                return (
                    "none",
                    {},
                    "Chart requires matching data arrays.",
                )

            try:

                clean_y = [
                    float(value)
                    for value in y_values
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
                        for x in x_values
                    ],
                    "y": clean_y,
                },
                "Real numeric data validated.",
            )

        if visual_type == VisualType.TIMELINE.value:

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
                    "events": events[:6]
                },
                "Chronological events validated.",
            )

        if visual_type == VisualType.EXAMPLE_GRID.value:

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
                    "examples": examples[:6]
                },
                "Concrete examples validated.",
            )

        if visual_type == VisualType.FORMULA.value:

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
                    "formula": formula
                },
                "Formula validated.",
            )

        if visual_type == VisualType.CONCEPT_MAP.value:

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
                    "center": center,
                    "concepts": concepts[:6],
                },
                "Concept relationships validated.",
            )

        return (
            "none",
            {},
            "Unsupported visual type.",
        )

    # ==========================================================
    # MAIN GENERATION
    # ==========================================================

    def generate(
        self,
        topic: str,
        context: str,
    ) -> SlideContent:

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

        bullets = self._normalize_bullets(
            result.get(
                "bullets",
                [],
            )
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

        repaired_visual, repaired_spec, repair_reason = (
            self._repair_visual_decision(
                requested_visual=requested_visual,
                requested_spec=requested_spec,
                content_type=content_type,
                context=context,
            )
        )

        visual_type, visual_spec, validation_reason = (
            self._validate_visual(
                repaired_visual,
                repaired_spec,
            )
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

        if (
            visual_type
            != VisualType.IMAGE.value
        ):
            image_query = None

        diagram = None

        if visual_type in {
            VisualType.DIAGRAM.value,
            VisualType.FLOWCHART.value,
            VisualType.HIERARCHY.value,
            VisualType.CONCEPT_MAP.value,
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

        self.llm.print_status()

        print(
            "=" * 60
        )

        return SlideContent(
            title=title,
            bullets=bullets,
            summary=result.get(
                "summary"
            ),
            image_query=image_query,
            keywords=(
                result.get(
                    "keywords",
                    []
                )
                if isinstance(
                    result.get(
                        "keywords",
                        []
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
                "content_type": content_type,
                "requested_visual_type": requested_visual,
                "visual_type": visual_type,
                "visual_validation": validation_reason,
                "llm_provider": (
                    self.llm.last_provider
                ),
            },
        )


content_generator = ContentGenerator()