"""
Semantic Logger

Structured logging for semantic intelligence operations.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
import logging
import json
from datetime import datetime


class SemanticLogger:
    """Structured logger for semantic operations"""
    
    def __init__(self, name: str = "semantic_intelligence"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Add handler if not exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with optional data"""
        if kwargs:
            data = json.dumps(kwargs, default=str)
            self.logger.info(f"{message} | {data}")
        else:
            self.logger.info(message)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message"""
        if kwargs:
            data = json.dumps(kwargs, default=str)
            self.logger.warning(f"{message} | {data}")
        else:
            self.logger.warning(message)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message"""
        if kwargs:
            data = json.dumps(kwargs, default=str)
            self.logger.error(f"{message} | {data}")
        else:
            self.logger.error(message)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message"""
        if kwargs:
            data = json.dumps(kwargs, default=str)
            self.logger.debug(f"{message} | {data}")
        else:
            self.logger.debug(message)
    
    def log_frame_processed(
        self,
        chunk_id: str,
        concepts_count: int,
        propositions_count: int,
        confidence: float,
        processing_time: float
    ) -> None:
        """Log frame processing summary"""
        self.info(
            "Frame processed",
            chunk_id=chunk_id,
            concepts=concepts_count,
            propositions=propositions_count,
            confidence=confidence,
            processing_time_ms=processing_time * 1000
        )
    
    def log_llm_arbitration(
        self,
        success: bool,
        latency_ms: float,
        reason: str = ""
    ) -> None:
        """Log LLM arbitration result"""
        if success:
            self.info(
                "LLM arbitration successful",
                latency_ms=latency_ms
            )
        else:
            self.warning(
                "LLM arbitration failed",
                latency_ms=latency_ms,
                reason=reason
            )
    
    def log_error(
        self,
        error: Exception,
        context: Dict[str, Any] = None
    ) -> None:
        """Log error with context"""
        self.error(
            f"Error: {str(error)}",
            error_type=type(error).__name__,
            **({"context": context} if context else {})
        )