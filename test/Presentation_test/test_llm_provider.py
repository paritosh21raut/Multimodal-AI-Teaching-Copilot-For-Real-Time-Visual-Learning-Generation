"""
LLM Provider System - Comprehensive Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.llm.llm_provider import LLMProvider
from app.presentation.llm.groq_provider import GroqProvider
from app.presentation.llm.deterministic_provider import DeterministicProvider
from app.presentation.llm.llm_router import LLMRouter


# EASY TESTS

def test_deterministic_provider_always_works():
    """Easy: Deterministic provider always returns content"""
    provider = DeterministicProvider()
    
    result = provider.generate_structured(
        prompt="TOPIC: TCP\nKEY CONCEPTS:\n- TCP\n- UDP",
    )
    
    assert result is not None
    assert "title" in result
    assert "bullets" in result


def test_router_returns_content():
    """Easy: Router returns content"""
    router = LLMRouter()
    
    result = router.generate_structured(
        prompt="TOPIC: TCP Protocol\n- TCP PROVIDES reliability",
    )
    
    assert result is not None
    assert "title" in result


def test_groq_provider_health():
    """Easy: Groq provider health check"""
    provider = GroqProvider()
    
    # Health depends on API key being set
    has_key = bool(provider.api_key)
    assert provider.health_check() == has_key


# MEDIUM TESTS

def test_deterministic_extracts_topic():
    """Medium: Deterministic extracts topic from prompt"""
    provider = DeterministicProvider()
    
    result = provider.generate_structured(
        prompt="TOPIC: Network Protocols\n- TCP PROVIDES reliability",
    )
    
    assert "Network" in result["title"] or "Protocol" in result["title"]


def test_deterministic_extracts_bullets():
    """Medium: Deterministic extracts bullets"""
    provider = DeterministicProvider()
    
    result = provider.generate_structured(
        prompt="TOPIC: TCP\n- TCP IS_A protocol\n- TCP PROVIDES reliability\n- TCP USES acknowledgements",
    )
    
    assert len(result["bullets"]) >= 1


def test_router_falls_back_to_deterministic():
    """Medium: Router falls back when Groq unavailable"""
    router = LLMRouter()
    
    # This should still work even without Groq API key
    result = router.generate_structured(
        prompt="TOPIC: Test",
    )
    
    assert result is not None


# HARD TESTS

def test_router_tracks_provider_failures():
    """Hard: Router tracks failures"""
    router = LLMRouter()
    
    # Get status
    status = router.get_provider_status()
    
    assert "groq" in status
    assert "deterministic" in status
    assert "failures" in status["groq"]
    assert "failures" in status["deterministic"]


def test_deterministic_never_fails():
    """Hard: Deterministic never returns None even with garbage input"""
    provider = DeterministicProvider()
    
    result = provider.generate_structured(prompt="")
    
    assert result is not None
    assert result["title"] != ""


def test_router_never_returns_none():
    """Hard: Router never returns None"""
    router = LLMRouter()
    
    # Even with empty prompt
    result = router.generate_structured(prompt="")
    
    assert result is not None
    assert "title" in result


# GENERIC TESTS

def test_works_across_domains():
    """Generic: Works for any domain"""
    provider = DeterministicProvider()
    
    domains = {
        "networking": "TOPIC: TCP\n- TCP PROVIDES reliability",
        "biology": "TOPIC: Photosynthesis\n- Photosynthesis PRODUCES glucose",
        "physics": "TOPIC: Force\n- Force CAUSES acceleration",
    }
    
    for domain, prompt in domains.items():
        result = provider.generate_structured(prompt=prompt)
        assert result is not None, f"Failed for {domain}"
        assert result["title"] != ""