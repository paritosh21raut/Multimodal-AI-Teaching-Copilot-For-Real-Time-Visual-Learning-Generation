"""
Groq Provider (FIXED)

Enforces correct output schema for slide content.
"""

from __future__ import annotations

import os
import json
from typing import Dict, List, Optional, Any

from openai import OpenAI

from .llm_provider import LLMProvider


class GroqProvider(LLMProvider):
    """Groq-hosted LLM provider with schema enforcement"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen/qwen3.8-27b",
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                return None
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client
    
    def generate_structured(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate structured JSON with schema enforcement"""
        client = self._get_client()
        if client is None:
            return None
        
        try:
            # Add schema enforcement to system prompt
            system_prompt = (
                "You are an educational presentation assistant.\n"
                "You MUST respond with ONLY valid JSON matching this EXACT schema:\n"
                '{\n'
                '    "title": "string",\n'
                '    "bullets": ["string", "string"],\n'
                '    "summary": "string",\n'
                '    "keywords": ["string"],\n'
                '    "content_type": "string",\n'
                '    "visual_type": "string",\n'
                '    "visual_reason": "string",\n'
                '    "visual_spec": {},\n'
                '    "diagram": ""\n'
                '}\n'
                "No markdown fences. No extra fields. Only this exact structure."
            )
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
                timeout=10.0,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean JSON
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            result = json.loads(content.strip())
            
            # VALIDATE schema - if wrong schema, return None
            # so router falls back to deterministic
            if not self._validate_schema(result):
                print(f"[GroqProvider] Schema mismatch: {list(result.keys())}")
                return None
            
            return result
        
        except Exception as e:
            print(f"[GroqProvider] Error: {e}")
            return None
    
    def _validate_schema(self, result: Dict[str, Any]) -> bool:
        """
        Validate that result matches expected schema.
        
        Required fields: title, bullets
        """
        required_fields = ["title", "bullets"]
        
        for field in required_fields:
            if field not in result:
                return False
        
        # bullets must be a list
        if not isinstance(result.get("bullets"), list):
            return False
        
        # title must be string
        if not isinstance(result.get("title"), str):
            return False
        
        return True
    
    def health_check(self) -> bool:
        return bool(self.api_key)
    
    def supports_json_schema(self) -> bool:
        return False
    
    def estimated_latency_ms(self) -> int:
        return 500
    
    def provider_name(self) -> str:
        return "groq"
    
    def model_name(self) -> str:
        return self.model