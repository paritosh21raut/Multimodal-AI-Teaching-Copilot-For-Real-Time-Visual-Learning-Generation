"""
Dashboard Models

Separates teacher cockpit from student presentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any


@dataclass
class TeacherCockpitData:
    """
    Data for teacher control view.
    
    Shows:
    - Live transcript
    - Current topic
    - Topic path
    - Semantic concepts
    - Instructional act
    - Development states
    - Importance scores
    - Slide decision
    - Representation
    - System latency
    - Queue state
    - Errors
    """
    # Transcript
    authoritative_transcript: str = ""
    current_utterance: str = ""
    
    # Topic
    current_topic: str = ""
    topic_path: List[str] = field(default_factory=list)
    
    # Semantic
    concepts: List[str] = field(default_factory=list)
    instructional_act: str = ""
    propositions: List[str] = field(default_factory=list)
    
    # Development & Importance
    development_states: Dict[str, str] = field(default_factory=dict)
    important_concepts: List[str] = field(default_factory=list)
    
    # Slide Decision
    slide_action: str = ""
    slide_reason: str = ""
    representation: str = ""
    
    # System
    pipeline_stage: str = ""
    latency_ms: float = 0.0
    queue_depth: int = 0
    errors: List[str] = field(default_factory=list)
    llm_provider: str = ""
    
    # Timestamp
    last_update: datetime = field(default_factory=datetime.now)


@dataclass
class StudentViewData:
    """
    Data for student presentation view.
    
    Shows ONLY the current slide - clean, focused, no diagnostics.
    """
    slide_title: str = ""
    bullet_points: List[str] = field(default_factory=list)
    visual_type: str = "none"
    image_path: str = ""
    current_slide_number: int = 0
    total_slides: int = 0


@dataclass
class DashboardState:
    """Complete dashboard state"""
    teacher_view: TeacherCockpitData = field(default_factory=TeacherCockpitData)
    student_view: StudentViewData = field(default_factory=StudentViewData)
    mode: str = "teacher"  # "teacher" or "student"
    running: bool = False