from app.audio.live_transcript_manager import LiveTranscriptManager


def test_update_stores_full_transcript():
    manager = LiveTranscriptManager()

    transcript = (
        "The signal is periodic. "
        "The system processes the signal."
    )

    manager.update(transcript)

    assert manager.get_full_transcript() == transcript


def test_analysis_returns_complete_sentences():
    manager = LiveTranscriptManager()

    transcript = (
        "The signal is periodic and repeats after a fixed interval. "
        "The system processes the signal using several stages of filtering "
        "and amplification. "
        "This is an important concept in digital signal processing."
    )

    manager.update(transcript)

    result = manager.get_new_analysis_text(transcript)

    assert result
    assert "The signal is periodic" in result
    assert result.endswith(".")


def test_analyzed_sentences_are_not_returned_again():
    manager = LiveTranscriptManager()

    transcript = (
        "The signal is periodic and repeats after a fixed interval. "
        "The system processes the signal using several stages of filtering "
        "and amplification."
    )

    manager.update(transcript)

    first = manager.get_new_analysis_text(transcript)

    assert first

    manager.mark_analyzed(first)

    second = manager.get_new_analysis_text(transcript)

    assert second is None


def test_topic_boundary_with_exact_raw_text():
    manager = LiveTranscriptManager()

    transcript = (
        "The signal is periodic. "
        "The system processes the signal."
    )

    manager.update(transcript)

    manager.start_new_topic(
        topic="Signal Processing",
        boundary_text="The system processes the signal.",
    )

    assert (
        manager.current_paragraph
        == "The system processes the signal."
    )


def test_topic_boundary_with_refined_text():
    """
    TranscriptIntelligence may remove speech artifacts before
    the refined text reaches the lecture pipeline.
    """

    manager = LiveTranscriptManager()

    raw_transcript = (
        "Um the signal is periodic. "
        "The system processes the signal."
    )

    manager.update(raw_transcript)

    refined_boundary = "The signal is periodic."

    manager.start_new_topic(
        topic="Signal Processing",
        boundary_text=refined_boundary,
    )

    assert manager.current_paragraph
    assert refined_boundary in manager.current_paragraph


def test_topic_boundary_after_transcript_refinement():
    manager = LiveTranscriptManager()

    raw_transcript = (
        "Um the the signal is periodic. "
        "The system processes the signal."
    )

    refined_boundary = "the signal is periodic."

    manager.update(raw_transcript)

    manager.start_new_topic(
        topic="Periodic Signals",
        boundary_text=refined_boundary,
    )

    assert manager.current_paragraph
    assert refined_boundary in manager.current_paragraph


def test_reset_clears_transcript_state():
    manager = LiveTranscriptManager()

    manager.update(
        "The signal is periodic. "
        "The system processes the signal."
    )

    manager.reset()

    assert manager.get_full_transcript() == ""
    assert manager.current_paragraph == ""