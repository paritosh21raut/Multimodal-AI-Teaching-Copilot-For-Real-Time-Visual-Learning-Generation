from __future__ import annotations

import os
import re
import sys
import time
import threading

import numpy as np
import sounddevice as sd


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
# PROJECT IMPORTS
# ============================================================

from app.audio.audio_queue import AudioQueue
from app.audio.audio_worker import AudioWorker


# ============================================================
# TEST CONFIGURATION
# ============================================================

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 320

# The speech should last roughly 45–55 seconds.
# The worker itself performs the actual 30-second split.
RECORDING_SECONDS = 60

TRANSCRIPT_PATH = (
    "outputs/audio_worker_test/"
    "hard_split_boundary_transcript.txt"
)


# ============================================================
# EXPECTED SPEECH
#
# IMPORTANT:
# Read these sentences exactly.
#
# Do NOT read the section headings.
# Do NOT say "sentence one", "sentence two", etc.
# Do NOT intentionally pause between sentences.
# Speak continuously at a normal lecture pace.
# ============================================================

EXPECTED_SPEECH = """
Today we are testing the thirty second boundary of the real time speech recognition pipeline.
The system continuously captures microphone audio and sends the speech through voice activity detection.
The first part of this test is deliberately long so that the production worker must create a hard segment boundary.
At the boundary the worker should preserve one second of overlapping audio before continuing with the next segment.
This overlap is important because a word can begin close to the segmentation point and must not be lost.
The second segment continues the same lecture without restarting the sentence or changing the topic.
The system must preserve the original order of the words while combining the two final transcriptions.
There should be no missing words caused by the thirty second split and there should be no repeated words caused by the one second overlap.
After the boundary we continue discussing automatic speech recognition, neural networks, transformer models, attention mechanisms, and speech transcription.
The final authoritative transcript should contain the complete lecture in the same order in which it was spoken.
This test is designed to verify that continuous speech remains reliable when one long recording is divided into multiple transcription segments.
"""


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for objective comparison.

    Punctuation and capitalization are ignored.
    """

    if not text:
        return ""

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)

    if not normalized:
        return []

    return normalized.split()


# ============================================================
# WORD ERROR RATE
# ============================================================

def calculate_wer(
    reference: str,
    hypothesis: str,
) -> tuple[float, int, int, int, int]:
    """
    Calculate word error rate.

    Returns:

        WER
        substitutions
        deletions
        insertions
        reference_word_count
    """

    reference_words = tokenize(reference)
    hypothesis_words = tokenize(hypothesis)

    n = len(reference_words)
    m = len(hypothesis_words)

    if n == 0:
        if m == 0:
            return 0.0, 0, 0, 0, 0

        return 1.0, 0, 0, m, 0

    # dp[i][j] = edit distance between
    # first i reference words and first j hypothesis words.
    dp = [
        [0] * (m + 1)
        for _ in range(n + 1)
    ]

    operation = [
        [None] * (m + 1)
        for _ in range(n + 1)
    ]

    for i in range(1, n + 1):
        dp[i][0] = i
        operation[i][0] = "delete"

    for j in range(1, m + 1):
        dp[0][j] = j
        operation[0][j] = "insert"

    for i in range(1, n + 1):

        for j in range(1, m + 1):

            if (
                reference_words[i - 1]
                == hypothesis_words[j - 1]
            ):

                dp[i][j] = dp[i - 1][j - 1]

                operation[i][j] = "correct"

            else:

                substitution = (
                    dp[i - 1][j - 1] + 1
                )

                deletion = (
                    dp[i - 1][j] + 1
                )

                insertion = (
                    dp[i][j - 1] + 1
                )

                best = min(
                    substitution,
                    deletion,
                    insertion,
                )

                dp[i][j] = best

                if best == substitution:
                    operation[i][j] = "substitute"

                elif best == deletion:
                    operation[i][j] = "delete"

                else:
                    operation[i][j] = "insert"

    substitutions = 0
    deletions = 0
    insertions = 0

    i = n
    j = m

    while i > 0 or j > 0:

        op = operation[i][j]

        if op == "correct":

            i -= 1
            j -= 1

        elif op == "substitute":

            substitutions += 1
            i -= 1
            j -= 1

        elif op == "delete":

            deletions += 1
            i -= 1

        elif op == "insert":

            insertions += 1
            j -= 1

        else:
            break

    wer = (
        substitutions
        + deletions
        + insertions
    ) / n

    return (
        wer,
        substitutions,
        deletions,
        insertions,
        n,
    )


# ============================================================
# N-GRAM DUPLICATION DETECTION
# ============================================================

def find_repeated_boundary_phrases(
    first_segment: str,
    second_segment: str,
    minimum_words: int = 3,
    maximum_words: int = 10,
) -> list[str]:
    """
    Find phrases repeated at the end of Segment 1 and
    beginning of Segment 2.

    This is specifically useful for detecting duplication
    caused by the one-second overlap.
    """

    first_words = tokenize(
        first_segment
    )

    second_words = tokenize(
        second_segment
    )

    if not first_words or not second_words:
        return []

    matches = []

    maximum = min(
        maximum_words,
        len(first_words),
        len(second_words),
    )

    for size in range(
        maximum,
        minimum_words - 1,
        -1,
    ):

        first_tail = first_words[-size:]
        second_head = second_words[:size]

        if first_tail == second_head:

            matches.append(
                " ".join(first_tail)
            )

    return matches


# ============================================================
# MICROPHONE STATE
# ============================================================

queue = None
callback_calls = 0
callback_errors = 0

callback_lock = threading.Lock()

final_results = []
preview_results = []

final_event = threading.Event()


# ============================================================
# CALLBACKS
# ============================================================

def microphone_callback(
    indata,
    frames,
    time_info,
    status,
):
    global callback_calls
    global callback_errors

    try:

        if status:
            print(
                f"[AUDIO STATUS] {status}"
            )

        chunk = (
            indata[:, 0]
            .copy()
            .astype(
                np.float32,
                copy=False,
            )
        )

        queue.put(
            chunk
        )

        with callback_lock:
            callback_calls += 1

    except Exception as error:

        with callback_lock:
            callback_errors += 1

        print(
            f"[CALLBACK ERROR] {error}"
        )


# ============================================================
# PREVIEW CALLBACK
# ============================================================

def on_preview(
    transcript,
    authoritative_transcript="",
):
    preview_results.append(
        transcript
    )


# ============================================================
# FINAL CALLBACK
# ============================================================

def on_final(
    transcript,
    authoritative_transcript="",
    segment_id=None,
):

    final_results.append(
        {
            "segment_id": segment_id,
            "transcript": transcript,
            "authoritative": authoritative_transcript,
        }
    )

    print()
    print(
        "------------------------------------------------------------"
    )

    print(
        f"[FINAL SEGMENT #{len(final_results)}]"
    )

    print(
        f"Segment ID: {segment_id}"
    )

    print(
        f"Text: {transcript}"
    )

    print(
        "------------------------------------------------------------"
    )


# ============================================================
# MAIN TEST
# ============================================================

def main():

    global queue

    print()
    print("=" * 70)
    print(
        "AI TEACHING COPILOT"
    )
    print(
        "30-SECOND HARD SPLIT + 1-SECOND OVERLAP TEST"
    )
    print("=" * 70)

    print()
    print(
        "This test uses the actual production:"
    )
    print(
        "  AudioQueue"
    )
    print(
        "  AudioWorker"
    )
    print(
        "  VoiceDetector"
    )
    print(
        "  SpeechSegmentBuilder"
    )
    print(
        "  WhisperWorker"
    )

    print()
    print(
        "No Gemini, Ollama, Dashboard, Slides, PPT, "
        "or Lecture Pipeline will start."
    )

    print()
    print("=" * 70)
    print(
        "EXPECTED SPEECH"
    )
    print("=" * 70)

    print(
        EXPECTED_SPEECH.strip()
    )

    print()
    print("=" * 70)
    print(
        "IMPORTANT INSTRUCTIONS"
    )
    print("=" * 70)

    print()
    print(
        "1. Read ONLY the speech above."
    )

    print(
        "2. Do NOT read the heading."
    )

    print(
        "3. Do NOT say sentence numbers."
    )

    print(
        "4. Speak continuously."
    )

    print(
        "5. Do NOT intentionally pause."
    )

    print(
        "6. Speak naturally at lecture speed."
    )

    print(
        "7. Try to finish the entire speech within "
        "about 45–55 seconds."
    )

    print(
        "8. The worker will automatically create "
        "the 30-second boundary."
    )

    print()
    print("=" * 70)

    input(
        "Press ENTER when you are ready..."
    )

    # ----------------------------------------------------------
    # Create queue.
    # ----------------------------------------------------------

    print()
    print(
        "Creating AudioQueue..."
    )

    queue = AudioQueue(
        max_chunks=1000
    )

    print(
        "[OK] AudioQueue created."
    )

    # ----------------------------------------------------------
    # Create worker.
    # ----------------------------------------------------------

    print()
    print(
        "Creating AudioWorker..."
    )

    worker = AudioWorker(
        audio_queue=queue,

        on_preview_transcript=on_preview,

        on_final_transcript=on_final,

        sample_rate=SAMPLE_RATE,

        silence_duration_seconds=1.2,

        minimum_speech_seconds=0.3,

        maximum_segment_seconds=30.0,

        overlap_seconds=1.0,

        pre_roll_seconds=0.25,

        preview_interval_seconds=3.0,

        preview_window_seconds=12.0,

        max_pending_final_jobs=4,

        transcript_path=TRANSCRIPT_PATH,
    )

    print(
        "[OK] AudioWorker created."
    )

    # ----------------------------------------------------------
    # Start worker.
    # ----------------------------------------------------------

    print()
    print(
        "Starting AudioWorker..."
    )

    worker.start()

    print(
        "[OK] AudioWorker started."
    )

    # ----------------------------------------------------------
    # Give worker a moment to initialize.
    # ----------------------------------------------------------

    time.sleep(1.0)

    # ----------------------------------------------------------
    # Start microphone.
    # ----------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "STARTING MICROPHONE"
    )
    print("=" * 70)

    print()
    print(
        "Starting in 3..."
    )

    time.sleep(1)

    print(
        "2..."
    )

    time.sleep(1)

    print(
        "1..."
    )

    time.sleep(1)

    print()
    print(
        ">>> GO — START READING NOW <<<"
    )

    print()

    stream = None

    start_time = time.monotonic()

    try:

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=microphone_callback,
        )

        stream.start()

        # ------------------------------------------------------
        # Automatically record for a fixed duration.
        #
        # This makes the test a single-run test.
        # ------------------------------------------------------

        while (
            time.monotonic()
            - start_time
            < RECORDING_SECONDS
        ):

            elapsed = (
                time.monotonic()
                - start_time
            )

            remaining = max(
                0,
                int(
                    RECORDING_SECONDS
                    - elapsed
                ),
            )

            if remaining % 10 == 0:

                print(
                    f"\rRecording... "
                    f"{remaining:02d}s remaining",
                    end="",
                    flush=True,
                )

            time.sleep(0.2)

        print()

    except KeyboardInterrupt:

        print()
        print(
            "Manual stop requested."
        )

    finally:

        # ------------------------------------------------------
        # Stop microphone.
        # ------------------------------------------------------

        if stream is not None:

            try:
                stream.stop()
            except Exception:
                pass

            try:
                stream.close()
            except Exception:
                pass

        print()
        print(
            "[OK] Microphone stopped."
        )

    # ----------------------------------------------------------
    # Stop worker.
    #
    # Worker drains already captured queue data before exiting.
    # ----------------------------------------------------------

    print()
    print(
        "Stopping AudioWorker..."
    )

    worker.stop()

    worker.join(
        timeout=30.0
    )

    if worker.is_alive():

        print(
            "[FAIL] AudioWorker did not stop "
            "within 30 seconds."
        )

    else:

        print(
            "[OK] AudioWorker stopped."
        )

    # ----------------------------------------------------------
    # Results.
    # ----------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "BOUNDARY TEST RESULTS"
    )
    print("=" * 70)

    print()

    print(
        f"Microphone callback calls : {callback_calls}"
    )

    print(
        f"Callback errors           : {callback_errors}"
    )

    print(
        f"Live previews             : "
        f"{len(preview_results)}"
    )

    print(
        f"Final segments            : "
        f"{len(final_results)}"
    )

    print()

    # ----------------------------------------------------------
    # Metrics.
    # ----------------------------------------------------------

    metrics = worker.get_metrics()

    print(
        "AUDIO WORKER METRICS"
    )

    print(
        "-" * 70
    )

    for key, value in metrics.items():

        if key in (
            "audio_queue",
            "vad",
        ):
            continue

        print(
            f"{key}: {value}"
        )

    print()

    # ----------------------------------------------------------
    # Queue statistics.
    # ----------------------------------------------------------

    print(
        "AUDIO QUEUE"
    )

    print(
        "-" * 70
    )

    queue_stats = queue.stats()

    print(
        queue_stats
    )

    print()

    # ----------------------------------------------------------
    # Segment ordering.
    # ----------------------------------------------------------

    print(
        "SEGMENT ORDER"
    )

    print(
        "-" * 70
    )

    segment_ids = [
        result["segment_id"]
        for result in final_results
        if result["segment_id"] is not None
    ]

    print(
        f"Segment IDs: {segment_ids}"
    )

    expected_ids = list(
        range(
            1,
            len(segment_ids) + 1,
        )
    )

    ordering_pass = (
        segment_ids == expected_ids
    )

    if ordering_pass:

        print(
            "[PASS] Final segment ordering is correct."
        )

    else:

        print(
            "[FAIL] Final segment ordering is incorrect."
        )

    print()

    # ----------------------------------------------------------
    # Require at least two segments.
    #
    # One hard split should occur during continuous speech.
    # ----------------------------------------------------------

    hard_splits = metrics.get(
        "hard_splits",
        0,
    )

    if hard_splits >= 1:

        print(
            "[PASS] At least one 30-second hard split occurred."
        )

    else:

        print(
            "[FAIL] No hard split occurred."
        )

    # ----------------------------------------------------------
    # Overlap verification.
    # ----------------------------------------------------------

    overlap_samples = metrics.get(
        "hard_split_overlap_samples",
        0,
    )

    expected_overlap_samples = (
        SAMPLE_RATE * 1
    )

    if overlap_samples >= expected_overlap_samples:

        print(
            "[PASS] 1-second overlap was retained."
        )

    else:

        print(
            "[FAIL] Expected 1-second overlap "
            "was not retained."
        )

    print()

    # ----------------------------------------------------------
    # Build final transcript.
    # ----------------------------------------------------------

    final_transcript = (
        worker.get_full_transcript()
    )

    print(
        "=" * 70
    )

    print(
        "AUTHORITATIVE TRANSCRIPT"
    )

    print(
        "=" * 70
    )

    print()

    print(
        final_transcript
    )

    print()

    # ----------------------------------------------------------
    # WER.
    # ----------------------------------------------------------

    (
        wer,
        substitutions,
        deletions,
        insertions,
        reference_words,
    ) = calculate_wer(
        EXPECTED_SPEECH,
        final_transcript,
    )

    print(
        "=" * 70
    )

    print(
        "WORD ERROR ANALYSIS"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"Reference words : {reference_words}"
    )

    print(
        f"WER             : {wer * 100:.2f}%"
    )

    print(
        f"Substitutions   : {substitutions}"
    )

    print(
        f"Deletions       : {deletions}"
    )

    print(
        f"Insertions      : {insertions}"
    )

    print()

    # ----------------------------------------------------------
    # Boundary duplication analysis.
    # ----------------------------------------------------------

    boundary_duplicates = []

    if len(final_results) >= 2:

        for index in range(
            len(final_results) - 1
        ):

            first = final_results[
                index
            ]["transcript"]

            second = final_results[
                index + 1
            ]["transcript"]

            duplicates = (
                find_repeated_boundary_phrases(
                    first,
                    second,
                )
            )

            for phrase in duplicates:

                if phrase not in boundary_duplicates:

                    boundary_duplicates.append(
                        phrase
                    )

    print(
        "=" * 70
    )

    print(
        "BOUNDARY DUPLICATION CHECK"
    )

    print(
        "=" * 70
    )

    print()

    if boundary_duplicates:

        print(
            "[WARNING] Repeated boundary phrases detected:"
        )

        for phrase in boundary_duplicates:

            print(
                f"  - {phrase}"
            )

    else:

        print(
            "[PASS] No obvious repeated boundary phrase detected."
        )

    print()

    # ----------------------------------------------------------
    # Final queue integrity.
    # ----------------------------------------------------------

    dropped_chunks = queue_stats.get(
        "dropped_chunks",
        0,
    )

    total_put = queue_stats.get(
        "total_put",
        0,
    )

    total_get = queue_stats.get(
        "total_get",
        0,
    )

    print(
        "=" * 70
    )

    print(
        "QUEUE INTEGRITY"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"Total captured : {total_put}"
    )

    print(
        f"Total processed: {total_get}"
    )

    print(
        f"Dropped chunks : {dropped_chunks}"
    )

    if dropped_chunks == 0:

        print(
            "[PASS] No audio chunks were dropped."
        )

    else:

        print(
            "[FAIL] Audio chunks were dropped."
        )

    print()

    # ----------------------------------------------------------
    # Save a detailed test report.
    # ----------------------------------------------------------

    report_path = os.path.abspath(
        "outputs/audio_worker_test/"
        "hard_split_boundary_report.txt"
    )

    os.makedirs(
        os.path.dirname(report_path),
        exist_ok=True,
    )

    with open(
        report_path,
        "w",
        encoding="utf-8",
    ) as report:

        report.write(
            "30-SECOND HARD SPLIT + 1-SECOND OVERLAP TEST\n"
        )

        report.write(
            "=" * 70
            + "\n\n"
        )

        report.write(
            "EXPECTED SPEECH\n\n"
        )

        report.write(
            EXPECTED_SPEECH.strip()
            + "\n\n"
        )

        report.write(
            "AUTHORITATIVE TRANSCRIPT\n\n"
        )

        report.write(
            final_transcript
            + "\n\n"
        )

        report.write(
            f"WER: {wer * 100:.2f}%\n"
        )

        report.write(
            f"Substitutions: {substitutions}\n"
        )

        report.write(
            f"Deletions: {deletions}\n"
        )

        report.write(
            f"Insertions: {insertions}\n\n"
        )

        report.write(
            "FINAL SEGMENTS\n\n"
        )

        for result in final_results:

            report.write(
                f"Segment ID: "
                f"{result['segment_id']}\n"
            )

            report.write(
                result["transcript"]
                + "\n\n"
            )

        report.write(
            "BOUNDARY DUPLICATES\n\n"
        )

        if boundary_duplicates:

            for phrase in boundary_duplicates:

                report.write(
                    phrase
                    + "\n"
                )

        else:

            report.write(
                "None detected.\n"
            )

    print(
        f"Detailed report saved to:\n"
        f"{report_path}"
    )

    # ----------------------------------------------------------
    # Basic verdict.
    #
    # We deliberately do NOT require WER == 0 because Whisper
    # itself can make recognition errors. The boundary-specific
    # checks are what matter here.
    # ----------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "BOUNDARY TEST VERDICT"
    )
    print("=" * 70)

    print()

    boundary_pass = (
        hard_splits >= 1
        and overlap_samples >= expected_overlap_samples
        and len(final_results) >= 2
        and ordering_pass
        and dropped_chunks == 0
        and not boundary_duplicates
        and not worker.is_alive()
        and callback_errors == 0
    )

    if boundary_pass:

        print(
            "[PASS] 30-second hard split + "
            "1-second overlap passed the structural test."
        )

    else:

        print(
            "[FAIL] Boundary test requires investigation."
        )

    print()

    print(
        "NOTE:"
    )

    print(
        "WER measures overall Whisper recognition accuracy."
    )

    print(
        "It does not by itself prove that a particular word "
        "was lost specifically at the boundary."
    )

    print(
        "The segment ordering, overlap, duplicate detection, "
        "and segment contents must be inspected together."
    )

    print()


if __name__ == "__main__":
    main()