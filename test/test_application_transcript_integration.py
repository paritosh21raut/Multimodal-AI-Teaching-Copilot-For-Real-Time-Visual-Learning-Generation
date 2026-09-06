import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def application_module(monkeypatch):
    content_generator_module = MagicMock()
    content_generator_module.content_generator = MagicMock()
    monkeypatch.setitem(
        sys.modules,
        "app.knowledge.content_generator",
        content_generator_module,
    )

    topic_intelligence_module = MagicMock()
    topic_intelligence_module.topic_intelligence = MagicMock()
    monkeypatch.setitem(
        sys.modules,
        "app.topics.topic_intelligence",
        topic_intelligence_module,
    )

    ppt_manager_module = MagicMock()
    ppt_manager_module.ppt_manager = MagicMock()
    monkeypatch.setitem(
        sys.modules,
        "app.ppt.ppt_manager",
        ppt_manager_module,
    )

    slide_manager_module = MagicMock()
    slide_manager_module.slide_manager = MagicMock()
    monkeypatch.setitem(
        sys.modules,
        "app.slides.slide_manager",
        slide_manager_module,
    )

    lecture_pipeline_module = MagicMock()
    lecture_pipeline_module.lecture_pipeline = MagicMock()
    monkeypatch.setitem(
        sys.modules,
        "app.lecture.lecture_pipeline",
        lecture_pipeline_module,
    )

    sys.modules.pop("app.application", None)

    import app.application as application_module

    return application_module


def test_application_uses_transcript_intelligence(application_module):
    app = application_module.Application.__new__(
        application_module.Application
    )

    raw_transcript = (
        "This is a lecture about machine learning. "
        "The model uses a training data set."
    )

    refined_transcript = (
        "This is a lecture about machine learning. "
        "The model uses a training dataset."
    )

    app.transcript_manager = MagicMock()
    app.transcript_intelligence = MagicMock()
    app.analysis_executor = MagicMock()

    app.transcript_manager.get_new_analysis_text.return_value = raw_transcript
    app.transcript_manager.get_analysis_context.return_value = (
        "Previous lecture context about machine learning."
    )

    refinement = MagicMock()
    refinement.refined_text = refined_transcript
    app.transcript_intelligence.refine.return_value = refinement

    submitted = {}

    def fake_submit(fn, raw_chunk, refined_chunk):
        submitted["fn"] = fn
        submitted["raw_chunk"] = raw_chunk
        submitted["refined_chunk"] = refined_chunk
        return MagicMock(done=lambda: False)

    app.analysis_executor.submit.side_effect = fake_submit
    app.analysis_future = None

    app._queue_backend_analysis(raw_transcript)

    app.transcript_intelligence.refine.assert_called_once_with(
        raw_transcript,
        context="Previous lecture context about machine learning.",
    )

    app.analysis_executor.submit.assert_called_once()

    assert submitted["raw_chunk"] == raw_transcript
    assert submitted["refined_chunk"] == refined_transcript


def test_application_does_not_analyze_without_complete_chunk(
    application_module,
):
    app = application_module.Application.__new__(
        application_module.Application
    )

    app.transcript_manager = MagicMock()
    app.transcript_intelligence = MagicMock()
    app.analysis_executor = MagicMock()
    app.analysis_future = None

    app.transcript_manager.get_new_analysis_text.return_value = None

    app._queue_backend_analysis(
        "This is an incomplete sentence"
    )

    app.transcript_intelligence.refine.assert_not_called()
    app.analysis_executor.submit.assert_not_called()


def test_application_does_not_queue_when_analysis_is_running(
    application_module,
):
    app = application_module.Application.__new__(
        application_module.Application
    )

    app.transcript_manager = MagicMock()
    app.transcript_intelligence = MagicMock()
    app.analysis_executor = MagicMock()

    app.analysis_future = MagicMock()
    app.analysis_future.done.return_value = False

    raw_transcript = (
        "The current lecture explains neural networks "
        "and their architecture."
    )

    app.transcript_manager.get_new_analysis_text.return_value = raw_transcript

    app._queue_backend_analysis(raw_transcript)

    app.transcript_intelligence.refine.assert_not_called()
    app.analysis_executor.submit.assert_not_called()


def test_application_falls_back_to_raw_chunk_when_refinement_fails(
    application_module,
):
    app = application_module.Application.__new__(
        application_module.Application
    )

    app.transcript_manager = MagicMock()
    app.transcript_intelligence = MagicMock()
    app.analysis_executor = MagicMock()
    app.analysis_future = None

    raw_transcript = (
        "The model is trained using a large training data set "
        "for better generalization."
    )

    app.transcript_manager.get_new_analysis_text.return_value = raw_transcript
    app.transcript_manager.get_analysis_context.return_value = (
        "Previous context."
    )

    app.transcript_intelligence.refine.side_effect = RuntimeError(
        "refinement failure"
    )

    submitted = {}

    def fake_submit(fn, raw_chunk, refined_chunk):
        submitted["raw_chunk"] = raw_chunk
        submitted["refined_chunk"] = refined_chunk
        return MagicMock()

    app.analysis_executor.submit.side_effect = fake_submit

    app._queue_backend_analysis(raw_transcript)

    assert submitted["raw_chunk"] == raw_transcript
    assert submitted["refined_chunk"] == raw_transcript


def test_application_uses_context_for_refinement(application_module):
    app = application_module.Application.__new__(
        application_module.Application
    )

    app.transcript_manager = MagicMock()
    app.transcript_intelligence = MagicMock()
    app.analysis_executor = MagicMock()
    app.analysis_future = None

    raw_chunk = (
        "The algorithm is trained on a training data set "
        "and evaluated on unseen examples."
    )

    context = (
        "Earlier the lecturer explained supervised learning "
        "and model evaluation."
    )

    app.transcript_manager.get_new_analysis_text.return_value = raw_chunk
    app.transcript_manager.get_analysis_context.return_value = context

    refinement = MagicMock()
    refinement.refined_text = raw_chunk
    app.transcript_intelligence.refine.return_value = refinement

    app.analysis_executor.submit.return_value = MagicMock()

    app._queue_backend_analysis(raw_chunk)

    app.transcript_manager.get_analysis_context.assert_called_once_with(
        transcript=raw_chunk,
        analysis_text=raw_chunk,
    )

    app.transcript_intelligence.refine.assert_called_once_with(
        raw_chunk,
        context=context,
    )