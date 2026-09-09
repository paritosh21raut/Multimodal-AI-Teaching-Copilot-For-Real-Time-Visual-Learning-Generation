from __future__ import annotations

from threading import Lock

from app.lecture.context_buffer import context_buffer
from app.lecture.lecture_state import lecture_state
from app.ppt.ppt_manager import ppt_manager
from app.dashboard.dashboard_state import dashboard_state

# NEW: Presentation Intelligence
from app.presentation.bridge import presentation_bridge
from app.semantic.semantic_pipeline import SemanticPipeline
from app.development.development_tracker import DevelopmentTracker
from app.importance.importance_scorer import ImportanceScorer


class LecturePipeline:

    def __init__(self):
        self._lock = Lock()
        self.topic_detector = None
        self.content_generator = None
        self.slide_manager = None

        # NEW: Intelligence pipeline
        self.semantic_pipeline = SemanticPipeline()
        self.development_tracker = DevelopmentTracker()
        self.importance_scorer = ImportanceScorer(self.development_tracker)
        self.presentation_bridge = presentation_bridge

        self.started = False

    def register_topic_detector(self, detector):
        self.topic_detector = detector

    def register_content_generator(self, generator):
        self.content_generator = generator

    def register_slide_manager(self, manager):
        self.slide_manager = manager

    def start(self):
        if self.started:
            return
        lecture_state.start_new_lecture()
        if ppt_manager.presentation is None:
            ppt_manager.create_new_presentation(lecture_state.lecture_title)
            ppt_manager.add_title_slide(lecture_state.lecture_title, "AI Teaching Copilot")
        context_buffer.clear()
        self.started = True
        print("[Pipeline] Lecture Pipeline Started")

    def process_transcript(self, transcript: str):
        transcript = transcript.strip()
        if not transcript:
            return None
        if not self.started:
            self.start()

        # LSI
        decision = self.topic_detector.process(
            latest_text=transcript,
            rolling_context=context_buffer.rolling_context(),
            current_topic=lecture_state.get_current_topic(),
            current_embedding=lecture_state.get_current_embedding(),
        )

        if not decision.is_relevant:
            return {
                "is_relevant": False,
                "reason": decision.reason,
                "topic": lecture_state.get_current_topic(),
            }

        context_buffer.add(transcript)

        # Semantic
        semantic_result = self.semantic_pipeline.process_transcript(
            transcript_text=transcript,
            chunk_id=f"chunk_{lecture_state.slide_count()}",
            lecture_id=lecture_state.lecture_title,
            topic_path=str(decision.topic),
            generate_embeddings=False,
        )

        if not semantic_result or not semantic_result.get("frame"):
            return {"is_relevant": True, "slide_created": False, "reason": "No semantic content"}

        frame = semantic_result["frame"]

        # Development
        self.development_tracker.process_frame(frame, chunk_id=f"chunk_{lecture_state.slide_count()}")

        # Importance
        important = self.importance_scorer.get_top_important(limit=5)
        important_names = [c.canonical_name for c in important]

        # Presentation Intelligence (NEW)
        result = self.presentation_bridge.process_transcript(
            frame=frame,
            topic_changed=decision.is_new_topic,
            current_topic=str(decision.topic),
            important_concepts=important_names,
            authoritative_transcript=transcript,
            chunk_id=f"chunk_{lecture_state.slide_count()}",
        )

        if not result:
            return {"is_relevant": True, "slide_created": False, "reason": "No action"}

        # If slide should be created/updated, use SlideManager
        if result.get("slide_created") and self.slide_manager and result.get("plan"):
            plan = result["plan"]
            
            # Build slide content from plan
            bullets = [block.text for block in plan.content_blocks if block.text]
            title = plan.focal_message or plan.purpose
            
            # Create or update slide
            if decision.is_new_topic:
                slide = lecture_state.create_slide(str(decision.topic))
            else:
                lecture_state.update_current_slide()
                slide = lecture_state.get_current_slide()
            
            if slide:
                # Update dashboard
                dashboard_state.update_topic(str(decision.topic), decision.confidence)
                dashboard_state.update_slide(
                    title=title,
                    bullets=bullets[:6],
                    slide_number=slide.slide_number,
                )

        lecture_state.set_current_topic(decision.topic, decision.embedding)

        return {
            "is_relevant": True,
            "is_new_topic": decision.is_new_topic,
            "topic": str(decision.topic),
            "slide_created": result.get("slide_created", False),
            "action": result.get("action", "no_action"),
            "reason": result.get("reason", ""),
            "concepts_count": len(frame.concepts),
            "propositions_count": len(frame.propositions),
        }


lecture_pipeline = LecturePipeline()