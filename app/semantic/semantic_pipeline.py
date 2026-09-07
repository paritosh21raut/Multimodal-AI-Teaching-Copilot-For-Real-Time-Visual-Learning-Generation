"""
Semantic Pipeline (Fixed)

Complete production-ready pipeline combining all components.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
import time
import threading

from .semantic_models import SemanticFrame
from .semantic_intelligence import SemanticIntelligence
from .semantic_integration import SemanticIntegration
from .logger import SemanticLogger
from .performance_monitor import PerformanceMonitor
from .config import SemanticConfig


class SemanticPipeline:
    """Production-ready semantic processing pipeline"""
    
    def __init__(self, config: Optional[SemanticConfig] = None):
        self.config = config or SemanticConfig()
        self.logger = SemanticLogger()
        self.monitor = PerformanceMonitor()
        
        # Initialize components
        self.semantic_intelligence = SemanticIntelligence(
            groq_api_key=self.config.groq_api_key,
            enable_llm=self.config.enable_llm
        )
        
        self.semantic_integration = SemanticIntegration()
        
        # Thread safety
        self._lock = threading.RLock()
    
    def process_transcript(
        self,
        transcript_text: str,
        chunk_id: str = "",
        lecture_id: str = "",
        topic_path: str = "",
        asr_confidence: Optional[float] = None,
        generate_embeddings: Optional[bool] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Process a transcript chunk through the complete pipeline.
        
        Returns:
            Dictionary with semantic frame and slide-ready content,
            or None if transcript is empty.
        """
        with self._lock:
            # Early return for empty transcript
            if not transcript_text or not transcript_text.strip():
                return None
            
            start_time = time.time()
            
            try:
                # Process through semantic intelligence
                self.monitor.start_operation("semantic_processing")
                
                # Use provided generate_embeddings or config default
                use_embeddings = (
                    generate_embeddings
                    if generate_embeddings is not None
                    else self.config.generate_embeddings
                )
                
                frame = self.semantic_intelligence.process(
                    transcript_text=transcript_text,
                    chunk_id=chunk_id,
                    lecture_id=lecture_id,
                    topic_path=topic_path,
                    asr_confidence=asr_confidence,
                    generate_embeddings=use_embeddings
                )
                
                processing_time = time.time() - start_time
                self.monitor.end_operation()
                self.monitor.record_frame_processing(processing_time)
                
                # Update integration layer
                self.semantic_integration.process_frame(frame)
                
                # Prepare slide content if we have concepts/propositions
                slide_content = None
                if frame.concepts or frame.propositions:
                    topic = ""
                    if frame.structural_context and "topic" in frame.structural_context:
                        topic = frame.structural_context["topic"]
                    
                    slide_content = self.semantic_integration.prepare_slide_content(
                        topic=topic or topic_path,
                        concepts=frame.concepts,
                        propositions=frame.propositions,
                        instructional_acts=frame.instructional_acts,
                        relations=frame.relations
                    )
                
                # Log processing
                self.logger.log_frame_processed(
                    chunk_id=chunk_id,
                    concepts_count=len(frame.concepts),
                    propositions_count=len(frame.propositions),
                    confidence=frame.frame_confidence.overall,
                    processing_time=processing_time
                )
                
                # Return result
                result = {
                    "frame": frame,
                    "slide_content": slide_content,
                    "processing_time_ms": processing_time * 1000,
                    "statistics": self.monitor.get_statistics()
                }
                
                return result
            
            except Exception as e:
                self.monitor.record_error()
                self.logger.log_error(e, {
                    "chunk_id": chunk_id,
                    "lecture_id": lecture_id
                })
                
                # Graceful degradation - return None
                return None
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get health report"""
        return self.monitor.get_health_report()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        stats = {
            "performance": self.monitor.get_statistics(),
            "semantic_memory": self.semantic_intelligence.get_memory_statistics()
        }
        return stats
    
    def get_semantic_summary(self) -> Dict[str, Any]:
        """Get semantic summary for downstream systems"""
        summary = self.semantic_integration.get_semantic_summary(
            concepts=self.semantic_intelligence.get_all_concepts(),
            propositions=list(self.semantic_intelligence.semantic_memory._propositions.values()),
            active_concepts=self.semantic_intelligence.semantic_memory.active_context.get_concept_refs(
                self.semantic_intelligence.semantic_memory.registry
            )
        )
        
        return {
            "active_concepts": summary.active_concepts,
            "top_developed": summary.top_developed_concepts,
            "top_important": summary.top_important_concepts,
            "active_propositions_count": len(summary.active_propositions),
            "statistics": summary.statistics
        }
    
    def reset(self) -> None:
        """Reset pipeline state"""
        with self._lock:
            self.semantic_intelligence = SemanticIntelligence(
                groq_api_key=self.config.groq_api_key,
                enable_llm=self.config.enable_llm
            )
            self.semantic_integration = SemanticIntegration()
            self.monitor = PerformanceMonitor()
            
            self.logger.info("Pipeline reset")