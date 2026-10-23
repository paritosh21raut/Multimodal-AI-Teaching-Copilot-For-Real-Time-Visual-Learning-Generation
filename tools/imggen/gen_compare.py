"""D1 style board: AI-generated comparison column (cloud providers + local SD-Turbo), timed per image.

    python tools/imggen/gen_compare.py cf_flux|cf_sdxl|hf_flux [limit]       (any python: stdlib only)
    tools/imggen/.venv/Scripts/python tools/imggen/gen_compare.py local [limit] [--whisper]   (--whisper: only a label;
      run hold_whisper.py first so the STT model really sits on the GPU)

Writes artifacts/style_board/gen/<provider>/<style>_<subject>.png and appends a timing row per image to
artifacts/style_board/gen/timings.jsonl. Keys are read from .env and never printed.
"""
from __future__ import annotations

import base64
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "style_board" / "gen"

STYLES = {
    "A": "flat vector illustration in Kurzgesagt style, rounded geometric shapes, no outlines, soft gradients, "
         "vibrant colours",
    "D": "soft 3D cartoon render in Pixar style, smooth gradient shading, rim light, friendly",
}
SUBJECTS = {
    "man": "a man standing, full body, front view",
    "child": "a young child standing, full body",
    "dog": "a dog standing, side view, full body",
    "bird": "a small bird, side view",
    "car": "a red car, side view",
    "rocket": "a rocket standing upright",
    "atom": "a hydrogen atom: one nucleus and one electron on a circular orbit",
    "graph": "a math graph of a curve with the area under it split into thin vertical strips",
    "street": "a rainy city street at night, lightning striking a lightning rod on a rooftop",
}
SCENES = {"street"}  # full scenes: no plain background, no cutout


def prompt(style: str, subject: str) -> str:
    bg = "" if subject in SCENES else ", isolated on a plain white background, centered, no text"
    return f"{SUBJECTS[subject]}, {STYLES[style]}{bg}"


SECRETS: list[str] = []


def env() -> dict[str, str]:
    out = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
            if out[k.strip()]:
                SECRETS.append(out[k.strip()])
    return out


def post(url: str, headers: dict, body: dict, timeout: float = 120) -> tuple[bytes, str]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def cloud(provider: str):
    e = env()
    if provider.startswith("cf_"):
        model = {"cf_flux": "@cf/black-forest-labs/flux-1-schnell",
                 "cf_sdxl": "@cf/bytedance/stable-diffusion-xl-lightning"}[provider]
        url = f"https://api.cloudflare.com/client/v4/accounts/{e['CloudFlare_id']}/ai/run/{model}"
        headers = {"Authorization": f"Bearer {e['CloudFlare_token']}"}

        def gen(p: str) -> bytes:
            body = {"prompt": p, "steps": 4} if provider == "cf_flux" else {"prompt": p, "width": 768, "height": 768}
            data, ctype = post(url, headers, body)
            if "json" in ctype:
                return base64.b64decode(json.loads(data)["result"]["image"])
            return data
        return gen
    if provider == "hf_flux":
        # hf-inference dropped FLUX.1-schnell (410); nscale serves it through the HF router (OpenAI images API)
        url = "https://router.huggingface.co/nscale/v1/images/generations"
        headers = {"Authorization": f"Bearer {e['HuggingFace_token']}"}

        def gen(p: str) -> bytes:
            body = {"model": "black-forest-labs/FLUX.1-schnell", "prompt": p, "response_format": "b64_json",
                    "size": "768x768"}
            return base64.b64decode(json.loads(post(url, headers, body)[0])["data"][0]["b64_json"])
        return gen
    raise SystemExit(f"unknown provider {provider}")


def gpu_used_mib() -> int:
    """Whole-GPU memory in use (all processes: SD-Turbo here + Whisper held by hold_whisper.py)."""
    import subprocess
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return int(out.split()[0])


def local():
    import io

    import torch
    from diffusers import AutoPipelineForText2Image

    t = time.perf_counter()
    pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sd-turbo", torch_dtype=torch.float16, variant="fp16")
    pipe.to("cuda")
    pipe.set_progress_bar_config(disable=True)
    print(f"load {time.perf_counter() - t:.1f}s, gpu {gpu_used_mib()} MiB", flush=True)

    def gen(p: str) -> bytes:
        img = pipe(prompt=p, num_inference_steps=1, guidance_scale=0.0, width=512, height=512).images[0]
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    def vram() -> dict:
        return {"torch_peak_mib": round(torch.cuda.max_memory_reserved() / 2**20), "gpu_used_mib": gpu_used_mib()}
    return gen, vram


def main() -> None:
    provider = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 99
    vram = None
    if provider == "local":
        gen, vram = local()
    else:
        gen = cloud(provider)
    out = OUT / provider
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(s, k) for s in STYLES for k in SUBJECTS][:limit]
    with (OUT / "timings.jsonl").open("a", encoding="utf-8") as log:
        for i, (style, subject) in enumerate(jobs):
            t = time.perf_counter()
            row = {"provider": provider, "style": style, "subject": subject, "n": i}
            try:
                data = gen(prompt(style, subject))
                (out / f"{style}_{subject}.png").write_bytes(data)
                row["ok"] = True
            except urllib.error.HTTPError as err:
                row.update(ok=False, error=f"HTTP {err.code}: {err.read()[:200].decode(errors='replace')}")
            except Exception as err:  # noqa: BLE001 - recorded, run continues
                msg = str(err)
                for secret in SECRETS:  # e.g. an invalid-header error echoes the Authorization value
                    msg = msg.replace(secret, "***")
                row.update(ok=False, error=f"{type(err).__name__}: {msg[:200]}")
            row["seconds"] = round(time.perf_counter() - t, 2)
            if vram:
                row.update(vram(), whisper="--whisper" in sys.argv)
            log.write(json.dumps(row) + "\n")
            print(row, flush=True)


if __name__ == "__main__":
    main()
