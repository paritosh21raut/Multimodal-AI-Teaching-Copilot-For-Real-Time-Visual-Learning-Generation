"""
Deterministic Provider

Fallback provider that generates content without LLM.
Uses templates and semantic data to create basic content.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Any

from .llm_provider import LLMProvider


class DeterministicProvider(LLMProvider):
    """
    Deterministic fallback provider.
    
    Never fails - always produces basic content.
    Uses templates based on semantic data.
    """
    
    def generate_structured(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate deterministic output.
        
        Extracts key terms from prompt and creates basic structure.
        """
        # Extract topic from prompt
        topic = self._extract_topic(prompt)
        
        # Build basic slide content
        return {
            "title": topic or "Lecture Slide",
            "bullets": self._extract_bullets(prompt),
            "summary": "",
            "keywords": self._extract_keywords(prompt),
            "content_type": "explanation",
            "visual_type": "none",
            "visual_reason": "deterministic fallback",
            "visual_spec": {},
            "diagram": "",
        }
    
    def health_check(self) -> bool:
        return True  # Always available
    
    def supports_json_schema(self) -> bool:
        return False
    
    def estimated_latency_ms(self) -> int:
        return 1  # Instant
    
    def provider_name(self) -> str:
        return "deterministic"
    
    def model_name(self) -> str:
        return "template"
    
    def _extract_topic(self, prompt: str) -> str:
        """Extract topic from prompt"""
        lines = prompt.split("\n")
        
        for line in lines:
            if line.startswith("TOPIC:"):
                return line.replace("TOPIC:", "").strip()
        
        return ""
    
    def _extract_bullets(self, prompt: str) -> List[str]:
        """Extract bullet points from prompt"""
        bullets = []
        lines = prompt.split("\n")
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- "):
                bullets.append(stripped[2:])
            elif "IS_A" in stripped or "PROVIDES" in stripped or "USES" in stripped:
                bullets.append(stripped)
        
        # If no bullets found, use topic
        if not bullets:
            topic = self._extract_topic(prompt)
            if topic:
                bullets = [topic]
            else:
                bullets = ["Content temporarily unavailable"]
        
        return bullets[:6]
    
    def _extract_keywords(self, prompt: str) -> List[str]:
        """Extract keywords from prompt"""
        keywords = []
        lines = prompt.split("\n")
        
        in_keywords = False
        for line in lines:
            if "KEY CONCEPTS" in line:
                in_keywords = True
                continue
            if in_keywords and line.strip().startswith("- "):
                keywords.append(line.strip()[2:])
            elif in_keywords and not line.strip():
                in_keywords = False
        
        return keywords[:5]