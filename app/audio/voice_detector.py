import numpy as np


class VoiceDetector:

    def __init__(self):
        # Adjust this threshold if needed
        self.threshold = 0.01

    def is_speech(self, audio):
        """
        Detect speech using audio energy.
        """
        energy = np.mean(np.abs(audio))
        return energy > self.threshold