"""
Semantic Intelligence Configuration

Production configuration management.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
import os
import json


class SemanticConfig:
    """Configuration for semantic intelligence"""
    
    def __init__(self):
        # Embedding settings
        self.embedding_model = "all-MiniLM-L6-v2"
        self.generate_embeddings = True
        
        # Entity resolution
        self.exact_match_threshold = 1.0
        self.normalized_match_threshold = 0.85
        self.embedding_match_threshold = 0.80
        self.ambiguity_margin = 0.03
        
        # Coreference
        self.min_pronoun_confidence = 0.5
        self.min_np_confidence = 0.5
        
        # Validation
        self.min_evidence_coverage = 0.5
        self.min_extraction_confidence = 0.4
        self.max_unsupported_propositions = 0.3
        
        # LLM arbitration
        self.enable_llm = True
        self.llm_model = "llama-3.1-8b-instant"
        self.llm_max_calls_per_minute = 30
        self.llm_timeout_seconds = 3.0
        
        # Performance
        self.max_recent_frames = 10
        self.active_context_window = 10
        self.max_concepts_per_frame = 50
        self.max_propositions_per_frame = 50
        
        # Load from environment
        self._load_from_env()
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables"""
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        
        # Optional overrides
        if os.getenv("SEMANTIC_EMBEDDING_MODEL"):
            self.embedding_model = os.getenv("SEMANTIC_EMBEDDING_MODEL")
        
        if os.getenv("SEMANTIC_ENABLE_LLM"):
            self.enable_llm = os.getenv("SEMANTIC_ENABLE_LLM").lower() == "true"
        
        if os.getenv("SEMANTIC_LLM_MODEL"):
            self.llm_model = os.getenv("SEMANTIC_LLM_MODEL")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "embedding_model": self.embedding_model,
            "generate_embeddings": self.generate_embeddings,
            "exact_match_threshold": self.exact_match_threshold,
            "normalized_match_threshold": self.normalized_match_threshold,
            "embedding_match_threshold": self.embedding_match_threshold,
            "ambiguity_margin": self.ambiguity_margin,
            "min_pronoun_confidence": self.min_pronoun_confidence,
            "min_np_confidence": self.min_np_confidence,
            "min_evidence_coverage": self.min_evidence_coverage,
            "min_extraction_confidence": self.min_extraction_confidence,
            "enable_llm": self.enable_llm,
            "llm_model": self.llm_model,
            "llm_max_calls_per_minute": self.llm_max_calls_per_minute,
            "llm_timeout_seconds": self.llm_timeout_seconds,
            "max_recent_frames": self.max_recent_frames
        }