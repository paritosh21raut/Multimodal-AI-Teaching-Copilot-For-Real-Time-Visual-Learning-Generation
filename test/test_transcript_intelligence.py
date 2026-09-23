from __future__ import annotations

from app.transcript.transcript_intelligence import (
    TranscriptIntelligence,
)


def _fresh():
    ti = TranscriptIntelligence(
        min_words_per_chunk=1,
        max_sentences_per_chunk=10,
    )
    return ti


def test_incremental_duplicate_prefix_is_not_repeated():

    ti = _fresh()

    c1 = ti.process(
        "Today we are going to learn about the solar system."
    )
    assert c1 is not None

    ti.mark_analyzed(c1.text)

    # Same text plus more.
    c2 = ti.process(
        "Today we are going to learn about the solar system. "
        "The Sun is at the center."
    )

    # Only the new sentence should appear.
    assert c2 is not None
    assert "The Sun is at the center." in c2.text
    assert c2.text.count("Today we are going to learn") == 0


def test_noise_only_chunk_rejected():

    ti = _fresh()

    result = ti.process("and so")
    assert result is None

    result = ti.process("um uh")
    assert result is None


def test_authoritative_transcript_preserved():

    ti = _fresh()

    ti.process(
        "Today we are going to learn about the solar system."
    )

    ti.process(
        "Today we are going to learn about the solar system. "
        "The Sun is at the center."
    )

    full = ti.authoritative_transcript()

    assert "Today we are going to learn about the solar system." in full
    assert "The Sun is at the center." in full


def test_chronological_order():

    ti = _fresh()

    chunks = []

    for text in (
        "First statement.",
        "First statement. Second statement.",
        "First statement. Second statement. Third statement.",
    ):

        c = ti.process(text)

        if c is not None:
            chunks.append(c.text)

            ti.mark_analyzed(c.text)

    combined = " ".join(chunks)

    assert combined.index("First statement") < combined.index(
        "Second statement"
    )
    assert combined.index("Second statement") < combined.index(
        "Third statement"
    )


def test_sentence_boundary_required_without_force():

    ti = _fresh()

    # No terminal punctuation -> not eligible unless forced.
    assert ti.process("The Sun is at the center") is None

    forced = ti.process(
        "The Sun is at the center",
        force=True,
    )

    assert forced is not None
    assert "Sun is at the center" in forced.text