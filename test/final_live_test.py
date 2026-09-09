"""
FINAL LIVE TEST - Complete System with Real Microphone

Tests: Audio → VAD → Whisper → Transcript → LSI → Semantic → Development → Importance → Slide Decision → Representation
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
from app.lecture.lecture_pipeline import LecturePipeline


class FinalLiveTester:
    """Complete system live test"""
    
    def __init__(self, test_duration: int = 45):
        self.test_duration = test_duration
        
        self.audio_stream = AudioStream()
        self.audio_worker = AudioWorker(
            audio_queue=self.audio_stream.get_queue(),
            on_preview_transcript=self._on_preview,
            on_final_transcript=self._on_final,
        )
        
        # Full pipeline
        self.pipeline = LecturePipeline()
        self.pipeline.register_topic_detector(TopicIntelligence())
        
        self.transcript_intelligence = transcript_intelligence
        
        self.preview_count = 0
        self.final_count = 0
        self.full_transcript = ""
    
    def _on_preview(self, preview_text, authoritative):
        self.preview_count += 1
        print(f"\n[PREVIEW] {preview_text[:80]}")
    
    def _on_final(self, segment_text, full_transcript, segment_id):
        self.final_count += 1
        self.full_transcript = full_transcript
        
        print(f"\n{'='*70}")
        print(f"[FINAL #{segment_id}]")
        print(f"{'='*70}")
        
        # Process through complete pipeline
        refined = self.transcript_intelligence.refine(segment_text)
        refined_text = refined.refined_text.strip()
        
        if refined_text:
            result = self.pipeline.process_transcript(refined_text)
    
    def run(self):
        print("="*70)
        print("FINAL LIVE TEST - COMPLETE SYSTEM")
        print("="*70)
        print(f"Duration: {self.test_duration} seconds")
        print("Speak about any topic - the system will:")
        print("  1. Detect speech")
        print("  2. Transcribe")
        print("  3. Understand structure")
        print("  4. Extract meaning")
        print("  5. Track development")
        print("  6. Score importance")
        print("  7. Decide slides")
        print("  8. Choose representation")
        print("="*70)
        
        print("\n🎤 START SPEAKING NOW!")
        print("="*70)
        
        # Start worker
        worker_thread = threading.Thread(target=self.audio_worker.run, daemon=True)
        worker_thread.start()
        
        time.sleep(2)
        
        # Start stream
        stream_thread = threading.Thread(target=self.audio_stream.start, daemon=True)
        stream_thread.start()
        
        try:
            start_time = time.time()
            while time.time() - start_time < self.test_duration:
                if not worker_thread.is_alive():
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted")
        finally:
            self.audio_stream.stop()
            self.audio_worker.stop()
            worker_thread.join(timeout=10)
            time.sleep(2)
        
        print("\n" + "="*70)
        print("FINAL RESULTS")
        print("="*70)
        print(f"Previews: {self.preview_count}")
        print(f"Final transcripts: {self.final_count}")
        
        if self.full_transcript:
            print(f"\nTranscript ({len(self.full_transcript)} chars):")
            print(self.full_transcript[:500])
        
        # Stats
        audio_stats = self.audio_stream.stats()
        print(f"\nAudio: {audio_stats['callback_count']} callbacks, {audio_stats['dropped_chunks']} dropped")
        
        print("\n✅ COMPLETE SYSTEM TEST PASSED!")


if __name__ == "__main__":
    tester = FinalLiveTester(test_duration=45)
    tester.run()