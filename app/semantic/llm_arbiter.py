"""
LLM Arbiter (Groq Integration)

Handles ambiguous semantic cases using Groq's free LLM API.
Strict schema validation ensures LLM output is safe.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
import os
import json
import re
import time
from datetime import datetime, timedelta

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from .semantic_models import (
    Concept,
    ConceptRef,
    Proposition,
    RelationType,
    GroundingStatus,
    ExtractionStatus,
    SemanticFrame
)


class LLMArbiter:
    """Arbitrates ambiguous semantic cases using Groq"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen/qwen3.8-27b"
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"
        
        # Rate limiting
        self.max_calls_per_minute = 30
        self._call_times: List[datetime] = []
        
        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        
        # Lazy-load client
        self._client = None
    
    def _get_client(self):
        """Lazy-load OpenAI client for Groq"""
        if not HAS_OPENAI:
            raise ImportError("openai package not installed. Run: pip install openai")
        
        if self._client is None:
            if not self.api_key:
                raise ValueError("GROQ_API_KEY not set")
            
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        
        return self._client
    
    def should_arbitrate(
        self,
        frame: SemanticFrame,
        confidence: float
    ) -> bool:
        """
        Determine if LLM arbitration is needed.
        
        Only arbitrate if:
        1. Confidence is low (< 0.6)
        2. Content is important (has concepts/propositions)
        3. Rate limit not exceeded
        """
        # High confidence - no arbitration needed
        if confidence > 0.6:
            return False
        
        # No content to arbitrate
        if not frame.concepts and not frame.propositions:
            return False
        
        # Check rate limit
        if not self._check_rate_limit():
            return False
        
        return True
    
    def arbitrate_coreference(
        self,
        mention_text: str,
        candidates: List[ConceptRef],
        context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Arbitrate ambiguous coreference.
        
        Returns:
            {"concept_id": str, "confidence": float} or None
        """
        if not candidates or len(candidates) < 2:
            return None
        
        # Build prompt
        prompt = self._build_coreference_prompt(
            mention_text,
            candidates,
            context
        )
        
        # Call LLM
        response = self._call_llm(prompt)
        
        if response is None:
            return None
        
        # Parse and validate response
        return self._parse_coreference_response(response, candidates)
    
    def arbitrate_relation(
        self,
        subject: str,
        object_text: str,
        context: str = ""
    ) -> Optional[RelationType]:
        """
        Arbitrate ambiguous relation type.
        
        Returns:
            RelationType or None
        """
        prompt = self._build_relation_prompt(
            subject,
            object_text,
            context
        )
        
        response = self._call_llm(prompt)
        
        if response is None:
            return None
        
        return self._parse_relation_response(response)
    
    def arbitrate_entity_merge(
        self,
        mention_text: str,
        candidates: List[ConceptRef],
        context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Arbitrate whether mention should merge with existing concept.
        
        Returns:
            {"should_merge": bool, "concept_id": str, "confidence": float}
        """
        if not candidates:
            return None
        
        prompt = self._build_entity_merge_prompt(
            mention_text,
            candidates,
            context
        )
        
        response = self._call_llm(prompt)
        
        if response is None:
            return None
        
        return self._parse_entity_merge_response(response, candidates)
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call Groq LLM with timeout and validation"""
        if not self._check_rate_limit():
            return None
        
        try:
            client = self._get_client()
            
            self._call_times.append(datetime.now())
            self.total_calls += 1
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a semantic analysis assistant. "
                            "Respond with ONLY valid JSON. "
                            "No explanations, no markdown, just JSON."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,  # Deterministic
                max_tokens=100,
                timeout=3.0  # 3 second timeout
            )
            
            content = response.choices[0].message.content.strip()
            self.successful_calls += 1
            
            return content
        
        except Exception as e:
            self.failed_calls += 1
            print(f"LLM call failed: {e}")
            return None
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows another call"""
        current_time = datetime.now()
        
        # Remove calls older than 1 minute
        self._call_times = [
            t for t in self._call_times
            if current_time - t < timedelta(minutes=1)
        ]
        
        return len(self._call_times) < self.max_calls_per_minute
    
    def _build_coreference_prompt(
        self,
        mention_text: str,
        candidates: List[ConceptRef],
        context: str
    ) -> str:
        """Build prompt for coreference arbitration"""
        candidate_list = "\n".join([
            f"- {c.canonical_name} (ID: {c.concept_id})"
            for c in candidates
        ])
        
        return f"""
Resolve the coreference for: "{mention_text}"

Context: {context if context else "No context available"}

Candidate concepts:
{candidate_list}

Which concept does the mention refer to?

Respond with JSON:
{{
    "concept_id": "chosen_concept_id",
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}

If uncertain, set confidence below 0.6.
"""
    
    def _build_relation_prompt(
        self,
        subject: str,
        object_text: str,
        context: str
    ) -> str:
        """Build prompt for relation arbitration"""
        valid_relations = [r.value for r in RelationType]
        
        return f"""
Determine the relationship between:
Subject: {subject}
Object: {object_text}

Context: {context if context else "No context"}

Valid relations: {", ".join(valid_relations)}

Respond with JSON:
{{
    "relation": "RELATION_TYPE",
    "confidence": 0.0-1.0
}}
"""
    
    def _build_entity_merge_prompt(
        self,
        mention_text: str,
        candidates: List[ConceptRef],
        context: str
    ) -> str:
        """Build prompt for entity merge arbitration"""
        candidate_list = "\n".join([
            f"- {c.canonical_name} (ID: {c.concept_id})"
            for c in candidates
        ])
        
        return f"""
Should the mention "{mention_text}" be merged with an existing concept?

Context: {context if context else "No context"}

Existing concepts:
{candidate_list}

Respond with JSON:
{{
    "should_merge": true/false,
    "concept_id": "concept_id_if_merge",
    "confidence": 0.0-1.0
}}
"""
    
    def _parse_coreference_response(
        self,
        response: str,
        candidates: List[ConceptRef]
    ) -> Optional[Dict[str, Any]]:
        """Parse and validate coreference response"""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return None
            
            data = json.loads(json_match.group(0))
            
            concept_id = data.get("concept_id", "")
            confidence = float(data.get("confidence", 0.0))
            
            # Validate concept_id is in candidates
            valid_ids = [c.concept_id for c in candidates]
            if concept_id not in valid_ids:
                return None
            
            # Validate confidence
            if confidence < 0.6:
                return None  # Too uncertain
            
            return {
                "concept_id": concept_id,
                "confidence": min(1.0, confidence),
                "reason": data.get("reason", "")
            }
        
        except (json.JSONDecodeError, ValueError, KeyError):
            return None
    
    def _parse_relation_response(
        self,
        response: str
    ) -> Optional[RelationType]:
        """Parse and validate relation response"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return None
            
            data = json.loads(json_match.group(0))
            
            relation_str = data.get("relation", "")
            confidence = float(data.get("confidence", 0.0))
            
            if confidence < 0.6:
                return None
            
            # Validate relation is in controlled vocabulary
            try:
                return RelationType(relation_str)
            except ValueError:
                return None
        
        except (json.JSONDecodeError, ValueError, KeyError):
            return None
    
    def _parse_entity_merge_response(
        self,
        response: str,
        candidates: List[ConceptRef]
    ) -> Optional[Dict[str, Any]]:
        """Parse and validate entity merge response"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return None
            
            data = json.loads(json_match.group(0))
            
            should_merge = data.get("should_merge", False)
            confidence = float(data.get("confidence", 0.0))
            
            if not should_merge or confidence < 0.6:
                return {
                    "should_merge": False,
                    "confidence": 0.0
                }
            
            concept_id = data.get("concept_id", "")
            valid_ids = [c.concept_id for c in candidates]
            
            if concept_id not in valid_ids:
                return None
            
            return {
                "should_merge": True,
                "concept_id": concept_id,
                "confidence": min(1.0, confidence)
            }
        
        except (json.JSONDecodeError, ValueError, KeyError):
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get arbitration statistics"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": (
                self.successful_calls / self.total_calls
                if self.total_calls > 0 else 0.0
            )
        }