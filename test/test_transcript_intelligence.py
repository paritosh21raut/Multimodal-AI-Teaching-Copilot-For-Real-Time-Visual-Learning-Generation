from __future__ import annotations

import pytest

from app.speech.transcript_intelligence import (
    TranscriptCorrection,
    TranscriptIntelligence,
)


@pytest.fixture
def intelligence():
    return TranscriptIntelligence()


# ==========================================================
# EMPTY INPUT
# ==========================================================


def test_empty_input(intelligence):
    result = intelligence.refine("")

    assert result.original_text == ""
    assert result.refined_text == ""
    assert result.changed is False
    assert result.quality_score == 0.0
    assert result.corrections == []


def test_whitespace_only_input(intelligence):
    result = intelligence.refine("   \n\t   ")

    assert result.refined_text == ""
    assert result.changed is False
    assert result.quality_score == 0.0


# ==========================================================
# WHITESPACE NORMALIZATION
# ==========================================================


def test_whitespace_normalization(intelligence):
    result = intelligence.refine(
        "  The   signal    is   periodic.  "
    )

    assert result.refined_text == (
        "The signal is periodic."
    )
    assert result.changed is True


def test_newline_and_tab_normalization(intelligence):
    result = intelligence.refine(
        "The signal\n\tis\r\nperiodic."
    )

    assert result.refined_text == (
        "The signal is periodic."
    )


# ==========================================================
# FILLER REMOVAL
# ==========================================================


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "Um the signal is periodic.",
            "the signal is periodic.",
        ),
        (
            "Uh the system processes the signal.",
            "the system processes the signal.",
        ),
        (
            "Basically the system has three stages.",
            "the system has three stages.",
        ),
        (
            "You know the signal is periodic.",
            "the signal is periodic.",
        ),
        (
            "I mean the output is amplified.",
            "the output is amplified.",
        ),
        (
            "The system is kind of complex.",
            "The system is complex.",
        ),
        (
            "The system is sort of complex.",
            "The system is complex.",
        ),
    ],
)
def test_filler_removal(
    intelligence,
    text,
    expected,
):
    result = intelligence.refine(text)

    assert result.refined_text == expected
    assert result.changed is True

    assert any(
        correction.correction_type == "filler"
        for correction in result.corrections
    )


# ==========================================================
# REPEATED WORD CLEANUP
# ==========================================================


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "The the signal is periodic.",
            "The signal is periodic.",
        ),
        (
            "This this system processes signals.",
            "This system processes signals.",
        ),
        (
            "The signal signal is periodic.",
            "The signal is periodic.",
        ),
    ],
)
def test_repeated_word_removal(
    intelligence,
    text,
    expected,
):
    result = intelligence.refine(text)

    assert result.refined_text == expected
    assert result.changed is True

    assert any(
        correction.correction_type == "repetition"
        for correction in result.corrections
    )


# ==========================================================
# REPEATED PHRASE CLEANUP
# ==========================================================


def test_repeated_phrase_removal(intelligence):
    text = (
        "The signal is periodic "
        "The signal is periodic "
        "and repeats continuously."
    )

    result = intelligence.refine(text)

    assert result.refined_text == (
        "The signal is periodic "
        "and repeats continuously."
    )

    assert result.changed is True


def test_long_repeated_phrase_removal(intelligence):
    text = (
        "The transmitter converts the information "
        "into an electrical signal "
        "The transmitter converts the information "
        "into an electrical signal "
        "before transmission."
    )

    result = intelligence.refine(text)

    assert result.refined_text == (
        "The transmitter converts the information "
        "into an electrical signal before transmission."
    )


def test_legitimate_non_repeated_text_is_preserved(
    intelligence,
):
    text = (
        "The transmitter converts information "
        "into an electrical signal before transmission."
    )

    result = intelligence.refine(text)

    assert result.refined_text == text


# ==========================================================
# PUNCTUATION CLEANUP
# ==========================================================


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "The signal , is periodic.",
            "The signal, is periodic.",
        ),
        (
            "The signal . It repeats.",
            "The signal. It repeats.",
        ),
        (
            "The signal,is periodic.",
            "The signal, is periodic.",
        ),
        (
            "The signal.is periodic.",
            "The signal. is periodic.",
        ),
    ],
)
def test_punctuation_cleanup(
    intelligence,
    text,
    expected,
):
    result = intelligence.refine(text)

    assert result.refined_text == expected

    assert any(
        correction.correction_type == "punctuation"
        for correction in result.corrections
    )


# ==========================================================
# GENERIC TERMINOLOGY NORMALIZATION
# ==========================================================


def test_dataset_normalization(intelligence):
    result = intelligence.refine(
        "The model uses a large data set."
    )

    assert "dataset" in result.refined_text


def test_fine_tuning_normalization(intelligence):
    result = intelligence.refine(
        "Fine tuning is required for the task."
    )

    assert "fine-tuning" in result.refined_text


def test_held_out_normalization(intelligence):
    result = intelligence.refine(
        "The model performs well on held out data."
    )

    assert "held-out data" in result.refined_text


def test_pre_training_normalization(intelligence):
    result = intelligence.refine(
        "The model uses pre training."
    )

    assert "pre-training" in result.refined_text


def test_pre_trained_normalization(intelligence):
    result = intelligence.refine(
        "A pre trained model is evaluated."
    )

    assert "pre-trained" in result.refined_text


def test_high_quality_normalization(intelligence):
    result = intelligence.refine(
        "The system produces high quality output."
    )

    assert "high-quality" in result.refined_text


def test_real_time_normalization(intelligence):
    result = intelligence.refine(
        "The system supports real time processing."
    )

    assert "real-time" in result.refined_text


# ==========================================================
# TECHNICAL TERMS ARE NOT AGGRESSIVELY REWRITTEN
# ==========================================================


def test_unknown_technical_term_is_preserved(
    intelligence,
):
    text = (
        "The system uses an experimental XQZ architecture."
    )

    result = intelligence.refine(text)

    assert "XQZ" in result.refined_text


def test_acronyms_are_preserved(intelligence):
    text = (
        "The ESR measurement is used with "
        "LVSCR and ASI parameters."
    )

    result = intelligence.refine(text)

    assert "ESR" in result.refined_text
    assert "LVSCR" in result.refined_text
    assert "ASI" in result.refined_text


def test_named_technical_term_is_preserved(
    intelligence,
):
    text = (
        "The system uses a transformer architecture."
    )

    result = intelligence.refine(text)

    assert result.refined_text == text


# ==========================================================
# CONTEXT / BOUNDARY REPAIR
# ==========================================================


def test_context_does_not_delete_valid_continuation(
    intelligence,
):
    result = intelligence.refine(
        "standard benchmarks, this approach "
        "improved the state of the art.",
        context=(
            "The method was evaluated on "
            "standard benchmarks."
        ),
    )

    assert result.refined_text == (
        "standard benchmarks, this approach "
        "improved the state of the art."
    )


def test_context_boundary_overlap_with_real_overlap(
    intelligence,
):
    result = intelligence.refine(
        "standard benchmarks, this approach "
        "improved the state of the art.",
        context=(
            "The method was evaluated on "
            "standard benchmarks."
        ),
    )

    assert result.refined_text == (
        "standard benchmarks, this approach "
        "improved the state of the art."
    )


def test_unrelated_context_does_not_change_text(
    intelligence,
):
    text = (
        "The communication system transmits "
        "information through the channel."
    )

    context = (
        "The previous discussion covered "
        "a completely different concept."
    )

    result = intelligence.refine(
        text,
        context=context,
    )

    assert result.refined_text == text


# ==========================================================
# GENERIC CONTEXT-AWARE CORRECTION
# ==========================================================


def test_context_can_support_obvious_word_correction(
    intelligence,
):
    result = intelligence.refine(
        "The model uses a transformer arctitecture.",
        context=(
            "The lecture discusses transformer "
            "architecture and attention mechanisms."
        ),
    )

    assert (
        "transformer architecture"
        in result.refined_text
    )


def test_context_can_support_obvious_spelling_correction(
    intelligence,
):
    result = intelligence.refine(
        "The transmitter sends a signel.",
        context=(
            "The transmitter sends a signal "
            "through the communication channel."
        ),
    )

    assert "signal" in result.refined_text


def test_context_can_support_domain_neutral_correction(
    intelligence,
):
    result = intelligence.refine(
        "The experiment produced consistant results.",
        context=(
            "The experiment produced consistent "
            "results across multiple trials."
        ),
    )

    assert "consistent results" in result.refined_text


def test_context_correction_requires_strong_evidence(
    intelligence,
):
    text = (
        "The system uses an experimental XQZ module."
    )

    context = (
        "The lecture discusses neural networks "
        "and signal processing."
    )

    result = intelligence.refine(
        text,
        context=context,
    )

    assert result.refined_text == text


def test_context_does_not_replace_valid_word(
    intelligence,
):
    text = (
        "The system uses a channel for transmission."
    )

    context = (
        "The lecture discusses communication "
        "channels and transmission systems."
    )

    result = intelligence.refine(
        text,
        context=context,
    )

    assert "channel" in result.refined_text


# ==========================================================
# CONSERVATIVE BEHAVIOR
# ==========================================================


def test_low_confidence_without_context_is_conservative(
    intelligence,
):
    text = (
        "The model performs well on unusual data."
    )

    result = intelligence.refine(text)

    assert "unusual data" in result.refined_text


def test_clean_text_is_preserved(intelligence):
    text = (
        "The communication system transmits information."
    )

    result = intelligence.refine(text)

    assert result.refined_text == text
    assert result.changed is False
    assert result.quality_score == 1.0


def test_normal_lecture_text_is_preserved(
    intelligence,
):
    text = (
        "In a cellular communication system, "
        "the available spectrum is divided into "
        "multiple frequency channels. "
        "Each cell is assigned a group of channels."
    )

    result = intelligence.refine(text)

    assert result.refined_text == text
    assert result.changed is False
    assert result.quality_score == 1.0


def test_no_hallucination_on_clean_text(
    intelligence,
):
    text = (
        "The neural network receives an input signal "
        "and produces an output classification."
    )

    result = intelligence.refine(text)

    assert result.refined_text == text


def test_no_aggressive_sentence_rewrite(
    intelligence,
):
    text = (
        "The communication channel introduces "
        "noise into the transmitted signal."
    )

    result = intelligence.refine(text)

    assert result.refined_text == text


# ==========================================================
# COMBINED CLEANUP
# ==========================================================


def test_combined_cleanup(intelligence):
    text = (
        "  Um  the  the signal , "
        "is periodic. "
        "The signal is periodic.  "
    )

    result = intelligence.refine(text)

    assert result.refined_text == (
        "the signal, is periodic."
    )

    assert result.changed is True

    correction_types = {
        correction.correction_type
        for correction in result.corrections
    }

    assert "filler" in correction_types
    assert "repetition" in correction_types
    assert "punctuation" in correction_types


# ==========================================================
# QUALITY SCORE
# ==========================================================


def test_quality_score_range(intelligence):
    cases = [
        "",
        "The signal is periodic.",
        "Um the signal is periodic.",
        "The the signal is periodic.",
        "The model performs well on unusual data.",
    ]

    for text in cases:
        result = intelligence.refine(text)

        assert (
            0.0
            <= result.quality_score
            <= 1.0
        )


def test_clean_text_has_high_quality_score(
    intelligence,
):
    result = intelligence.refine(
        "The communication system transmits information."
    )

    assert result.quality_score == 1.0


def test_refined_text_quality_does_not_go_below_zero(
    intelligence,
):
    result = intelligence.refine(
        "Um uh er ah basically you know "
        "the signal is periodic."
    )

    assert result.quality_score >= 0.0
    assert result.quality_score <= 1.0


# ==========================================================
# RESULT STRUCTURE
# ==========================================================


def test_result_structure(intelligence):
    result = intelligence.refine(
        "The signal is periodic."
    )

    assert result.original_text == (
        "The signal is periodic."
    )

    assert result.refined_text == (
        "The signal is periodic."
    )

    assert isinstance(
        result.changed,
        bool,
    )

    assert isinstance(
        result.quality_score,
        float,
    )

    assert isinstance(
        result.corrections,
        list,
    )


# ==========================================================
# CORRECTION METADATA
# ==========================================================


def test_correction_metadata(intelligence):
    result = intelligence.refine(
        "The transmitter sends a signel.",
        context=(
            "The transmitter sends a signal "
            "through the communication channel."
        ),
    )

    assert result.corrections

    correction = next(
        correction
        for correction in result.corrections
        if correction.correction_type
        == "contextual_spelling"
    )

    assert correction.original == "signel"
    assert correction.replacement == "signal"
    assert correction.confidence >= 0.80

    for correction in result.corrections:
        assert isinstance(
            correction,
            TranscriptCorrection,
        )

        assert correction.original
        assert correction.replacement
        assert correction.correction_type

        assert (
            0.0
            <= correction.confidence
            <= 1.0
        )


def test_terminology_correction_metadata(
    intelligence,
):
    result = intelligence.refine(
        "The model uses data set processing."
    )

    terminology_corrections = [
        correction
        for correction in result.corrections
        if correction.correction_type
        == "terminology"
    ]

    assert terminology_corrections

    for correction in terminology_corrections:
        assert correction.confidence >= 0.90


# ==========================================================
# IDEMPOTENCY
# ==========================================================


def test_refinement_is_idempotent(
    intelligence,
):
    text = (
        "Um the signal is repeated "
        "and uses held out data."
    )

    first = intelligence.refine(text)

    second = intelligence.refine(
        first.refined_text
    )

    assert (
        second.refined_text
        == first.refined_text
    )


def test_contextual_refinement_is_idempotent(
    intelligence,
):
    text = (
        "The experiment produced consistant results."
    )

    context = (
        "The experiment produced consistent "
        "results across multiple trials."
    )

    first = intelligence.refine(
        text,
        context=context,
    )

    second = intelligence.refine(
        first.refined_text,
        context=context,
    )

    assert (
        second.refined_text
        == first.refined_text
    )


# ==========================================================
# REALISTIC WHISPER ERRORS
# ==========================================================


def test_realistic_spelling_error(
    intelligence,
):
    result = intelligence.refine(
        "The receiver measures the frequncy "
        "of the incoming signal.",
        context=(
            "The receiver measures the frequency "
            "of the incoming signal."
        ),
    )

    assert "frequency" in result.refined_text


def test_realistic_missing_word_context(
    intelligence,
):
    result = intelligence.refine(
        "The system uses a modulation scheme.",
        context=(
            "The communication system uses "
            "a modulation scheme to transmit information."
        ),
    )

    assert "modulation scheme" in result.refined_text


def test_realistic_repeated_whisper_output(
    intelligence,
):
    result = intelligence.refine(
        "The signal is the signal is periodic."
    )

    assert result.refined_text == (
        "The signal is periodic."
    )


def test_realistic_filler_heavy_whisper_output(
    intelligence,
):
    result = intelligence.refine(
        "Um basically the system uh processes "
        "the signal you know in real time."
    )

    assert result.refined_text == (
        "the system processes the signal in real-time."
    )


# ==========================================================
# TOPIC AGNOSTICITY
# ==========================================================


@pytest.mark.parametrize(
    "text",
    [
        (
            "The transistor amplifies the input signal."
        ),
        (
            "The neural network processes the input vector."
        ),
        (
            "The cell membrane controls molecular transport."
        ),
        (
            "The beam bends when it passes through the lens."
        ),
        (
            "The algorithm sorts the elements by value."
        ),
        (
            "The engine converts thermal energy into work."
        ),
        (
            "The chemical reaction releases energy."
        ),
    ],
)
def test_clean_text_is_topic_agnostic(
    intelligence,
    text,
):
    result = intelligence.refine(text)

    assert result.refined_text == text
    assert result.changed is False


def test_context_correction_is_topic_agnostic(
    intelligence,
):
    result = intelligence.refine(
        "The circuit uses a resistence.",
        context=(
            "The circuit uses a resistance "
            "to limit current."
        ),
    )

    assert "resistance" in result.refined_text


# ==========================================================
# NO TOPIC-SPECIFIC KNOWLEDGE
# ==========================================================


def test_no_topic_specific_semantic_dictionary(
    intelligence,
):
    assert not hasattr(
        intelligence,
        "_SEMANTIC_CANDIDATES",
    )


def test_no_hardcoded_domain_replacement_engine(
    intelligence,
):
    text = (
        "The system uses an unknown "
        "experimental component."
    )

    result = intelligence.refine(
        text,
        context=(
            "The lecture discusses a completely "
            "different subject."
        ),
    )

    assert result.refined_text == text