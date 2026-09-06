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

BEAM_SIZE = 5

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
    / "vad_comparison_report.txt"
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

    return np.ascontiguousarray(
        audio,
        dtype=np.float32,
    )


# ============================================================
# TRANSCRIBE
# ============================================================

def transcribe(
    model: WhisperModel,
    audio: np.ndarray,
    vad_filter: bool,
) -> dict:

    start = time.perf_counter()

    segments, info = model.transcribe(
        audio,
        language="en",
        beam_size=BEAM_SIZE,
        vad_filter=vad_filter,
        condition_on_previous_text=False,
        temperature=0.0,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        repetition_penalty=1.05,
    )

    text_parts: list[str] = []

    segment_details: list[dict] = []

    for segment in segments:

        text = segment.text.strip()

        if not text:
            continue

        text_parts.append(
            text
        )

        segment_details.append(
            {
                "start": float(
                    segment.start
                ),
                "end": float(
                    segment.end
                ),
                "text": text,
            }
        )

    elapsed = (
        time.perf_counter()
        - start
    )

    transcript = " ".join(
        text_parts
    ).strip()

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

    return {
        "vad_filter": vad_filter,
        "transcript": transcript,
        "transcription_time": elapsed,
        "real_time_factor": elapsed,
        "wer": wer,
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "reference_words": reference_words,
        "segment_count": len(
            segment_details
        ),
        "segments": segment_details,
        "language": getattr(
            info,
            "language",
            None,
        ),
        "language_probability": getattr(
            info,
            "language_probability",
            None,
        ),
    }


# ============================================================
# PRINT RESULT
# ============================================================

def print_result(
    name: str,
    result: dict,
    duration: float,
):

    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    transcription_time = result[
        "transcription_time"
    ]

    realtime_speed = (
        duration
        / transcription_time
        if transcription_time > 0
        else 0.0
    )

    result[
        "real_time_factor"
    ] = (
        transcription_time
        / duration
        if duration > 0
        else 0.0
    )

    print()

    print(
        f"VAD filter         : "
        f"{result['vad_filter']}"
    )

    print(
        f"Audio duration     : "
        f"{duration:.3f}s"
    )

    print(
        f"Transcription time : "
        f"{transcription_time:.3f}s"
    )

    print(
        f"Real-time factor   : "
        f"{result['real_time_factor']:.4f}x"
    )

    print(
        f"Realtime speed     : "
        f"{realtime_speed:.2f}x"
    )

    print(
        f"WER                : "
        f"{result['wer'] * 100:.2f}%"
    )

    print(
        f"Substitutions      : "
        f"{result['substitutions']}"
    )

    print(
        f"Deletions          : "
        f"{result['deletions']}"
    )

    print(
        f"Insertions         : "
        f"{result['insertions']}"
    )

    print(
        f"Whisper segments   : "
        f"{result['segment_count']}"
    )

    print(
        f"Language           : "
        f"{result['language']}"
    )

    probability = result[
        "language_probability"
    ]

    if probability is not None:

        print(
            f"Language probability: "
            f"{probability:.2f}"
        )

    print()

    print("TRANSCRIPT")

    print("-" * 70)

    print(
        result["transcript"]
    )

    print()

    print("LAST 30 WORDS")

    print("-" * 70)

    words = result[
        "transcript"
    ].split()

    print(
        " ".join(
            words[-30:]
        )
    )


# ============================================================
# PRINT COMPARISON
# ============================================================

def print_comparison(
    vad_on: dict,
    vad_off: dict,
):

    print()
    print("=" * 70)
    print("VAD COMPARISON")
    print("=" * 70)

    print()

    print(
        f"{'Metric':<25}"
        f"{'VAD ON':>15}"
        f"{'VAD OFF':>15}"
        f"{'Difference':>15}"
    )

    print("-" * 70)

    metrics = [
        (
            "WER %",
            vad_on["wer"] * 100,
            vad_off["wer"] * 100,
        ),
        (
            "Substitutions",
            vad_on["substitutions"],
            vad_off["substitutions"],
        ),
        (
            "Deletions",
            vad_on["deletions"],
            vad_off["deletions"],
        ),
        (
            "Insertions",
            vad_on["insertions"],
            vad_off["insertions"],
        ),
        (
            "Segments",
            vad_on["segment_count"],
            vad_off["segment_count"],
        ),
        (
            "Time (seconds)",
            vad_on["transcription_time"],
            vad_off["transcription_time"],
        ),
    ]

    for name, on_value, off_value in metrics:

        difference = (
            off_value
            - on_value
        )

        print(
            f"{name:<25}"
            f"{on_value:>15.3f}"
            f"{off_value:>15.3f}"
            f"{difference:>15.3f}"
        )

    print()


# ============================================================
# SAVE REPORT
# ============================================================

def save_report(
    duration: float,
    load_time: float,
    vad_on: dict,
    vad_off: dict,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with REPORT_PATH.open(
        "w",
        encoding="utf-8",
    ) as report:

        report.write(
            "WHISPER SMALL VAD COMPARISON\n"
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
            f"Beam size: "
            f"{BEAM_SIZE}\n"
        )

        report.write(
            f"Audio duration: "
            f"{duration:.3f}s\n"
        )

        report.write(
            f"Model load time: "
            f"{load_time:.3f}s\n\n"
        )

        for name, result in (
            ("VAD ON", vad_on),
            ("VAD OFF", vad_off),
        ):

            report.write(
                "=" * 70
                + "\n"
            )

            report.write(
                f"{name}\n"
            )

            report.write(
                "=" * 70
                + "\n\n"
            )

            report.write(
                f"Transcription time: "
                f"{result['transcription_time']:.3f}s\n"
            )

            report.write(
                f"Real-time factor: "
                f"{result['real_time_factor']:.4f}x\n"
            )

            report.write(
                f"WER: "
                f"{result['wer'] * 100:.2f}%\n"
            )

            report.write(
                f"Substitutions: "
                f"{result['substitutions']}\n"
            )

            report.write(
                f"Deletions: "
                f"{result['deletions']}\n"
            )

            report.write(
                f"Insertions: "
                f"{result['insertions']}\n"
            )

            report.write(
                f"Whisper segments: "
                f"{result['segment_count']}\n"
            )

            report.write(
                f"Language: "
                f"{result['language']}\n"
            )

            report.write(
                f"Language probability: "
                f"{result['language_probability']}\n\n"
            )

            report.write(
                "TRANSCRIPT\n"
            )

            report.write(
                "-" * 70
                + "\n"
            )

            report.write(
                result["transcript"]
                + "\n\n"
            )

            report.write(
                "SEGMENTS\n"
            )

            report.write(
                "-" * 70
                + "\n"
            )

            for index, segment in enumerate(
                result["segments"],
                start=1,
            ):

                report.write(
                    f"[{index}] "
                    f"{segment['start']:.3f}s -> "
                    f"{segment['end']:.3f}s\n"
                )

                report.write(
                    f"{segment['text']}\n\n"
                )

        report.write(
            "=" * 70
            + "\n"
        )

        report.write(
            "REFERENCE SPEECH\n"
        )

        report.write(
            "=" * 70
            + "\n\n"
        )

        report.write(
            EXPECTED_SPEECH.strip()
            + "\n"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("AI TEACHING COPILOT")
    print("WHISPER SMALL - VAD A/B VALIDATION")
    print("=" * 70)
    print()

    print(
        f"Model        : {MODEL_NAME}"
    )

    print(
        f"Device       : {MODEL_DEVICE}"
    )

    print(
        f"Compute type : {MODEL_COMPUTE_TYPE}"
    )

    print(
        f"Beam size    : {BEAM_SIZE}"
    )

    print(
        f"Audio        : {AUDIO_PATH}"
    )

    print()

    # --------------------------------------------------------
    # Load audio.
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
        f"Samples  : {len(audio):,}"
    )

    print(
        f"Duration : {duration:.3f}s"
    )

    # --------------------------------------------------------
    # Load model once.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("LOADING WHISPER SMALL")
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
    # VAD ON.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TEST A - VAD ENABLED")
    print("=" * 70)

    print()
    print(
        "Transcribing with "
        "vad_filter=True..."
    )

    vad_on = transcribe(
        model,
        audio,
        vad_filter=True,
    )

    print_result(
        "VAD ENABLED RESULT",
        vad_on,
        duration,
    )

    # --------------------------------------------------------
    # VAD OFF.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TEST B - VAD DISABLED")
    print("=" * 70)

    print()
    print(
        "Transcribing with "
        "vad_filter=False..."
    )

    vad_off = transcribe(
        model,
        audio,
        vad_filter=False,
    )

    print_result(
        "VAD DISABLED RESULT",
        vad_off,
        duration,
    )

    # --------------------------------------------------------
    # Comparison.
    # --------------------------------------------------------

    print_comparison(
        vad_on,
        vad_off,
    )

    # --------------------------------------------------------
    # Save report.
    # --------------------------------------------------------

    save_report(
        duration,
        load_time,
        vad_on,
        vad_off,
    )

    print()
    print("=" * 70)
    print("VALIDATION COMPLETE")
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