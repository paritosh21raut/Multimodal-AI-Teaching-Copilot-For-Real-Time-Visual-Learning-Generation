"""
FINAL END-TO-END TEST (WITH PPT GENERATION)

Complete system: Audio → Intelligence → PPT → Dashboard
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
from app.presentation.bridge import PresentationBridge
from app.semantic.semantic_pipeline import SemanticPipeline
from app.development.development_tracker import DevelopmentTracker
from app.importance.importance_scorer import ImportanceScorer

# PPT imports
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

from app.presentation.design.design_system import design_system
from app.presentation.design.typography import typography
from app.presentation.renderer.slide_renderer import SlideRenderer
from app.presentation.layout.layout_engine import LayoutEngine


class FinalE2ETester:
    """Complete system test with actual PPT generation"""
    
    def __init__(self, test_duration: int = 60):
        self.test_duration = test_duration
        
        # Audio
        self.audio_stream = AudioStream()
        self.audio_worker = AudioWorker(
            audio_queue=self.audio_stream.get_queue(),
            on_preview_transcript=self._on_preview,
            on_final_transcript=self._on_final,
        )
        
        # Intelligence
        self.transcript_intelligence = transcript_intelligence
        self.topic_intelligence = TopicIntelligence()
        self.semantic_pipeline = SemanticPipeline()
        self.development_tracker = DevelopmentTracker()
        self.importance_scorer = ImportanceScorer(self.development_tracker)
        self.presentation_bridge = PresentationBridge()
        
        # PPT
        self.prs = Presentation()
        self.slide_renderer = SlideRenderer()
        self.layout_engine = LayoutEngine()
        self.slide_number = 0
        
        # State
        self.current_topic = None
        self.current_embedding = None
        self.context = ""
        
        # Stats
        self.preview_count = 0
        self.final_count = 0
        self.slide_count = 0
        self.full_transcript = ""
        
        # Create output directory
        os.makedirs("outputs/presentations", exist_ok=True)
        self.ppt_path = f"outputs/presentations/E2E_Test_{int(time.time())}.pptx"
    
    def _on_preview(self, preview_text, authoritative):
        self.preview_count += 1
    
    def _on_final(self, segment_text, full_transcript, segment_id):
        self.final_count += 1
        self.full_transcript = full_transcript
        
        print(f"\n[FINAL #{segment_id}]")
        
        # Refine
        refined = self.transcript_intelligence.refine(segment_text, context=self.context)
        refined_text = refined.refined_text.strip()
        
        if not refined_text:
            return
        
        # LSI
        topic_decision = self.topic_intelligence.process(
            latest_text=refined_text,
            rolling_context=self.context,
            current_topic=self.current_topic,
            current_embedding=self.current_embedding,
        )
        
        if not topic_decision.is_relevant:
            return
        
        self.current_topic = topic_decision.topic
        self.current_embedding = topic_decision.embedding
        self.context = f"{self.context} {refined_text}".strip()
        
        # Semantic
        semantic_result = self.semantic_pipeline.process_transcript(
            transcript_text=refined_text,
            chunk_id=f"chunk_{self.final_count}",
            lecture_id="e2e_test",
            topic_path=str(topic_decision.topic),
            generate_embeddings=False,
        )
        
        if not semantic_result or not semantic_result.get("frame"):
            return
        
        frame = semantic_result["frame"]
        
        # Development
        self.development_tracker.process_frame(frame, chunk_id=f"chunk_{self.final_count}")
        
        # Importance
        important = self.importance_scorer.get_top_important(
            limit=5, current_chunk_id=f"chunk_{self.final_count}"
        )
        important_names = [c.canonical_name for c in important]
        
        print(f"[TOPIC] {topic_decision.topic[:60]}")
        print(f"[CONCEPTS] {len(frame.concepts)}")
        print(f"[IMPORTANT] {important_names[:3]}")
        
        # Presentation Bridge
        result = self.presentation_bridge.process_transcript(
            frame=frame,
            topic_changed=topic_decision.is_new_topic,
            current_topic=str(topic_decision.topic),
            important_concepts=important_names,
            authoritative_transcript=self.full_transcript,
            chunk_id=f"chunk_{self.final_count}",
        )
        
        if result and result.get("plan"):
            plan = result["plan"]
            layout = result["layout"]
            visual_spec = result.get("visual_spec")
            
            # ACTUALLY RENDER PPT SLIDE
            slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])  # Blank layout
            self.slide_renderer.render_slide(slide, plan, layout, visual_spec)
            
            self.slide_number += 1
            self.slide_count += 1
            
            print(f"[SLIDE #{self.slide_number}] {plan.focal_message[:50]}")
            print(f"[LAYOUT] {plan.layout_family.value}")
            print(f"[REPRESENTATION] {plan.representation.representation_type.value if plan.representation else 'none'}")
            
            # Save PPT after each slide
            self.prs.save(self.ppt_path)
            print(f"[PPT SAVED] {self.ppt_path}")
    
    def run(self):
        print("="*70)
        print("FINAL E2E TEST - WITH PPT GENERATION")
        print("="*70)
        print(f"Duration: {self.test_duration} seconds")
        print("="*70)
        
        print("\n🎤 SPEAK NOW!")
        print("="*70)
        
        worker_thread = threading.Thread(target=self.audio_worker.run, daemon=True)
        worker_thread.start()
        
        time.sleep(2)
        
        stream_thread = threading.Thread(target=self.audio_stream.start, daemon=True)
        stream_thread.start()
        
        try:
            start_time = time.time()
            while time.time() - start_time < self.test_duration:
                if not worker_thread.is_alive():
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.audio_stream.stop()
            self.audio_worker.stop()
            worker_thread.join(timeout=15)
            time.sleep(3)
        
        # Final save
        if self.slide_count > 0:
            self.prs.save(self.ppt_path)
        
        print("\n" + "="*70)
        print("RESULTS")
        print("="*70)
        print(f"Previews: {self.preview_count}")
        print(f"Final transcripts: {self.final_count}")
        print(f"Slides: {self.slide_count}")
        print(f"PPT File: {self.ppt_path}")
        print(f"PPT exists: {os.path.exists(self.ppt_path)}")
        
        if os.path.exists(self.ppt_path):
            print(f"PPT size: {os.path.getsize(self.ppt_path)} bytes")
        
        audio_stats = self.audio_stream.stats()
        print(f"Audio: {audio_stats['callback_count']} callbacks, {audio_stats['dropped_chunks']} dropped")
        
        print("\n✅ TEST COMPLETE")
        print(f"📁 Open PPT at: {os.path.abspath(self.ppt_path)}")


if __name__ == "__main__":
    tester = FinalE2ETester(test_duration=60)
    tester.run()