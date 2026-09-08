"""
Slide Renderer

Renders SlidePlan into PowerPoint using:
- Design System (colors, typography, spacing)
- Layout Plan (proportional regions)
- Structured Visual Specs

Key principle: Regions are proportional, not fixed coordinates.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple
import threading

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR

from app.presentation.models.presentation_models import (
    SlidePlan,
    LayoutPlan,
    LayoutFamily,
    ContentBlock,
    ContentBlockType,
    RepresentationType,
)
from app.presentation.design.design_system import design_system
from app.presentation.design.typography import typography


class SlideRenderer:
    """
    Renders slide plans into professional PowerPoint slides.
    
    Uses proportional regions from LayoutPlan.
    Applies Design System tokens.
    """
    
    def __init__(self):
        self._lock = threading.RLock()
    
    def render_slide(
        self,
        slide,
        plan: SlidePlan,
        layout: LayoutPlan,
        visual_spec: Optional[Dict[str, Any]] = None,
    ):
        """
        Render a slide plan onto a PowerPoint slide.
        
        Args:
            slide: python-pptx slide object
            plan: SlidePlan with content
            layout: LayoutPlan with regions
            visual_spec: Optional structured visual spec
        """
        with self._lock:
            # Clear existing shapes (except title)
            self._clear_slide(slide)
            
            # Render title
            self._render_title(slide, plan, layout)
            
            # Render content based on layout family
            self._render_content(slide, plan, layout, visual_spec)
    
    def _clear_slide(self, slide):
        """Clear all shapes except title placeholder"""
        title_shape = slide.shapes.title
        
        keep_ids = set()
        if title_shape:
            keep_ids.add(id(title_shape))
        
        for shape in list(slide.shapes):
            if id(shape) not in keep_ids:
                shape._element.getparent().remove(shape._element)
    
    def _render_title(self, slide, plan: SlidePlan, layout: LayoutPlan):
        """Render slide title"""
        title_region = layout.regions.get("title", {})
        
        left = title_region.get("left", 0.05) * design_system.slide_width
        top = title_region.get("top", 0.05) * design_system.slide_height
        width = title_region.get("width", 0.90) * design_system.slide_width
        height = title_region.get("height", 0.10) * design_system.slide_height
        
        title_shape = slide.shapes.title
        if title_shape is None:
            title_shape = slide.shapes.add_textbox(
                Inches(left), Inches(top), Inches(width), Inches(height)
            )
        else:
            title_shape.left = Inches(left)
            title_shape.top = Inches(top)
            title_shape.width = Inches(width)
            title_shape.height = Inches(height)
        
        title_shape.text = plan.focal_message or plan.purpose
        
        paragraph = title_shape.text_frame.paragraphs[0]
        paragraph.font.size = Pt(typography.get_size("slide_title", plan.density))
        paragraph.font.bold = True
        paragraph.font.color.rgb = RGBColor(*design_system.get_color("foreground"))
        paragraph.alignment = PP_ALIGN.LEFT
    
    def _render_content(
        self,
        slide,
        plan: SlidePlan,
        layout: LayoutPlan,
        visual_spec: Optional[Dict[str, Any]],
    ):
        """Render slide content based on layout family"""
        
        family = plan.layout_family
        
        if family == LayoutFamily.HERO_DEFINITION:
            self._render_hero_definition(slide, plan, layout)
        
        elif family == LayoutFamily.FULL_WIDTH_PROCESS:
            self._render_full_width_process(slide, plan, layout, visual_spec)
        
        elif family == LayoutFamily.FULL_WIDTH_COMPARISON:
            self._render_full_width_comparison(slide, plan, layout, visual_spec)
        
        elif family == LayoutFamily.TWO_COLUMN_CONTRAST:
            self._render_two_column_contrast(slide, plan, layout, visual_spec)
        
        elif family == LayoutFamily.CENTERED_FORMULA:
            self._render_centered_formula(slide, plan, layout)
        
        elif family == LayoutFamily.BIG_NUMBER:
            self._render_big_number(slide, plan, layout)
        
        elif family == LayoutFamily.EXAMPLE_GRID:
            self._render_example_grid(slide, plan, layout, visual_spec)
        
        elif family == LayoutFamily.HIERARCHY_CENTERED:
            self._render_hierarchy(slide, plan, layout, visual_spec)
        
        elif family == LayoutFamily.SYSTEM_ARCHITECTURE:
            self._render_system_architecture(slide, plan, layout, visual_spec)
        
        elif family == LayoutFamily.CONCEPT_MAP_FULL:
            self._render_concept_map(slide, plan, layout, visual_spec)
        
        else:
            self._render_text_left_visual_right(slide, plan, layout, visual_spec)
    
    def _render_hero_definition(self, slide, plan, layout):
        """Hero definition: large centered definition text"""
        definition_region = layout.regions.get("definition", {})
        
        left = definition_region.get("left", 0.10) * design_system.slide_width
        top = definition_region.get("top", 0.25) * design_system.slide_height
        width = definition_region.get("width", 0.80) * design_system.slide_width
        height = definition_region.get("height", 0.35) * design_system.slide_height
        
        # Find definition text
        definition_text = plan.focal_message
        for block in plan.content_blocks:
            if block.block_type == ContentBlockType.KEY_CLAIM:
                definition_text = block.text
                break
        
        text_box = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        text_frame = text_box.text_frame
        text_frame.word_wrap = True
        text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        
        paragraph = text_frame.paragraphs[0]
        paragraph.text = definition_text
        paragraph.font.size = Pt(typography.get_size("focal_message", plan.density))
        paragraph.font.color.rgb = RGBColor(*design_system.get_color("foreground"))
        paragraph.alignment = PP_ALIGN.CENTER
        
        # Add accent line below definition
        accent_left = 0.30 * design_system.slide_width
        accent_top = (top + height + 0.03) * design_system.slide_height
        accent_width = 0.40 * design_system.slide_width
        accent_height = 0.02 * design_system.slide_height
        
        accent_shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(accent_left),
            Inches(accent_top),
            Inches(accent_width),
            Inches(accent_height),
        )
        accent_shape.fill.solid()
        accent_shape.fill.fore_color.rgb = RGBColor(*design_system.get_color("primary"))
        accent_shape.line.fill.background()
    
    def _render_full_width_process(self, slide, plan, layout, visual_spec):
        """Full width process: horizontal flowchart"""
        process_region = layout.regions.get("process", {})
        
        left = process_region.get("left", 0.05) * design_system.slide_width
        top = process_region.get("top", 0.25) * design_system.slide_height
        width = process_region.get("width", 0.90) * design_system.slide_width
        height = process_region.get("height", 0.55) * design_system.slide_height
        
        if visual_spec and visual_spec.get("type") == "flowchart":
            nodes = visual_spec.get("nodes", [])
            self._render_horizontal_flowchart(slide, nodes, left, top, width, height)
    
    def _render_horizontal_flowchart(
        self,
        slide,
        nodes: List[str],
        left: float,
        top: float,
        width: float,
        height: float,
    ):
        """Render horizontal flowchart"""
        if not nodes:
            return
        
        count = len(nodes)
        gap = 0.3  # inches between shapes
        shape_width = min(1.8, (width - (count - 1) * gap) / count)
        shape_height = min(1.0, height * 0.6)
        
        total_width = count * shape_width + (count - 1) * gap
        start_x = left + (width - total_width) / 2
        shape_top = top + (height - shape_height) / 2
        
        shapes = []
        
        for i, node_text in enumerate(nodes):
            shape_left = start_x + i * (shape_width + gap)
            
            shape = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(shape_left),
                Inches(shape_top),
                Inches(shape_width),
                Inches(shape_height),
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(*design_system.get_color("primary_light"))
            shape.line.color.rgb = RGBColor(*design_system.get_color("primary"))
            
            text_frame = shape.text_frame
            text_frame.word_wrap = True
            text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            
            paragraph = text_frame.paragraphs[0]
            paragraph.text = node_text
            paragraph.font.size = Pt(typography.get_size("diagram_node", 0.5))
            paragraph.font.color.rgb = RGBColor(*design_system.get_color("foreground"))
            paragraph.alignment = PP_ALIGN.CENTER
            
            shapes.append(shape)
        
        # Add connectors
        for i in range(len(shapes) - 1):
            connector = slide.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT,
                shapes[i].left + shapes[i].width,
                shapes[i].top + shapes[i].height // 2,
                shapes[i + 1].left,
                shapes[i + 1].top + shapes[i + 1].height // 2,
            )
            connector.line.color.rgb = RGBColor(*design_system.get_color("primary"))
            connector.line.width = Pt(design_system.get_line_width("normal"))
    
    def _render_full_width_comparison(self, slide, plan, layout, visual_spec):
        """Full width comparison: table"""
        comparison_region = layout.regions.get("comparison", {})
        
        left = comparison_region.get("left", 0.05) * design_system.slide_width
        top = comparison_region.get("top", 0.20) * design_system.slide_height
        width = comparison_region.get("width", 0.90) * design_system.slide_width
        height = comparison_region.get("height", 0.60) * design_system.slide_height
        
        if visual_spec and visual_spec.get("type") in ["comparison_table", "contrast"]:
            columns = visual_spec.get("columns", ["A", "B"])
            rows = visual_spec.get("rows", [])
            
            self._render_table(slide, columns, rows, left, top, width, height)
    
    def _render_table(
        self,
        slide,
        columns: List[str],
        rows: List[Dict],
        left: float,
        top: float,
        width: float,
        height: float,
    ):
        """Render comparison table"""
        if not columns:
            return
        
        row_count = min(len(rows) + 1, 7)  # +1 for header
        col_count = len(columns)
        
        table_shape = slide.shapes.add_table(
            row_count,
            col_count,
            Inches(left),
            Inches(top),
            Inches(width),
            Inches(height),
        )
        
        table = table_shape.table
        
        # Header row
        for col, header in enumerate(columns):
            cell = table.cell(0, col)
            cell.text = header
            self._format_cell(cell, bold=True, fill=design_system.get_color("primary_light"))
        
        # Data rows
        for row_idx, row_data in enumerate(rows[:row_count - 1], start=1):
            label = row_data.get("label", "")
            values = row_data.get("values", [])
            
            cell = table.cell(row_idx, 0)
            cell.text = label
            self._format_cell(cell, bold=True)
            
            for col_idx in range(1, col_count):
                value = values[col_idx - 1] if col_idx - 1 < len(values) else ""
                cell = table.cell(row_idx, col_idx)
                cell.text = value
                self._format_cell(cell)
    
    def _format_cell(self, cell, bold=False, fill=None):
        """Format table cell"""
        cell.margin_left = Inches(0.05)
        cell.margin_right = Inches(0.05)
        cell.margin_top = Inches(0.03)
        cell.margin_bottom = Inches(0.03)
        
        if fill:
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(*fill)
        
        for paragraph in cell.text_frame.paragraphs:
            paragraph.font.size = Pt(typography.get_size("table_body", 0.5))
            paragraph.font.bold = bold
            paragraph.font.color.rgb = RGBColor(*design_system.get_color("foreground"))
            paragraph.alignment = PP_ALIGN.CENTER
    
    def _render_two_column_contrast(self, slide, plan, layout, visual_spec):
        """Two column contrast"""
        left_region = layout.regions.get("left_column", {})
        right_region = layout.regions.get("right_column", {})
        
        # Render left column
        self._render_text_column(slide, plan, left_region, "left")
        
        # Render right column
        self._render_text_column(slide, plan, right_region, "right")
    
    def _render_text_column(self, slide, plan, region, side):
        """Render a text column"""
        left = region.get("left", 0.05) * design_system.slide_width
        top = region.get("top", 0.20) * design_system.slide_height
        width = region.get("width", 0.42) * design_system.slide_width
        height = region.get("height", 0.65) * design_system.slide_height
        
        text_box = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        text_frame = text_box.text_frame
        text_frame.word_wrap = True
        
        # Add content blocks
        items = [
            block.text for block in plan.content_blocks
            if block.text and block.block_type in [
                ContentBlockType.KEY_CLAIM,
                ContentBlockType.EXPLANATION,
                ContentBlockType.EXAMPLE,
            ]
        ]
        
        for i, item in enumerate(items[:4]):
            paragraph = text_frame.paragraphs[0] if i == 0 else text_frame.add_paragraph()
            paragraph.text = f"• {item}"
            paragraph.font.size = Pt(typography.get_size("body", plan.density))
            paragraph.font.color.rgb = RGBColor(*design_system.get_color("foreground"))
            paragraph.space_after = Pt(8)
    
    def _render_centered_formula(self, slide, plan, layout):
        """Centered formula layout"""
        formula_region = layout.regions.get("formula", {})
        
        left = formula_region.get("left", 0.15) * design_system.slide_width
        top = formula_region.get("top", 0.25) * design_system.slide_height
        width = formula_region.get("width", 0.70) * design_system.slide_width
        height = formula_region.get("height", 0.25) * design_system.slide_height
        
        formula_text = plan.focal_message
        
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(*design_system.get_color("primary_light"))
        shape.line.color.rgb = RGBColor(*design_system.get_color("primary"))
        
        text_frame = shape.text_frame
        text_frame.word_wrap = True
        text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        
        paragraph = text_frame.paragraphs[0]
        paragraph.text = formula_text
        paragraph.font.size = Pt(typography.get_size("formula", plan.density))
        paragraph.font.color.rgb = RGBColor(*design_system.get_color("foreground"))
        paragraph.alignment = PP_ALIGN.CENTER
    
    def _render_big_number(self, slide, plan, layout):
        """Big number layout"""
        number_region = layout.regions.get("number", {})
        
        left = number_region.get("left", 0.20) * design_system.slide_width
        top = number_region.get("top", 0.25) * design_system.slide_height
        width = number_region.get("width", 0.60) * design_system.slide_width
        height = number_region.get("height", 0.30) * design_system.slide_height
        
        number_text = plan.focal_message
        
        text_box = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        text_frame = text_box.text_frame
        text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        
        paragraph = text_frame.paragraphs[0]
        paragraph.text = number_text
        paragraph.font.size = Pt(typography.get_size("big_number", plan.density))
        paragraph.font.bold = True
        paragraph.font.color.rgb = RGBColor(*design_system.get_color("primary"))
        paragraph.alignment = PP_ALIGN.CENTER
    
    def _render_example_grid(self, slide, plan, layout, visual_spec):
        """Example grid layout"""
        grid_region = layout.regions.get("grid", {})
        
        left = grid_region.get("left", 0.05) * design_system.slide_width
        top = grid_region.get("top", 0.20) * design_system.slide_height
        width = grid_region.get("width", 0.90) * design_system.slide_width
        height = grid_region.get("height", 0.65) * design_system.slide_height
        
        examples = []
        if visual_spec and visual_spec.get("type") == "example_grid":
            examples = visual_spec.get("examples", [])
        else:
            examples = [
                block.text for block in plan.content_blocks
                if block.block_type == ContentBlockType.EXAMPLE
            ]
        
        if not examples:
            return
        
        count = min(len(examples), 6)
        columns = 3 if count > 3 else count
        rows = (count + columns - 1) // columns
        
        gap = 0.15
        card_width = (width - (columns - 1) * gap) / columns
        card_height = min(1.2, (height - (rows - 1) * gap) / rows)
        
        for i, example in enumerate(examples):
            row = i // columns
            col = i % columns
            
            card_left = left + col * (card_width + gap)
            card_top = top + row * (card_height + gap)
            
            card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(card_left),
                Inches(card_top),
                Inches(card_width),
                Inches(card_height),
            )
            card.fill.solid()
            card.fill.fore_color.rgb = RGBColor(*design_system.get_color("primary_light"))
            card.line.color.rgb = RGBColor(*design_system.get_color("border"))
            
            text_frame = card.text_frame
            text_frame.word_wrap = True
            text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            
            paragraph = text_frame.paragraphs[0]
            paragraph.text = example
            paragraph.font.size = Pt(typography.get_size("body", plan.density))
            paragraph.alignment = PP_ALIGN.CENTER
    
    def _render_hierarchy(self, slide, plan, layout, visual_spec):
        """Hierarchy layout"""
        # Simplified: render as text for now
        hierarchy_region = layout.regions.get("hierarchy", {})
        self._render_simple_text(slide, plan, hierarchy_region)
    
    def _render_system_architecture(self, slide, plan, layout, visual_spec):
        """System architecture layout"""
        diagram_region = layout.regions.get("diagram", {})
        self._render_simple_text(slide, plan, diagram_region)
    
    def _render_concept_map(self, slide, plan, layout, visual_spec):
        """Concept map layout"""
        map_region = layout.regions.get("map", {})
        self._render_simple_text(slide, plan, map_region)
    
    def _render_text_left_visual_right(self, slide, plan, layout, visual_spec):
        """Default text left / visual right"""
        text_region = layout.regions.get("text", {})
        visual_region = layout.regions.get("visual", {})
        
        # Render text
        self._render_simple_text(slide, plan, text_region)
    
    def _render_simple_text(self, slide, plan, region):
        """Render simple text in a region"""
        left = region.get("left", 0.05) * design_system.slide_width
        top = region.get("top", 0.20) * design_system.slide_height
        width = region.get("width", 0.42) * design_system.slide_width
        height = region.get("height", 0.65) * design_system.slide_height
        
        text_box = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        text_frame = text_box.text_frame
        text_frame.word_wrap = True
        
        items = [
            block.text for block in plan.content_blocks
            if block.text and block.block_type != ContentBlockType.VISUAL
        ]
        
        for i, item in enumerate(items[:6]):
            paragraph = text_frame.paragraphs[0] if i == 0 else text_frame.add_paragraph()
            paragraph.text = f"• {item}"
            paragraph.font.size = Pt(typography.get_size("body", plan.density))
            paragraph.font.color.rgb = RGBColor(*design_system.get_color("foreground"))
            paragraph.space_after = Pt(6)