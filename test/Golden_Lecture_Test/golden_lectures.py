"""
Golden Lecture Corpus

Reusable evaluation dataset across multiple domains and instructional scenarios.
Each lecture specifies expected outputs for validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class GoldenLectureChunk:
    """A single chunk in a golden lecture"""
    transcript: str
    expected_topic: str = ""
    expected_action: str = ""  # create_new, update, no_change, etc.
    expected_representation: str = ""  # definition, comparison, process, etc.
    expected_concepts: List[str] = field(default_factory=list)
    expected_propositions: List[str] = field(default_factory=list)
    is_chatter: bool = False


@dataclass
class GoldenLecture:
    """Complete golden lecture scenario"""
    domain: str
    name: str
    description: str
    chunks: List[GoldenLectureChunk] = field(default_factory=list)


# ============================================================
# COMPUTER NETWORKING LECTURE
# ============================================================

networking_lecture = GoldenLecture(
    domain="networking",
    name="TCP vs UDP",
    description="Comparison of TCP and UDP protocols",
    chunks=[
        GoldenLectureChunk(
            transcript="Today we are going to discuss computer networks.",
            expected_topic="Computer Networks",
            expected_action="create_new",
            expected_concepts=["computer", "networks"],
        ),
        GoldenLectureChunk(
            transcript="A network is a collection of interconnected devices.",
            expected_topic="Computer Networks",
            expected_action="update",
            expected_concepts=["network", "devices"],
            expected_propositions=["network IS_A collection"],
        ),
        GoldenLectureChunk(
            transcript="Now let's discuss TCP.",
            expected_topic="TCP",
            expected_action="create_new",
            expected_concepts=["TCP"],
        ),
        GoldenLectureChunk(
            transcript="TCP is a connection-oriented protocol.",
            expected_topic="TCP",
            expected_action="update",
            expected_concepts=["TCP", "protocol"],
            expected_propositions=["TCP IS_A protocol"],
        ),
        GoldenLectureChunk(
            transcript="TCP provides reliable data transmission.",
            expected_topic="TCP",
            expected_action="update",
            expected_propositions=["TCP PROVIDES transmission"],
        ),
        GoldenLectureChunk(
            transcript="UDP is a connectionless protocol.",
            expected_topic="UDP",
            expected_action="create_new",
            expected_concepts=["UDP", "protocol"],
        ),
        GoldenLectureChunk(
            transcript="Unlike TCP, UDP does not guarantee delivery.",
            expected_topic="UDP",
            expected_action="update",
            expected_representation="contrast",
            expected_concepts=["TCP", "UDP"],
        ),
    ],
)


# ============================================================
# BIOLOGY LECTURE
# ============================================================

biology_lecture = GoldenLecture(
    domain="biology",
    name="Photosynthesis",
    description="Explanation of photosynthesis process",
    chunks=[
        GoldenLectureChunk(
            transcript="Today we are learning about photosynthesis.",
            expected_topic="Photosynthesis",
            expected_action="create_new",
            expected_concepts=["photosynthesis"],
        ),
        GoldenLectureChunk(
            transcript="Photosynthesis is the process by which plants convert light energy to chemical energy.",
            expected_topic="Photosynthesis",
            expected_action="update",
            expected_representation="definition",
            expected_concepts=["photosynthesis", "plants", "energy"],
        ),
        GoldenLectureChunk(
            transcript="The process requires sunlight, water, and carbon dioxide.",
            expected_topic="Photosynthesis",
            expected_action="update",
            expected_concepts=["sunlight", "water", "carbon dioxide"],
        ),
        GoldenLectureChunk(
            transcript="It produces glucose and oxygen as products.",
            expected_topic="Photosynthesis",
            expected_action="update",
            expected_concepts=["glucose", "oxygen"],
        ),
    ],
)


# ============================================================
# PHYSICS LECTURE
# ============================================================

physics_lecture = GoldenLecture(
    domain="physics",
    name="Newton's Laws",
    description="Introduction to Newton's Laws of Motion",
    chunks=[
        GoldenLectureChunk(
            transcript="Today we are discussing Newton's laws of motion.",
            expected_topic="Newton's Laws",
            expected_action="create_new",
            expected_concepts=["Newton", "laws", "motion"],
        ),
        GoldenLectureChunk(
            transcript="The first law states that an object remains at rest unless acted upon by a force.",
            expected_topic="Newton's Laws",
            expected_action="update",
            expected_propositions=["object REMAINS at rest"],
        ),
        GoldenLectureChunk(
            transcript="The second law states that force equals mass times acceleration.",
            expected_topic="Newton's Laws",
            expected_action="update",
            expected_representation="formula",
            expected_propositions=["force EQUALS mass"],
        ),
        GoldenLectureChunk(
            transcript="The third law states that for every action there is an equal and opposite reaction.",
            expected_topic="Newton's Laws",
            expected_action="update",
            expected_propositions=["action HAS_ATTRIBUTE reaction"],
        ),
    ],
)


# ============================================================
# MATHEMATICS LECTURE
# ============================================================

math_lecture = GoldenLecture(
    domain="mathematics",
    name="Derivatives",
    description="Introduction to derivatives in calculus",
    chunks=[
        GoldenLectureChunk(
            transcript="Today we are learning about derivatives.",
            expected_topic="Derivatives",
            expected_action="create_new",
            expected_concepts=["derivatives"],
        ),
        GoldenLectureChunk(
            transcript="A derivative represents the rate of change of a function.",
            expected_topic="Derivatives",
            expected_action="update",
            expected_representation="definition",
            expected_concepts=["derivative", "function"],
        ),
        GoldenLectureChunk(
            transcript="For example, the derivative of position is velocity.",
            expected_topic="Derivatives",
            expected_action="update",
            expected_representation="example",
            expected_concepts=["position", "velocity"],
        ),
    ],
)


# ============================================================
# CLASSROOM CHATTER (should be filtered)
# ============================================================

chatter_test = GoldenLecture(
    domain="classroom",
    name="Chatter Filtering",
    description="Classroom chatter should be filtered",
    chunks=[
        GoldenLectureChunk(
            transcript="Can you hear me in the back?",
            is_chatter=True,
        ),
        GoldenLectureChunk(
            transcript="I forgot my notebook.",
            is_chatter=True,
        ),
    ],
)


# ============================================================
# ALL GOLDEN LECTURES
# ============================================================

ALL_GOLDEN_LECTURES = [
    networking_lecture,
    biology_lecture,
    physics_lecture,
    math_lecture,
    chatter_test,
]