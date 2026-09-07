from __future__ import annotations

from threading import Lock

from app.lecture.context_buffer import (
    context_buffer,
)

from app.lecture.lecture_state import (
    lecture_state,
)

from app.ppt.ppt_manager import (
    ppt_manager,
)

from app.dashboard.dashboard_state import (
    dashboard_state,
)

# Import all intelligence subsystems
from app.semantic.semantic_pipeline import SemanticPipeline
from app.development.development_tracker import DevelopmentTracker
from app.importance.importance_scorer import ImportanceScorer
from app.slide_decision.slide_decision_engine import SlideDecisionEngine
from app.slide_decision.slide_decision_models import SlideAction
from app.representation.representation_engine import RepresentationEngine
from app.representation.representation_models import VisualRepresentation


class LecturePipeline:

    def __init__(self):

        self._lock = Lock()

        self.topic_detector = None
        self.content_generator = None
        self.slide_manager = None

        # Initialize all intelligence subsystems
        self.semantic_pipeline = SemanticPipeline()
        self.development_tracker = DevelopmentTracker()
        self.importance_scorer = ImportanceScorer(self.development_tracker)
        self.slide_decision_engine = SlideDecisionEngine(
            self.development_tracker,
            self.importance_scorer,
        )
        self.representation_engine = RepresentationEngine()

        self.started = False

    # ==========================================================
    # REGISTRATION
    # ==========================================================

    def register_topic_detector(self, detector):
        self.topic_detector = detector

    def register_content_generator(self, generator):
        self.content_generator = generator

    def register_slide_manager(self, manager):
        self.slide_manager = manager

    # ==========================================================
    # START
    # ==========================================================

    def start(self):
        if self.started:
            return

        lecture_state.start_new_lecture()

        if ppt_manager.presentation is None:
            ppt_manager.create_new_presentation(
                lecture_state.lecture_title
            )
            ppt_manager.add_title_slide(
                lecture_state.lecture_title,
                "AI Teaching Copilot",
            )

        context_buffer.clear()
        self.started = True
        print("[Pipeline] Lecture Pipeline Started")

    # ==========================================================
    # PROCESS
    # ==========================================================

    def process_transcript(self, transcript: str):
        transcript = transcript.strip()

        if not transcript:
            return None

        if not self.started:
            self.start()

        # ==========================================
        # STEP 1: Topic Intelligence (LSI)
        # ==========================================
        decision = self.topic_detector.process(
            latest_text=transcript,
            rolling_context=context_buffer.rolling_context(),
            current_topic=lecture_state.get_current_topic(),
            current_embedding=lecture_state.get_current_embedding(),
        )

        # Skip irrelevant speech
        if hasattr(decision, "is_relevant") and not decision.is_relevant:
            print(f"\n[LSI] IRRELEVANT: {decision.reason}")
            return {
                "is_relevant": False,
                "is_new_topic": False,
                "topic": lecture_state.get_current_topic(),
                "confidence": 0.0,
                "reason": decision.reason,
            }

        # Add to context
        context_buffer.add(transcript)

        # ==========================================
        # STEP 2: Semantic Intelligence
        # ==========================================
        topic_path = str(decision.topic) if decision.topic else ""
        
        semantic_result = self.semantic_pipeline.process_transcript(
            transcript_text=transcript,
            chunk_id=f"chunk_{lecture_state.get_current_slide().slide_number if lecture_state.get_current_slide() else 0}",
            lecture_id=lecture_state.lecture_title,
            topic_path=topic_path,
            generate_embeddings=False,
        )

        frame = None
        if semantic_result and semantic_result.get("frame"):
            frame = semantic_result["frame"]

        # ==========================================
        # STEP 3: Development Intelligence
        # ==========================================
        development_events = []
        if frame:
            development_events = self.development_tracker.process_frame(
                frame,
                chunk_id=str(lecture_state.get_current_slide().slide_number if lecture_state.get_current_slide() else 0),
            )

        # ==========================================
        # STEP 4: Importance Intelligence
        # ==========================================
        important_concepts = []
        if frame:
            important_concepts = self.importance_scorer.get_top_important(
                limit=5,
                current_chunk_id=str(lecture_state.get_current_slide().slide_number if lecture_state.get_current_slide() else 0),
            )

        # ==========================================
        # STEP 5: Slide Decision Engine
        # ==========================================
        slide_decision = self.slide_decision_engine.decide(
            topic_changed=decision.is_new_topic,
            current_topic=str(decision.topic),
            chunk_id=str(lecture_state.get_current_slide().slide_number if lecture_state.get_current_slide() else 0),
        )

        # ==========================================
        # STEP 6: Representation Engine
        # ==========================================
        representation_decision = None
        if frame:
            representation_decision = self.representation_engine.decide(
                frame,
                topic=str(decision.topic),
            )

        # ==========================================
        # STEP 7: Update Lecture State
        # ==========================================
        if decision.is_new_topic:
            slide = lecture_state.create_slide(decision.topic)
            slide_action = "NEW SLIDE"
        else:
            lecture_state.update_current_slide()
            slide = lecture_state.get_current_slide()
            slide_action = "UPDATE SLIDE"

        lecture_state.set_current_topic(
            decision.topic,
            decision.embedding,
        )

        # ==========================================
        # STEP 8: Print Analysis Report
        # ==========================================
        print("\n" + "=" * 70)
        print("LECTURE ANALYSIS REPORT")
        print("=" * 70)
        print(f"Input: {transcript[:80]}")
        print(f"Topic: {decision.topic}")
        print(f"Structure: {decision.structural_decision}")
        
        if frame:
            print(f"Concepts: {len(frame.concepts)}")
            print(f"Propositions: {len(frame.propositions)}")
        
        if development_events:
            state_changes = [
                e for e in development_events
                if e.event_type.value == "state_changed"
            ]
            if state_changes:
                for event in state_changes:
                    print(f"Development: {event.payload.get('concept_name', '')} → {event.payload.get('new_state', '')}")
        
        if important_concepts:
            print(f"Important: {[c.canonical_name for c in important_concepts[:3]]}")
        
        print(f"Slide Action: {slide_decision.action.value}")
        print(f"Slide Trigger: {slide_decision.trigger.value}")
        
        if representation_decision:
            print(f"Visual: {representation_decision.visual_type.value}")
            print(f"Content Type: {representation_decision.content_type.value}")
        
        print("=" * 70)

        # ==========================================
        # STEP 9: Generate Content (if needed)
        # ==========================================
        content = None
        should_generate = slide_decision.action in [
            SlideAction.CREATE_NEW,
            SlideAction.UPDATE_CURRENT,
        ]

        if should_generate and self.content_generator:
            print("Generating educational content...")
            
            try:
                # Pass semantic + representation info to content generator
                semantic_context = {}
                if frame:
                    semantic_context = {
                        "concepts": [c.canonical_name for c in frame.concepts[:5]],
                        "propositions": [
                            f"{p.subject.canonical_name} {p.predicate.value} {p.object.canonical_name}"
                            if p.subject and p.object and p.predicate else ""
                            for p in frame.propositions[:5]
                        ],
                    }
                
                content = self.content_generator.generate(
                    topic=str(decision.topic),
                    context=context_buffer.rolling_context(),
                    semantic_content=semantic_context,
                )
                
                print(f"Content: {content.content_type}")
                print(f"Visual: {content.visual_type}")
                
            except Exception as error:
                print(f"Content generation failed: {error}")

        # ==========================================
        # STEP 10: Create/Update Slide
        # ==========================================
        if content and self.slide_manager:
            if decision.is_new_topic:
                result = self.slide_manager.create_slide(slide, content)
            else:
                result = self.slide_manager.update_slide(slide, content)
            
            if result.success:
                print(f"Slide: {result.slide_number} - {result.presentation_path}")
        
        # ==========================================
        # STEP 11: Update Dashboard
        # ==========================================
        dashboard_state.update_topic(
            str(decision.topic),
            decision.confidence if hasattr(decision, 'confidence') else 0.5,
        )
        
        dashboard_state.set_pipeline(
            "Complete",
            "Ready",
        )

        # ==========================================
        # RETURN RESULT
        # ==========================================
        return {
            "is_relevant": True,
            "is_new_topic": decision.is_new_topic,
            "topic": str(decision.topic),
            "slide_action": slide_decision.action.value,
            "slide_trigger": slide_decision.trigger.value,
            "visual_type": representation_decision.visual_type.value if representation_decision else "none",
            "content_type": representation_decision.content_type.value if representation_decision else "mixed",
            "concepts_count": len(frame.concepts) if frame else 0,
            "propositions_count": len(frame.propositions) if frame else 0,
            "development_events": len(development_events),
            "important_concepts": [c.canonical_name for c in important_concepts[:3]],
            "slide_number": slide.slide_number if slide else 0,
        }


lecture_pipeline = LecturePipeline()