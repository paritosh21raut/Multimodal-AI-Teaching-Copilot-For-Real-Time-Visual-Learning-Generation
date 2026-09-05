from __future__ import annotations

import sys
import time
import threading
from pathlib import Path


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORTS
# ============================================================

import numpy as np
import sounddevice as sd

from app.audio.audio_queue import AudioQueue
from app.audio.audio_worker import AudioWorker


# ============================================================
# CONFIGURATION
# ============================================================

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 320

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "audio_worker_test"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

TRANSCRIPT_FILE = (
    OUTPUT_DIR
    / "production_transcript.txt"
)


# ============================================================
# TEST STATE
# ============================================================

audio_queue = None

preview_transcripts = []
final_transcripts = []

preview_lock = threading.Lock()
final_lock = threading.Lock()

callback_count = 0
callback_error_count = 0


# ============================================================
# CALLBACKS
# ============================================================

def on_preview(
    text: str,
    authoritative_transcript: str = "",
):

    text = " ".join(
        str(text).split()
    ).strip()

    if not text:
        return

    with preview_lock:

        preview_transcripts.append(
            text
        )

        number = len(
            preview_transcripts
        )

    print(
        "\n"
        + "-" * 70
    )

    print(
        f"[LIVE PREVIEW #{number}]"
    )

    print(text)

    print(
        "-" * 70
    )


def on_final(
    text: str,
    authoritative_transcript: str = "",
    segment_id=None,
):

    text = " ".join(
        str(text).split()
    ).strip()

    if not text:
        return

    with final_lock:

        final_transcripts.append(
            {
                "segment_id": segment_id,
                "text": text,
                "authoritative": authoritative_transcript,
            }
        )

        number = len(
            final_transcripts
        )

    print(
        "\n"
        + "=" * 70
    )

    print(
        f"[FINAL TRANSCRIPT #{number}]"
    )

    print(
        f"Segment ID: {segment_id}"
    )

    print(
        f"Text: {text}"
    )

    print(
        "=" * 70
    )


# ============================================================
# MICROPHONE CALLBACK
# ============================================================

def microphone_callback(
    indata,
    frames,
    time_info,
    status,
):

    global callback_count
    global callback_error_count

    callback_count += 1

    if status:

        print(
            f"\n[AUDIO STATUS] {status}",
            flush=True,
        )

    try:

        chunk = indata.copy()

        audio_queue.put(
            chunk
        )

    except Exception as exc:

        callback_error_count += 1

        print(
            "\n[AUDIO CALLBACK ERROR]"
        )

        print(
            exc
        )


# ============================================================
# METRICS
# ============================================================

def print_metrics(worker):

    print(
        "\n"
        + "=" * 70
    )

    print(
        "AUDIO WORKER METRICS"
    )

    print(
        "=" * 70
    )

    try:

        metrics = worker.get_metrics()

        if isinstance(metrics, dict):

            for key, value in metrics.items():

                print(
                    f"{key}: {value}"
                )

        else:

            print(metrics)

    except Exception as exc:

        print(
            f"Could not retrieve metrics: {exc}"
        )


# ============================================================
# SAVE TRANSCRIPT
# ============================================================

def save_result():

    with final_lock:

        final_items = list(
            final_transcripts
        )

    lines = []

    for item in final_items:

        text = item["text"]

        if text:
            lines.append(text)

    transcript = "\n".join(
        lines
    ).strip()

    TRANSCRIPT_FILE.write_text(
        transcript + "\n",
        encoding="utf-8",
    )

    print(
        "\nFinal transcript saved to:"
    )

    print(
        TRANSCRIPT_FILE
    )


# ============================================================
# MAIN
# ============================================================

def main():

    global audio_queue

    print(
        "\n"
        + "=" * 70
    )

    print(
        "AI TEACHING COPILOT"
    )

    print(
        "PRODUCTION AUDIO WORKER TEST"
    )

    print(
        "=" * 70
    )

    print(
        "\nTesting the actual production:"
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

    print(
        "  production segmentation"
    )

    print(
        "  preview scheduling"
    )

    print(
        "  final scheduling"
    )

    print(
        "\nThis test does NOT start:"
    )

    print(
        "  Gemini"
    )

    print(
        "  Ollama"
    )

    print(
        "  Lecture Pipeline"
    )

    print(
        "  Dashboard"
    )

    print(
        "  Slides"
    )

    print(
        "  PPT"
    )

    print(
        "\n"
        + "=" * 70
    )

    # ========================================================
    # AUDIO QUEUE
    # ========================================================

    print(
        "\nCreating AudioQueue..."
    )

    audio_queue = AudioQueue(
        max_chunks=500
    )

    print(
        "[OK] AudioQueue created."
    )

    # ========================================================
    # AUDIO WORKER
    # ========================================================

    print(
        "\nCreating AudioWorker..."
    )

    worker = AudioWorker(
        audio_queue,
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
        transcript_path=str(
            TRANSCRIPT_FILE
        ),
    )

    print(
        "[OK] AudioWorker created."
    )

    # ========================================================
    # START WORKER
    # ========================================================

    print(
        "\nStarting AudioWorker..."
    )

    worker.start()

    print(
        "[OK] AudioWorker started."
    )

    # ========================================================
    # AUDIO DEVICES
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "AVAILABLE INPUT DEVICES"
    )

    print(
        "=" * 70
    )

    try:

        devices = sd.query_devices()

        for index, device in enumerate(
            devices
        ):

            if (
                device[
                    "max_input_channels"
                ]
                > 0
            ):

                print(
                    f"[{index}] "
                    f"{device['name']}"
                )

    except Exception as exc:

        print(
            f"Could not list devices: {exc}"
        )

    # ========================================================
    # MICROPHONE
    # ========================================================

    stream = None

    try:

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=CHANNELS,
            dtype="float32",
            callback=microphone_callback,
            latency="low",
        )

        stream.start()

        print(
            "\n"
            + "=" * 70
        )

        print(
            "PRODUCTION AUDIO PIPELINE RUNNING"
        )

        print(
            "=" * 70
        )

        print(
            "\n"
            "TEST 1 — NORMAL LECTURE SPEECH"
        )

        print(
            "Speak naturally for about 15 seconds."
        )

        print(
            "\n"
            "TEST 2 — PAUSE HANDLING"
        )

        print(
            "Say one sentence."
        )

        print(
            "Pause 2–3 seconds."
        )

        print(
            "Say another sentence."
        )

        print(
            "\n"
            "TEST 3 — HARD SPLIT"
        )

        print(
            "Speak continuously for 40–60 seconds."
        )

        print(
            "Do not intentionally pause."
        )

        print(
            "This tests the 30-second boundary."
        )

        print(
            "\n"
            "TEST 4 — TECHNICAL TERMS"
        )

        print(
            "Whisper, SpecAugment, neural network,"
        )

        print(
            "frequency masking, time masking,"
        )

        print(
            "automatic speech recognition,"
        )

        print(
            "transformer, beam search,"
        )

        print(
            "word error rate."
        )

        print(
            "\n"
            "TEST 5 — SHORT PHRASES"
        )

        print(
            "Hello."
        )

        print(
            "This is a test."
        )

        print(
            "Speech recognition."
        )

        print(
            "Artificial intelligence."
        )

        print(
            "\n"
            + "=" * 70
        )

        print(
            "PRESS CTRL+C AFTER COMPLETING ALL TESTS"
        )

        print(
            "=" * 70
        )

        print()

        while True:

            time.sleep(
                0.5
            )

    except KeyboardInterrupt:

        print(
            "\n\n"
            + "=" * 70
        )

        print(
            "STOPPING MICROPHONE"
        )

        print(
            "=" * 70
        )

    except Exception as exc:

        print(
            "\n"
            + "=" * 70
        )

        print(
            "MICROPHONE ERROR"
        )

        print(
            "=" * 70
        )

        print(
            exc
        )

        return 1

    finally:

        # ====================================================
        # STOP MICROPHONE
        # ====================================================

        if stream is not None:

            try:
                stream.stop()
            except Exception:
                pass

            try:
                stream.close()
            except Exception:
                pass

        print(
            "\n[OK] Microphone stopped."
        )

        # ====================================================
        # STOP WORKER
        # ====================================================

        print(
            "\nStopping AudioWorker..."
        )

        try:

            worker.stop()

        except Exception as exc:

            print(
                f"Worker stop error: {exc}"
            )

        # ====================================================
        # WAIT
        # ====================================================

        print(
            "Waiting for AudioWorker..."
        )

        try:

            worker.join(
                timeout=25
            )

        except Exception as exc:

            print(
                f"Worker join error: {exc}"
            )

        if worker.is_alive():

            print(
                "\n"
                "[WARNING] AudioWorker is "
                "still alive after 25 seconds."
            )

        else:

            print(
                "[OK] AudioWorker stopped."
            )

    # ========================================================
    # RESULTS
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "PRODUCTION AUDIO TEST RESULTS"
    )

    print(
        "=" * 70
    )

    with preview_lock:

        previews = list(
            preview_transcripts
        )

    with final_lock:

        finals = list(
            final_transcripts
        )

    print(
        f"\nMicrophone callback calls : "
        f"{callback_count}"
    )

    print(
        f"Callback errors           : "
        f"{callback_error_count}"
    )

    print(
        f"Live previews             : "
        f"{len(previews)}"
    )

    print(
        f"Final transcripts         : "
        f"{len(finals)}"
    )

    # ========================================================
    # QUEUE
    # ========================================================

    print(
        "\nAUDIO QUEUE"
    )

    print(
        "-" * 70
    )

    try:

        print(
            f"Current queue size: "
            f"{audio_queue.size()}"
        )

        print(
            f"Queue statistics: "
            f"{audio_queue.stats()}"
        )

    except Exception as exc:

        print(
            f"Could not read queue statistics: {exc}"
        )

    # ========================================================
    # WORKER METRICS
    # ========================================================

    print_metrics(
        worker
    )

    # ========================================================
    # FINAL TRANSCRIPT
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "FINAL AUTHORITATIVE TRANSCRIPT"
    )

    print(
        "=" * 70
    )

    if finals:

        for index, item in enumerate(
            finals,
            start=1,
        ):

            print(
                f"\n{index}. "
                f"[Segment {item['segment_id']}]"
            )

            print(
                item["text"]
            )

    else:

        print(
            "\nNo final transcripts received."
        )

    # ========================================================
    # PREVIEWS
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "LIVE PREVIEW RESULTS"
    )

    print(
        "=" * 70
    )

    if previews:

        for index, text in enumerate(
            previews,
            start=1,
        ):

            print(
                f"\n{index}. {text}"
            )

    else:

        print(
            "\nNo preview transcripts received."
        )

    # ========================================================
    # SAVE
    # ========================================================

    try:

        save_result()

    except Exception as exc:

        print(
            f"\nCould not save transcript: {exc}"
        )

    # ========================================================
    # BASIC VERDICT
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "BASIC TEST VERDICT"
    )

    print(
        "=" * 70
    )

    if callback_error_count == 0:

        print(
            "[PASS] No microphone callback errors."
        )

    else:

        print(
            "[FAIL] Microphone callback errors occurred."
        )

    if finals:

        print(
            "[PASS] Final transcription produced."
        )

    else:

        print(
            "[FAIL] No final transcription produced."
        )

    if not worker.is_alive():

        print(
            "[PASS] AudioWorker shut down."
        )

    else:

        print(
            "[FAIL] AudioWorker did not shut down."
        )

    print(
        "\n"
        + "=" * 70
    )

    return 0


if __name__ == "__main__":

    sys.exit(
        main()
    )