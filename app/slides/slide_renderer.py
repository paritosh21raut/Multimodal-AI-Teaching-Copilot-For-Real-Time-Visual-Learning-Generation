from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Optional, Tuple

from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


class SlideRenderer:
    """
    Production-oriented PPT slide renderer.

    Structured visuals use adaptive layouts so that:
    - visual content stays inside its container
    - connectors terminate at shape boundaries
    - text is never crossed by connectors
    - containers use only the space they need
    - layouts remain robust across different topics
    """

    SLIDE_WIDTH = 10.0
    SLIDE_HEIGHT = 7.5

    TITLE_FONT_SIZE = 28
    BODY_FONT_SIZE = 17

    TITLE_COLOR = RGBColor(33, 37, 41)
    BODY_COLOR = RGBColor(60, 60, 60)
    MUTED_COLOR = RGBColor(105, 105, 105)

    BORDER_COLOR = RGBColor(180, 185, 192)
    LIGHT_BORDER = RGBColor(220, 223, 227)

    WHITE = RGBColor(255, 255, 255)

    ACCENT_COLOR = RGBColor(52, 101, 164)
    ACCENT_LIGHT = RGBColor(232, 240, 249)

    VISUAL_BACKGROUND = RGBColor(
        249,
        250,
        252,
    )

    # ==========================================================
    # REGIONS
    # ==========================================================

    def _get_regions(
        self,
        visual_type: str,
    ) -> Dict[str, float]:

        structured = {
            "diagram",
            "flowchart",
            "comparison_table",
            "chart",
            "hierarchy",
            "example_grid",
            "timeline",
            "concept_map",
            "formula",
        }

        visual_type = (
            str(visual_type)
            .lower()
            .strip()
        )

        if visual_type in structured:

            return {
                "content_left": 0.60,
                "content_width": 3.85,
                "visual_left": 4.65,
                "visual_width": 4.75,
            }

        return {
            "content_left": 0.65,
            "content_width": 4.35,
            "visual_left": 5.15,
            "visual_width": 4.15,
        }

    # ==========================================================
    # TITLE SLIDE
    # ==========================================================

    def render_title_slide(
        self,
        slide,
        title: str,
        subtitle: str,
    ):

        title_box = slide.shapes.title

        if title_box is None:

            title_box = slide.shapes.add_textbox(
                Inches(1.0),
                Inches(2.1),
                Inches(8.0),
                Inches(1.0),
            )

        title_box.text = title

        paragraph = (
            title_box
            .text_frame
            .paragraphs[0]
        )

        paragraph.font.size = Pt(
            self.TITLE_FONT_SIZE
        )
        paragraph.font.bold = True
        paragraph.font.color.rgb = (
            self.TITLE_COLOR
        )
        paragraph.alignment = (
            PP_ALIGN.CENTER
        )

        subtitle_box = None

        if len(slide.placeholders) > 1:

            candidate = slide.placeholders[1]

            if hasattr(
                candidate,
                "text_frame",
            ):

                subtitle_box = candidate

        if subtitle_box is None:

            subtitle_box = slide.shapes.add_textbox(
                Inches(1.5),
                Inches(3.3),
                Inches(7.0),
                Inches(0.7),
            )

        subtitle_box.text = subtitle

        paragraph = (
            subtitle_box
            .text_frame
            .paragraphs[0]
        )

        paragraph.font.size = Pt(16)
        paragraph.font.color.rgb = (
            self.MUTED_COLOR
        )
        paragraph.alignment = (
            PP_ALIGN.CENTER
        )

    # ==========================================================
    # CONTENT SLIDE
    # ==========================================================

    def render_content_slide(
        self,
        slide,
        title: str,
        bullets,
        image_path=None,
        visual_type="none",
        visual_spec=None,
        content_type="explanation",
        visual_reason="",
    ):

        visual_spec = visual_spec or {}

        self._remove_generated_shapes(
            slide
        )

        visual_type = (
            str(visual_type)
            .lower()
            .strip()
        )

        regions = self._get_regions(
            visual_type
        )

        # ------------------------------------------------------
        # TITLE
        # ------------------------------------------------------

        title_shape = self._get_title_shape(
            slide
        )

        title_shape.left = Inches(0.55)
        title_shape.top = Inches(0.25)
        title_shape.width = Inches(9.0)
        title_shape.height = Inches(0.7)

        title_shape.text = title

        title_para = (
            title_shape
            .text_frame
            .paragraphs[0]
        )

        title_para.font.size = Pt(
            self.TITLE_FONT_SIZE
        )
        title_para.font.bold = True
        title_para.font.color.rgb = (
            self.TITLE_COLOR
        )

        # ------------------------------------------------------
        # BODY
        # ------------------------------------------------------

        body_shape = self._get_body_shape(
            slide,
            title_shape,
        )

        if body_shape is None:

            body_shape = slide.shapes.add_textbox(
                Inches(regions["content_left"]),
                Inches(1.35),
                Inches(regions["content_width"]),
                Inches(5.2),
            )

        body_shape.left = Inches(
            regions["content_left"]
        )
        body_shape.top = Inches(1.35)
        body_shape.width = Inches(
            regions["content_width"]
        )
        body_shape.height = Inches(5.2)

        body = body_shape.text_frame

        body.clear()
        body.word_wrap = True

        body.margin_left = Inches(0.02)
        body.margin_right = Inches(0.03)
        body.margin_top = Inches(0.02)
        body.margin_bottom = Inches(0.02)

        self._render_bullets(
            body,
            bullets,
        )

        print(
            "[PPT] Added",
            len(list(bullets or [])),
            "bullets",
        )

        # ------------------------------------------------------
        # VISUAL
        # ------------------------------------------------------

        if visual_type == "image":

            self._render_image(
                slide,
                image_path,
                regions,
            )

        elif visual_type == "diagram":

            self._render_diagram(
                slide,
                visual_spec,
                regions,
            )

        elif visual_type == "flowchart":

            self._render_flowchart(
                slide,
                visual_spec,
                regions,
            )

        elif visual_type == "comparison_table":

            self._render_comparison_table(
                slide,
                visual_spec,
                regions,
            )

        elif visual_type == "chart":

            self._render_chart(
                slide,
                visual_spec,
                regions,
            )

        elif visual_type == "hierarchy":

            self._render_hierarchy(
                slide,
                visual_spec,
                regions,
            )

        elif visual_type == "example_grid":

            self._render_example_grid(
                slide,
                visual_spec,
                regions,
            )

        elif visual_type == "timeline":

            self._render_timeline(
                slide,
                visual_spec,
                regions,
            )

        elif visual_type == "formula":

            self._render_formula(
                slide,
                visual_spec,
                regions,
            )

        elif visual_type == "concept_map":

            self._render_concept_map(
                slide,
                visual_spec,
                regions,
            )

    # ==========================================================
    # BULLETS
    # ==========================================================

    def _render_bullets(
        self,
        text_frame,
        bullets: Iterable[str],
    ):

        bullets = list(
            bullets or []
        )

        if not bullets:

            text_frame.paragraphs[0].text = ""

            return

        for index, bullet in enumerate(
            bullets
        ):

            paragraph = (
                text_frame.paragraphs[0]
                if index == 0
                else text_frame.add_paragraph()
            )

            paragraph.text = str(
                bullet
            )

            paragraph.level = 0

            paragraph.font.size = Pt(
                self.BODY_FONT_SIZE
            )
            paragraph.font.color.rgb = (
                self.BODY_COLOR
            )
            paragraph.space_after = Pt(
                10
            )
            paragraph.line_spacing = 1.08

    # ==========================================================
    # SHAPES
    # ==========================================================

    def _get_title_shape(
        self,
        slide,
    ):

        if slide.shapes.title is not None:

            return slide.shapes.title

        return slide.shapes.add_textbox(
            Inches(0.55),
            Inches(0.25),
            Inches(9.0),
            Inches(0.7),
        )

    def _get_body_shape(
        self,
        slide,
        title_shape,
    ):

        for shape in slide.placeholders:

            if shape == title_shape:
                continue

            if hasattr(
                shape,
                "text_frame",
            ):

                return shape

        return None

    # ==========================================================
    # REMOVE OLD VISUALS
    # ==========================================================

    def _remove_generated_shapes(
        self,
        slide,
    ):

        title_shape = slide.shapes.title

        body_shape = None

        if title_shape is not None:

            body_shape = self._get_body_shape(
                slide,
                title_shape,
            )

        keep = set()

        if title_shape is not None:
            keep.add(id(title_shape))

        if body_shape is not None:
            keep.add(id(body_shape))

        for shape in list(
            slide.shapes
        ):

            if id(shape) in keep:
                continue

            element = shape._element

            element.getparent().remove(
                element
            )

    # ==========================================================
    # VISUAL CONTAINER
    # ==========================================================

    def _add_visual_container(
        self,
        slide,
        left: float,
        top: float,
        width: float,
        height: float,
        title: Optional[str] = None,
    ):

        container = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(left),
            Inches(top),
            Inches(width),
            Inches(height),
        )

        container.fill.solid()
        container.fill.fore_color.rgb = (
            self.VISUAL_BACKGROUND
        )
        container.line.color.rgb = (
            self.LIGHT_BORDER
        )

        if title:

            title_box = slide.shapes.add_textbox(
                Inches(left + 0.18),
                Inches(top + 0.08),
                Inches(width - 0.36),
                Inches(0.34),
            )

            paragraph = (
                title_box
                .text_frame
                .paragraphs[0]
            )

            paragraph.text = title
            paragraph.alignment = (
                PP_ALIGN.CENTER
            )
            paragraph.font.size = Pt(
                13
            )
            paragraph.font.bold = True
            paragraph.font.color.rgb = (
                self.MUTED_COLOR
            )

        return container

    # ==========================================================
    # BOX
    # ==========================================================

    def _add_box(
        self,
        slide,
        text: str,
        left: float,
        top: float,
        width: float,
        height: float,
        font_size: int = 15,
        bold: bool = False,
        fill=None,
    ):

        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(left),
            Inches(top),
            Inches(width),
            Inches(height),
        )

        shape.fill.solid()
        shape.fill.fore_color.rgb = (
            fill or self.WHITE
        )
        shape.line.color.rgb = (
            self.BORDER_COLOR
        )

        frame = shape.text_frame

        frame.clear()
        frame.word_wrap = True
        frame.vertical_anchor = (
            MSO_ANCHOR.MIDDLE
        )

        frame.margin_left = Inches(0.07)
        frame.margin_right = Inches(0.07)
        frame.margin_top = Inches(0.04)
        frame.margin_bottom = Inches(0.04)

        paragraph = frame.paragraphs[0]

        paragraph.text = str(text)
        paragraph.alignment = (
            PP_ALIGN.CENTER
        )

        paragraph.font.size = Pt(
            font_size
        )
        paragraph.font.bold = bold
        paragraph.font.color.rgb = (
            self.BODY_COLOR
        )

        return shape

    # ==========================================================
    # IMAGE
    # ==========================================================

    def _render_image(
        self,
        slide,
        image_path,
        regions,
    ):

        if not image_path:
            return

        try:

            slide.shapes.add_picture(
                image_path,
                Inches(
                    regions["visual_left"]
                ),
                Inches(1.35),
                Inches(
                    regions["visual_width"]
                ),
                Inches(5.2),
            )

            print(
                "[PPT] Image inserted"
            )

        except Exception as error:

            print(
                "[PPT] Image insertion failed:",
                error,
            )

    # ==========================================================
    # CONNECTORS
    # ==========================================================

    def _add_line(
        self,
        slide,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        width: float = 1.25,
    ):

        line = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT,
            Inches(start_x),
            Inches(start_y),
            Inches(end_x),
            Inches(end_y),
        )

        line.line.color.rgb = (
            self.ACCENT_COLOR
        )
        line.line.width = Pt(
            width
        )

        return line

    @staticmethod
    def _shape_bounds(
        shape,
    ) -> Tuple[float, float, float, float]:

        return (
            shape.left / 914400,
            shape.top / 914400,
            shape.width / 914400,
            shape.height / 914400,
        )

    @staticmethod
    def _shape_center(
        shape,
    ) -> Tuple[float, float]:

        left, top, width, height = (
            SlideRenderer._shape_bounds(
                shape
            )
        )

        return (
            left + width / 2,
            top + height / 2,
        )

    def _boundary_point(
        self,
        shape,
        target_x: float,
        target_y: float,
    ) -> Tuple[float, float]:

        left, top, width, height = (
            self._shape_bounds(
                shape
            )
        )

        cx = left + width / 2
        cy = top + height / 2

        dx = target_x - cx
        dy = target_y - cy

        if (
            abs(dx) < 1e-8
            and abs(dy) < 1e-8
        ):

            return (
                cx,
                cy,
            )

        half_w = width / 2
        half_h = height / 2

        scale_x = (
            half_w / abs(dx)
            if abs(dx) > 1e-8
            else float("inf")
        )

        scale_y = (
            half_h / abs(dy)
            if abs(dy) > 1e-8
            else float("inf")
        )

        scale = min(
            scale_x,
            scale_y,
        )

        return (
            cx + dx * scale,
            cy + dy * scale,
        )

    def _connect_shapes(
        self,
        slide,
        source,
        target,
    ):

        sx, sy = self._shape_center(
            source
        )

        tx, ty = self._shape_center(
            target
        )

        start = self._boundary_point(
            source,
            tx,
            ty,
        )

        end = self._boundary_point(
            target,
            sx,
            sy,
        )

        self._add_line(
            slide,
            start[0],
            start[1],
            end[0],
            end[1],
        )

    def _connect_vertical(
        self,
        slide,
        source,
        target,
    ):

        s_left, s_top, s_width, s_height = (
            self._shape_bounds(source)
        )

        t_left, t_top, t_width, t_height = (
            self._shape_bounds(target)
        )

        source_x = s_left + s_width / 2
        target_x = t_left + t_width / 2

        source_bottom = (
            s_top + s_height
        )

        target_top = t_top

        if abs(
            source_x - target_x
        ) < 0.01:

            self._add_line(
                slide,
                source_x,
                source_bottom,
                target_x,
                target_top,
            )

            return

        middle_y = (
            source_bottom
            + (
                target_top
                - source_bottom
            ) / 2
        )

        self._add_line(
            slide,
            source_x,
            source_bottom,
            source_x,
            middle_y,
        )

        self._add_line(
            slide,
            source_x,
            middle_y,
            target_x,
            middle_y,
        )

        self._add_line(
            slide,
            target_x,
            middle_y,
            target_x,
            target_top,
        )

    # ==========================================================
    # FLOWCHART
    # ==========================================================

    def _render_flowchart(
        self,
        slide,
        spec,
        regions,
    ):

        nodes = [
            str(item)
            for item in spec.get(
                "nodes",
                [],
            )
            if str(item).strip()
        ][:6]

        if not nodes:
            return

        box_width = min(
            3.15,
            regions["visual_width"] - 0.70,
        )

        box_height = 0.68
        gap = 0.34

        required = (
            len(nodes) * box_height
            + max(
                len(nodes) - 1,
                0,
            ) * gap
            + 1.05
        )

        container_height = min(
            max(
                required,
                4.15,
            ),
            5.35,
        )

        container_top = (
            3.95
            - container_height / 2
        )

        self._add_visual_container(
            slide,
            regions["visual_left"],
            container_top,
            regions["visual_width"],
            container_height,
            "Process",
        )

        x = (
            regions["visual_left"]
            + (
                regions["visual_width"]
                - box_width
            ) / 2
        )

        nodes_height = (
            len(nodes) * box_height
            + (
                len(nodes) - 1
            ) * gap
        )

        start_y = (
            container_top
            + (
                container_height
                - nodes_height
            ) / 2
        )

        boxes = []

        for index, node in enumerate(
            nodes
        ):

            top = (
                start_y
                + index
                * (
                    box_height + gap
                )
            )

            boxes.append(
                self._add_box(
                    slide,
                    node,
                    x,
                    top,
                    box_width,
                    box_height,
                    14,
                    True,
                    self.ACCENT_LIGHT,
                )
            )

        for index in range(
            len(boxes) - 1
        ):

            self._connect_vertical(
                slide,
                boxes[index],
                boxes[index + 1],
            )

    # ==========================================================
    # ARCHITECTURE / DIAGRAM
    # ==========================================================

    def _render_diagram(
        self,
        slide,
        spec,
        regions,
    ):

        center_text = str(
            spec.get(
                "center",
                "System",
            )
        )

        components = [
            str(item)
            for item in spec.get(
                "components",
                [],
            )
            if str(item).strip()
        ][:6]

        if not components:
            return

        width = regions[
            "visual_width"
        ]

        height = (
            4.55
            if len(components) <= 4
            else 5.05
        )

        top = (
            3.95 - height / 2
        )

        left = regions[
            "visual_left"
        ]

        self._add_visual_container(
            slide,
            left,
            top,
            width,
            height,
            "Architecture",
        )

        center_width = min(
            2.15,
            width - 1.0,
        )

        center_height = 0.78

        center_left = (
            left
            + (
                width
                - center_width
            ) / 2
        )

        center_top = (
            top
            + height / 2
            - center_height / 2
        )

        center_box = self._add_box(
            slide,
            center_text,
            center_left,
            center_top,
            center_width,
            center_height,
            15,
            True,
            self.ACCENT_LIGHT,
        )

        node_width = min(
            1.68,
            (
                width - 0.80
            ) / 2,
        )

        node_height = 0.62

        top_y = (
            top + 0.82
        )

        bottom_y = (
            top
            + height
            - 0.82
            - node_height
        )

        if len(components) == 1:

            box = self._add_box(
                slide,
                components[0],
                center_left,
                top_y,
                node_width,
                node_height,
                12,
                True,
            )

            self._connect_vertical(
                slide,
                box,
                center_box,
            )

            return

        # Top row.
        top_left = (
            left + 0.20
        )

        top_right = (
            left
            + width
            - 0.20
            - node_width
        )

        top_boxes = []

        for component, node_left in zip(
            components[:2],
            [top_left, top_right],
        ):

            top_boxes.append(
                self._add_box(
                    slide,
                    component,
                    node_left,
                    top_y,
                    node_width,
                    node_height,
                    12,
                    True,
                )
            )

        for box in top_boxes:

            self._connect_vertical(
                slide,
                box,
                center_box,
            )

        # Bottom row.
        bottom_components = components[
            2:
        ]

        bottom_boxes = []

        if bottom_components:

            count = min(
                len(bottom_components),
                3,
            )

            if count == 1:

                x_positions = [
                    center_left
                ]

            else:

                spacing = (
                    (
                        width
                        - 0.40
                        - count
                        * node_width
                    )
                    / (
                        count - 1
                    )
                )

                x_positions = [
                    left
                    + 0.20
                    + index
                    * (
                        node_width
                        + spacing
                    )
                    for index in range(
                        count
                    )
                ]

            for component, node_left in zip(
                bottom_components[:count],
                x_positions,
            ):

                bottom_boxes.append(
                    self._add_box(
                        slide,
                        component,
                        node_left,
                        bottom_y,
                        node_width,
                        node_height,
                        11,
                        True,
                    )
                )

            for box in bottom_boxes:

                self._connect_vertical(
                    slide,
                    center_box,
                    box,
                )

    # ==========================================================
    # COMPARISON TABLE
    # ==========================================================

    def _render_comparison_table(
        self,
        slide,
        spec,
        regions,
    ):

        columns = [
            str(item)
            for item in spec.get(
                "columns",
                [],
            )
        ]

        rows = spec.get(
            "rows",
            [],
        )

        if len(columns) < 2:
            return

        row_count = min(
            len(rows) + 1,
            7,
        )

        col_count = min(
            len(columns),
            4,
        )

        table_height = max(
            2.8,
            row_count * 0.62,
        )

        container_height = min(
            table_height + 1.1,
            5.35,
        )

        container_top = (
            3.95
            - container_height / 2
        )

        self._add_visual_container(
            slide,
            regions["visual_left"],
            container_top,
            regions["visual_width"],
            container_height,
            "Comparison",
        )

        table_left = (
            regions["visual_left"]
            + 0.22
        )

        table_top = (
            container_top + 0.65
        )

        table_width = (
            regions["visual_width"]
            - 0.44
        )

        table_height = (
            container_height
            - 0.85
        )

        table_shape = (
            slide.shapes.add_table(
                row_count,
                col_count,
                Inches(table_left),
                Inches(table_top),
                Inches(table_width),
                Inches(table_height),
            )
        )

        table = table_shape.table

        for col, header in enumerate(
            columns[:col_count]
        ):

            cell = table.cell(
                0,
                col,
            )

            cell.text = header

            self._format_table_cell(
                cell,
                True,
            )

        for row_index, row in enumerate(
            rows[:row_count - 1],
            start=1,
        ):

            label = str(
                row.get(
                    "label",
                    "",
                )
            )

            values = row.get(
                "values",
                [],
            )

            cell = table.cell(
                row_index,
                0,
            )

            cell.text = label

            self._format_table_cell(
                cell,
                True,
            )

            for col_index in range(
                1,
                col_count,
            ):

                value_index = (
                    col_index - 1
                )

                value = ""

                if (
                    value_index
                    < len(values)
                ):

                    value = str(
                        values[
                            value_index
                        ]
                    )

                cell = table.cell(
                    row_index,
                    col_index,
                )

                cell.text = value

                self._format_table_cell(
                    cell
                )

        for col in range(
            col_count
        ):

            table.columns[
                col
            ].width = Inches(
                table_width / col_count
            )

    # ==========================================================
    # TABLE CELL
    # ==========================================================

    def _format_table_cell(
        self,
        cell,
        bold=False,
    ):

        cell.margin_left = Inches(
            0.04
        )
        cell.margin_right = Inches(
            0.04
        )
        cell.margin_top = Inches(
            0.03
        )
        cell.margin_bottom = Inches(
            0.03
        )

        for paragraph in (
            cell
            .text_frame
            .paragraphs
        ):

            paragraph.alignment = (
                PP_ALIGN.CENTER
            )

            paragraph.font.size = Pt(
                11
            )

            paragraph.font.bold = bold

            paragraph.font.color.rgb = (
                self.BODY_COLOR
            )

    # ==========================================================
    # CHART
    # ==========================================================

    def _render_chart(
        self,
        slide,
        spec,
        regions,
    ):

        labels = spec.get(
            "x",
            [],
        )

        values = spec.get(
            "y",
            [],
        )

        if not labels or not values:
            return

        try:

            values = [
                float(value)
                for value in values
            ]

        except (
            TypeError,
            ValueError,
        ):

            return

        height = 4.9

        top = (
            3.95 - height / 2
        )

        self._add_visual_container(
            slide,
            regions["visual_left"],
            top,
            regions["visual_width"],
            height,
            "Data",
        )

        chart_data = (
            CategoryChartData()
        )

        chart_data.categories = [
            str(label)
            for label in labels
        ]

        chart_data.add_series(
            "Value",
            values,
        )

        chart = (
            slide.shapes.add_chart(
                XL_CHART_TYPE.COLUMN_CLUSTERED,
                Inches(
                    regions["visual_left"]
                    + 0.20
                ),
                Inches(
                    top + 0.65
                ),
                Inches(
                    regions["visual_width"]
                    - 0.40
                ),
                Inches(
                    height - 0.90
                ),
                chart_data,
            )
            .chart
        )

        chart.has_legend = False
        chart.has_title = False

        if chart.value_axis:

            chart.value_axis.has_major_gridlines = (
                True
            )

    # ==========================================================
    # HIERARCHY
    # ==========================================================

    def _render_hierarchy(
        self,
        slide,
        spec,
        regions,
    ):

        root = str(
            spec.get(
                "root",
                "Category",
            )
        )

        levels = spec.get(
            "levels",
            [],
        )[:2]

        if not levels:
            return

        height = (
            4.20
            if len(levels) == 1
            else 5.05
        )

        top = (
            3.95 - height / 2
        )

        left = regions[
            "visual_left"
        ]

        width = regions[
            "visual_width"
        ]

        self._add_visual_container(
            slide,
            left,
            top,
            width,
            height,
            "Classification",
        )

        root_width = min(
            1.95,
            width - 1.0,
        )

        root_left = (
            left
            + (
                width
                - root_width
            ) / 2
        )

        # Move root slightly lower so the title
        # has clean separation.
        root_box = self._add_box(
            slide,
            root,
            root_left,
            top + 0.78,
            root_width,
            0.65,
            15,
            True,
            self.ACCENT_LIGHT,
        )

        previous_box = root_box

        current_top = (
            top + 1.75
        )

        for level in levels:

            name = str(
                level.get(
                    "name",
                    "",
                )
            ).strip()

            children = [
                str(item).strip()
                for item in level.get(
                    "children",
                    [],
                )
                if str(item).strip()
            ][:5]

            if not name:
                continue

            level_box = self._add_box(
                slide,
                name,
                root_left,
                current_top,
                root_width,
                0.55,
                12,
                True,
            )

            self._connect_vertical(
                slide,
                previous_box,
                level_box,
            )

            if children:

                count = len(children)

                available = (
                    width - 0.40
                )

                gap = 0.18

                child_width = min(
                    1.05,
                    (
                        available
                        - (
                            count - 1
                        ) * gap
                    ) / count,
                )

                total_width = (
                    count
                    * child_width
                    + (
                        count - 1
                    ) * gap
                )

                child_left_start = (
                    left
                    + (
                        width
                        - total_width
                    ) / 2
                )

                child_top = (
                    current_top + 0.82
                )

                # Horizontal branch first.
                first_center = (
                    child_left_start
                    + child_width / 2
                )

                last_center = (
                    child_left_start
                    + (
                        count - 1
                    )
                    * (
                        child_width + gap
                    )
                    + child_width / 2
                )

                branch_y = (
                    child_top - 0.16
                )

                level_left, level_top, level_width, level_height = (
                    self._shape_bounds(
                        level_box
                    )
                )

                level_center_x = (
                    level_left
                    + level_width / 2
                )

                level_bottom = (
                    level_top
                    + level_height
                )

                self._add_line(
                    slide,
                    level_center_x,
                    level_bottom,
                    level_center_x,
                    branch_y,
                )

                if count > 1:

                    self._add_line(
                        slide,
                        first_center,
                        branch_y,
                        last_center,
                        branch_y,
                    )

                for index, child in enumerate(
                    children
                ):

                    child_left = (
                        child_left_start
                        + index
                        * (
                            child_width
                            + gap
                        )
                    )

                    child_box = self._add_box(
                        slide,
                        child,
                        child_left,
                        child_top,
                        child_width,
                        0.50,
                        9,
                        True,
                    )

                    child_center = (
                        child_left
                        + child_width / 2
                    )

                    self._add_line(
                        slide,
                        child_center,
                        branch_y,
                        child_center,
                        child_top,
                    )

            previous_box = level_box

            current_top += 1.65

    # ==========================================================
    # EXAMPLE GRID
    # ==========================================================

    def _render_example_grid(
        self,
        slide,
        spec,
        regions,
    ):

        examples = spec.get(
            "examples",
            spec.get(
                "items",
                [],
            ),
        )

        examples = [
            str(item).strip()
            for item in examples
            if str(item).strip()
        ][:6]

        if not examples:
            return

        count = len(examples)

        columns = (
            1
            if count == 1
            else 2
        )

        rows = math.ceil(
            count / columns
        )

        box_height = 0.78
        gap_y = 0.30

        box_width = min(
            1.78,
            (
                regions["visual_width"]
                - 0.80
                - (
                    columns - 1
                ) * 0.22
            ) / columns,
        )

        content_height = (
            rows * box_height
            + (
                rows - 1
            ) * gap_y
        )

        container_height = min(
            max(
                content_height + 1.15,
                3.5,
            ),
            5.15,
        )

        container_top = (
            3.95
            - container_height / 2
        )

        left = regions[
            "visual_left"
        ]

        self._add_visual_container(
            slide,
            left,
            container_top,
            regions["visual_width"],
            container_height,
            "Examples",
        )

        start_y = (
            container_top
            + 0.72
        )

        # Reserve explicit space below the title.
        available_height = (
            container_height
            - 0.95
        )

        if content_height < available_height:

            start_y = (
                container_top
                + 0.52
                + (
                    available_height
                    - content_height
                ) / 2
            )

        total_width = (
            columns * box_width
            + (
                columns - 1
            ) * 0.22
        )

        start_x = (
            left
            + (
                regions["visual_width"]
                - total_width
            ) / 2
        )

        for index, example in enumerate(
            examples
        ):

            row = (
                index // columns
            )

            col = (
                index % columns
            )

            x = (
                start_x
                + col
                * (
                    box_width + 0.22
                )
            )

            y = (
                start_y
                + row
                * (
                    box_height + gap_y
                )
            )

            self._add_box(
                slide,
                example,
                x,
                y,
                box_width,
                box_height,
                10,
                True,
            )

    # ==========================================================
    # TIMELINE
    # ==========================================================

    def _render_timeline(
        self,
        slide,
        spec,
        regions,
    ):

        events = spec.get(
            "events",
            spec.get(
                "steps",
                [],
            ),
        )

        events = [
            str(item).strip()
            for item in events
            if str(item).strip()
        ][:6]

        if not events:
            return

        count = len(events)

        # Timeline needs more horizontal room.
        width = 5.15

        left = 4.55

        # Keep it inside the slide.
        if left + width > 9.65:

            width = (
                9.65 - left
            )

        height = 4.35

        top = (
            3.95 - height / 2
        )

        self._add_visual_container(
            slide,
            left,
            top,
            width,
            height,
            "Timeline",
        )

        inner_left = (
            left + 0.42
        )

        inner_right = (
            left + width - 0.42
        )

        line_y = (
            top + height / 2
        )

        if count == 1:

            positions = [
                (
                    inner_left
                    + inner_right
                ) / 2
            ]

        else:

            spacing = (
                inner_right
                - inner_left
            ) / (
                count - 1
            )

            positions = [
                inner_left
                + index
                * spacing
                for index in range(
                    count
                )
            ]

        # Main line.
        self._add_line(
            slide,
            positions[0],
            line_y,
            positions[-1],
            line_y,
            2.0,
        )

        available_step = (
            (
                inner_right
                - inner_left
            )
            / max(
                count,
                1,
            )
        )

        card_width = min(
            1.22,
            max(
                0.82,
                available_step
                - 0.12,
            ),
        )

        card_height = 0.66

        for index, event in enumerate(
            events
        ):

            center_x = positions[
                index
            ]

            circle = slide.shapes.add_shape(
                MSO_SHAPE.OVAL,
                Inches(
                    center_x - 0.12
                ),
                Inches(
                    line_y - 0.12
                ),
                Inches(0.24),
                Inches(0.24),
            )

            circle.fill.solid()
            circle.fill.fore_color.rgb = (
                self.ACCENT_COLOR
            )
            circle.line.fill.background()

            upper = (
                index % 2 == 0
            )

            if upper:

                card_top = (
                    top + 0.56
                )

                stem_start = (
                    card_top
                    + card_height
                )

            else:

                card_top = (
                    top
                    + height
                    - 1.22
                )

                stem_start = line_y

            card_left = (
                center_x
                - card_width / 2
            )

            self._add_box(
                slide,
                event,
                card_left,
                card_top,
                card_width,
                card_height,
                9,
                True,
            )

            self._add_line(
                slide,
                center_x,
                stem_start,
                center_x,
                line_y
                if upper
                else card_top,
                1.0,
            )

    # ==========================================================
    # FORMULA
    # ==========================================================

    def _render_formula(
        self,
        slide,
        spec,
        regions,
    ):

        formula = str(
            spec.get(
                "formula",
                "",
            )
        ).strip()

        if not formula:
            return

        width = min(
            3.75,
            regions["visual_width"],
        )

        height = 2.25

        left = (
            regions["visual_left"]
            + (
                regions["visual_width"]
                - width
            ) / 2
        )

        top = (
            3.95 - height / 2
        )

        self._add_visual_container(
            slide,
            left,
            top,
            width,
            height,
            "Formula",
        )

        self._add_box(
            slide,
            formula,
            left + 0.28,
            top + 0.75,
            width - 0.56,
            0.90,
            23,
            True,
            self.ACCENT_LIGHT,
        )

    # ==========================================================
    # CONCEPT MAP - NEW STRATEGY
    # ==========================================================

    def _render_concept_map(
        self,
        slide,
        spec,
        regions,
    ):
        """
        New concept-map strategy:

            +-----------------------------+
            |          Concept Map        |
            |                             |
            |        [CENTER CONCEPT]     |
            |                |            |
            |       +--------+--------+   |
            |       |        |        |   |
            |     [A]      [B]      [C]  |
            |       |        |        |   |
            |     [D]      [E]      [F]  |
            |                             |
            +-----------------------------+

        This intentionally avoids a radial graph.

        Why:
        - no diagonal crossing
        - no box overlap
        - no connector through text
        - works for short and long concept names
        - naturally scales from 2 to 6 concepts
        - much more stable for different topics
        """

        center_text = str(
            spec.get(
                "center",
                "Concept",
            )
        ).strip()

        concepts = [
            str(item).strip()
            for item in spec.get(
                "concepts",
                [],
            )
            if str(item).strip()
        ][:6]

        if not concepts:
            return

        left = regions[
            "visual_left"
        ]

        width = regions[
            "visual_width"
        ]

        # ------------------------------------------------------
        # Adaptive number of columns.
        #
        # 4 concepts -> 2 x 2
        # 5/6 concepts -> 3 x 2
        # Short labels can safely use 3 columns.
        # ------------------------------------------------------

        if len(concepts) <= 3:

            columns = len(concepts)

        else:

            columns = 3

        rows = math.ceil(
            len(concepts)
            / columns
        )

        center_height = 0.72

        card_height = 0.68

        vertical_gap = 0.35

        title_space = 0.55

        center_to_cards = 0.45

        row_gap = 0.28

        content_height = (
            title_space
            + center_height
            + center_to_cards
            + rows * card_height
            + max(
                rows - 1,
                0,
            ) * row_gap
            + 0.45
        )

        container_height = min(
            max(
                content_height,
                4.15,
            ),
            5.25,
        )

        top = (
            3.95
            - container_height / 2
        )

        self._add_visual_container(
            slide,
            left,
            top,
            width,
            container_height,
            "Concept Map",
        )

        # ------------------------------------------------------
        # Center concept.
        # ------------------------------------------------------

        center_width = min(
            2.20,
            width - 0.90,
        )

        center_left = (
            left
            + (
                width
                - center_width
            ) / 2
        )

        center_top = (
            top
            + 0.62
        )

        center_box = self._add_box(
            slide,
            center_text,
            center_left,
            center_top,
            center_width,
            center_height,
            14,
            True,
            self.ACCENT_LIGHT,
        )

        # ------------------------------------------------------
        # Cards.
        # ------------------------------------------------------

        horizontal_gap = 0.18

        available_width = (
            width - 0.46
        )

        card_width = min(
            1.30,
            (
                available_width
                - (
                    columns - 1
                ) * horizontal_gap
            )
            / columns,
        )

        actual_row_width = (
            columns * card_width
            + (
                columns - 1
            ) * horizontal_gap
        )

        cards_left = (
            left
            + (
                width
                - actual_row_width
            ) / 2
        )

        cards_top = (
            center_top
            + center_height
            + center_to_cards
        )

        card_rows: List[List[Any]] = []

        for row_index in range(
            rows
        ):

            row_cards = []

            row_start = (
                row_index
                * columns
            )

            row_end = min(
                row_start + columns,
                len(concepts),
            )

            for index in range(
                row_start,
                row_end,
            ):

                col = (
                    index - row_start
                )

                card_left = (
                    cards_left
                    + col
                    * (
                        card_width
                        + horizontal_gap
                    )
                )

                card_top = (
                    cards_top
                    + row_index
                    * (
                        card_height
                        + row_gap
                    )
                )

                box = self._add_box(
                    slide,
                    concepts[index],
                    card_left,
                    card_top,
                    card_width,
                    card_height,
                    9,
                    True,
                )

                row_cards.append(
                    box
                )

            card_rows.append(
                row_cards
            )

        if not card_rows:
            return

        # ------------------------------------------------------
        # Build a simple bus network.
        #
        # Center
        #   |
        #   +----------+
        #   |    |     |
        #  A     B     C
        #
        # For a second row, a second bus is connected from
        # the first bus. There are never diagonal lines.
        # ------------------------------------------------------

        first_row = card_rows[0]

        if first_row:

            centers = [
                self._shape_center(
                    box
                )
                for box in first_row
            ]

            first_bus_y = (
                self._shape_bounds(
                    first_row[0]
                )[1]
                - 0.16
            )

            first_card_center_y = (
                self._shape_bounds(
                    first_row[0]
                )[1]
            )

            center_bottom = (
                self._shape_bounds(
                    center_box
                )[1]
                + self._shape_bounds(
                    center_box
                )[3]
            )

            center_x = self._shape_center(
                center_box
            )[0]

            self._add_line(
                slide,
                center_x,
                center_bottom,
                center_x,
                first_bus_y,
            )

            if len(centers) > 1:

                self._add_line(
                    slide,
                    centers[0][0],
                    first_bus_y,
                    centers[-1][0],
                    first_bus_y,
                )

            for cx, _ in centers:

                self._add_line(
                    slide,
                    cx,
                    first_bus_y,
                    cx,
                    first_card_center_y,
                )

        # ------------------------------------------------------
        # Second row:
        # connect it from the first row's bus.
        # ------------------------------------------------------

        if len(card_rows) > 1:

            second_row = card_rows[1]

            if second_row:

                first_card = first_row[0]

                first_row_bottom = (
                    self._shape_bounds(
                        first_card
                    )[1]
                    + self._shape_bounds(
                        first_card
                    )[3]
                )

                second_card_top = (
                    self._shape_bounds(
                        second_row[0]
                    )[1]
                )

                bus_x = (
                    left
                    + width / 2
                )

                second_bus_y = (
                    second_card_top
                    - 0.16
                )

                self._add_line(
                    slide,
                    bus_x,
                    first_row_bottom,
                    bus_x,
                    second_bus_y,
                )

                centers = [
                    self._shape_center(
                        box
                    )
                    for box in second_row
                ]

                if len(centers) > 1:

                    self._add_line(
                        slide,
                        centers[0][0],
                        second_bus_y,
                        centers[-1][0],
                        second_bus_y,
                    )

                for cx, _ in centers:

                    self._add_line(
                        slide,
                        cx,
                        second_bus_y,
                        cx,
                        second_card_top,
                    )


slide_renderer = SlideRenderer()