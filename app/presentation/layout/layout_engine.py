"""
Layout Engine

Constraint-based layout system.
Maps LayoutFamily to actual regions and constraints.

No fixed x/y coordinates - uses proportions and constraints.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
import threading

from app.presentation.models.presentation_models import (
    LayoutFamily,
    LayoutPlan,
    SlidePlan,
    ContentBlockType,
)
from app.presentation.design.design_system import design_system


class LayoutEngine:
    """
    Constraint-based layout engine.
    
    Maps layout family to region definitions.
    Regions are expressed as proportions of slide dimensions.
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # Layout family definitions
        self._layout_definitions = self._build_layout_definitions()
    
    def create_layout(
        self,
        plan: SlidePlan,
    ) -> LayoutPlan:
        """
        Create a layout plan for a slide plan.
        
        Args:
            plan: SlidePlan with layout family and density
            
        Returns:
            LayoutPlan with regions and constraints
        """
        with self._lock:
            family = plan.layout_family
            density = plan.density
            
            # Get layout definition
            definition = self._layout_definitions.get(
                family,
                self._layout_definitions[LayoutFamily.TEXT_LEFT_VISUAL_RIGHT],
            )
            
            # Adjust regions based on density
            regions = self._adjust_for_density(definition["regions"], density)
            
            # Build constraints
            constraints = self._build_constraints(plan, density)
            
            return LayoutPlan(
                layout_family=family,
                regions=regions,
                constraints=constraints,
                typography_assignments=self._assign_typography(plan),
            )
    
    def _build_layout_definitions(self) -> Dict:
        """Build all layout family definitions"""
        return {
            # ==========================================
            # HERO DEFINITION
            # Central, large definition text
            # ==========================================
            LayoutFamily.HERO_DEFINITION: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "definition": {"top": 0.25, "left": 0.10, "width": 0.80, "height": 0.35},
                    "supporting": {"top": 0.65, "left": 0.10, "width": 0.80, "height": 0.25},
                    "visual": {"top": 0.20, "left": 0.68, "width": 0.28, "height": 0.50},
                }
            },
            
            # ==========================================
            # TITLE + FOCAL VISUAL
            # ==========================================
            LayoutFamily.TITLE_PLUS_FOCAL_VISUAL: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "focal_visual": {"top": 0.20, "left": 0.15, "width": 0.70, "height": 0.50},
                    "caption": {"top": 0.72, "left": 0.15, "width": 0.70, "height": 0.10},
                }
            },
            
            # ==========================================
            # TEXT LEFT / VISUAL RIGHT
            # ==========================================
            LayoutFamily.TEXT_LEFT_VISUAL_RIGHT: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "text": {"top": 0.20, "left": 0.05, "width": 0.42, "height": 0.65},
                    "visual": {"top": 0.20, "left": 0.52, "width": 0.43, "height": 0.65},
                }
            },
            
            # ==========================================
            # FULL WIDTH PROCESS
            # ==========================================
            LayoutFamily.FULL_WIDTH_PROCESS: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "process": {"top": 0.25, "left": 0.05, "width": 0.90, "height": 0.55},
                    "takeaway": {"top": 0.82, "left": 0.10, "width": 0.80, "height": 0.10},
                }
            },
            
            # ==========================================
            # FULL WIDTH COMPARISON
            # ==========================================
            LayoutFamily.FULL_WIDTH_COMPARISON: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "comparison": {"top": 0.20, "left": 0.05, "width": 0.90, "height": 0.60},
                    "summary": {"top": 0.82, "left": 0.10, "width": 0.80, "height": 0.10},
                }
            },
            
            # ==========================================
            # CENTERED FORMULA
            # ==========================================
            LayoutFamily.CENTERED_FORMULA: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "formula": {"top": 0.25, "left": 0.15, "width": 0.70, "height": 0.25},
                    "variables": {"top": 0.55, "left": 0.15, "width": 0.70, "height": 0.30},
                }
            },
            
            # ==========================================
            # TWO COLUMN CONTRAST
            # ==========================================
            LayoutFamily.TWO_COLUMN_CONTRAST: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "left_column": {"top": 0.20, "left": 0.05, "width": 0.42, "height": 0.65},
                    "right_column": {"top": 0.20, "left": 0.53, "width": 0.42, "height": 0.65},
                }
            },
            
            # ==========================================
            # BIG NUMBER
            # ==========================================
            LayoutFamily.BIG_NUMBER: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "number": {"top": 0.25, "left": 0.20, "width": 0.60, "height": 0.30},
                    "context": {"top": 0.60, "left": 0.15, "width": 0.70, "height": 0.20},
                }
            },
            
            # ==========================================
            # EXAMPLE GRID
            # ==========================================
            LayoutFamily.EXAMPLE_GRID: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "grid": {"top": 0.20, "left": 0.05, "width": 0.90, "height": 0.65},
                }
            },
            
            # ==========================================
            # HIERARCHY CENTERED
            # ==========================================
            LayoutFamily.HIERARCHY_CENTERED: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "hierarchy": {"top": 0.20, "left": 0.08, "width": 0.84, "height": 0.65},
                }
            },
            
            # ==========================================
            # SYSTEM ARCHITECTURE
            # ==========================================
            LayoutFamily.SYSTEM_ARCHITECTURE: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "diagram": {"top": 0.18, "left": 0.05, "width": 0.62, "height": 0.67},
                    "side_notes": {"top": 0.18, "left": 0.70, "width": 0.25, "height": 0.67},
                }
            },
            
            # ==========================================
            # CONCEPT MAP FULL
            # ==========================================
            LayoutFamily.CONCEPT_MAP_FULL: {
                "regions": {
                    "title": {"top": 0.05, "left": 0.05, "width": 0.90, "height": 0.10},
                    "map": {"top": 0.18, "left": 0.05, "width": 0.90, "height": 0.67},
                }
            },
        }
    
    def _adjust_for_density(
        self,
        regions: Dict[str, Dict[str, float]],
        density: float,
    ) -> Dict[str, Dict[str, float]]:
        """
        Adjust regions based on content density.
        
        Higher density = tighter regions.
        Lower density = more whitespace.
        """
        adjusted = {}
        
        for region_name, region in regions.items():
            adjusted_region = dict(region)
            
            # Adjust padding based on density
            if density > 0.7:
                # Dense: shrink slightly
                adjusted_region["width"] = region.get("width", 0.9) * 0.95
                adjusted_region["height"] = region.get("height", 0.65) * 0.95
            elif density < 0.3:
                # Sparse: expand slightly
                adjusted_region["width"] = min(0.92, region.get("width", 0.9) * 1.05)
                adjusted_region["height"] = min(0.75, region.get("height", 0.65) * 1.05)
            
            adjusted[region_name] = adjusted_region
        
        return adjusted
    
    def _build_constraints(
        self,
        plan: SlidePlan,
        density: float,
    ) -> Dict[str, Any]:
        """Build layout constraints"""
        return {
            "density": density,
            "min_font_size": 11 if density < 0.5 else 10,
            "max_content_blocks": self._max_blocks_for_density(density),
            "allow_visual": density < 0.8,
            "preferred_aspect_ratio": 1.5 if density < 0.5 else 1.0,
        }
    
    def _max_blocks_for_density(self, density: float) -> int:
        """Maximum content blocks based on density"""
        if density < 0.3:
            return 3  # Sparse: few blocks, large
        elif density < 0.5:
            return 5  # Medium
        elif density < 0.7:
            return 7  # Dense
        else:
            return 9  # Very dense
    
    def _assign_typography(self, plan: SlidePlan) -> Dict[str, str]:
        """Assign typography roles to regions"""
        assignments = {}
        
        # Determine primary region based on layout family
        primary_region = self._get_primary_region(plan.layout_family)
        
        assignments["title"] = "slide_title"
        assignments[primary_region] = "focal_message"
        
        # Supporting regions get body typography
        for region in ["text", "supporting", "side_notes", "context", "summary"]:
            assignments[region] = "body"
        
        return assignments
    
    def _get_primary_region(self, family: LayoutFamily) -> str:
        """Get the primary content region for a layout family"""
        primary_map = {
            LayoutFamily.HERO_DEFINITION: "definition",
            LayoutFamily.TITLE_PLUS_FOCAL_VISUAL: "focal_visual",
            LayoutFamily.FULL_WIDTH_PROCESS: "process",
            LayoutFamily.FULL_WIDTH_COMPARISON: "comparison",
            LayoutFamily.CENTERED_FORMULA: "formula",
            LayoutFamily.BIG_NUMBER: "number",
            LayoutFamily.EXAMPLE_GRID: "grid",
            LayoutFamily.HIERARCHY_CENTERED: "hierarchy",
            LayoutFamily.SYSTEM_ARCHITECTURE: "diagram",
            LayoutFamily.CONCEPT_MAP_FULL: "map",
            LayoutFamily.TWO_COLUMN_CONTRAST: "left_column",
            LayoutFamily.TEXT_LEFT_VISUAL_RIGHT: "text",
        }
        return primary_map.get(family, "text")