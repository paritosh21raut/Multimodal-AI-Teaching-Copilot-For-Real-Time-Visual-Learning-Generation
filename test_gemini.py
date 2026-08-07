from app.ai.gemini_client import GeminiClient
from app.config import GEMINI_API_KEY

client = GeminiClient(GEMINI_API_KEY)

result = client.generate_slide(
    topic="Fourier Transform",
    context="""
Fourier Transform converts a signal from time domain to frequency domain.
It is used in DSP, Robotics, AI and Image Processing.
"""
)

print(result)