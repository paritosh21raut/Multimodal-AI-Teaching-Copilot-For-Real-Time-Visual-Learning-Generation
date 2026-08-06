import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from app.audio.audio_recorder import AudioRecorder

print("Creating Dummy Audio...")

audio = np.zeros((16000 * 5, 1), dtype=np.float32)

recorder = AudioRecorder()

filename = recorder.save(audio)

print("Saved :", filename)