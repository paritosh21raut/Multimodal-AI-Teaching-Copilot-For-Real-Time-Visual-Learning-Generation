"""
VAD Debug Test - Check actual audio data
"""

import sys
import os
import numpy as np
import time
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.audio.audio_stream import AudioStream


def debug_audio():
    """Debug what audio data looks like"""
    
    print("="*60)
    print("AUDIO DEBUG TEST")
    print("="*60)
    
    stream = AudioStream()
    queue = stream.get_queue()
    
    stream_thread = threading.Thread(target=stream.start, daemon=True)
    stream_thread.start()
    
    time.sleep(2)
    
    print("\n🎤 SPEAK NOW! (5 seconds)")
    print("="*60)
    
    start_time = time.time()
    chunk_count = 0
    max_energy = 0.0
    min_energy = 999.0
    
    try:
        while time.time() - start_time < 5:
            try:
                chunk = queue.get(timeout=0.1)
                chunk_count += 1
                
                # Check shape
                if chunk_count <= 3:
                    print(f"\nChunk #{chunk_count}:")
                    print(f"  Shape: {chunk.shape}")
                    print(f"  Dtype: {chunk.dtype}")
                    print(f"  Min: {np.min(chunk):.4f}")
                    print(f"  Max: {np.max(chunk):.4f}")
                    print(f"  Mean: {np.mean(chunk):.6f}")
                    print(f"  Abs Mean: {np.mean(np.abs(chunk)):.6f}")
                
                # Calculate energy
                flat = chunk.flatten()
                energy = float(np.mean(np.abs(flat)))
                max_energy = max(max_energy, energy)
                min_energy = min(min_energy, energy)
                
            except Exception:
                continue
    
    except KeyboardInterrupt:
        pass
    
    finally:
        stream.stop()
        time.sleep(1)
    
    print(f"\nResults:")
    print(f"  Chunks received: {chunk_count}")
    print(f"  Min energy: {min_energy:.6f}")
    print(f"  Max energy: {max_energy:.6f}")
    
    if max_energy < 0.005:
        print("\n⚠️ AUDIO TOO QUIET!")
        print("  The microphone may be muted or too quiet.")
        print("  Try: Increase microphone volume in Windows settings")
    elif max_energy < 0.01:
        print("\n⚠️ AUDIO MARGINAL!")
        print("  Speech detected but energy is low.")
    else:
        print("\n✅ AUDIO ENERGY OK!")
        print(f"  Energy range: {min_energy:.6f} to {max_energy:.6f}")


if __name__ == "__main__":
    debug_audio()