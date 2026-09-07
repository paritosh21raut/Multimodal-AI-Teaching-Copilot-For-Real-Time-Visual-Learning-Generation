"""
Slide Decision Engine Subsystem

Decides when presentation state should change.
"""

from .slide_decision_models import SlideAction, SlideTrigger, SlideDecision
from .slide_decision_engine import SlideDecisionEngine

__version__ = "1.0.0"

__all__ = [
    "SlideAction",
    "SlideTrigger",
    "SlideDecision",
    "SlideDecisionEngine",
] 