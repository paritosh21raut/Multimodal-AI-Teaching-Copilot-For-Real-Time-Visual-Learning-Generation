import os
import sys

sys.path.append(os.path.abspath("."))

from app.speech.whisper_worker import WhisperWorker


worker = WhisperWorker()

text = worker.transcribe("outputs/temp.wav")

print()
print("=" * 50)
print("TRANSCRIPT")
print("=" * 50)
print(text)