"""Applying checked SceneOps (scene.validate) to a scene: each op gives a new scene version (rev + 1). Engine output
(geom, frames, stage, derived) is left to scene.layout.solve, run once after a batch of ops.

    add      a new entity (an `add` of an existing id of the same kind merges, so a retried stream is harmless)
    set      merge props / name / expr into an entity
    remove   the entity, its relations, its behaviour, its focus
    relate   a relation; one per entity `a` (a new one replaces it: "now put the circle around the square")
    behave   a behaviour; one per target
    label    the entity's printed label (said words only)
    focus    the entities to highlight
"""
from __future__ import annotations

from copilot.scene.spec import Behavior, Entity, Label, Look, Relation, SceneSpec
from copilot.scene.validate import Checked

ROLES = ("main", "second", "third", "accent")


def _entity(c: Checked, scene: SceneSpec) -> Entity:
    op = c.op
    used = {e.look.role for e in scene.entities}
    role = next((r for r in ROLES if r not in used), ROLES[len(scene.entities) % len(ROLES)])
    return Entity(id=op.id, kind=op.kind, name=c.name, props=dict(c.props), expr=op.expr, expr_shown=c.expr_shown,
                  label=Label(text=c.name, source="said") if c.name else Label(), look=Look(role=role))


def _merge(e: Entity, c: Checked) -> Entity:
    upd: dict = {"props": {**e.props, **c.props}}
    if c.name:
        upd["name"] = c.name
        if e.label.source != "said" or e.label.text == e.name:
            upd["label"] = Label(text=c.name, source="said")
    if c.op.expr:
        upd["expr"], upd["expr_shown"] = c.op.expr, c.expr_shown
    return e.model_copy(update=upd)


def apply(scene: SceneSpec, c: Checked) -> SceneSpec:
    op = c.op
    ents = list(scene.entities)
    upd: dict = {}
    if op.op in ("add", "set"):
        i = next((k for k, e in enumerate(ents) if e.id == op.id), None)
        if i is None:
            ents.append(_entity(c, scene))
        else:
            ents[i] = _merge(ents[i], c)
        upd["entities"] = ents
    elif op.op == "remove":
        upd = {"entities": [e for e in ents if e.id != op.id],
               "relations": [r for r in scene.relations if op.id not in (r.a, r.b)],
               "behaviors": [b for b in scene.behaviors if b.target != op.id],
               "focus": [f for f in scene.focus if f != op.id]}
    elif op.op == "relate":
        upd["relations"] = [r for r in scene.relations if r.a != op.a] + [Relation(kind=op.kind, a=op.a, b=op.b)]
    elif op.op == "behave":
        old = next((b for b in scene.behaviors if b.target == op.target and b.kind == op.kind), None)
        params = {**(old.params if old is not None else {}), **c.params}
        upd["behaviors"] = [b for b in scene.behaviors if b.target != op.target] + [
            Behavior(kind=op.kind, target=op.target, params=params)]
    elif op.op == "label":
        assert c.label is not None
        upd["entities"] = [e.model_copy(update={"label": c.label}) if e.id == op.id else e for e in ents]
    elif op.op == "focus":
        upd["focus"] = list(op.ids)
    return scene.model_copy(update={**upd, "rev": scene.rev + 1})
