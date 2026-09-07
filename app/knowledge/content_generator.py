"""
Content Generator - Groq Edition

Uses Groq (Llama 3.1 8B Instant) for slide generation.
14,400 free requests/day vs Gemini's 20/day.
"""

from __future__ import annotations

import os
import json
from typing import Optional, Dict, Any, List

from openai import OpenAI

from app.slides.slide_models import (
    BulletPoint,
    SlideContent,
    DiagramAsset,
)


class ContentGenerator:
    """Generates slide content using Groq LLM"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama-3.1-8b-instant",
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"
        
        self._client = None
    
    def _get_client(self):
        """Lazy-load Groq client"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("GROQ_API_KEY not set")
            
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        
        return self._client

    def generate(
        self,
        topic: str,
        context: str,
        semantic_content: Optional[Dict[str, Any]] = None,
    ) -> SlideContent:
        """
        Generate slide content using intelligence data.
        
        Args:
            topic: Topic name
            context: Rolling lecture context
            semantic_content: Intelligence data (concepts, propositions, etc.)
        """
        
        prompt = self._build_prompt(topic, context, semantic_content)
        result = self._call_groq(prompt)
        
        if result is None:
            # Fallback to basic content
            return self._fallback_content(topic)
        
        bullets = [
            BulletPoint(text=item)
            for item in result.get("bullets", [])
        ]
        
        content_type = result.get("content_type", "explanation")
        visual_type = result.get("visual_type", "none")
        visual_spec = result.get("visual_spec", {})
        visual_reason = result.get("visual_reason", "")
        
        diagram = None
        diagram_text = result.get("diagram")
        
        if (
            diagram_text
            and visual_type in ("diagram", "flowchart", "hierarchy", "concept_map")
        ):
            diagram = DiagramAsset(
                title=result.get("title", topic),
                description=diagram_text,
                diagram_type=visual_type,
                data=visual_spec,
            )
        
        print("=" * 60)
        print("[ContentGenerator - Groq]")
        print(f"Model        : {self.model}")
        print(f"Content Type : {content_type}")
        print(f"Visual Type  : {visual_type}")
        print("=" * 60)
        
        return SlideContent(
            title=result.get("title", topic),
            bullets=bullets,
            summary=result.get("summary"),
            image_query=result.get("image_query"),
            keywords=result.get("keywords", []),
            diagram=diagram,
            content_type=content_type,
            visual_type=visual_type,
            visual_reason=visual_reason,
            visual_spec=visual_spec,
            metadata={
                "content_type": content_type,
                "visual_type": visual_type,
                "llm_model": self.model,
            },
        )
    
    def _call_groq(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Groq LLM and parse response"""
        try:
            client = self._get_client()
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert educational presentation designer. "
                            "Generate slide content based on intelligence data. "
                            "Respond with ONLY valid JSON."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0.3,  # Slightly creative but consistent
                max_tokens=500,
                timeout=5.0,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean JSON
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            return json.loads(content.strip())
        
        except Exception as error:
            print(f"[ContentGenerator] Groq call failed: {error}")
            return None
    
    def _build_prompt(
        self,
        topic: str,
        context: str,
        semantic_content: Optional[Dict[str, Any]],
    ) -> str:
        """Build prompt with intelligence data"""
        
        prompt = f"""
TOPIC: {topic}

LECTURE CONTEXT:
{context[:400]}

"""
        
        if semantic_content:
            concepts = semantic_content.get("concepts", [])
            propositions = semantic_content.get("propositions", [])
            important = semantic_content.get("important_concepts", [])
            visual_rec = semantic_content.get("visual_type", "none")
            content_rec = semantic_content.get("content_type", "explanation")
            
            if concepts:
                prompt += "KEY CONCEPTS:\n"
                for c in concepts[:5]:
                    prompt += f"- {c}\n"
            
            if propositions:
                prompt += "\nSEMANTIC PROPOSITIONS:\n"
                for p in propositions[:5]:
                    if p:
                        prompt += f"- {p}\n"
            
            if important:
                prompt += "\nIMPORTANT CONCEPTS:\n"
                for c in important[:3]:
                    prompt += f"- {c}\n"
            
            prompt += f"\nRECOMMENDED VISUAL: {visual_rec}"
            prompt += f"\nRECOMMENDED CONTENT: {content_rec}"
        
        prompt += """

Generate ONE educational slide.

Return JSON:
{
    "title": "...",
    "bullets": ["...", "..."],
    "summary": "...",
    "keywords": ["..."],
    "content_type": "...",
    "visual_type": "...",
    "visual_reason": "...",
    "image_query": "...",
    "visual_spec": {},
    "diagram": ""
}

Rules:
- Maximum 6 bullets
- Maximum 14 words per bullet
- Use recommended visual type if provided
- Don't invent data
"""
        
        return prompt
    
    def _fallback_content(self, topic: str) -> SlideContent:
        """Fallback content if Groq fails"""
        return SlideContent(
            title=topic,
            bullets=[BulletPoint(text="Content generation temporarily unavailable.")],
            summary="",
            keywords=[],
            content_type="explanation",
            visual_type="none",
            visual_reason="fallback",
            visual_spec={},
        )


content_generator = ContentGenerator()