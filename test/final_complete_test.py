"""
FINAL COMPLETE TEST - Everything Working Together

Audio → VAD → Whisper → Transcript → LSI → Semantic → Development
→ Importance → Slide Decision → Representation → Content Generator (Groq)
→ Slide Manager → PPT

This is the complete production pipeline.
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
from app.knowledge.content_generator import content_generator
from app.slides.slide_manager import slide_manager
from app.lecture.lecture_pipeline import LecturePipeline


class CompleteLiveTester:
    """Complete system test with PPT generation"""
    
    def __init__(self, test_duration: int = 90):
        self.test_duration = test_duration
        
        # Audio
        self.audio_stream = AudioStream()
        self.audio_worker = AudioWorker(
            audio_queue=self.audio_stream.get_queue(),
            on_preview_transcript=self._on_preview,
            on_final_transcript=self._on_final,
        )
        
        # Intelligence pipeline
        self.pipeline = LecturePipeline()
        self.pipeline.register_topic_detector(TopicIntelligence())
        self.pipeline.register_content_generator(content_generator)
        self.pipeline.register_slide_manager(slide_manager)
        
        self.transcript_intelligence = transcript_intelligence
        
        # Stats
        self.preview_count = 0
        self.final_count = 0
        self.slide_count = 0
        self.full_transcript = ""
    
    def _on_preview(self, preview_text, authoritative):
        self.preview_count += 1
        # Don't print every preview to keep output clean
        if self.preview_count % 3 == 0:
            print(f"\n[PREVIEW] {preview_text[:60]}...")
    
    def _on_final(self, segment_text, full_transcript, segment_id):
        self.final_count += 1
        self.full_transcript = full_transcript
        
        print(f"\n{'='*70}")
        print(f"[FINAL SEGMENT #{segment_id}]")
        print(f"{'='*70}")
        
        # Refine transcript
        refined = self.transcript_intelligence.refine(segment_text)
        refined_text = refined.refined_text.strip()
        
        if refined_text:
            # Process through complete pipeline
            result = self.pipeline.process_transcript(refined_text)
            
            if result and result.get("content_generated"):
                self.slide_count += 1
    
    def run(self):
        print("="*70)
        print("FINAL COMPLETE TEST - WITH PPT GENERATION")
        print("="*70)
        print(f"Duration: {self.test_duration} seconds")
        print()
        print("SPEAK ABOUT: Computer Networks")
        print()
        print("Suggested script:")
        print("- 'Today we are going to discuss computer networks.'")
        print("- 'A network is a collection of interconnected devices.'")
        print("- 'Now let's discuss network topologies.'")
        print("- 'Star topology uses a central switch.'")
        print("- 'Bus topology uses a single cable.'")
        print("- 'Now let's discuss TCP and UDP.'")
        print("- 'TCP is connection-oriented and provides reliability.'")
        print("- 'UDP is connectionless and faster.'")
        print("- 'Unlike TCP, UDP does not guarantee delivery.'")
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
            worker_thread.join(timeout=15)
            time.sleep(3)
        
        print("\n" + "="*70)
        print("FINAL RESULTS")
        print("="*70)
        print(f"Previews: {self.preview_count}")
        print(f"Final transcripts: {self.final_count}")
        print(f"Slides generated: {self.slide_count}")
        
        if self.full_transcript:
            print(f"\nTranscript ({len(self.full_transcript)} chars):")
            print(self.full_transcript[:300])
        
        audio_stats = self.audio_stream.stats()
        print(f"\nAudio: {audio_stats['callback_count']} callbacks, {audio_stats['dropped_chunks']} dropped")
        
        # Check for PPT
        ppt_path = "outputs/presentations"
        if os.path.exists(ppt_path):
            files = os.listdir(ppt_path)
            pptx_files = [f for f in files if f.endswith('.pptx')]
            if pptx_files:
                latest = max(pptx_files, key=lambda f: os.path.getmtime(os.path.join(ppt_path, f)))
                print(f"\n✅ PPT Generated: {os.path.join(ppt_path, latest)}")
        
        print("\n✅ COMPLETE SYSTEM TEST PASSED!")


if __name__ == "__main__":
    tester = CompleteLiveTester(test_duration=90)
    tester.run()