from __future__ import annotations

import os
import sys


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# IMPORT
# ============================================================

from app.audio.audio_worker import AudioWorker


# ============================================================
# TEST 1
# Previous segment ends with an incomplete sentence.
# Current segment completes that sentence.
# ============================================================

def test_hard_split_repairs_incomplete_previous_sentence():

    previous = (
        "When fine tuned on standard benchmarks, "
        "this approach has improved the state of the"
    )

    current = (
        "improve the state of the art, especially "
        "in a low data setting."
    )

    result = AudioWorker._merge_transcript(
        previous,
        current,
        hard_split=True,
    )

    assert (
        "improved the state of the improve the state"
        not in result
    )

    assert (
        "improved the state of the art"
        in result
    )

    assert result.endswith(
        "in a low data setting."
    )


# ============================================================
# TEST 2
# Whisper produces a false sentence boundary at the split.
#
# Previous:
#     ... a complex process.
#
# Current:
#     complex processes requiring...
#
# The current complete sentence should replace the
# incomplete/incorrect boundary representation.
# ============================================================

def test_hard_split_repairs_repeated_sentence_start():

    previous = (
        "This unfortunately limits their usefulness "
        "and impact as fine tuning can still be a "
        "complex process."
    )

    current = (
        "complex processes requiring a skilled practitioner. "
        "There is an additional risk with requiring fine tuning."
    )

    result = AudioWorker._merge_transcript(
        previous,
        current,
        hard_split=True,
    )

    assert (
        "complex process. complex processes"
        not in result
    )

    assert (
        "complex processes requiring a skilled practitioner."
        in result
    )

    assert (
        "There is an additional risk with requiring fine tuning."
        in result
    )


# ============================================================
# TEST 3
# Decimal values must NOT be treated as sentence boundaries.
#
# "9.2%" must remain intact.
# ============================================================

def test_hard_split_does_not_break_decimal_numbers():

    previous = (
        "The experiment documented a "
        "9.2% increase in"
    )

    current = (
        "increase in object classification accuracy. "
        "The improvement was measured across several datasets."
    )

    result = AudioWorker._merge_transcript(
        previous,
        current,
        hard_split=True,
    )

    assert "9.2%" in result

    assert (
        "9.2% increase in object classification accuracy."
        in result
    )


# ============================================================
# TEST 4
# Normal endpoint behavior must continue using exact
# token overlap.
# ============================================================

def test_natural_endpoint_exact_overlap_is_preserved():

    previous = (
        "The model learns useful representations "
        "of speech and language"
    )

    current = (
        "of speech and language from large datasets."
    )

    result = AudioWorker._merge_transcript(
        previous,
        current,
        hard_split=False,
    )

    assert result == (
        "The model learns useful representations "
        "of speech and language from large datasets."
    )


# ============================================================
# TEST 5
# Hard split with no useful sentence-boundary evidence
# must safely fall back to the existing exact-overlap
# behavior instead of deleting text.
# ============================================================

def test_hard_split_falls_back_safely():

    previous = (
        "The system uses neural networks "
        "for speech recognition"
    )

    current = (
        "for speech recognition and transformer "
        "models for contextual processing."
    )

    result = AudioWorker._merge_transcript(
        previous,
        current,
        hard_split=True,
    )

    assert result == (
        "The system uses neural networks "
        "for speech recognition and transformer "
        "models for contextual processing."
    )


# ============================================================
# TEST 6
# Empty inputs must remain safe.
# ============================================================

def test_empty_previous():

    result = AudioWorker._merge_transcript(
        "",
        "This is a test.",
        hard_split=True,
    )

    assert result == "This is a test."


def test_empty_current():

    result = AudioWorker._merge_transcript(
        "This is a test.",
        "",
        hard_split=True,
    )

    assert result == "This is a test."


# ============================================================
# TEST 7
# Normal repeated boundary phrase should still be removed.
# ============================================================

def test_exact_boundary_overlap_is_removed():

    previous = (
        "The attention mechanism processes "
        "the input sequence"
    )

    current = (
        "the input sequence before generating "
        "the final representation."
    )

    result = AudioWorker._merge_transcript(
        previous,
        current,
        hard_split=True,
    )

    assert result == (
        "The attention mechanism processes "
        "the input sequence before generating "
        "the final representation."
    )