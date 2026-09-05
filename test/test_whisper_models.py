from __future__ import annotations

import re
import sys
import time
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# CONFIGURATION
# ============================================================

SAMPLE_RATE = 16000

MODEL_NAME = "small"
MODEL_DEVICE = "cpu"
MODEL_COMPUTE_TYPE = "int8"

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "whisper_model_benchmark"
)

AUDIO_PATH = (
    OUTPUT_DIR
    / "benchmark_recording.wav"
)

REPORT_PATH = (
    OUTPUT_DIR
    / "small_validation_report.txt"
)


# ============================================================
# REFERENCE SPEECH
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

def normalize_text(
    text: str,
) -> str:

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


def tokenize(
    text: str,
) -> list[str]:

    normalized = normalize_text(
        text
    )

    if not normalized:
        return []

    return normalized.split()


# ============================================================
# WER
# ============================================================

def calculate_wer(
    reference: str,
    hypothesis: str,
) -> tuple[float, int, int, int, int]:

    reference_words = tokenize(
        reference
    )

    hypothesis_words = tokenize(
        hypothesis
    )

    n = len(reference_words)
    m = len(hypothesis_words)

    if n == 0:

        if m == 0:
            return 0.0, 0, 0, 0, 0

        return 1.0, 0, 0, m, 0

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
                    dp[i - 1][j - 1]
                    + 1
                )

                deletion = (
                    dp[i - 1][j]
                    + 1
                )

                insertion = (
                    dp[i][j - 1]
                    + 1
                )

                best = min(
                    substitution,
                    deletion,
                    insertion,
                )

                dp[i][j] = best

                if best == substitution:

                    operation[i][j] = (
                        "substitute"
                    )

                elif best == deletion:

                    operation[i][j] = (
                        "delete"
                    )

                else:

                    operation[i][j] = (
                        "insert"
                    )

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
# LOAD WAV
# ============================================================

def load_wav(
    path: Path,
) -> np.ndarray:

    if not path.exists():

        raise FileNotFoundError(
            f"Recording not found:\n{path}"
        )

    with wave.open(
        str(path),
        "rb",
    ) as wav:

        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frame_count = wav.getnframes()

        raw = wav.readframes(
            frame_count
        )

    if sample_width != 2:

        raise ValueError(
            "Expected 16-bit PCM WAV."
        )

    audio = np.frombuffer(
        raw,
        dtype=np.int16,
    ).astype(
        np.float32
    )

    if channels > 1:

        audio = audio.reshape(
            -1,
            channels,
        ).mean(
            axis=1
        )

    audio /= 32768.0

    if sample_rate != SAMPLE_RATE:

        raise ValueError(
            f"Expected {SAMPLE_RATE} Hz audio, "
            f"got {sample_rate} Hz."
        )

    return audio


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)

    print(
        "AI TEACHING COPILOT"
    )

    print(
        "WHISPER SMALL VALIDATION"
    )

    print("=" * 70)

    print()

    print(
        f"Model         : {MODEL_NAME}"
    )

    print(
        f"Device        : {MODEL_DEVICE}"
    )

    print(
        f"Compute type  : {MODEL_COMPUTE_TYPE}"
    )

    print(
        f"Audio         : {AUDIO_PATH}"
    )

    print()

    # --------------------------------------------------------
    # Load recording.
    # --------------------------------------------------------

    audio = load_wav(
        AUDIO_PATH
    )

    duration = (
        len(audio)
        / SAMPLE_RATE
    )

    print(
        "[OK] Recording loaded."
    )

    print(
        f"Samples       : {len(audio):,}"
    )

    print(
        f"Duration      : {duration:.3f}s"
    )

    # --------------------------------------------------------
    # Load model.
    # --------------------------------------------------------

    print()
    print("=" * 70)

    print(
        "LOADING WHISPER SMALL"
    )

    print("=" * 70)

    load_start = time.perf_counter()

    model = WhisperModel(
        MODEL_NAME,
        device=MODEL_DEVICE,
        compute_type=MODEL_COMPUTE_TYPE,
    )

    load_time = (
        time.perf_counter()
        - load_start
    )

    print(
        f"Model loaded in {load_time:.3f}s"
    )

    # --------------------------------------------------------
    # Transcription.
    # --------------------------------------------------------

    print()
    print(
        "Transcribing..."
    )

    start = time.perf_counter()

    segments, info = model.transcribe(
        audio,
        language="en",
        beam_size=5,
        vad_filter=True,
    )

    text_parts = []

    segment_count = 0

    for segment in segments:

        segment_count += 1

        text = segment.text.strip()

        if text:
            text_parts.append(
                text
            )

    transcription_time = (
        time.perf_counter()
        - start
    )

    transcript = " ".join(
        text_parts
    ).strip()

    # --------------------------------------------------------
    # Metrics.
    # --------------------------------------------------------

    real_time_factor = (
        transcription_time
        / duration
    )

    speed_multiplier = (
        duration
        / transcription_time
    )

    (
        wer,
        substitutions,
        deletions,
        insertions,
        reference_words,
    ) = calculate_wer(
        EXPECTED_SPEECH,
        transcript,
    )

    # --------------------------------------------------------
    # Console result.
    # --------------------------------------------------------

    print()
    print("=" * 70)

    print(
        "WHISPER SMALL RESULT"
    )

    print("=" * 70)

    print()

    print(
        f"Audio duration     : "
        f"{duration:.3f}s"
    )

    print(
        f"Model load time    : "
        f"{load_time:.3f}s"
    )

    print(
        f"Transcription time : "
        f"{transcription_time:.3f}s"
    )

    print(
        f"Real-time factor   : "
        f"{real_time_factor:.4f}x"
    )

    print(
        f"Realtime speed     : "
        f"{speed_multiplier:.2f}x"
    )

    print(
        f"WER                : "
        f"{wer * 100:.2f}%"
    )

    print(
        f"Substitutions      : "
        f"{substitutions}"
    )

    print(
        f"Deletions          : "
        f"{deletions}"
    )

    print(
        f"Insertions         : "
        f"{insertions}"
    )

    print(
        f"Whisper segments   : "
        f"{segment_count}"
    )

    print(
        f"Detected language  : "
        f"{getattr(info, 'language', None)}"
    )

    print()

    print(
        "TRANSCRIPT"
    )

    print(
        "-" * 70
    )

    print(
        transcript
    )

    # --------------------------------------------------------
    # Save report.
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        REPORT_PATH,
        "w",
        encoding="utf-8",
    ) as report:

        report.write(
            "WHISPER SMALL VALIDATION\n"
        )

        report.write(
            "=" * 70
            + "\n\n"
        )

        report.write(
            f"Model: {MODEL_NAME}\n"
        )

        report.write(
            f"Device: {MODEL_DEVICE}\n"
        )

        report.write(
            f"Compute type: "
            f"{MODEL_COMPUTE_TYPE}\n"
        )

        report.write(
            f"Audio duration: "
            f"{duration:.3f}s\n"
        )

        report.write(
            f"Model load time: "
            f"{load_time:.3f}s\n"
        )

        report.write(
            f"Transcription time: "
            f"{transcription_time:.3f}s\n"
        )

        report.write(
            f"Real-time factor: "
            f"{real_time_factor:.4f}x\n"
        )

        report.write(
            f"Realtime speed: "
            f"{speed_multiplier:.2f}x\n"
        )

        report.write(
            f"WER: "
            f"{wer * 100:.2f}%\n"
        )

        report.write(
            f"Substitutions: "
            f"{substitutions}\n"
        )

        report.write(
            f"Deletions: "
            f"{deletions}\n"
        )

        report.write(
            f"Insertions: "
            f"{insertions}\n"
        )

        report.write(
            f"Whisper segments: "
            f"{segment_count}\n\n"
        )

        report.write(
            "REFERENCE SPEECH\n"
        )

        report.write(
            "-" * 70
            + "\n"
        )

        report.write(
            EXPECTED_SPEECH.strip()
            + "\n\n"
        )

        report.write(
            "TRANSCRIPT\n"
        )

        report.write(
            "-" * 70
            + "\n"
        )

        report.write(
            transcript
            + "\n"
        )

    print()
    print("=" * 70)

    print(
        "VALIDATION COMPLETE"
    )

    print("=" * 70)

    print()

    print(
        f"Report saved to:"
    )

    print(
        REPORT_PATH
    )

    print()


if __name__ == "__main__":
    main()