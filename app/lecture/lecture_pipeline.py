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


class LecturePipeline:

    def __init__(self):

        self._lock = Lock()

        self.topic_detector = None
        self.content_generator = None
        self.slide_manager = None

        # Phase 4 sidecar. Set via register_semantic_intelligence().
        self.semantic_intelligence = None

        # Phase 5 sidecar. Set via register_importance_intelligence().
        self.importance_intelligence = None

        # Phase 6 engine. Set via register_slide_decision_engine().
        self.slide_decision_engine = None

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

    def register_semantic_intelligence(self, sidecar):
        self.semantic_intelligence = sidecar

    def register_importance_intelligence(self, sidecar):
        self.importance_intelligence = sidecar

    def register_slide_decision_engine(self, engine):
        self.slide_decision_engine = engine

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

        if (
            self.topic_detector is not None
            and hasattr(self.topic_detector, "reset")
        ):
            self.topic_detector.reset()

        if self.semantic_intelligence is not None:
            try:
                self.semantic_intelligence.reset()
                self.semantic_intelligence.start()
            except Exception as error:
                print(
                    "[Pipeline] Semantic sidecar reset failed:",
                    error,
                )

        if self.importance_intelligence is not None:
            try:
                self.importance_intelligence.reset()
            except Exception as error:
                print(
                    "[Pipeline] Importance sidecar reset failed:",
                    error,
                )

        if self.slide_decision_engine is not None:
            try:
                self.slide_decision_engine.reset()
            except Exception as error:
                print(
                    "[Pipeline] Slide decision engine reset failed:",
                    error,
                )

        self.started = True

        print("[Pipeline] Lecture Pipeline Started")

    # ==========================================================
    # PHASE 6 HELPERS
    # ==========================================================

    def _build_slide_decision_context(
        self, transcript, decision, importance_result
    ):
        try:
            from app.slide_decision.slide_decision_context import (
                SlideDecisionContext,
            )
            import uuid

            concept_label = None
            concept_first_seen = None
            concept_prior_assertions_count = None

            if self.importance_intelligence is not None:
                try:
                    ctx = self.importance_intelligence._build_context(
                        chunk_text=transcript,
                        topic_decision=decision,
                    )
                    concept_label = ctx.concept_under_annotation
                    concept_first_seen = ctx.concept_first_seen
                    concept_prior_assertions_count = len(
                        ctx.prior_assertions_for_concept
                    )
                except Exception:
                    pass

            current_slide = lecture_state.get_current_slide()
            has_slide = lecture_state.has_slides()

            return SlideDecisionContext(
                chunk_id=str(uuid.uuid4()),
                chunk_text=transcript,
                lsi_relation=getattr(decision, "relation", None),
                lsi_is_new_topic=bool(
                    getattr(decision, "is_new_topic", False)
                ),
                lsi_is_new_subtopic=bool(
                    getattr(decision, "is_new_subtopic", False)
                ),
                lsi_is_return=bool(
                    getattr(decision, "is_return", False)
                ),
                lsi_topic=getattr(decision, "topic", None),
                lsi_similarity=(
                    float(getattr(decision, "similarity"))
                    if getattr(decision, "similarity", None) is not None
                    else None
                ),
                has_current_slide=has_slide,
                current_slide_number=(
                    current_slide.slide_number
                    if current_slide is not None
                    else None
                ),
                current_slide_topic=lecture_state.get_current_topic(),
                phase5_centrality=(
                    importance_result.structural_centrality
                    if importance_result is not None
                    else None
                ),
                phase5_developmental_roles=(
                    list(importance_result.developmental_roles)
                    if importance_result is not None
                    else []
                ),
                phase5_explicit_emphasis=(
                    importance_result.explicit_emphasis
                    if importance_result is not None
                    else None
                ),
                phase5_confidence=(
                    float(importance_result.confidence)
                    if importance_result is not None
                    else None
                ),
                concept_label=concept_label,
                concept_first_seen=concept_first_seen,
                concept_prior_assertions_count=concept_prior_assertions_count,
                previous_decision=(
                    self.slide_decision_engine.last_decision()
                    if self.slide_decision_engine is not None
                    else None
                ),
                previous_topic=(
                    self.slide_decision_engine.last_topic()
                    if self.slide_decision_engine is not None
                    else None
                ),
            )
        except Exception as error:
            print(
                "[Pipeline] Slide decision context build failed:",
                error,
            )
            return None

    def _log_slide_decision(self, result):
        try:
            print(
                "[SLIDE_DECISION] "
                f"decision={result.decision} "
                f"reason={result.reason} "
                f"lsi_relation={result.lsi_relation} "
                f"centrality={result.centrality} "
                f"roles={','.join(result.developmental_roles)} "
                f"emphasis={result.explicit_emphasis} "
                f"current_slide={result.current_slide_id} "
                f"concept_first_seen={result.concept_first_seen}"
            )
        except Exception:
            pass

    # ==========================================================
    # PROCESS
    # ==========================================================

    def process_transcript(self, transcript: str):

        transcript = transcript.strip()

        if not transcript:
            return None

        if not self.started:
            self.start()

        decision = self.topic_detector.process(
            latest_text=transcript,
            rolling_context=context_buffer.rolling_context(),
            current_topic=lecture_state.get_current_topic(),
            current_embedding=lecture_state.get_current_embedding(),
        )

        # Phase 4: non-blocking enqueue of semantic work.
        if self.semantic_intelligence is not None:
            try:
                self.semantic_intelligence.enqueue(
                    transcript, decision
                )
            except Exception as error:
                print(
                    "[Pipeline] Semantic enqueue failed:",
                    error,
                )

        # Phase 5: synchronous, fail-open importance evaluation.
        importance_result = None
        if self.importance_intelligence is not None:
            try:
                importance_result = (
                    self.importance_intelligence.evaluate(
                        chunk_text=transcript,
                        topic_decision=decision,
                    )
                )
                if importance_result is not None:
                    print(
                        "[Phase5] centrality={centrality} "
                        "emphasis={emphasis} roles={roles} "
                        "conf={conf}".format(
                            centrality=importance_result.structural_centrality,
                            emphasis=importance_result.explicit_emphasis,
                            roles=",".join(importance_result.developmental_roles),
                            conf=importance_result.confidence,
                        )
                    )
            except Exception as error:
                print(
                    "[Pipeline] Importance evaluation failed:",
                    error,
                )

        # ----------------------------------------------------------
        # Irrelevant speech — retain existing short-circuit.
        # ----------------------------------------------------------

        if (
            hasattr(decision, "is_relevant")
            and not decision.is_relevant
        ):

            print()
            print("ANALYSIS RESULT")
            print("-" * 70)
            print("Relevant      : NO")
            print("Action        : KEEP CURRENT SLIDE")
            print(f"Reason        : {decision.reason}")
            print("-" * 70)

            return {
                "is_relevant": False,
                "is_new_topic": False,
                "topic": lecture_state.get_current_topic(),
                "confidence": 0.0,
                "reason": decision.reason,
                "slide_action": "KEEP_CURRENT_SLIDE",
                "content_generated": False,
            }

        context_buffer.add(transcript)

        # ----------------------------------------------------------
        # Phase 6: slide decision.
        # ----------------------------------------------------------

        phase6_result = None
        use_phase6 = False
        if self.slide_decision_engine is not None:
            ctx = self._build_slide_decision_context(
                transcript, decision, importance_result
            )
            if ctx is not None:
                try:
                    phase6_result = self.slide_decision_engine.decide(ctx)
                    use_phase6 = phase6_result is not None
                except Exception as error:
                    print(
                        "[Pipeline] Slide decision failed:",
                        error,
                    )
                    phase6_result = None
                    use_phase6 = False

        # Determine effective action and slide target.
        has_current_slide = lecture_state.has_slides()
        current_slide = lecture_state.get_current_slide()

        if use_phase6 and phase6_result is not None:
            self._log_slide_decision(phase6_result)

            action = phase6_result.decision

            if action == "KEEP_CURRENT_SLIDE" and has_current_slide:
                # Real KEEP: no content generation, no slide_manager call.
                print(
                    f"Slide Decision : KEEP_CURRENT_SLIDE "
                    f"({phase6_result.reason})"
                )
                dashboard_state.update_topic(
                    str(lecture_state.get_current_topic()),
                    float(phase6_result.confidence_hint),
                )
                dashboard_state.set_pipeline(
                    "Slide Kept", "Ready"
                )
                return {
                    "is_relevant": True,
                    "is_new_topic": False,
                    "topic": lecture_state.get_current_topic(),
                    "confidence": float(phase6_result.confidence_hint),
                    "slide_action": "KEEP_CURRENT_SLIDE",
                    "slide_number": current_slide.slide_number,
                    "content_generated": False,
                    "phase6_reason": phase6_result.reason,
                }

            # KEEP without a current slide -> fall back to existing behavior.
            if action == "KEEP_CURRENT_SLIDE" and not has_current_slide:
                is_new_topic_effective = bool(
                    getattr(decision, "is_new_topic", False)
                )
            elif action == "NEW_SLIDE":
                is_new_topic_effective = True
            elif action == "UPDATE_CURRENT_SLIDE":
                is_new_topic_effective = not has_current_slide
            else:
                is_new_topic_effective = bool(
                    getattr(decision, "is_new_topic", False)
                )
        else:
            # No Phase 6: preserve existing behavior.
            is_new_topic_effective = bool(
                getattr(decision, "is_new_topic", False)
            )

        # ----------------------------------------------------------
        # Slide lifecycle (unchanged semantics for NEW/UPDATE).
        # ----------------------------------------------------------

        if lecture_state.get_current_topic() is None:
            confidence = 1.0
        elif is_new_topic_effective:
            confidence = max(
                0.0,
                min(1.0, 1.0 - float(decision.similarity)),
            )
        else:
            confidence = max(
                0.0,
                min(1.0, float(decision.similarity)),
            )

        if is_new_topic_effective:
            slide_action = "NEW SLIDE"
            slide = lecture_state.create_slide(decision.topic)
        else:
            slide_action = "SAME SLIDE - UPDATE"
            lecture_state.update_current_slide()
            slide = lecture_state.get_current_slide()

        lecture_state.set_current_topic(
            decision.topic, decision.embedding
        )

        print()
        print("=" * 70)
        print("LECTURE ANALYSIS REPORT")
        print("=" * 70)

        print(f"Input Chunk    : {transcript}")
        print(f"Topic          : {decision.topic}")
        print(f"Similarity     : {decision.similarity:.3f}")
        print(f"Confidence     : {confidence:.3f}")
        print(f"New Topic      : {decision.is_new_topic}")
        print(f"Slide Decision : {slide_action}")
        print(f"Slide Number   : {slide.slide_number}")
        print(f"Reason         : {decision.reason}")
        print("-" * 70)

        dashboard_state.update_topic(
            str(decision.topic), confidence
        )

        print("Generating educational content...")

        try:
            content = self.content_generator.generate(
                topic=decision.topic,
                context=context_buffer.rolling_context(),
            )
        except Exception as error:

            print("Content Generation : FAILED")
            print(f"Error              : {error}")

            dashboard_state.set_error(str(error))
            dashboard_state.set_pipeline(
                "Content Generation", "Failed"
            )

            return {
                "is_relevant": True,
                "is_new_topic": decision.is_new_topic,
                "topic": str(decision.topic),
                "confidence": confidence,
                "slide_number": slide.slide_number,
                "content_generated": False,
            }

        print(f"Content Type   : {content.content_type}")
        print(f"Visual Type    : {content.visual_type}")
        print(f"Visual Reason  : {content.visual_reason}")
        print(f"Visual Spec    : {content.visual_spec}")
        print(f"Title          : {content.title}")
        print(f"Bullets        : {len(content.bullets)}")

        dashboard_state.update_slide(
            content.title,
            [b.text for b in content.bullets],
            slide.slide_number,
        )

        dashboard_state.set_pipeline(
            "Content Generated", "Generating"
        )

        if is_new_topic_effective:
            result = self.slide_manager.create_slide(
                slide, content
            )
        else:
            result = self.slide_manager.update_slide(
                slide, content
            )

        print(
            "Slide Generation : "
            f"{'SUCCESS' if result.success else 'FAILED'}"
        )
        print(f"PPT              : {result.presentation_path or '-'}")
        print("=" * 70)

        return {
            "is_relevant": True,
            "is_new_topic": bool(is_new_topic_effective),
            "topic": str(decision.topic),
            "confidence": confidence,
            "slide_action": slide_action,
            "slide_number": slide.slide_number,
            "content_generated": True,
            "title": content.title,
            "bullets": [b.text for b in content.bullets],
            "content_type": content.content_type,
            "visual_type": content.visual_type,
            "visual_reason": content.visual_reason,
            "visual_spec": content.visual_spec,
        }



lecture_pipeline = LecturePipeline()
