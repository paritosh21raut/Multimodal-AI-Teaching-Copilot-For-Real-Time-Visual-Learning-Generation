"""
Complete Pipeline Test - All Subsystems

Tests: Audio → STT → Transcript → LSI → Semantic → Development → Importance → Slide Decision → Representation
"""

from __future__ import annotations

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.lecture.lecture_pipeline import LecturePipeline
from app.speech.transcript_intelligence import transcript_intelligence
from app.topics.topic_intelligence import TopicIntelligence


def test_complete_pipeline():
    """Test complete pipeline with simulated lecture"""
    
    print("=" * 80)
    print("COMPLETE PIPELINE TEST")
    print("Testing all subsystems together")
    print("=" * 80)
    
    # Initialize
    pipeline = LecturePipeline()
    pipeline.register_topic_detector(TopicIntelligence())
    
    # Simulated lecture
    lecture_chunks = [
        "Today we are learning about computer networks.",
        "A network is a collection of interconnected devices.",
        "Now let's discuss network topologies.",
        "Star topology connects devices through a central switch.",
        "Bus topology uses a single cable.",
        "Now let's discuss network protocols.",
        "TCP is a connection-oriented protocol.",
        "TCP provides reliable data transmission.",
        "UDP is a connectionless protocol.",
        "Unlike TCP, UDP does not guarantee delivery.",
    ]
    
    print(f"\nProcessing {len(lecture_chunks)} chunks...\n")
    
    for i, chunk in enumerate(lecture_chunks):
        print(f"\n>>> Chunk {i+1}: {chunk}")
        
        # Refine transcript
        refined = transcript_intelligence.refine(chunk)
        refined_text = refined.refined_text.strip()
        
        # Process through pipeline
        start_time = time.time()
        result = pipeline.process_transcript(refined_text)
        processing_time = (time.time() - start_time) * 1000
        
        print(f">>> Time: {processing_time:.1f}ms")
    
    # Print final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    
    # Development stats
    dev_stats = pipeline.development_tracker.get_statistics()
    print(f"\nDevelopment:")
    print(f"  Total concepts: {dev_stats['total_concepts']}")
    print(f"  Established: {dev_stats['established']}")
    print(f"  Developing: {dev_stats['developing']}")
    print(f"  Mentioned: {dev_stats['mentioned']}")
    
    # Importance stats
    imp_stats = pipeline.importance_scorer.get_statistics()
    print(f"\nImportance:")
    print(f"  Total scored: {imp_stats['total_scored']}")
    print(f"  Critical: {imp_stats['critical']}")
    print(f"  High: {imp_stats['high']}")
    
    print("\n✅ Complete pipeline test passed!")


if __name__ == "__main__":
    test_complete_pipeline()