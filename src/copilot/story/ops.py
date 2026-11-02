"""Op and affordance registry (ADR-0015 addendum 2026-11-02, docs/v3/P1a-benchmark-registry.md). Data, not code paths:
every op of the closed vocabulary (world.OPS) states what it needs, what it changes, how long it takes, what happens
when it cannot run, and the motion primitives it expands to (its choreography). The compiler reads it; classify()
sorts each event of a line into one of four classes before anything is animated:

    executable      the engine has the motion and the things it needs (assets with the right affordance)
    unsupported     understood (a valid op), but the engine has no motion for it yet -> explicit fallback
    invalid         the op's preconditions fail (ride a table, a tree speaks) -> never animates
    missing_asset   valid, but a thing it needs has no drawn asset (sit on a bench, no bench) -> drawn as a box

ACTS maps the benchmark's semantic actions (tests/fixtures/story/bench/) onto the ops that express them; an action
not in ACTS is an UNKNOWN_ACTION (P1b adds actions by those counts, not by a guessed list).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from copilot.story import world as W

ANIMATE = ("person", "animal", "group", "agent")
MOVERS = ANIMATE + ("prop",)
CLASSES = ("executable", "unsupported", "invalid", "missing_asset")
# attach mode -> the affordance its target must have, and the class of actor that can do it
MODE_AFFORDANCE = {"hold": "holdable", "ride": "rideable", "sit_on": "supports_sitting", "in": "container"}
MODE_ACTOR = {"hold": ("person", "animal", "group"), "ride": ("person", "animal", "group"), "sit_on": ("person", "animal", "group"),
              "in": MOVERS}
# motion primitives the renderer / compiler know (the vocabulary choreographies are written in)
_TARGET_DRAWN = ("attach", "move_to", "enter", "fall", "throw", "work", "detach", "put", "give", "climb", "push")
PRIMITIVES = ("approach", "face", "posture", "reach", "grip", "release", "carry", "step", "tween", "ballistic",
              "contact", "bubble", "gesture", "express", "hide", "show", "crouch", "hop", "climb", "slide", "handover")
# op -> the affordance its target must have (when the target has a drawn asset); a person rig does the hand ops
OP_AFFORDANCE = {"climb": "climbable"}
RIG_OPS = ("put", "give", "jump", "climb", "push", "throw")   # need a rigged actor (a person): hands, a hop


@dataclass(frozen=True)
class Op:
    name: str
    actor: tuple[str, ...]                 # entity kinds that may do it
    target: str                            # "required" | "optional" | "none"
    effects: tuple[str, ...]               # world changes (world.World._event)
    dur: float                             # seconds of the compiled motion (speak: + per_char)
    fail: str                              # what the scene does when it cannot run
    expands: tuple[str, ...]               # choreography: the primitives in order
    motion: bool                           # P0 has a motion for it (the compiler executes it)
    values: tuple[str, ...] = ()           # the closed values ("" = none needed)
    motion_values: tuple[str, ...] = ()    # values with a motion (empty = all of `values`)
    per_char: float = 0.0
    tail: float = 0.0                      # speak: the bubble stays this long after typing
    pre: tuple[str, ...] = field(default=())  # extra preconditions, named (checked in classify)


OPS: dict[str, Op] = {o.name: o for o in (
    Op("enter", MOVERS, "optional", ("place: leaves the old location",), 0.0, "actor stays where it is",
       ("show", "approach"), True, pre=("target_drawn",)),
    Op("exit", MOVERS, "optional", ("place: leaves every location",), 0.0, "actor stays (fallback)",
       ("face", "approach", "hide"), True),
    Op("move_to", MOVERS, "required", ("place: leaves the old location", "arrives at target"), 0.0,
       "actor stays where it is", ("face", "approach"), True, pre=("target_drawn",)),
    Op("follow_path", MOVERS, "optional", ("place: leaves the old location",), 0.0, "actor stays (fallback)",
       ("face", "approach"), True),
    Op("change_posture", ANIMATE, "none", ("posture = value",), 0.9, "keeps the old posture (rider: no change)",
       ("posture",), True, values=W.POSTURES),
    Op("attach", MOVERS, "required", ("relation actor-mode-target", "ride / sit_on: posture sit"), 1.1,
       "nothing attaches; actor keeps its place", ("approach", "reach", "grip", "carry"), True,
       values=W.MODES, motion_values=("ride", "sit_on", "hold"), pre=("mode_actor", "mode_affordance")),
    Op("detach", MOVERS, "optional", ("ends hold / ride / sit_on (with target: only that one)",), 0.8,
       "the attachment stays", ("release", "step"), True),
    Op("fall", MOVERS, "optional", ("leaves where it hung / was held", "person: posture lie"), 0.6,
       "already down / on a carrier: stays (fallback)", ("ballistic", "contact"), True, values=("",) + W.PARTS),
    Op("throw", ("person", "group"), "optional", ("obj leaves the hand",), 0.5, "obj stays held (fallback)",
       ("face", "reach", "release", "ballistic", "contact"), True, pre=("obj_or_target",)),
    Op("look_at", ANIMATE, "required", ("faces target",), 1.2, "no turn", ("face",), True),
    Op("point_at", ANIMATE, "required", ("faces target",), 1.2, "no turn", ("face", "gesture"), True),
    Op("speak", MOVERS, "optional", ("faces listener (both)",), 0.5, "caption only", ("face", "bubble"), True,
       per_char=0.06, tail=1.6),
    Op("react", MOVERS, "none", ("feeling shown",), 1.4, "no expression", ("express",), True, values=W.FEELINGS),
    Op("work", ("person", "group"), "optional", ("acts on target",), 1.5, "actor stays (fallback)",
       ("approach", "gesture"), False),
    Op("put", ("person", "group"), "optional", ("obj leaves the hold", "obj value target (no target: the ground)"),
       0.9, "obj stays held (fallback)", ("approach", "crouch", "release", "tween"), True, values=W.PUT),
    Op("give", ("person", "group"), "required", ("the hold moves to the target",), 1.2, "obj stays with the giver",
       ("approach", "face", "reach", "handover"), True, pre=("target_animate",)),
    Op("jump", ANIMATE, "optional", ("onto: actor on target", "off: leaves where it stood / sat in"), 0.0,
       "actor stays (fallback)", ("crouch", "hop", "contact"), True, values=W.JUMP),
    Op("climb", ANIMATE, "required", ("actor on target",), 0.0, "actor stays at the foot (fallback)",
       ("approach", "reach", "climb"), True, pre=("op_affordance",)),
    Op("push", ANIMATE + ("agent",), "required", ("target moves away (pull: towards)",), 1.4,
       "target stays (fallback)", ("approach", "reach", "slide"), True, values=W.PUSH),
    Op("none", MOVERS + ("place",), "none", (), 0.0, "actor stays, the line is a caption", (), False),
)}

# semantic action (benchmark annotation) -> the (op, value) alternatives that express it; full credit for any
ACTS: dict[str, tuple[tuple[str, str], ...]] = {
    "walk": (("move_to", ""), ("follow_path", ""), ("enter", "")),   # no destination said: a path
    "go": (("move_to", ""), ("follow_path", ""), ("enter", "")), "run": (("move_to", ""), ("follow_path", "")), "arrive": (("move_to", ""), ("enter", "")), "enter": (("enter", ""), ("move_to", "")),
    "leave": (("exit", ""), ("move_to", "")), "fly": (("move_to", ""),), "swim": (("move_to", ""),),
    "sit": (("change_posture", "sit"), ("attach", "sit_on")), "sit_on": (("attach", "sit_on"),),
    "stand": (("change_posture", "stand"),), "lie": (("change_posture", "lie"),),
    "sleep": (("change_posture", "lie"),), "kneel": (("change_posture", "kneel"),),
    "crouch": (("change_posture", "crouch"),),
    "ride": (("attach", "ride"),), "hold": (("attach", "hold"),), "carry": (("attach", "hold"),),
    "pick_up": (("attach", "hold"),), "get_in": (("attach", "in"), ("move_to", "")),
    "get_off": (("detach", ""),), "drop": (("detach", ""), ("fall", ""), ("put", "")), "let_go": (("detach", ""),),
    "put": (("put", ""),), "put_down": (("put", ""), ("detach", "")), "give": (("give", ""),),
    "jump": (("jump", ""),), "climb": (("climb", ""),), "push": (("push", "push"),), "pull": (("push", "pull"),),
    "catch": (("attach", "hold"),), "lift": (("attach", "hold"),), "take": (("attach", "hold"),),
    "follow": (("move_to", ""), ("follow_path", "")), "wake": (("change_posture", "stand"), ("change_posture", "sit")),
    "fall": (("fall", ""),), "throw": (("throw", ""),),
    "look": (("look_at", ""),), "point": (("point_at", ""),),
    "say": (("speak", ""),), "ask": (("speak", ""),), "shout": (("speak", ""),), "reply": (("speak", ""),),
    "react": (("react", ""),), "work": (("work", ""),),
}


def affordances(asset: dict) -> dict[str, dict]:
    return asset.get("affordances", {}) if asset else {}


def classify(ev: W.Event, world: W.World, asset_of: Callable[[W.Entity], str],
             assets: dict[str, dict]) -> tuple[str, str]:
    """(class, why) for one validated event against the world and the asset sidecars."""
    op = OPS[ev.op]
    ents = world.entities
    a = ents[ev.actor]
    tgt: Optional[W.Entity] = ents.get(ev.target or ev.obj) if (ev.target or ev.obj) else None
    if a.kind not in op.actor:
        return "invalid", f"{ev.op}: a {a.kind} cannot"
    if op.target == "required" and tgt is None:
        return "invalid", f"{ev.op}: no target"
    if "obj_or_target" in op.pre and tgt is None:
        return "invalid", f"{ev.op}: nothing to act on"
    if "target_animate" in op.pre and tgt is not None and tgt.kind not in ("person", "animal", "group"):
        return "invalid", f"{ev.op}: a {tgt.kind} cannot take it"
    if ev.op in OP_AFFORDANCE and tgt is not None:
        need, name = OP_AFFORDANCE[ev.op], asset_of(tgt)
        if name and need not in affordances(assets.get(name, {})):
            return "invalid", f"{ev.op}: {name} is not {need}"
    if ev.op == "attach":
        if a.kind not in MODE_ACTOR[ev.value]:
            return "invalid", f"{ev.value}: a {a.kind} cannot"
        need = MODE_AFFORDANCE[ev.value]
        name = asset_of(tgt) if tgt else ""
        if name and need not in affordances(assets.get(name, {})):
            return "invalid", f"{ev.value}: {name} is not {need}"
    if not op.motion or (op.motion_values and ev.value not in op.motion_values):
        return "unsupported", f"no motion for {ev.op}" + (f" {ev.value}" if ev.value else "")
    for e in (a, tgt if ev.op in _TARGET_DRAWN else None):  # a listener / a looked-at thing needs no anchor
        if e is not None and e.kind != "person" and not asset_of(e) and not (ev.op == "push" and e is a and
                                                                              a.kind == "agent"):
            return "missing_asset", f"no asset for {e.noun or e.name}"
    held = ents.get(ev.obj) if ev.obj else None
    if ev.op in ("put", "give", "throw") and held is not None and held.kind != "person" and not asset_of(held):
        return "missing_asset", f"no asset for {held.noun or held.name}"
    return "executable", ""


def check_registry() -> list[str]:
    """Every op of world.OPS has a full entry; every choreography uses known primitives; ACTS names real ops."""
    bad = [f"missing op {o}" for o in W.OPS if o not in OPS]
    bad += [f"extra op {o}" for o in OPS if o not in W.OPS]
    for o in OPS.values():
        if o.target not in ("required", "optional", "none") or not o.fail or o.dur < 0 or not o.actor:
            bad.append(f"{o.name}: incomplete")
        if o.name != "none" and not (o.effects and o.expands):
            bad.append(f"{o.name}: no effects / choreography")
        bad += [f"{o.name}: primitive {p}" for p in o.expands if p not in PRIMITIVES]
        bad += [f"{o.name}: motion value {v}" for v in o.motion_values if v not in o.values]
    for act, alts in ACTS.items():
        bad += [f"act {act}: op {op}" for op, v in alts if op not in OPS or (v and v not in OPS[op].values)]
    return bad
