"""
Typography Design System

Professional type scale for projector-readable educational slides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class FontRole:
    """Typography role definition"""
    min_size: int
    max_size: int
    weight: str  # regular, medium, bold
    line_spacing: float
    letter_spacing: float = 0.0


class Typography:
    """
    Typography scale for educational slides.
    
    Sized for PROJECTOR readability:
    - Title: Large, bold
    - Body: Readable from back of room
    - Caption: Small but still legible
    - Diagram label: Compact but clear
    """
    
    def __init__(self):
        self.roles: Dict[str, FontRole] = {
            # Display/Title
            "slide_title": FontRole(
                min_size=28,
                max_size=36,
                weight="bold",
                line_spacing=1.1,
            ),
            
            # Section header
            "section_title": FontRole(
                min_size=20,
                max_size=24,
                weight="bold",
                line_spacing=1.1,
            ),
            
            # Focal message/definition
            "focal_message": FontRole(
                min_size=18,
                max_size=24,
                weight="medium",
                line_spacing=1.3,
            ),
            
            # Body text
            "body": FontRole(
                min_size=14,
                max_size=18,
                weight="regular",
                line_spacing=1.4,
            ),
            
            # Bullet points
            "bullet": FontRole(
                min_size=14,
                max_size=18,
                weight="regular",
                line_spacing=1.4,
            ),
            
            # Caption/label
            "caption": FontRole(
                min_size=11,
                max_size=13,
                weight="regular",
                line_spacing=1.2,
            ),
            
            # Diagram node label
            "diagram_node": FontRole(
                min_size=10,
                max_size=13,
                weight="medium",
                line_spacing=1.2,
            ),
            
            # Diagram edge label
            "diagram_edge": FontRole(
                min_size=9,
                max_size=11,
                weight="regular",
                line_spacing=1.1,
            ),
            
            # Table header
            "table_header": FontRole(
                min_size=12,
                max_size=14,
                weight="bold",
                line_spacing=1.1,
            ),
            
            # Table body
            "table_body": FontRole(
                min_size=11,
                max_size=13,
                weight="regular",
                line_spacing=1.2,
            ),
            
            # Big number
            "big_number": FontRole(
                min_size=40,
                max_size=56,
                weight="bold",
                line_spacing=1.0,
            ),
            
            # Formula
            "formula": FontRole(
                min_size=18,
                max_size=26,
                weight="medium",
                line_spacing=1.2,
            ),
            
            # Emphasis/highlight
            "emphasis": FontRole(
                min_size=16,
                max_size=20,
                weight="bold",
                line_spacing=1.2,
            ),
        }
    
    def get_role(self, role_name: str) -> Optional[FontRole]:
        """Get font role by name"""
        return self.roles.get(role_name)
    
    def get_size(
        self,
        role_name: str,
        density: float = 0.5,
    ) -> int:
        """
        Get font size for a role, adjusted by density.
        
        Higher density = smaller font (within role's min/max).
        """
        role = self.roles.get(role_name)
        if not role:
            return 14
        
        # Lower density → larger font
        # Higher density → smaller font
        size_range = role.max_size - role.min_size
        adjusted = role.max_size - (size_range * density)
        
        return max(role.min_size, min(role.max_size, int(adjusted)))
    
    def get_weight(self, role_name: str) -> str:
        """Get font weight for a role"""
        role = self.roles.get(role_name)
        if not role:
            return "regular"
        return role.weight


typography = Typography()