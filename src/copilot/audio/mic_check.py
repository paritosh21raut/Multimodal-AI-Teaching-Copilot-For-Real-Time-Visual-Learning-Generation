"""Microphone check: python -m copilot.audio.mic_check [--device N] [--seconds 8]

Lists input devices, records while you speak, prints levels/VAD and a transcript.
Use it to pick `audio.device` in config/local.toml before a lecture.
"""
from __future__ import annotations

import argparse

import numpy as np


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--device", default=None, help="input device index (default: system default)")
    p.add_argument("--seconds", type=float, default=8.0)
    p.add_argument("--no-stt", action="store_true")
    args = p.parse_args()

    import sounddevice as sd

    from copilot.audio.vad import FRAME, SileroVad

    print("Input devices:")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            api = sd.query_hostapis(d["hostapi"])["name"]
            print(f"  {i:3d}  {d['name'][:60]}  [{api}]")
    device = int(args.device) if args.device is not None else None
    print(f"\nRecording {args.seconds:.0f} s from device {device if device is not None else 'default'} - speak now ...")
    audio = sd.rec(int(args.seconds * 16_000), samplerate=16_000, channels=1, dtype="float32", device=device)
    sd.wait()
    audio = audio[:, 0]
    usable = len(audio) // FRAME * FRAME
    vad = SileroVad()
    probs = [vad(audio[i:i + FRAME]) for i in range(0, usable, FRAME)]
    speech = sum(1 for pr in probs if pr >= 0.5) * FRAME / 16_000
    rms_db = 20 * np.log10(max(1e-9, float(np.sqrt(np.mean(audio ** 2)))))
    peak_db = 20 * np.log10(max(1e-9, float(np.abs(audio).max())))
    print(f"level: rms {rms_db:.1f} dBFS, peak {peak_db:.1f} dBFS; speech detected: {speech:.1f} s")
    if peak_db < -50:
        print("WARNING: almost no signal. Check the mic is unmuted, the input volume, and the selected device.")
    if args.no_stt or speech < 0.3:
        return
    from copilot.core.config import load_config
    from copilot.stt.factory import make_engine

    engine = make_engine(load_config())
    engine.load()
    res = engine.transcribe(audio)
    print(f"transcript ({res.infer_ms:.0f} ms, conf {res.confidence:.2f}): {res.text!r}"
          + (f"  [rejected: {res.rejected}]" if res.rejected else ""))


if __name__ == "__main__":
    main()
