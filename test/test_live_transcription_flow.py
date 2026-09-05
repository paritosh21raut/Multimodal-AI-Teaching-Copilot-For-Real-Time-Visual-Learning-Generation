from __future__ import annotations

import sys
from pathlib import Path

# ------------------------------------------------------------
# Add project root to Python import path
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import time
import queue

import numpy as np
import sounddevice as sd

from app.speech.whisper_worker import WhisperWorker

# ============================================================
# CONFIGURATION
# ============================================================

SAMPLE_RATE = 16000
CHANNELS = 1

# ~20 ms audio frames
BLOCK_SIZE = 320

# VAD
ENERGY_THRESHOLD = 0.012
SILENCE_DURATION = 1.2

# Ignore extremely short sounds
MIN_SPEECH_DURATION = 0.30

# Safety limit for a single speech segment
MAX_SEGMENT_DURATION = 30.0

# Small pre-roll so the beginning of words is not lost
PRE_ROLL_DURATION = 0.25

# Keep a small overlap between hard-split segments
OVERLAP_DURATION = 1.0

OUTPUT_DIR = Path("outputs/audio_stt_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# AUDIO QUEUE
# ============================================================

audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=500)

stream_error = False


def audio_callback(indata, frames, time_info, status):
    """
    Real-time microphone callback.

    IMPORTANT:
    Do not perform Whisper, VAD, file I/O, or other expensive
    operations here.
    """

    global stream_error

    if status:
        print(f"\n[AUDIO WARNING] {status}", flush=True)

    try:
        chunk = indata.copy()

        try:
            audio_queue.put_nowait(chunk)
        except queue.Full:
            # Drop oldest queued chunk rather than blocking
            # the real-time audio callback.
            try:
                audio_queue.get_nowait()
            except queue.Empty:
                pass

            try:
                audio_queue.put_nowait(chunk)
            except queue.Full:
                stream_error = True

    except Exception as exc:
        stream_error = True
        print(f"\n[AUDIO CALLBACK ERROR] {exc}", flush=True)


# ============================================================
# AUDIO NORMALIZATION
# ============================================================

def normalize_audio(audio: np.ndarray) -> np.ndarray:

    audio = np.asarray(audio, dtype=np.float32)

    if audio.ndim == 2:

        if audio.shape[1] == 1:
            audio = audio[:, 0]

        else:
            audio = np.mean(audio, axis=1)

    elif audio.ndim != 1:
        audio = audio.reshape(-1)

    if audio.size == 0:
        return np.empty(0, dtype=np.float32)

    audio = np.nan_to_num(
        audio,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )

    audio = np.clip(audio, -1.0, 1.0)

    return audio.astype(np.float32, copy=False)


# ============================================================
# SIMPLE ROBUST ENERGY VAD
# ============================================================

class EnergyVAD:

    def __init__(self):

        self.noise_floor = 0.003

        self.start_threshold = ENERGY_THRESHOLD
        self.stop_threshold = ENERGY_THRESHOLD * 0.65

    def energy(self, audio):

        audio = normalize_audio(audio)

        if audio.size == 0:
            return 0.0

        return float(np.sqrt(np.mean(audio * audio)))

    def is_speech(self, audio):

        value = self.energy(audio)

        # Slowly learn background noise only when signal is quiet.
        if value < self.start_threshold:

            self.noise_floor = (
                0.995 * self.noise_floor
                + 0.005 * value
            )

        dynamic_threshold = max(
            self.start_threshold,
            self.noise_floor * 3.0,
        )

        return value >= dynamic_threshold

    def is_silence(self, audio):

        value = self.energy(audio)

        return value < self.stop_threshold


# ============================================================
# WHISPER
# ============================================================

def load_whisper():

    print("\n" + "=" * 60)
    print("LOADING FASTER-WHISPER")
    print("=" * 60)

    print("Model : base")
    print("Device: CPU")
    print("Compute: int8")
    print("Language: English")
    print()

    worker = WhisperWorker()

    print("Whisper loaded successfully.")

    return worker


# ============================================================
# TRANSCRIPTION
# ============================================================

def transcribe_segment(
    whisper_worker: WhisperWorker,
    audio: np.ndarray,
    segment_number: int,
):

    audio = normalize_audio(audio)

    duration = len(audio) / SAMPLE_RATE

    if duration < MIN_SPEECH_DURATION:

        print(
            f"\n[SEGMENT {segment_number}] "
            f"Too short ({duration:.2f}s) - ignored."
        )

        return ""

    print("\n" + "-" * 60)
    print(
        f"[WHISPER] Segment {segment_number} "
        f"({duration:.2f}s)"
    )
    print("-" * 60)

    started = time.perf_counter()

    try:

        text = whisper_worker.transcribe_audio(audio)

        elapsed = time.perf_counter() - started

        text = " ".join(text.split())

        print(f"[TIME] {elapsed:.2f}s")
        print(f"[TEXT] {text}")

        if not text:
            print("[RESULT] No speech recognized.")

        return text

    except Exception as exc:

        print(
            f"[WHISPER ERROR] "
            f"Segment {segment_number}: {exc}"
        )

        return ""


# ============================================================
# SAVE TRANSCRIPT
# ============================================================

def save_transcript(transcript_lines):

    output_file = OUTPUT_DIR / "transcript.txt"

    text = "\n".join(transcript_lines).strip()

    output_file.write_text(
        text + "\n",
        encoding="utf-8",
    )

    print(
        f"\nTranscript saved to:\n"
        f"{output_file}"
    )


# ============================================================
# MAIN AUDIO TEST
# ============================================================

def main():

    print("\n" + "=" * 70)
    print("AI TEACHING COPILOT - AUDIO / STT ISOLATION TEST")
    print("=" * 70)

    print("\nThis test DOES NOT start:")
    print("  - Gemini")
    print("  - Ollama")
    print("  - Lecture pipeline")
    print("  - Dashboard")
    print("  - Slide generation")
    print("  - PPT generation")

    print("\nIt tests ONLY:")
    print("  Microphone")
    print("  Audio streaming")
    print("  Energy VAD")
    print("  Speech segmentation")
    print("  Faster-Whisper")
    print("  Transcript generation")

    print("\n" + "=" * 70)

    # --------------------------------------------------------
    # Check microphone devices
    # --------------------------------------------------------

    print("\nAVAILABLE AUDIO DEVICES")
    print("-" * 70)

    try:

        devices = sd.query_devices()

        for index, device in enumerate(devices):

            if device["max_input_channels"] > 0:

                print(
                    f"[{index}] "
                    f"{device['name']}"
                )

    except Exception as exc:

        print(f"Could not query microphones: {exc}")
        return 1

    # --------------------------------------------------------
    # Load Whisper
    # --------------------------------------------------------

    whisper_worker = load_whisper()

    # --------------------------------------------------------
    # VAD
    # --------------------------------------------------------

    vad = EnergyVAD()

    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    pre_roll_chunks = []

    max_pre_roll_chunks = max(
        1,
        int(
            PRE_ROLL_DURATION
            * SAMPLE_RATE
            / BLOCK_SIZE
        ),
    )

    segment_chunks = []

    recording = False

    speech_samples = 0
    silence_samples = 0

    segment_number = 0

    transcript_lines = []

    total_audio_samples = 0
    total_speech_samples = 0

    start_time = time.perf_counter()

    print("\n" + "=" * 70)
    print("MICROPHONE TEST STARTING")
    print("=" * 70)

    print("\nSpeak normally into your microphone.")
    print("Pause naturally between sentences.")
    print("Press Ctrl+C to stop.")
    print()

    # --------------------------------------------------------
    # Open microphone
    # --------------------------------------------------------

    try:

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=CHANNELS,
            dtype="float32",
            callback=audio_callback,
            latency="low",
        ):

            print("[OK] Microphone stream running.")
            print("[OK] Waiting for speech...\n")

            while True:

                try:

                    chunk = audio_queue.get(
                        timeout=0.5
                    )

                except queue.Empty:

                    continue

                chunk = normalize_audio(chunk)

                if chunk.size == 0:
                    continue

                total_audio_samples += len(chunk)

                speech = vad.is_speech(chunk)

                # ------------------------------------------------
                # Maintain pre-roll
                # ------------------------------------------------

                if not recording:

                    pre_roll_chunks.append(chunk)

                    if len(pre_roll_chunks) > max_pre_roll_chunks:

                        pre_roll_chunks.pop(0)

                # ------------------------------------------------
                # SPEECH START
                # ------------------------------------------------

                if speech and not recording:

                    recording = True

                    segment_chunks = list(
                        pre_roll_chunks
                    )

                    pre_roll_chunks.clear()

                    speech_samples = sum(
                        len(x)
                        for x in segment_chunks
                    )

                    silence_samples = 0

                    print(
                        "\n[SPEECH START]"
                    )

                # ------------------------------------------------
                # RECORDING
                # ------------------------------------------------

                if recording:

                    segment_chunks.append(chunk)

                    if speech:

                        speech_samples += len(chunk)

                        total_speech_samples += len(chunk)

                        silence_samples = 0

                    else:

                        silence_samples += len(chunk)

                # ------------------------------------------------
                # Current segment duration
                # ------------------------------------------------

                if recording:

                    segment_samples = sum(
                        len(x)
                        for x in segment_chunks
                    )

                    segment_duration = (
                        segment_samples
                        / SAMPLE_RATE
                    )

                    silence_duration = (
                        silence_samples
                        / SAMPLE_RATE
                    )

                    # ------------------------------------------------
                    # NATURAL ENDPOINT
                    # ------------------------------------------------

                    should_finalize = (
                        silence_duration
                        >= SILENCE_DURATION
                        and
                        speech_samples
                        >= MIN_SPEECH_DURATION
                        * SAMPLE_RATE
                    )

                    # ------------------------------------------------
                    # HARD MAXIMUM
                    # ------------------------------------------------

                    hard_split = (
                        segment_duration
                        >= MAX_SEGMENT_DURATION
                    )

                    if should_finalize or hard_split:

                        segment_number += 1

                        audio = np.concatenate(
                            segment_chunks
                        ).astype(
                            np.float32,
                            copy=False
                        )

                        reason = (
                            "natural silence"
                            if should_finalize
                            else "30s hard limit"
                        )

                        print(
                            "\n[SEGMENT END] "
                            f"Reason: {reason}"
                        )

                        text = transcribe_segment(
                            whisper_worker,
                            audio,
                            segment_number,
                        )

                        if text:

                            transcript_lines.append(
                                text
                            )

                        # ------------------------------------------------
                        # Reset
                        # ------------------------------------------------

                        recording = False

                        segment_chunks = []

                        speech_samples = 0
                        silence_samples = 0

                        pre_roll_chunks.clear()

                        print(
                            "\n[LISTENING] "
                            "Waiting for next speech..."
                        )

    except KeyboardInterrupt:

        print("\n\nStopping microphone test...")

    except Exception as exc:

        print(
            f"\n[FATAL AUDIO ERROR] {exc}"
        )

        return 1

    finally:

        # ------------------------------------------------------------
        # Flush active speech when stopping
        # ------------------------------------------------------------

        if recording and segment_chunks:

            audio = np.concatenate(
                segment_chunks
            ).astype(
                np.float32,
                copy=False
            )

            duration = len(audio) / SAMPLE_RATE

            if duration >= MIN_SPEECH_DURATION:

                segment_number += 1

                print(
                    "\n[FINAL FLUSH] "
                    f"{duration:.2f}s"
                )

                text = transcribe_segment(
                    whisper_worker,
                    audio,
                    segment_number,
                )

                if text:
                    transcript_lines.append(text)

    # ============================================================
    # RESULTS
    # ============================================================

    elapsed = time.perf_counter() - start_time

    total_audio_duration = (
        total_audio_samples
        / SAMPLE_RATE
    )

    speech_duration = (
        total_speech_samples
        / SAMPLE_RATE
    )

    print("\n" + "=" * 70)
    print("AUDIO / STT TEST COMPLETE")
    print("=" * 70)

    print(
        f"\nTotal microphone audio : "
        f"{total_audio_duration:.2f}s"
    )

    print(
        f"Detected speech        : "
        f"{speech_duration:.2f}s"
    )

    print(
        f"Segments transcribed   : "
        f"{segment_number}"
    )

    print(
        f"Test runtime           : "
        f"{elapsed:.2f}s"
    )

    print("\nFINAL TRANSCRIPT")
    print("-" * 70)

    if transcript_lines:

        for index, text in enumerate(
            transcript_lines,
            start=1,
        ):

            print(
                f"{index}. {text}"
            )

    else:

        print("No transcript generated.")

    save_transcript(
        transcript_lines
    )

    print("\n" + "=" * 70)
    print("TEST FINISHED")
    print("=" * 70)

    return 0


if __name__ == "__main__":

    sys.exit(main())