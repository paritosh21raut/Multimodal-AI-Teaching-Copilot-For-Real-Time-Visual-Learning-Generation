"""D1c puppet proof: cut the SIDE view of `man in all poses.jpg` into rig parts (flat-colour masks, hidden areas filled).

    .venv/Scripts/python tools/imggen/cut_puppet.py [--debug]
-> artifacts/d1c/parts/*.png + parts.json (pivots in part pixels, metres per pixel). --debug writes class/part previews.
The art is flat colour on white, so every pixel is classed by its nearest palette colour; alpha = un-blend from white.
"""
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "whatsapp_artifacts" / "man in all poses.jpg"
OUT = ROOT / "artifacts" / "d1c"
BOX = (840, 85, 1110, 1165)                     # side view in the 1920x1280 sheet
HEIGHT_M = 1.80                                  # hair tip to sole

PAL = {  # sampled from the sheet (see --debug), not the spec hex, so fills match the art exactly
    "hair": None, "skin": None, "skinD": None, "shirt": None, "pants": None, "shoes": None,
}
SEED = {"hair": (46, 43, 41), "skin": (250, 213, 176), "skinD": (232, 184, 150), "shirt": (79, 166, 178),
        "pants": (219, 203, 174), "shoes": (139, 126, 116), "eye": (110, 75, 45), "white": (255, 255, 255)}

# joints in SHEET pixels (side view, facing right) — read off the gridded crop
J = {"neck": (985, 330), "shoulder": (962, 395), "elbow": (958, 592), "wrist": (990, 690),
     "hip": (972, 735), "knee": (978, 905), "ankle": (985, 1092)}


def classify(img):
    a = img.astype(np.float32)
    names = list(SEED)
    cols = np.array([SEED[n] for n in names], np.float32)
    d = ((a[:, :, None, :] - cols[None, None]) ** 2).sum(-1)
    return np.array(names)[d.argmin(-1)], names


def sample_palette(img, cls):
    for n in PAL:
        m = cls == n
        PAL[n] = tuple(int(v) for v in np.median(img[m], axis=0)) if m.sum() > 50 else SEED[n]


def unblend_alpha(img):
    """alpha from how far a pixel is from white (flat art on white): 0 = white, 1 = a solid colour."""
    a = img.astype(np.float32)
    dark = 255 - a.min(-1)                      # distance of the darkest channel from white
    return np.clip(dark / 40.0, 0, 1)


def row_fill(rgba, mask, colour, y0, y1):
    """fill each row's span of `mask` between y0..y1 with `colour` (hides what lay on top, e.g. the arm)."""
    h, w = mask.shape
    for y in range(max(0, y0), min(h, y1)):
        xs = np.nonzero(mask[y])[0]
        if len(xs) > 1:
            rgba[y, xs[0]:xs[-1] + 1, :3] = colour
            rgba[y, xs[0] + 1:xs[-1], 3] = 255


def largest(mask):
    """the largest 8-connected piece of a mask (drops specks and neighbouring edge lines)."""
    seen = np.zeros_like(mask)
    best, best_n = None, 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        q, pix = deque([(y0, x0)]), []
        seen[y0, x0] = True
        while q:
            y, x = q.popleft()
            pix.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    v, u = y + dy, x + dx
                    if 0 <= v < mask.shape[0] and 0 <= u < mask.shape[1] and mask[v, u] and not seen[v, u]:
                        seen[v, u] = True
                        q.append((v, u))
        if len(pix) > best_n:
            best, best_n = pix, len(pix)
    out = np.zeros_like(mask)
    if best:
        ys, xs = zip(*best)
        out[list(ys), list(xs)] = True
    return out


def part(name, rgba, keep, pivot, parts, pad=6):
    """crop the pixels in `keep` to a tight PNG, remember the pivot in part pixels."""
    keep = largest(keep & (rgba[:, :, 3] > 0))
    a = rgba.copy()
    a[~keep, 3] = 0
    ys, xs = np.nonzero(a[:, :, 3] > 0)
    x0, x1, y0, y1 = xs.min() - pad, xs.max() + pad, ys.min() - pad, ys.max() + pad
    x0, y0 = max(0, x0), max(0, y0)
    Image.fromarray(a[y0:y1 + 1, x0:x1 + 1]).save(OUT / "parts" / f"{name}.png")
    px, py = pivot[0] - BOX[0], pivot[1] - BOX[1]
    parts[name] = {"file": f"parts/{name}.png", "pivot": [int(px - x0), int(py - y0)], "origin": [int(x0), int(y0)]}


def main():
    (OUT / "parts").mkdir(parents=True, exist_ok=True)
    img = np.array(Image.open(SRC).convert("RGB").crop(BOX))
    cls, _ = classify(img)
    sample_palette(img, cls)
    alpha = unblend_alpha(img)
    fig = alpha > 0.08                          # drops faint JPEG specks
    H, W = cls.shape
    yy, xx = np.mgrid[0:H, 0:W]
    j = {k: (v[0] - BOX[0], v[1] - BOX[1]) for k, v in J.items()}
    # edge pixels were blended with the white page: un-blend so no light halo shows on a dark background
    a3 = np.maximum(alpha, 1e-3)[:, :, None]
    clean = np.clip((img.astype(np.float32) - (1 - a3) * 255) / a3, 0, 255).astype(np.uint8)
    rgba = np.dstack([np.where(fig[:, :, None], clean, img), (alpha * fig * 255).astype(np.uint8)])
    solid = lambda n: tuple(PAL[n])
    parts = {}

    shirt = (cls == "shirt") & fig
    pants = (cls == "pants") & fig
    shoes = (cls == "shoes") & fig
    skin = np.isin(cls, ["skin", "skinD"]) & fig

    # --- arm (in front of the torso): sleeve = shirt pixels inside a polygon band, skin below the sleeve hem
    sleeve_poly = (yy > j["shoulder"][1] - 45) & (yy < 512 - BOX[1]) & (xx > 925 - BOX[0]) & (xx < 1012 - BOX[0])
    upper = (skin & (yy >= 500 - BOX[1]) & (yy < j["elbow"][1] + 14)) & (xx < 1000 - BOX[0])
    lower = skin & (yy >= j["elbow"][1] - 14) & (yy < 800 - BOX[1]) & (xx > 925 - BOX[0]) & ~((cls == "skinD") & (xx < 975 - BOX[0]) & (yy > 690 - BOX[1]))
    # the sleeve is teal on teal (no edge in the art): the page draws it as a rounded shape over this skin part
    del sleeve_poly
    part("upperArm", rgba, upper, J["shoulder"], parts)
    part("foreArm", rgba, lower, J["elbow"], parts)

    # --- torso: shirt silhouette with the arm hole filled flat teal; neck skin above the collar rides on the torso
    tor = rgba.copy()
    row_fill(tor, shirt, solid("shirt"), 0, H)
    shirt_full = tor[:, :, 3] > 0
    shirt_full &= (np.abs(tor[:, :, :3].astype(int) - solid("shirt")).sum(-1) < 60) | shirt
    neck = skin & (yy > 300 - BOX[1]) & (yy < 360 - BOX[1]) & (xx > 935 - BOX[0]) & (xx < 1010 - BOX[0])
    part("torso", tor, shirt_full | neck, J["hip"], parts)

    # --- head: everything above the jaw/neck line that is hair or skin (the face is redrawn live)
    head = fig & (yy < 336 - BOX[1]) & ~shirt     # overlaps the neck; drawn on top of the torso
    hd = rgba.copy()
    face_box = (xx > 1008 - BOX[0]) & (xx < 1068 - BOX[0]) & (yy > 198 - BOX[1]) & (yy < 302 - BOX[1])
    erase = face_box & head & ~np.isin(cls, ["skin"]) & (alpha > 0.3)
    hd[erase, :3] = solid("skin")              # wipe drawn eye, brow, mouth (nose is silhouette, kept)
    for y in range(198 - BOX[1], 302 - BOX[1]):  # eye whites read as background: make the face solid skin up to its profile edge
        xs = np.nonzero(head[y] & (alpha[y] > 0.5))[0]
        if len(xs) < 2:
            continue
        span = np.zeros(W, bool)
        span[xs[0]:xs[-1]] = True
        fix = span & face_box[y] & (cls[y] != "hair")
        hd[y, fix, :3] = solid("skin")
        hd[y, fix, 3] = 255
        head[y, xs[0]:xs[-1]] = True
    part("head", hd, head, J["neck"], parts)

    # --- legs: pants rows filled flat (removes the hand), split at the knee; shoe separate
    pl = rgba.copy()
    row_fill(pl, pants, solid("pants"), 0, H)
    pfull = (pl[:, :, 3] > 0) & (np.abs(pl[:, :, :3].astype(int) - solid("pants")).sum(-1) < 60) | pants
    pfull &= yy > 680 - BOX[1]
    part("pelvis", pl, pfull & (yy < j["hip"][1] + 40), J["hip"], parts)
    part("thigh", pl, pfull & (yy > j["hip"][1] - 30) & (yy < j["knee"][1] + 18), J["hip"], parts)
    part("shin", pl, pfull & (yy > j["knee"][1] - 18) & (yy < j["ankle"][1] + 6), J["knee"], parts)
    part("shoe", rgba, shoes & (yy > 1080 - BOX[1]), J["ankle"], parts)

    top = np.nonzero(fig.any(1))[0]
    mpp = HEIGHT_M / (top.max() - top.min())
    face = {k: [v[0] - parts["head"]["origin"][0], v[1] - parts["head"]["origin"][1]] for k, v in
            {"eye": (1050 - BOX[0], 240 - BOX[1]), "brow": (1046 - BOX[0], 214 - BOX[1]), "mouth": (1046 - BOX[0], 292 - BOX[1])}.items()}
    meta = {"view": "side", "facing": "right", "m_per_px": mpp, "palette": PAL, "parts": parts, "face": face,
            "joints_sheet_px": J, "box": BOX, "source": SRC.name}
    (OUT / "parts.json").write_text(json.dumps(meta, indent=1))
    print("parts:", list(parts), "m/px %.5f" % mpp, "palette", PAL)
    if "--debug" in sys.argv:
        colours = {n: SEED[n] for n in SEED}
        dbg = np.zeros((H, W, 3), np.uint8)
        for n, c in colours.items():
            dbg[cls == n] = c
        Image.fromarray(dbg).save(OUT / "debug_classes.png")


if __name__ == "__main__":
    main()
