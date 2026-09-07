"""
Content Generator - Groq Test
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.knowledge.content_generator import ContentGenerator


@pytest.fixture
def generator():
    """Create generator (requires GROQ_API_KEY)"""
    return ContentGenerator()


def test_generate_basic(generator):
    """Test basic generation"""
    content = generator.generate(
        topic="TCP Protocol",
        context="TCP is a connection-oriented protocol.",
        semantic_content={
            "concepts": ["TCP", "protocol", "connection"],
            "propositions": ["TCP IS_A protocol"],
            "visual_type": "none",
            "content_type": "definition",
        },
    )
    
    assert content is not None
    assert content.title != ""


def test_generate_with_intelligence(generator):
    """Test generation with intelligence data"""
    content = generator.generate(
        topic="TCP vs UDP",
        context="TCP is connection-oriented. UDP is connectionless.",
        semantic_content={
            "concepts": ["TCP", "UDP"],
            "propositions": [
                "TCP IS_A connection-oriented",
                "UDP IS_A connectionless",
            ],
            "important_concepts": ["TCP", "UDP"],
            "visual_type": "comparison_table",
            "content_type": "comparison",
        },
    )
    
    assert content is not None
    assert content.visual_type == "comparison_table" or content.visual_type != ""


def test_fallback_on_no_api_key():
    """Test that fallback works without API key"""
    generator = ContentGenerator(api_key="")  # Empty key
    
    content = generator.generate(
        topic="Test",
        context="",
        semantic_content=None,
    )
    
    assert content is not None
    assert content.title == "Test"  # Fallback uses topic as title