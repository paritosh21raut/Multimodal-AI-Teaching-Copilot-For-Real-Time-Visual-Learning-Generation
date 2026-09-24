from __future__ import annotations

from app.lecture.lecture_pipeline import LecturePipeline
from app.slide_decision.slide_decision_engine import SlideDecisionEngine


class _FakeDecision:
    def __init__(
        self,
        relation="continuation",
        node_id="n1",
        topic="Capacitors",
        parent_node_id=None,
        depth=0,
        is_new_topic=False,
        is_new_subtopic=False,
        is_return=False,
        similarity=0.8,
        is_relevant=True,
        reason="relevant_continuation",
        embedding=None,
    ):
        self.relation = relation
        self.node_id = node_id
        self.topic = topic
        self.parent_node_id = parent_node_id
        self.depth = depth
        self.is_new_topic = is_new_topic
        self.is_new_subtopic = is_new_subtopic
        self.is_return = is_return
        self.similarity = similarity
        self.is_relevant = is_relevant
        self.reason = reason
        self.embedding = embedding


def test_pipeline_keep_skips_content_and_slides(monkeypatch):
    """
    Verify KEEP does not call ContentGenerator or SlideManager.
    """
    from app.lecture import lecture_pipeline as lp_module

    pipeline = LecturePipeline()

    # Register Phase 6 only; no Phase 5 sidecar needed for this test.
    pipeline.register_slide_decision_engine(SlideDecisionEngine())

    calls = {"content": 0, "create": 0, "update": 0}

    class FakeGenerator:
        def generate(self, topic, context):
            calls["content"] += 1
            raise AssertionError("ContentGenerator must not be called on KEEP")

    class FakeManager:
        def create_slide(self, slide, content):
            calls["create"] += 1
            raise AssertionError("create_slide must not be called on KEEP")

        def update_slide(self, slide, content):
            calls["update"] += 1
            raise AssertionError("update_slide must not be called on KEEP")

    pipeline.register_content_generator(FakeGenerator())
    pipeline.register_slide_manager(FakeManager())

    # Seed lecture_state with one slide.
    from app.lecture.lecture_state import lecture_state
    lecture_state.start_new_lecture()
    lecture_state.create_slide("Capacitors")
    lecture_state.set_current_topic("Capacitors")

    pipeline.started = True

    # Monkeypatch the topic detector to return an incidental decision.
    class FakeDetector:
        def process(self, **kwargs):
            return _FakeDecision(
                relation="continuation",
                topic="Capacitors",
                is_new_topic=False,
                similarity=0.9,
                is_relevant=True,
            )

    pipeline.register_topic_detector(FakeDetector())

    # Monkeypatch importance sidecar to produce INCIDENTAL.
    class FakeImportance:
        def evaluate(self, *, chunk_text, topic_decision):
            class R:
                structural_centrality = "INCIDENTAL"
                developmental_roles = ["META"]
                explicit_emphasis = "NO"
                confidence = 0.85
            return R()

        def reset(self):
            pass

        def _build_context(self, *, chunk_text, topic_decision):
            class C:
                concept_under_annotation = None
                concept_first_seen = False
                prior_assertions_for_concept = ()
            return C()

    pipeline.register_importance_intelligence(FakeImportance())

    result = pipeline.process_transcript(
        "By the way, the lab uses a 10 microfarad capacitor."
    )

    assert result is not None
    assert result["slide_action"] == "KEEP_CURRENT_SLIDE"
    assert result["content_generated"] is False
    assert calls["content"] == 0
    assert calls["create"] == 0
    assert calls["update"] == 0
    assert lecture_state.slide_count() == 1