"""Builds web/vendor/icons/scene-icons.js from the Tabler Icons package (MIT, @tabler/icons 3.19.0): the curated
icons a live scene may draw for a said noun (F-015 L2a), with the words each one answers to.

    python tools/build_scene_icons.py <dir with icons.json, tabler-nodes-outline.json, LICENSE>

Words: ours (PICK) and the icon's own name: a said noun that is one of them gets the icon. Tabler's tags are kept apart
(looser: "space" is a rocket's tag); scene.assets embeds the name, words and tags for the nearest-meaning match."""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "web" / "vendor" / "icons"
# icon -> our words (singular; a plural matches too)
PICK: dict[str, str] = {
    # vehicles
    "rocket": "rocket spaceship spacecraft missile", "train": "train locomotive railway rail metro engine",
    "ship": "ship steamer liner vessel", "sailboat": "boat sailboat yacht", "speedboat": "motorboat speedboat",
    "kayak": "kayak canoe rowboat", "submarine": "submarine", "plane": "plane aeroplane airplane aircraft jet",
    "helicopter": "helicopter chopper", "bus": "bus coach", "truck": "truck lorry", "bike": "bicycle bike cycle cyclist",
    "motorbike": "motorbike motorcycle", "scooter": "scooter", "tractor": "tractor", "ambulance": "ambulance",
    "firetruck": "firetruck fire engine", "tank": "tank", "trolley": "tram", "air-balloon": "balloon hot air",
    "zeppelin": "airship zeppelin", "drone": "drone", "parachute": "parachute parachutist", "car-suv": "jeep suv",
    "skateboard": "skateboard", "sleigh": "sleigh sledge sled", "caravan": "caravan", "forklift": "forklift",
    "crane": "crane", "bulldozer": "bulldozer", "wheelchair": "wheelchair", "ufo": "ufo",
    "satellite": "satellite", "comet": "comet", "meteor": "meteor meteorite asteroid", "planet": "planet",
    "moon": "moon", "sun": "sun star",
    # people
    "walk": "person man boy girl walker pedestrian student child kid human policeman thief soldier worker farmer teacher driver passenger traveller traveler observer", "woman": "woman lady",
    "run": "runner athlete sprinter jogger", "swimming": "swimmer", "man": "gentleman",
    "ice-skating": "skater", "ski-jumping": "skier", "play-football": "footballer player",
    # animals
    "dog": "dog puppy", "cat": "cat kitten", "fish": "fish shark", "horse": "horse pony", "deer": "deer",
    "pig": "pig", "spider": "spider", "butterfly": "butterfly", "bug": "insect bug beetle", "bat": "bat",
    "feather": "feather",
    # objects
    "ball-football": "football soccer", "ball-basketball": "basketball", "ball-tennis": "tennis",
    "ball-baseball": "baseball", "ball-volleyball": "volleyball", "ball-bowling": "bowling",
    "ball-american-football": "rugby", "balloon": "balloon", "umbrella": "umbrella",
    "apple": "apple fruit", "bucket": "bucket pail", "bottle": "bottle", "cup": "cup glass", "anchor": "anchor",
    "barbell": "barbell dumbbell", "weight": "weight", "hammer": "hammer", "ladder": "ladder", "magnet": "magnet",
    "bulb": "bulb lamp", "tree": "tree", "flower": "flower", "leaf": "leaf", "mountain": "mountain hill",
    "cloud": "cloud", "cloud-rain": "rain raindrop", "snowflake": "snow snowflake", "building": "building",
    "home": "house home", "tent": "tent", "building-bridge": "bridge", "building-lighthouse": "lighthouse",
    "building-skyscraper": "tower skyscraper", "egg": "egg", "wheel": "wheel",
}


def main(src: Path) -> None:
    meta = json.loads((src / "icons.json").read_text(encoding="utf-8"))
    nodes = json.loads((src / "tabler-nodes-outline.json").read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for name, ours in PICK.items():
        if name not in nodes:
            print("missing", name)
            continue
        words = ours.split() + [w for w in name.split("-") if w not in ("ball", "play", "building", "2")]
        tags = [t.lower() for t in meta.get(name, {}).get("tags", []) if t.isalpha() and t.lower() not in words]
        out[name] = {"words": list(dict.fromkeys(w.lower() for w in words)), "tags": tags, "nodes": nodes[name]}
    OUT.mkdir(parents=True, exist_ok=True)
    body = json.dumps(out, separators=(",", ":"), ensure_ascii=False)
    (OUT / "scene-icons.js").write_text(
        "// Tabler Icons 3.19.0 (MIT, LICENSE-tabler.txt), outline, 24 x 24, stroke currentColor. Curated for live\n"
        "// scenes by tools/build_scene_icons.py: icon -> {words it answers to, Tabler's tags, its SVG nodes}. Read by scene.assets too.\n"
        f"export const ICONS = {body};\n", encoding="utf-8")
    (OUT / "LICENSE-tabler.txt").write_text((src / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8")
    print(len(out), "icons,", len(body) // 1024, "KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
