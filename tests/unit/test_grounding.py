"""Grounding guard: silent corrections of spoken formulas are reverted and raised as concerns (M3 live fix b)."""
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


def test_silent_formula_correction_is_reverted_and_raised():
    it = formula_it("6CO2 + 6H2O + light → C6H12O6 + 6O2",
                    [("CO2", "carbon dioxide"), ("H2O", "water"), ("C6H12O6", "glucose")])
    out, reverted = enforce_grounding(it, [SAID])
    f = out.acts[0].items.formula
    assert f.expression == "6CO2 + 6H2 + light → C6H12O6 + 6O2"     # kept as said
    assert [v.symbol for v in f.variables] == ["CO2", "H2", "C6H12O6"]   # derived symbol follows the spoken form
    assert "6H2O->6H2" in reverted
    assert len(out.concerns) == 1
    c = out.concerns[0]
    assert c.kind == "transcription" and c.suggested_correction == "6H2O" and "6H2" in c.claim
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
    assert "6H2 " in out.acts[0].items.formula.expression


def test_points_are_grounded_too():
    it = Interpretation(topic="T", relation="same_concept", acts=[DiscourseAct(
        act="explanation", lines=[1], items=ContentItems(points=["Plants make C6H12O6 from CO2"]))])
    out, reverted = enforce_grounding(it, ["Plants make C6H12O from CO2."])
    assert out.acts[0].items.points == ["Plants make C6H12O from CO2"] and reverted == ["C6H12O6->C6H12O"]
    assert out.concerns[0].suggested_correction == "C6H12O6"
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
    assert res.interpretation.acts[0].items.formula.expression.startswith("6CO2 + 6H2 +")
    kinds = [(c.kind, c.suggested_correction) for c in res.interpretation.concerns]
    assert kinds == [("transcription", "6H2O")]          # low-confidence factual dropped, transcription kept


def test_review7_a_different_molecule_named_in_words_is_not_reverted():
    for line, point in [("Water is H2O. Hydrogen peroxide is different.", "Hydrogen peroxide is H2O2"),
                        ("Sulfuric acid is H2SO4 and sulfurous acid is weaker.", "Sulfurous acid H2SO3 is weaker")]:
        it = Interpretation(topic="T", relation="same_concept", acts=[DiscourseAct(
            act="explanation", lines=[1], items=ContentItems(points=[point]))])
        assert enforce_grounding(it, [line]) == (it, []), line


def test_review8_accepting_the_transcription_fix_also_fixes_derived_symbols():
    from copilot.presentation.content import FormulaData, Piece
    from copilot.presentation.holds import ConcernInfo, resolve
    p = Piece("formula", formula=FormulaData("6CO2 + 6H2 + light -> C6H12O6 + 6O2", (("H2", "water"),)))
    out = resolve(p, ConcernInfo("c", "transcription", "6H2", "6H2O"), "accepted")
    assert out.formula.expression == "6CO2 + 6H2O + light -> C6H12O6 + 6O2"
    assert out.formula.variables == (("H2O", "water"),)
