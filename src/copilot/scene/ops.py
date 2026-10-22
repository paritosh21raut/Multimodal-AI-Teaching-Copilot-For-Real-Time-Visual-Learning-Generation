"""Applying checked SceneOps (scene.validate) to a scene: each op gives a new scene version (rev + 1). Engine output
(geom, frames, stage, derived) is left to scene.layout.solve, run once after a batch of ops.

    add      a new entity (an `add` of an existing id of the same kind merges, so a retried stream is harmless)
    set      merge props / name / expr into an entity
    remove   the entity, its relations, its behaviour, its focus
    relate   a relation; one per entity `a` (a new one replaces it: "now put the circle around the square")
    behave   a behaviour; one per target
    label    the entity's printed label (said words only)
    focus    the entities to highlight
    frame    the relative world seen from an entity ("as seen by the man"; "" = the ground)
    unsafe   nothing here (the controller drops the call's ops)

F-016: a scene has one place (a new one replaces it and takes over its relations); a thing keeps one motion and one
emit ("a fish swims and blows bubbles"); transform_into names the noun it becomes (its picture: scene.pictures).
"""
from __future__ import annotations

from copilot.scene import pictures
from copilot.scene.spec import Behavior, Entity, Label, Look, Relation, SceneSpec
from copilot.scene.validate import Checked

ROLES = ("main", "second", "third", "accent")


def _entity(c: Checked, scene: SceneSpec) -> Entity:
    op = c.op
    used = {e.look.role for e in scene.entities}
    role = next((r for r in ROLES if r not in used), ROLES[len(scene.entities) % len(ROLES)])
    form = pictures.form_of(c.noun) if op.kind == "thing" else ""
    return Entity(id=op.id, kind=op.kind, name=c.name, props=dict(c.props), expr=op.expr, expr_shown=c.expr_shown,
                  label=Label(text=c.name, source="said") if c.name else Label(),
                  look=Look(role=role, noun=c.noun, form=form), dir=c.dir, toward=c.toward, size=c.size)


def _merge(e: Entity, c: Checked) -> Entity:
    upd: dict = {"props": {**e.props, **c.props}}
    if c.name:
        upd["name"] = c.name
        if e.label.source != "said" or e.label.text == e.name:
            upd["label"] = Label(text=c.name, source="said")
    if c.op.expr:
        upd["expr"], upd["expr_shown"] = c.op.expr, c.expr_shown
    if c.dir:
        upd["dir"], upd["toward"] = c.dir, c.toward
    if c.size:
        upd["size"] = c.size
    if c.noun and e.look.pick == "auto" and c.noun != e.look.noun:  # a new noun: its picture is found again
        upd["look"] = e.look.model_copy(update={"noun": c.noun, "icon": "", "glyph": "", "image": "", "emoji": "",
                                                "form": pictures.form_of(c.noun) if e.kind == "thing" else ""})
    return e.model_copy(update=upd)


def apply(scene: SceneSpec, c: Checked) -> SceneSpec:
    op = c.op
    ents = list(scene.entities)
    upd: dict = {}
    if op.op in ("add", "set"):
        i = next((k for k, e in enumerate(ents) if e.id == op.id), None)
        if i is None and op.kind == "place":  # one place: the new one replaces the old and takes its relations
            old = {e.id for e in ents if e.kind == "place"}
            ents = [e for e in ents if e.id not in old]
            upd["relations"] = [r.model_copy(update={"b": op.id}) if r.b in old else r for r in scene.relations]
            upd["focus"] = [f for f in scene.focus if f not in old]
        if i is None:
            ents.append(_entity(c, scene))
        else:
            ents[i] = _merge(ents[i], c)
        upd["entities"] = ents
    elif op.op == "remove":
        upd = {"entities": [e for e in ents if e.id != op.id],
               "relations": [r for r in scene.relations if op.id not in (r.a, r.b, r.c)],
               "behaviors": [b for b in scene.behaviors if op.id not in (b.target, b.b)],
               "focus": [f for f in scene.focus if f != op.id],
               **({"frame": ""} if scene.frame == op.id else {})}
    elif op.op == "relate":
        upd["relations"] = [r for r in scene.relations if r.a != op.a] + [
            Relation(kind=op.kind, a=op.a, b=op.b, c=op.c if op.kind == "between" else "")]
    elif op.op == "behave":
        old = next((b for b in scene.behaviors if b.target == op.target and b.kind == op.kind), None)
        params = {**(old.params if old is not None else {}), **c.params}
        emit = op.kind == "emit"  # an emit sits beside the thing's motion; a motion replaces a motion
        keep = [b for b in scene.behaviors if b.target != op.target or (b.kind == "emit") != emit]
        upd["behaviors"] = keep + [Behavior(kind=op.kind, target=op.target, params=params,
                                            b=op.b if op.kind in ("follow", "chase", "orbit", "move_to", "collide")
                                            else "", text=c.text)]
        if op.kind == "transform_into":
            upd["entities"] = [e.model_copy(update={"look": e.look.model_copy(update={
                "to_noun": c.text, "to_icon": "", "to_emoji": ""})}) if e.id == op.target else e for e in ents]
    elif op.op == "label":
        assert c.label is not None
        upd["entities"] = [e.model_copy(update={"label": c.label}) if e.id == op.id else e for e in ents]
    elif op.op == "focus":
        upd["focus"] = list(op.ids)
    elif op.op == "frame":
        upd["frame"] = op.id
    return scene.model_copy(update={**upd, "rev": scene.rev + 1})
