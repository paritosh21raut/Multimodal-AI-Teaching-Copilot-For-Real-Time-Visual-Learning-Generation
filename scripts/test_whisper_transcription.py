import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.speech.whisper_model import WhisperModelManager

model = WhisperModelManager()

text = model.transcribe("outputs/temp.wav")

print("\n====================")
print("TRANSCRIPT")
print("====================")
print(text)