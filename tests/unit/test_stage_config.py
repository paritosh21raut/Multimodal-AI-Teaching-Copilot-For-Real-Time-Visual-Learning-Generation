"""F-017 E1: the stage's committed data (catalog, cast, clip table, motion pack) and the hand-made patch fixtures."""
import json
import sys
from pathlib import Path

import pytest

from copilot.scene.sizes import TYPICAL
from copilot.stage.motion import CLIPS, MOTION, VERBS, Motion, clip_table, clips, load

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "stage"))
import make_patches  # noqa: E402

CATALOG = json.loads((ROOT / "config" / "stage_catalog.json").read_text(encoding="utf-8"))
CAST = json.loads((ROOT / "config" / "stage_cast.json").read_text(encoding="utf-8"))["cast"]
CONTRACT_VERBS = set("""walk jog run stand sit jump push pull throw catch carry pick_up put_down hold point talk call
phone fold_arms nod shake_head wave drive swim float climb crouch kneel roll slide water plant harvest chop eat
drink dance look_at""".split())


@pytest.fixture(scope="module")
def motion():
    return Motion(load())


def test_catalog_ids_are_unique_and_sizes_positive():
    for kind in ("props", "backdrops", "species"):
        ids = [r["id"] for r in CATALOG[kind]]
        assert len(ids) == len(set(ids)), kind
    assert 55 <= len(CATALOG["props"]) and len(CATALOG["backdrops"]) == 10 and len(CATALOG["species"]) == 6
    for r in CATALOG["props"] + CATALOG["species"]:
        assert len(r["size_m"]) == 2 and min(r["size_m"]) > 0, r["id"]
    for r in CATALOG["props"]:
        assert r["names"] and all(len(a) == 2 for a in r["anchors"].values()), r["id"]


def test_prop_sizes_agree_with_the_sizes_table():
    for r in CATALOG["props"]:
        if r["category"] in ("sky", "effect"):  # sky things: the size they look; rain: an area
            continue
        known = [TYPICAL[n] for n in r["names"] if n in TYPICAL]
        assert known, f"{r['id']}: no name in copilot.scene.sizes"
        w, h = r["size_m"]
        if min(known) > 50:  # a landscape noun (cliff) drawn as a set piece
            continue
        assert any(0.55 <= h / m <= 1.8 or 0.55 <= max(w, h) / m <= 1.8 for m in known), (r["id"], r["size_m"], known)


def test_cast_has_twelve_varied_people():
    ids = [c["id"] for c in CAST]
    assert len(ids) == 12 == len(set(ids))
    assert sum(c["sex"] == "m" for c in CAST) == 6 and sum(c["sex"] == "f" for c in CAST) == 6
    assert sum(c["child"] for c in CAST) >= 3 and any("elder" in c["id"] for c in CAST)
    assert len({c["skin"] for c in CAST}) >= 10 and len({c["top"] for c in CAST}) == 12
    assert {c["hair_style"] for c in CAST} >= {"short", "long", "bun", "ponytail", "curly", "bald"}
    keys = {"id", "sex", "child", "skin", "hair", "hair_style", "beard", "glasses", "top", "sleeve", "bottom", "bottom_type",
            "shoes", "build", "height_m"}
    for c in CAST:
        assert keys <= set(c), c["id"]
        # natural skin, fair to medium-dark (user, 2026-10-26): perceived lightness 0.299 R + 0.587 G + 0.114 B >= 120
        r, g, b = (int(c["skin"][i:i + 2], 16) for i in (1, 3, 5))
        assert 0.299 * r + 0.587 * g + 0.114 * b >= 120 and r > g > b, (c["id"], c["skin"])
        assert c["bottom_type"] in ("pants", "skirt", "shorts") and 1.0 < c["height_m"] < 2.0


def test_clip_table_matches_the_motion_pack(motion):
    table = clips()
    assert set(table) == set(motion.clips)
    assert MOTION.stat().st_size <= 1.6e6
    for name, r in table.items():
        n = len(motion.clips[name]["frames"])
        assert r["frames"] == n and set(r["verb"]) <= CONTRACT_VERBS
        for k, v in r["events"].items():
            frames = [f for f, _ in v] if k == "footstrike" else [v]
            assert all(0 <= f < n for f in frames), (name, k)
        if "lock" in r:
            assert len(r["lock"]["l"]) == len(r["lock"]["r"]) == n == len(r["contact"]["l"])
    assert set(VERBS) <= CONTRACT_VERBS
    for v in ("walk", "jog", "run"):
        assert all(table[c]["stride_mps"] > 0.1 for c in VERBS[v])
    assert table["Sitting_Idle_Loop"]["seat_h"] > 0.2 and "release" in table["OverhandThrow"]["events"]


def test_the_committed_clip_table_is_reproducible():
    assert json.loads(CLIPS.read_text(encoding="utf-8")) == json.loads(json.dumps(clip_table(load())))


def test_the_foot_lock_keeps_planted_feet_still(motion):
    """At stride speed, a planted contact point moves under 1 mm (per m of height) between frames with the lock."""
    table = clips()
    for name in ("Walk_Loop", "Jog_Fwd_Loop", "Sprint_Loop", "Walk_Carry_Loop", "Push_Loop"):
        r, f = table[name], motion.clips[name]["frames"]
        n, step = len(f), r["stride_mps"] * r["dur"] / len(f)
        for s in "lr":
            code, lk = [int(c) for c in r["contact"][s]], r["lock"][s]
            for i in range(n):
                j = (i + 1) % n
                if code[i] and code[j] and (code[i] & 2) == (code[j] & 2):
                    p = motion.ji[("ball_" if code[i] & 2 else "foot_") + s]
                    a = f[i][p][0] + step * i + lk[i]
                    b = f[j][p][0] + step * (i + 1) + lk[j]
                    assert abs(b - a) < 1e-3, (name, s, i)


def test_make_patches_is_deterministic_and_committed():
    a, b = make_patches.build(), make_patches.build()
    assert a == b
    for n, p in a.items():
        f = make_patches.OUT / f"{n}.json"
        assert f.read_text(encoding="utf-8") == make_patches.dump(p), f"{n}: run tools/stage/make_patches.py"
        assert p["source"].startswith("hand-made")
    assert sorted(a) == sorted(make_patches.NAMES) and len(a) == 8
    for n in ("push", "rain"):  # a looping walk restarts in step with its clip (tug: the rope resets anyway)
        tr = next(t for t in a[n]["tracks"] if t["kind"] == "clip")
        cyc = a[n]["period"] * tr["rate"] / clips()[tr["clip"]]["dur"]
        assert abs(cyc - round(cyc)) < 1e-3, (n, cyc)


def test_patches_use_the_clip_facts(motion):
    table, cast = clips(), {c["id"]: c for c in CAST}
    pats = make_patches.build()
    # the throw lets go at the clip's release frame, and the ball's flight starts there
    th = pats["throw"]
    rel = motion.frame_time("OverhandThrow", table["OverhandThrow"]["events"]["release"])
    path = next(t for t in th["tracks"] if t["id"] == "ball" and t["kind"] == "path")
    sock = next(t for t in th["tracks"] if t["kind"] == "socket")
    assert abs(path["samples"][0][0] - rel) <= 1 / 24 and abs(sock["t1"] - rel) <= 1 / 24
    # a locked walk moves at the clip's stride speed x the rate
    for p in pats.values():
        ents = {e["id"]: e for e in p["entities"]}
        for tr in p["tracks"]:
            if tr["kind"] != "clip" or not tr.get("lock"):
                continue
            pth = next(t for t in p["tracks"] if t["id"] == tr["id"] and t["kind"] == "path")
            (t0, x0, _), (t1, x1, _) = pth["samples"][0][:3], pth["samples"][1][:3]
            h = cast[ents[tr["id"]]["draw"][5:]]["height_m"]
            fwd = ents[tr["id"]].get("xform", {}).get("dir", 1) * (-1 if tr.get("mirror") else 1)  # a mirrored clip steps back
            assert abs((x1 - x0) / (t1 - t0) - fwd * table[tr["clip"]]["stride_mps"] * h * tr["rate"]) < 1e-3, p["name"]
    # every drawn id is in the catalog or the cast
    ids = {r["id"] for r in CATALOG["props"]}
    for p in pats.values():
        for e in p["entities"]:
            d = e["draw"]
            assert (d[5:] in cast) if d.startswith("cast:") else (d in ids), (p["name"], d)
