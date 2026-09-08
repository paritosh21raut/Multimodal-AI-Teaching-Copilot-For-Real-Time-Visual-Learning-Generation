"""
Presentation Intelligence Subsystem
"""

from .models.presentation_models import (
    SlideAction,
    RepresentationType,
    LayoutFamily,
    ContentBlockType,
    SlideDecision,
    SelectedInformation,
    RepresentationDecision,
    ContentBlock,
    SlidePlan,
    LayoutPlan,
    SlideValidationResult,
)

__version__ = "0.1.0"

__all__ = [
    "SlideAction",
    "RepresentationType",
    "LayoutFamily",
    "ContentBlockType",
    "SlideDecision",
    "SelectedInformation",
    "RepresentationDecision",
    "ContentBlock",
    "SlidePlan",
    "LayoutPlan",
    "SlideValidationResult",
]