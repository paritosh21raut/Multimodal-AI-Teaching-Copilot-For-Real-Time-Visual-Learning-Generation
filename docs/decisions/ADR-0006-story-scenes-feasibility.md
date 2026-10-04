# ADR-0006: Story Scenes — storyboard, not generative video
Status: accepted (2026-10-05), revisit at V4

**Findings (local laptop, 4 GB VRAM, 16 GB RAM).**
- Open text-to-video models (SVD, AnimateDiff, CogVideoX, LTX-Video, Wan): need 8–24 GB VRAM for usable quality;
  with offloading on 4 GB they take minutes per few seconds of clip → not real time. Coherence and factual accuracy
  for history/science are unreliable.
- Local image generation (SD-Turbo / SDXL-Turbo, 512 px): ~1–3 s per image on 4 GB is borderline feasible, but it competes
  with Whisper for VRAM and has accuracy risk for educational content.
- Paid video APIs are excluded and still take 30 s – minutes.
- Procedural animation (SVG/CSS/Canvas/WebGL) + retrieved images: real time, deterministic, cheap.

**Decision.** V4 first version = **storyboard**: 3–6 scenes made of retrieved or teacher images (optionally
locally generated stills as an experiment) with procedural motion (Ken Burns, parallax, highlight
overlays, map/timeline animations), captions synced to the narration, and scene transitions. Latency target: first scene
≤ 10 s, scenes added progressively.

**Future.** Generative video as an optional paid or high-GPU upgrade behind the same `StoryboardSpec` (pre-rendered between lectures).
