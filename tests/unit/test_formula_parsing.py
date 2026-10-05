"""Formulas from the model reach the slide (live tests 2026-10-06: energy, resistors, quadratic lost their formulas)."""
import json

from copilot.understanding.gate import BufferedLine
from copilot.understanding.interpreter import _cover_dropped_sentences, parse_interpretation

# exact gpt-oss-120b reply for the energy unit (one probe call, 2026-10-06): the formula is flattened into items
RAW_ENERGY = ('{"topic":"Energy","subtopic":"Kinetic and Potential Energy","relation":"same_concept","acts":['
              '{"act":"formula","lines":[1],"items":{"expression":"KE = ½ m v^2","variables":[{"symbol":"m",'
              '"meaning":"mass"},{"symbol":"v","meaning":"velocity"}]}},{"act":"example","lines":[2],"items":'
              '{"examples":["rolling ball","running person","speeding car"]}},{"act":"formula","lines":[3],"items":'
              '{"expression":"PE = m g h","variables":[{"symbol":"m","meaning":"mass"},{"symbol":"g","meaning":'
              '"gravitational acceleration"},{"symbol":"h","meaning":"height"}]}}],"representation_hint":'
              '"formula, example","summary_delta":"Added formulas.","level_estimate":"Grade 10",'
              '"subject_estimate":"Physics"}')


def reply(items, **act):
    return json.dumps({"topic": "T", "subtopic": "S", "relation": "same_concept",
                       "acts": [{"act": "formula", "lines": [1], "items": items, **act}]})


def test_flattened_formula_from_the_real_reply_is_kept():
    it = parse_interpretation(RAW_ENERGY)
    f1, f2 = it.acts[0].items.formula, it.acts[2].items.formula
    assert f1.expression == "KE = ½ m v^2" and [v.symbol for v in f1.variables] == ["m", "v"]
    assert f2.expression == "PE = m g h" and [v.meaning for v in f2.variables][-1] == "height"


def test_other_formula_shapes():
    assert parse_interpretation(reply({"formula": "C = Q / V"})).acts[0].items.formula.expression == "C = Q / V"
    assert parse_interpretation(reply({"equation": "G = 1/R"})).acts[0].items.formula.expression == "G = 1/R"
    it = parse_interpretation(reply({}, expression="F = m a", variables={"F": "force", "m": "mass"}))
    assert it.acts[0].items.formula.expression == "F = m a"
    assert [(v.symbol, v.meaning) for v in it.acts[0].items.formula.variables] == [("F", "force"), ("m", "mass")]
    it = parse_interpretation(reply({"formula": {"equation": "V = I R", "variables": ["V: voltage", "R = resistance"]}}))
    assert [(v.symbol, v.meaning) for v in it.acts[0].items.formula.variables] == [("V", "voltage"),
                                                                                  ("R", "resistance")]
    assert parse_interpretation(reply({"formula": {"expression": ""}})).acts[0].items.formula is None


def lines(*texts):
    return [BufferedLine(str(i), t, i, i + 1) for i, t in enumerate(texts)]


def test_spoken_maths_covered_by_an_equation_is_not_shown_again():
    """Live kinematics/neutralization tests: the spoken sentence was added as a raw point next to the equations."""
    it = parse_interpretation(json.dumps({"topic": "Kinematics", "subtopic": "Acceleration", "relation": "same_concept",
        "acts": [{"act": "explanation", "lines": [1], "items": {"points": ["v = u + at", "s = ut + ½at²"]}}]}))
    ls = lines("The key kinematic equations are v equals to u plus a t, s equals to u t plus half a t square.")
    assert _cover_dropped_sentences(it, ls, "") == it


def test_live_lines_are_not_shown_twice():
    """Exact lines and model acts of the live tests 2026-10-06 (guard act removed): nothing is added again."""
    energy = parse_interpretation(RAW_ENERGY)
    ls = lines("Kinetic energy equals half mv square, where m is mass and v is the velocity.",
               "Examples are a rolling ball, a running person or a speeding car.",
               "Potential energy equals mgh that is mass times gravitation times height.")
    assert _cover_dropped_sentences(energy, ls, "") == energy
    neutral = parse_interpretation(json.dumps({"topic": "Chemistry", "subtopic": "Neutralization Reaction",
        "relation": "elaboration", "acts": [{"act": "explanation", "lines": [1, 2], "items": {"points": [
            "Acid provides H⁺ ions", "Base provides OH⁻ ions", "H⁺ + OH⁻ → H₂O", "Acid and base neutralize each other"]}}]}))
    ls = lines("So what's happening? The acid provide H plus ions while the base provides OH negative ions. They "
               "combine H plus plus O minus gives H2O. So the acid and base neutralizes each other.",
               "In one line, acid plus base gives salt plus water equals neutralization reaction.")
    assert _cover_dropped_sentences(neutral, ls, "") == neutral


def test_a_real_left_out_sentence_is_still_shown():
    it = parse_interpretation(json.dumps({"topic": "Matter", "subtopic": "Particles", "relation": "same_concept",
        "acts": [{"act": "explanation", "lines": [1], "items": {"points": ["v = u + at"]}}]}))
    ls = lines("The matter particles attract each other and are in the state of continuous motion.")
    out = _cover_dropped_sentences(it, ls, "")
    assert len(out.acts) == 2 and "continuous motion" in out.acts[1].items.points[0]
