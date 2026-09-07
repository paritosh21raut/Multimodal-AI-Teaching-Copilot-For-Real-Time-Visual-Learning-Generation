from __future__ import annotations

import time

import numpy as np

from app.audio.audio_worker import AudioWorker


class FakeQueue:

    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)

    def empty(self):
        return len(self.items) == 0

    def get(self):
        return self.items.pop(0)


def main():

    print("=" * 70)
    print("AUDIO QUEUE / LIVE STT SCHEDULING TEST")
    print("=" * 70)

    queue = FakeQueue()

    worker = AudioWorker(queue)

    # Replace real Whisper before submitting jobs.
    class FakeWhisper:

        def transcribe_audio(self, audio):

            print(
                f"[TEST] Whisper received "
                f"{len(audio)} samples"
            )

            time.sleep(0.5)

            return (
                "test speech segment"
            )

    worker.whisper = FakeWhisper()

    # Submit several independent audio windows
    # while Whisper is still processing.
    for index in range(5):

        audio = np.zeros(
            32000,
            dtype=np.float32,
        )

        worker._submit_live_transcription(
            audio
        )

        print(
            f"[TEST] Submitted window {index + 1}"
        )

    # Wait for queued jobs.
    worker.live_executor.shutdown(
        wait=True
    )

    print("=" * 70)
    print("ALL AUDIO WINDOWS PROCESSED")
    print("=" * 70)


if __name__ == "__main__":
    main()