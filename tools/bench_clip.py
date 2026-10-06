"""CLIP latency + sanity benchmark (F-007b step 1). CPU only.

    .venv/Scripts/python tools/bench_clip.py

Downloads 8 Commons thumbnails for a few queries once (artifacts/bench_clip/), then measures model load, text
embedding, preprocessing and the vision encoder for 8 candidates (int8 vs fp32, 2 vs 4 threads), and prints the
score matrix (each query vs every image) so relevance separation can be checked by eye.
"""
from __future__ import annotations

import io
import statistics
import sys
import time
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from copilot.visuals.clip import ClipScorer, preprocess  # noqa: E402

OUT = ROOT / "artifacts" / "bench_clip"
UA = {"User-Agent": "TeachingCopilot/0.1 (educational research prototype; paritosh21raut@gmail.com)"}
QUERIES = {"heart": "human heart diagram", "saturn": "planet Saturn", "lungs": "human lungs",
           "microscope": "light microscope", "leaf": "photosynthesis leaf diagram", "frog": "frog life cycle",
           "volcano": "volcano eruption", "circuit": "simple electric circuit"}


def fetch() -> list[tuple[str, Path]]:
    OUT.mkdir(parents=True, exist_ok=True)
    out = []
    with httpx.Client(headers=UA, timeout=15, follow_redirects=True) as c:
        for key, q in QUERIES.items():
            path = OUT / f"{key}.jpg"
            if not path.exists():
                r = c.get("https://commons.wikimedia.org/w/api.php", params={
                    "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                    "gsrsearch": f"{q} filetype:bitmap", "gsrlimit": 1, "prop": "imageinfo",
                    "iiprop": "url|mime", "iiurlwidth": 640})
                page = next(iter(r.json()["query"]["pages"].values()))
                img = c.get(page["imageinfo"][0]["thumburl"]).content
                Image.open(io.BytesIO(img)).convert("RGB").save(path, quality=90)
                print(f"{key}: {page['title']}")
            out.append((key, path))
    return out


def ms(f, n=5) -> float:
    f()  # warm-up
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        f()
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times)


def main() -> None:
    images = fetch()
    pil = [Image.open(p) for _, p in images]
    for img in pil:
        img.load()
    keys = [k for k, _ in images]
    for quantized in (True, False):
        for threads in (2, 4):
            s = ClipScorer(ROOT / "models" / "clip", quantized=quantized, threads=threads)
            load = s.load()
            text = ms(lambda: s.embed_texts(["human heart diagram"]))
            prep = ms(lambda: [preprocess(i) for i in pil])
            vis = ms(lambda: s.embed_images(pil), n=3)
            print(f"{'int8' if quantized else 'fp32'} threads={threads}: load {load:.2f} s | text {text:.0f} ms | "
                  f"preprocess x8 {prep:.0f} ms | vision x8 {vis:.0f} ms | total x8 ≈ {text + vis:.0f} ms")
        t = s.embed_texts([QUERIES[k] for k in keys])
        v = s.embed_images(pil)
        sim = t @ v.T
        print("scores (rows = query, cols = image):", " ".join(f"{k[:6]:>6}" for k in keys))
        for k, row in zip(keys, sim):
            print(f"  {k:<10}", " ".join(f"{x:6.3f}" for x in row),
                  "  OK" if row.argmax() == keys.index(k) else "  MISS")


if __name__ == "__main__":
    main()
