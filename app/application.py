from app.audio.audio_pipeline import AudioPipeline
from app.knowledge.content_generator import content_generator
from app.lecture.lecture_pipeline import lecture_pipeline
from app.slides.slide_manager import slide_manager
from app.topics.topic_intelligence import topic_intelligence
from app.utils.logger import app_logger
from app.ppt.ppt_manager import ppt_manager
from app.lecture.context_buffer import context_buffer

from app.config import (
    SEMANTIC_BATCH_SIZE,
    SEMANTIC_BATCH_TIMEOUT,
    SEMANTIC_ENABLED,
    SEMANTIC_FALLBACK_MODEL,
    SEMANTIC_MAX_CALLS_PER_MINUTE,
    SEMANTIC_MIN_INTERVAL_SECONDS,
    SEMANTIC_QUEUE_MAX_SIZE,
    SEMANTIC_REASONER_MAX_TOKENS,
    SEMANTIC_REASONER_MODEL,
    SEMANTIC_REASONER_REASONING_EFFORT,
)
from app.semantic.semantic_intelligence import SemanticIntelligence
from app.ai.groq_semantic_reasoner import GroqSemanticReasoner

from app.importance.importance_intelligence import ImportanceIntelligence


class Application:

    def __init__(self):

        app_logger.info("Initializing Application")

        self.pipeline = AudioPipeline()

        lecture_pipeline.register_topic_detector(
            topic_intelligence
        )

        lecture_pipeline.register_content_generator(
            content_generator
        )

        lecture_pipeline.register_slide_manager(
            slide_manager
        )

        semantic_sidecar = None

        if SEMANTIC_ENABLED:

            try:

                shared_client = getattr(
                    content_generator, "ai", None
                )

                embedding_model = topic_intelligence.lsi._model
                lsi_registry = topic_intelligence.lsi._registry

                primary = None
                fallback = None

                if shared_client is not None:

                    primary = GroqSemanticReasoner(
                        shared_client,
                        model=SEMANTIC_REASONER_MODEL,
                        max_tokens=SEMANTIC_REASONER_MAX_TOKENS,
                        reasoning_effort=SEMANTIC_REASONER_REASONING_EFFORT,
                    )

                    fallback = GroqSemanticReasoner(
                        shared_client,
                        model=SEMANTIC_FALLBACK_MODEL,
                        max_tokens=SEMANTIC_REASONER_MAX_TOKENS,
                        reasoning_effort=None,
                    )

                semantic_sidecar = SemanticIntelligence(
                    embedding_model=embedding_model,
                    lsi_registry_getter=lsi_registry.get,
                    reasoner=primary,
                    fallback_reasoner=fallback,
                    max_queue_size=SEMANTIC_QUEUE_MAX_SIZE,
                    batch_size=SEMANTIC_BATCH_SIZE,
                    batch_timeout=SEMANTIC_BATCH_TIMEOUT,
                    max_calls_per_minute=SEMANTIC_MAX_CALLS_PER_MINUTE,
                    min_interval_seconds=SEMANTIC_MIN_INTERVAL_SECONDS,
                    enabled=True,
                )

                lecture_pipeline.register_semantic_intelligence(
                    semantic_sidecar
                )

                app_logger.info(
                    "[Application] Semantic Intelligence registered "
                    f"(throttle: {SEMANTIC_MAX_CALLS_PER_MINUTE}/min, "
                    f"min interval {SEMANTIC_MIN_INTERVAL_SECONDS}s)"
                )

            except Exception as error:

                app_logger.warning(
                    "[Application] Semantic sidecar init failed: "
                    f"{error}"
                )
                app_logger.warning(
                    "[Application] Continuing without semantic sidecar"
                )

        # Phase 5 registration.
        try:

            semantic_ledger = (
                semantic_sidecar._ledger
                if semantic_sidecar is not None
                else None
            )

            importance_sidecar = ImportanceIntelligence(
                context_buffer=context_buffer,
                semantic_ledger=semantic_ledger,
                enabled=True,
            )

            lecture_pipeline.register_importance_intelligence(
                importance_sidecar
            )

            app_logger.info(
                "[Application] Importance Intelligence registered"
            )

        except Exception as error:

            app_logger.warning(
                "[Application] Importance sidecar init failed: "
                f"{error}"
            )
            app_logger.warning(
                "[Application] Continuing without importance sidecar"
            )

        ppt_manager.create_new_presentation("Live Lecture")
        ppt_manager.add_title_slide(
            title="Live Lecture",
            subtitle="AI Teaching Copilot"
        )

        app_logger.success("Lecture Pipeline Ready")

    def start(self):

        app_logger.success("Application Started")

        self.pipeline.start()