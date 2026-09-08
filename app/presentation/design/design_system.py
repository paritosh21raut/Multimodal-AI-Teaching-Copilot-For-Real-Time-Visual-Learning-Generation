"""
Design System

Professional educational theme with color tokens, spacing, and borders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class ColorPalette:
    """Color palette for slides"""
    background: Tuple[int, int, int]
    foreground: Tuple[int, int, int]
    muted: Tuple[int, int, int]
    primary: Tuple[int, int, int]
    primary_light: Tuple[int, int, int]
    secondary: Tuple[int, int, int]
    accent: Tuple[int, int, int]
    border: Tuple[int, int, int]
    white: Tuple[int, int, int]
    success: Tuple[int, int, int]
    warning: Tuple[int, int, int]


class DesignSystem:
    """
    Complete design system for educational slides.
    
    Modern, clean, academic, high-contrast.
    NOT a dashboard or corporate sales deck.
    """
    
    def __init__(self):
        # Professional academic theme
        self.colors = ColorPalette(
            background=(255, 255, 255),      # White
            foreground=(33, 37, 41),          # Near-black
            muted=(108, 117, 125),            # Gray
            primary=(37, 99, 235),            # Blue
            primary_light=(219, 234, 254),    # Light blue
            secondary=(79, 70, 229),          # Indigo
            accent=(5, 150, 105),             # Green
            border=(209, 213, 219),           # Light gray border
            white=(255, 255, 255),
            success=(22, 163, 74),            # Green
            warning=(234, 88, 12),            # Orange
        )
        
        # Spacing scale (in inches)
        self.spacing = {
            "xs": 0.05,
            "sm": 0.1,
            "md": 0.2,
            "lg": 0.35,
            "xl": 0.5,
            "xxl": 0.75,
        }
        
        # Border radius
        self.border_radius = {
            "none": 0.0,
            "sm": 0.04,
            "md": 0.08,
            "lg": 0.12,
        }
        
        # Line widths
        self.line_widths = {
            "thin": 0.75,
            "normal": 1.25,
            "thick": 2.0,
        }
        
        # Layout constants
        self.slide_width = 10.0  # inches
        self.slide_height = 7.5  # inches
        self.margin = 0.5  # outer margin
        self.title_height = 0.8
        self.body_top = 1.3
    
    def get_color(self, name: str) -> Tuple[int, int, int]:
        """Get color by name"""
        return getattr(self.colors, name, self.colors.foreground)
    
    def get_spacing(self, name: str) -> float:
        """Get spacing by name"""
        return self.spacing.get(name, 0.2)
    
    def get_radius(self, name: str) -> float:
        """Get border radius by name"""
        return self.border_radius.get(name, 0.08)
    
    def get_line_width(self, name: str) -> float:
        """Get line width by name"""
        return self.line_widths.get(name, 1.25)


design_system = DesignSystem()