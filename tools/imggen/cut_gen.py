"""D1: background removal for the generated comparison images (the app's own u2netp matting, CPU), timed.

    .venv/Scripts/python tools/imggen/cut_gen.py [provider]  -> artifacts/style_board/gen/<provider>_cut/*.png
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from PIL import Image  # noqa: E402

from copilot.scene.photos import Matting, cutout  # noqa: E402

provider = sys.argv[1] if len(sys.argv) > 1 else "local"
src = ROOT / "artifacts" / "style_board" / "gen" / provider
dst = src.parent / f"{provider}_cut"
dst.mkdir(parents=True, exist_ok=True)
m = Matting()
times = []
for f in sorted(src.glob("*.png")):
    img = Image.open(f)
    if f.stem.endswith("_street"):  # a full scene: kept whole
        img.save(dst / f.name)
        continue
    t = time.perf_counter()
    out = cutout(img, m.alpha(img))
    times.append(time.perf_counter() - t)
    out.save(dst / f.name)
if times:  # the first call also loads the model: reported apart from the warm mean
    warm = times[1:] or times
    print(f"{len(times)} cutouts, first {times[0]:.2f}s (model load), warm mean {sum(warm) / len(warm):.2f}s")
else:
    print(f"no images in {src}")
