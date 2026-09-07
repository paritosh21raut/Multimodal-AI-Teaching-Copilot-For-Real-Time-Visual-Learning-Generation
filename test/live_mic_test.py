"""
Live Microphone Test (Fixed v2)

Fixed: Actually starts the audio stream.
"""

from __future__ import annotations

import sys
import os
import time
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.audio.audio_stream import AudioStream
from app.audio.audio_worker import AudioWorker
from app.speech.transcript_intelligence import transcript_intelligence
from app.topics.topic_intelligence import TopicIntelligence
from app.semantic.semantic_pipeline import SemanticPipeline


class LiveMicTester:
    def __init__(self, test_duration_seconds: int = 30):
        self.test_duration = test_duration_seconds
        
        self.audio_stream = AudioStream()
        
        self.audio_worker = AudioWorker(
            audio_queue=self.audio_stream.get_queue(),
            on_preview_transcript=self._on_preview,
            on_final_transcript=self._on_final,
        )
        
        self.transcript_intelligence = transcript_intelligence
        self.topic_intelligence = TopicIntelligence()
        self.semantic_pipeline = SemanticPipeline()
        
        self.current_topic = None
        self.current_embedding = None
        self.context = ""
        self.chunk_count = 0
        self.full_transcript = ""
        
        self.preview_count = 0
        self.final_count = 0
    
    def _on_preview(self, preview_text: str, authoritative: str):
        self.preview_count += 1
        print(f"\n[PREVIEW] {preview_text[:100]}")
    
    def _on_final(self, segment_text: str, full_transcript: str, segment_id: int):
        self.final_count += 1
        self.full_transcript = full_transcript
        
        print(f"\n{'='*70}")
        print(f"[FINAL #{segment_id}] {segment_text}")
        print(f"{'='*70}")
        
        self._process_transcript(segment_text)
    
    def _process_transcript(self, text: str):
        refined = self.transcript_intelligence.refine(text, context=self.context)
        refined_text = refined.refined_text.strip()
        
        if not refined_text:
            return
        
        topic_decision = self.topic_intelligence.process(
            latest_text=refined_text,
            rolling_context=self.context,
            current_topic=self.current_topic,
            current_embedding=self.current_embedding,
        )
        
        if not topic_decision.is_relevant:
            print(f"[LSI] IRRELEVANT: {topic_decision.reason}")
            return
        
        self.current_topic = topic_decision.topic
        self.current_embedding = topic_decision.embedding
        self.context = f"{self.context} {refined_text}".strip()
        self.chunk_count += 1
        
        semantic_result = self.semantic_pipeline.process_transcript(
            transcript_text=refined_text,
            chunk_id=f"chunk_{self.chunk_count}",
            lecture_id="live_mic_test",
            topic_path=str(topic_decision.topic),
            generate_embeddings=False,
        )
        
        print(f"[TOPIC] {topic_decision.topic}")
        print(f"[STRUCTURE] {topic_decision.structural_decision}")
        
        if semantic_result and semantic_result.get("frame"):
            frame = semantic_result["frame"]
            
            if frame.concepts:
                print(f"[CONCEPTS] {', '.join(c.canonical_name for c in frame.concepts[:5])}")
    
    def run(self):
        print("="*70)
        print("LIVE MICROPHONE TEST")
        print("="*70)
        print(f"Duration: {self.test_duration} seconds")
        print("="*70)
        
        print("\n🎤 Starting microphone...")
        print("SPEAK NOW!")
        print("="*70)
        
        # Start worker thread
        worker_thread = threading.Thread(
            target=self.audio_worker.run,
            daemon=True,
            name="AudioWorker",
        )
        worker_thread.start()
        
        # Wait for worker to start
        time.sleep(2)
        
        # Start audio stream (THIS IS THE KEY - it blocks)
        try:
            # Run stream for test duration
            start_time = time.time()
            
            # Start stream in a separate thread so we can stop it
            stream_thread = threading.Thread(
                target=self.audio_stream.start,
                daemon=True,
                name="AudioStream",
            )
            stream_thread.start()
            
            # Wait for test duration
            while time.time() - start_time < self.test_duration:
                if not worker_thread.is_alive():
                    print("❌ Worker died!")
                    break
                time.sleep(1)
            
            # Stop the stream
            self.audio_stream.stop()
            
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted")
            self.audio_stream.stop()
        
        finally:
            # Stop worker
            self.audio_worker.stop()
            worker_thread.join(timeout=10)
            
            time.sleep(1)
            
            print("\n" + "="*70)
            print("RESULTS")
            print("="*70)
            print(f"Previews: {self.preview_count}")
            print(f"Finals: {self.final_count}")
            print(f"Chunks: {self.chunk_count}")
            
            if self.full_transcript:
                print(f"\nTranscript:\n{self.full_transcript[:500]}")
            
            audio_stats = self.audio_stream.stats()
            print(f"\nAudio: {audio_stats['callback_count']} callbacks, {audio_stats['dropped_chunks']} dropped")
            
            worker_metrics = self.audio_worker.get_metrics()
            print(f"Speech chunks: {worker_metrics['speech_chunks']}")
            print(f"Segments: {worker_metrics['segments_finalized']}")
            
            print("\n✅ Test complete!")


if __name__ == "__main__":
    tester = LiveMicTester(test_duration_seconds=30)
    tester.run()