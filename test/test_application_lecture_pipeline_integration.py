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


def test_refined_transcript_reaches_lecture_pipeline(
    application_module,
):
    app = application_module.Application.__new__(
        application_module.Application
    )

    app.transcript_manager = MagicMock()

    application_module.lecture_pipeline.process_transcript.return_value = {
        "is_relevant": True,
        "is_new_topic": False,
        "topic": "",
    }

    raw_chunk = (
        "The model uses a training data set "
        "to learn the underlying representation."
    )

    refined_chunk = (
        "The model uses a training dataset "
        "to learn the underlying representation."
    )

    app._analyze_chunk(
        raw_chunk,
        refined_chunk,
    )

    application_module.lecture_pipeline.process_transcript.assert_called_once_with(
        refined_chunk
    )

    app.transcript_manager.mark_analyzed.assert_called_once_with(
        raw_chunk
    )


def test_new_topic_uses_refined_boundary(application_module):
    app = application_module.Application.__new__(
        application_module.Application
    )

    app.transcript_manager = MagicMock()

    application_module.lecture_pipeline.process_transcript.return_value = {
        "is_relevant": True,
        "is_new_topic": True,
        "topic": "Neural Networks",
    }

    raw_chunk = (
        "Now we will discuss the neural network training data set."
    )

    refined_chunk = (
        "Now we will discuss the neural network training dataset."
    )

    app._analyze_chunk(
        raw_chunk,
        refined_chunk,
    )

    application_module.lecture_pipeline.process_transcript.assert_called_once_with(
        refined_chunk
    )

    app.transcript_manager.mark_analyzed.assert_called_once_with(
        raw_chunk
    )

    app.transcript_manager.start_new_topic.assert_called_once_with(
        topic="Neural Networks",
        boundary_text=refined_chunk,
    )


def test_irrelevant_refined_transcript_is_not_marked_analyzed(
    application_module,
):
    app = application_module.Application.__new__(
        application_module.Application
    )

    app.transcript_manager = MagicMock()

    application_module.lecture_pipeline.process_transcript.return_value = {
        "is_relevant": False,
        "is_new_topic": False,
        "topic": "",
    }

    raw_chunk = (
        "This is unrelated background conversation "
        "that should not enter the lecture pipeline."
    )

    refined_chunk = (
        "This is unrelated background conversation "
        "that should not enter the lecture pipeline."
    )

    app._analyze_chunk(
        raw_chunk,
        refined_chunk,
    )

    application_module.lecture_pipeline.process_transcript.assert_called_once_with(
        refined_chunk
    )

    app.transcript_manager.mark_analyzed.assert_not_called()
    app.transcript_manager.start_new_topic.assert_not_called()