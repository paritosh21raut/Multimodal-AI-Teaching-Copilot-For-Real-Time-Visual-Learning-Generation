"""Grounding guard: silent corrections of spoken formulas are always reported to the teacher (M3 live fix b).

Truthful slides (M4 verify fixes): the slide keeps the corrected form; the guard only makes sure a concern says
what was actually heard (wrong) and what the slide shows (right)."""
import json

import httpx

from copilot.core.interpretation import ConcernItem, ContentItems, DiscourseAct, Formula, Interpretation, Variable
from copilot.core.state import LectureState
from copilot.llm.providers import OpenAICompatProvider, ProviderConfig
from copilot.llm.ratelimit import RateLimiter
from copilot.llm.router import Entry, LLMRouter, RouterSettings
from copilot.understanding.gate import BufferedLine
from copilot.understanding.grounding import enforce_grounding
from copilot.understanding.interpreter import Interpreter

SAID = "The chemical equation is 6CO2 plus 6H2 plus light gives us C6H12O6 plus 6O2."


def formula_it(expr, variables=(), concerns=()):
    return Interpretation(topic="Photosynthesis", relation="same_concept", acts=[DiscourseAct(
        act="formula", lines=[1], items=ContentItems(formula=Formula(
            expression=expr, variables=[Variable(symbol=s, meaning=m) for s, m in variables])))],
        concerns=list(concerns))


def test_silent_formula_correction_is_reported_not_hidden():
    it = formula_it("6CO2 + 6H2O + light → C6H12O6 + 6O2",
                    [("CO2", "carbon dioxide"), ("H2O", "water"), ("C6H12O6", "glucose")])
    out, changes = enforce_grounding(it, [SAID])
    assert out.acts == it.acts                                       # the correct form stays on the slide
    assert "6H2->6H2O" in changes
    assert len(out.concerns) == 1
    c = out.concerns[0]
    assert c.kind == "transcription" and (c.wrong, c.right) == ("6H2", "6H2O") and c.claim == "6H2"
    assert c.lines == [1] and 0.3 <= c.confidence < 0.6


def test_grounded_formula_and_spoken_word_conversions_are_untouched():
    it = formula_it("6CO2 + 6H2 + light → C6H12O6 + 6O2")
    out, reverted = enforce_grounding(it, [SAID])
    assert out == it and reverted == []
    # "carbon dioxide plus water" written as symbols: nothing close was spoken, so nothing to revert
    words = "carbon dioxide plus water, in the presence of sunlight, gives glucose plus oxygen."
    it2 = formula_it("CO2 + H2O → C6H12O6 + O2")
    assert enforce_grounding(it2, [words]) == (it2, [])


def test_spoken_coefficients_and_subscripts_count_as_said():
    it = formula_it("6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂")
    out, reverted = enforce_grounding(it, ["six CO2 plus 6 H2O gives C6H12O6 plus six O2"])
    assert reverted == [] and out.concerns == []


def test_existing_model_concern_is_not_duplicated():
    model_concern = ConcernItem(claim="6H2", issue="water is H2O", suggested_correction="6H2O", confidence=0.4,
                                lines=[1], kind="transcription")
    it = formula_it("6CO2 + 6H2O + light → C6H12O6 + 6O2", concerns=[model_concern])
    out, _ = enforce_grounding(it, [SAID])
    assert out.concerns == [model_concern]
    assert "6H2O" in out.acts[0].items.formula.expression


def test_points_are_grounded_too():
    it = Interpretation(topic="T", relation="same_concept", acts=[DiscourseAct(
        act="explanation", lines=[1], items=ContentItems(points=["Plants make C6H12O6 from CO2"]))])
    out, changes = enforce_grounding(it, ["Plants make C6H12O from CO2."])
    assert out.acts[0].items.points == ["Plants make C6H12O6 from CO2"] and changes == ["C6H12O->C6H12O6"]
    assert (out.concerns[0].wrong, out.concerns[0].right) == ("C6H12O", "C6H12O6")
    # a 2-character token with one changed character is too ambiguous to call a correction (O2 vs O3)
    it2 = Interpretation(topic="T", relation="same_concept", acts=[DiscourseAct(
        act="explanation", lines=[1], items=ContentItems(points=["Ozone is O3"]))])
    assert enforce_grounding(it2, ["Ozone is O2."]) == (it2, [])


def test_a_different_molecule_is_never_taken_for_a_mishearing():
    it = Interpretation(topic="T", relation="same_concept", acts=[DiscourseAct(
        act="explanation", lines=[1], items=ContentItems(points=["Plants release O2"]))])
    out, reverted = enforce_grounding(it, ["Plants take in CO2 and release oxygen."])
    assert out == it and reverted == []                  # O2 is not a mis-heard CO2


def _router(content: str) -> LLMRouter:
    def handler(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 10}})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    prov = OpenAICompatProvider(ProviderConfig(name="m", base_url="https://p.test/v1", model="m"), "k", client)
    return LLMRouter([Entry(prov, RateLimiter(100, 100000))], RouterSettings(timeout_s=2.0, retries=0))


async def test_interpreter_keeps_low_confidence_transcription_concern_and_grounds_output():
    out = {"topic": "Photosynthesis", "subtopic": "Process", "relation": "same_concept",
           "acts": [{"act": "formula", "lines": [1], "items": {"formula": {
               "expression": "6CO2 + 6H2O + light -> C6H12O6 + 6O2", "variables": []}}}],
           "concerns": [{"claim": "x", "issue": "y", "confidence": 0.35, "lines": [1], "kind": "factual"}],
           "representation_hint": "formula"}
    interp = Interpreter(_router(json.dumps(out)))
    res = await interp.interpret(LectureState(session_id="s"), [BufferedLine("a", SAID, 0, 10)])
    assert not res.fallback
    assert res.interpretation.acts[0].items.formula.expression.startswith("6CO2 + 6H2O +")
    kinds = [(c.kind, c.wrong, c.right) for c in res.interpretation.concerns]
    assert kinds == [("transcription", "6H2", "6H2O")]   # low-confidence factual dropped, transcription kept


def test_review7_a_different_molecule_named_in_words_is_not_reverted():
    for line, point in [("Water is H2O. Hydrogen peroxide is different.", "Hydrogen peroxide is H2O2"),
                        ("Sulfuric acid is H2SO4 and sulfurous acid is weaker.", "Sulfurous acid H2SO3 is weaker")]:
        it = Interpretation(topic="T", relation="same_concept", acts=[DiscourseAct(
            act="explanation", lines=[1], items=ContentItems(points=[point]))])
        assert enforce_grounding(it, [line]) == (it, []), line


def test_minimal_change_and_revision_filtering():
    from copilot.core.interpretation import Revision
    from copilot.understanding.interpreter import _sanitise, minimal_change
    assert minimal_change("Neptune is the coldest planet", "Uranus is the coldest planet") == ("Neptune", "Uranus")
    assert minimal_change("Plants take in oxygen.", "Plants take in carbon dioxide.") == ("oxygen", "carbon dioxide")
    st = LectureState(session_id="s", slide_refs={"S1": "a/b"})
    it = Interpretation(topic="T", relation="same_concept", revisions=[Revision(ref="s1", text="x"),
                                                                       Revision(ref="S9", text="y")],
                        concerns=[ConcernItem(claim="Neptune is the coldest", issue="i", confidence=0.9,
                                              suggested_correction="Uranus is the coldest")])
    out = _sanitise(it, 3, 0.6, st)
    assert [r.ref for r in out.revisions] == ["S1"]                  # unknown refs dropped, case normalised
    assert (out.concerns[0].wrong, out.concerns[0].right) == ("Neptune", "Uranus")
