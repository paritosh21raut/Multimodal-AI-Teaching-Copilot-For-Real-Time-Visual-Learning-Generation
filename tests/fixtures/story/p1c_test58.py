"""test58 (P1c live, try 3) rebuilt as scene answers: the lines as heard and answers shaped like gpt-oss-20b's (the
compiled shots of the run show the events it gave). Hand-written, not recorded: the live answers were not logged
then (they are now: "[STORY] anim answer")."""
import json


def _a(new=(), events=(), relations=()):
    return json.dumps({"new": list(new), "events": list(events), "relations": list(relations), "end": []})


def _n(i, kind, name, noun, g=""):
    return {"id": i, "kind": kind, "name": name, "noun": noun, "known": "", "gender": g, "posture": "stand"}


def _e(op, actor, target="", obj="", value="", verb=""):
    return {"op": op, "actor": actor, "target": target, "obj": obj, "value": value, "verb": verb}


def _r(a, rel, b):
    return {"a": a, "rel": rel, "b": b}


LINES = [
    ("Let me tell you the story of Ravi.", _a([_n("e1", "person", "Ravi", "Ravi")])),
    ("Ravi was sitting under an apple tree.", _a([_n("e2", "prop", "an apple tree", "tree")],
                                                 [_e("change_posture", "e1", value="sit", verb="sitting")],
                                                 [_r("e1", "under", "e2")])),
    ("An apple fell on his head.", _a([_n("e3", "prop", "An apple", "apple")],
                                      [_e("fall", "e3", "e1", value="head", verb="fell")])),
    ("Ravi picked up the apple and walked to the village.", _a(
        [_n("e4", "place", "the village", "village")],
        [_e("attach", "e1", "e3", value="hold", verb="picked"), _e("move_to", "e1", "e4", verb="walked")],
        [_r("e1", "hold", "e3"), _r("e1", "towards", "e4")])),
    ("There he met his sister, Mina.", _a([_n("e5", "person", "Mina", "sister", "she")],
                                          [_e("none", "e1", "e5", verb="met")])),
    ("Ravi gave the apple to Mina.", _a(events=[_e("give", "e1", "e5", "e3", verb="gave")])),
    ("Mina said, Thank you brother.", _a(events=[_e("speak", "e5", "e1", value="Thank you brother", verb="said")])),
    ("Then Mina threw the apple to Ravi.", _a(events=[_e("throw", "e5", "e1", "e3", verb="threw")])),
    ("Ravi, put the apple in a basket.", _a([_n("e6", "prop", "a basket", "basket")],
                                            [_e("put", "e1", "e6", "e3", value="in", verb="put")])),
    ("Ravi climbed the apple tree.", _a(events=[_e("climb", "e1", "e2", verb="climbed")])),
    ("Then he jumped off the tree.", _a(events=[_e("jump", "e1", "e2", value="off", verb="jumped")])),
    ("An old man rode his horse to the village.", _a(
        [_n("e7", "person", "An old man", "man", "he"), _n("e8", "animal", "his horse", "horse")],
        [_e("attach", "e7", "e8", value="ride", verb="rode"), _e("move_to", "e7", "e4", verb="rode")],
        [_r("e7", "ride", "e8")])),
    ("Mina picked up a stone and pushed a cart.", _a(
        [_n("e9", "prop", "a stone", "stone"), _n("e10", "prop", "a cart", "cart")],
        [_e("attach", "e5", "e9", value="hold", verb="picked"), _e("push", "e5", "e10", value="push", verb="pushed")],
        [_r("e5", "hold", "e9")])),
]
ANSWERS = dict(LINES)
