"""
Quick VAD Test - Check if Silero VAD detects speech from microphone
"""

import sys
import os
import numpy as np
import time
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.audio.audio_stream import AudioStream
from app.audio.voice_detector import VoiceDetector


def test_vad():
    """Test VAD with real microphone"""
    
    print("="*50)
    print("QUICK VAD TEST")
    print("="*50)
    
    detector = VoiceDetector()
    print(f"Using: {detector.get_state()['model']}")
    
    stream = AudioStream()
    queue = stream.get_queue()
    
    # Start stream
    stream_thread = threading.Thread(target=stream.start, daemon=True)
    stream_thread.start()
    
    time.sleep(2)
    
    print("\n🎤 SPEAK NOW! (5 seconds)")
    print("="*50)
    
    speech_detected = False
    silence_detected = False
    start_time = time.time()
    chunk_count = 0
    speech_chunks = 0
    
    try:
        while time.time() - start_time < 10:
            try:
                chunk = queue.get(timeout=0.1)
                chunk_count += 1
                
                # Get raw audio
                if hasattr(chunk, 'shape'):
                    audio = chunk.flatten()
                else:
                    audio = np.asarray(chunk).flatten()
                
                # Check energy directly
                energy = np.mean(np.abs(audio))
                
                # Check VAD
                is_speech = detector.is_speech(audio)
                
                if is_speech:
                    speech_chunks += 1
                    if not speech_detected:
                        print(f"✅ SPEECH DETECTED! Energy: {energy:.4f}")
                        speech_detected = True
                
            except Exception:
                continue
        
    except KeyboardInterrupt:
        pass
    
    finally:
        stream.stop()
        time.sleep(1)
    
    print(f"\nResults:")
    print(f"  Chunks: {chunk_count}")
    print(f"  Speech chunks: {speech_chunks}")
    print(f"  Speech detected: {speech_detected}")
    print(f"  Detector state: {detector.get_state()}")


if __name__ == "__main__":
    test_vad()