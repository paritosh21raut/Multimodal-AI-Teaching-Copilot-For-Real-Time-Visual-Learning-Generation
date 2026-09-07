"""
Live Test - Complete Pipeline Without PPT

Tests: Audio → STT → Transcript Intelligence → Topic Intelligence → Semantic Intelligence
Skips: Content Generator → Slide Manager → PPT
"""

from __future__ import annotations

import sys
import os
import time
import threading
from typing import Optional, Dict, Any

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.speech.transcript_intelligence import transcript_intelligence
from app.topics.topic_intelligence import TopicIntelligence, StructuralDecision
from app.semantic.semantic_pipeline import SemanticPipeline


class LiveLectureTester:
    """Tests complete pipeline without PPT generation"""
    
    def __init__(self):
        # Initialize TopicIntelligence instance
        self.topic_intelligence = TopicIntelligence(
            model_name="all-MiniLM-L6-v2",
            new_topic_threshold=0.55,
            irrelevant_threshold=0.30,
            subtopic_threshold=0.45,
            centroid_update_weight=0.15
        )
        
        self.transcript_intelligence = transcript_intelligence
        self.semantic_pipeline = SemanticPipeline()
        
        # State
        self.current_topic = None
        self.current_embedding = None
        self.context = ""
        self.chunk_count = 0
        self.total_processing_time = 0.0
        
        # Results log
        self.results = []
    
    def process_transcript(self, transcript: str) -> Dict[str, Any]:
        """Process a refined transcript through the pipeline"""
        
        transcript = transcript.strip()
        if not transcript:
            return {"error": "empty transcript"}
        
        start_time = time.time()
        
        # ==========================================
        # Step 1: Topic Intelligence (LSI)
        # ==========================================
        topic_decision = self.topic_intelligence.process(
            latest_text=transcript,
            rolling_context=self.context,
            current_topic=self.current_topic,
            current_embedding=self.current_embedding
        )
        
        # Skip irrelevant speech
        if not topic_decision.is_relevant:
            return {
                "is_relevant": False,
                "reason": topic_decision.reason,
                "structural_decision": topic_decision.structural_decision,
                "processing_time_ms": (time.time() - start_time) * 1000
            }
        
        # Update context
        self.context = f"{self.context} {transcript}".strip()
        
        # ==========================================
        # Step 2: Semantic Intelligence
        # ==========================================
        semantic_result = self.semantic_pipeline.process_transcript(
            transcript_text=transcript,
            chunk_id=f"chunk_{self.chunk_count}",
            lecture_id="live_test_lecture",
            topic_path=str(topic_decision.topic),
            generate_embeddings=False  # Disable for speed
        )
        
        # Update state
        self.current_topic = topic_decision.topic
        self.current_embedding = topic_decision.embedding
        self.chunk_count += 1
        
        processing_time = time.time() - start_time
        self.total_processing_time += processing_time
        
        # Build result
        result = {
            "is_relevant": True,
            "chunk_id": self.chunk_count,
            "transcript": transcript,
            "topic": topic_decision.topic,
            "structural_decision": topic_decision.structural_decision,
            "semantic_concepts": [],
            "semantic_propositions": [],
            "confidence": topic_decision.confidence,
            "processing_time_ms": processing_time * 1000
        }
        
        if semantic_result and semantic_result.get("frame"):
            frame = semantic_result["frame"]
            result["semantic_concepts"] = [
                c.canonical_name for c in frame.concepts
            ]
            result["semantic_propositions"] = [
                f"{p.subject.canonical_name} {p.predicate.value} {p.object.canonical_name}"
                if p.subject and p.object and p.predicate
                else str(p.proposition_id)
                for p in frame.propositions
            ]
        
        self.results.append(result)
        return result
    
    def print_result(self, result: Dict[str, Any]) -> None:
        """Pretty print a result"""
        print("\n" + "=" * 80)
        print(f"CHUNK #{result.get('chunk_id', '?')}")
        print("=" * 80)
        
        if not result.get("is_relevant", False):
            print(f"❌ IRRELEVANT: {result.get('reason', '')}")
            print(f"   Decision: {result.get('structural_decision', '')}")
            print(f"   Time: {result.get('processing_time_ms', 0):.1f}ms")
            return
        
        print(f"📝 TRANSCRIPT: {result['transcript'][:80]}")
        print(f"📚 TOPIC: {result['topic']}")
        print(f"🔀 STRUCTURE: {result['structural_decision']}")
        print(f"⏱️  TIME: {result['processing_time_ms']:.1f}ms")
        
        concepts = result.get("semantic_concepts", [])
        if concepts:
            print(f"🧠 CONCEPTS ({len(concepts)}):")
            for i, c in enumerate(concepts[:10], 1):
                print(f"   {i}. {c}")
        
        propositions = result.get("semantic_propositions", [])
        if propositions:
            print(f"💡 PROPOSITIONS ({len(propositions)}):")
            for i, p in enumerate(propositions[:5], 1):
                print(f"   {i}. {p}")
    
    def print_summary(self) -> None:
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        total_chunks = self.chunk_count
        relevant_chunks = len(self.results)
        avg_time = self.total_processing_time / max(1, total_chunks) * 1000
        
        print(f"Total chunks processed: {total_chunks}")
        print(f"Relevant chunks: {relevant_chunks}")
        print(f"Average processing time: {avg_time:.1f}ms")
        
        # Semantic stats
        semantic_stats = self.semantic_pipeline.get_statistics()
        if "semantic_memory" in semantic_stats:
            mem = semantic_stats["semantic_memory"]
            if "registry" in mem:
                print(f"Total concepts: {mem['registry'].get('total_concepts', 0)}")
                print(f"Total mentions: {mem['registry'].get('total_mentions', 0)}")
        
        # Topic stats
        topics = set(r.get("topic", "") for r in self.results)
        print(f"\nTopics detected:")
        for topic in topics:
            print(f"   - {topic}")


def simulate_live_test():
    """Simulate a live lecture without actual audio"""
    
    print("=" * 80)
    print("LIVE LECTURE TEST - SIMULATION")
    print("=" * 80)
    print("Testing: Transcript → Topic Intelligence → Semantic Intelligence")
    print("Skipping: PPT Generation, Content Generator")
    print("=" * 80)
    
    tester = LiveLectureTester()
    
    # Simulated lecture transcript chunks (as if from Whisper)
    lecture_chunks = [
        # Introduction
        "Today we are learning about computer networks.",
        "A computer network is a collection of interconnected devices.",
        
        # Network topologies
        "Now let's discuss network topologies.",
        "Star topology connects all devices through a central switch.",
        "In a star topology, if one cable fails, only that device is affected.",
        "Bus topology uses a single cable to connect all devices.",
        
        # Network protocols
        "Now let's discuss network protocols.",
        "TCP is a connection-oriented protocol.",
        "TCP provides reliable data transmission.",
        "It uses acknowledgements to ensure delivery.",
        "For example, TCP uses a three-way handshake to establish connections.",
        "UDP is a connectionless protocol.",
        "Unlike TCP, UDP does not guarantee delivery.",
        
        # OSI Model
        "Now let's look at the OSI model.",
        "The OSI model has seven layers.",
        "The physical layer deals with raw bit transmission.",
        "The data link layer provides error detection.",
        "The network layer handles routing and addressing.",
        "The transport layer provides end-to-end communication.",
        
        # Summary
        "To summarize, networks connect devices and protocols define communication rules.",
        
        # Chatter (should be filtered)
        "Can you hear me in the back?",
    ]
    
    print("\n🎤 SIMULATING LIVE LECTURE...\n")
    
    for i, chunk in enumerate(lecture_chunks):
        print(f"\n>>> Processing chunk {i+1}/{len(lecture_chunks)}")
        print(f">>> Raw transcript: {chunk}")
        
        # Simulate Transcript Intelligence refinement
        refined = tester.transcript_intelligence.refine(
            chunk,
            context=tester.context
        )
        
        refined_text = refined.refined_text.strip()
        
        if refined_text != chunk:
            print(f">>> Refined: {refined_text}")
        
        # Process through pipeline
        result = tester.process_transcript(refined_text)
        
        # Print result
        tester.print_result(result)
        
        # Small delay to simulate real-time
        time.sleep(0.1)
    
    # Print summary
    tester.print_summary()
    
    return tester


if __name__ == "__main__":
    tester = simulate_live_test()
    
    print("\n✅ LIVE TEST COMPLETE!")
    print("\nNext steps:")
    print("1. Review the output above")
    print("2. Check that topics are correctly identified")
    print("3. Check that concepts are extracted")
    print("4. Check that propositions are generated")
    print("5. Check that irrelevant chatter is filtered")