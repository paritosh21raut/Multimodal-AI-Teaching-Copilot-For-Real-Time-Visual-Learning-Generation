"""Prompt budget, JSON parsing/normalisation, repair and deterministic fallback."""
import json

import httpx
import pytest

from copilot.core.state import LectureSetup, LectureState, TopicNode
from copilot.core.textutil import approx_tokens
from copilot.llm.providers import OpenAICompatProvider, ProviderConfig
from copilot.llm.ratelimit import RateLimiter
from copilot.llm.router import Entry, LLMRouter, RouterSettings
from copilot.understanding.gate import BufferedLine
from copilot.understanding.interpreter import (
    InvalidInterpretation,
    Interpreter,
    InterpreterSettings,
    parse_interpretation,
)
from copilot.understanding.prompt import SYSTEM_PROMPT, PromptBudgetError, build_prompt

VALID = {
    "topic": "Photosynthesis", "subtopic": "Process", "relation": "sibling_concept",
    "acts": [{"act": "process", "lines": [1, 2, 9], "items": {"steps": ["light absorbed", "water split"]}}],
    "representation_hint": "process_flow", "meta_lines": [], "summary_delta": "Steps of photosynthesis.",
    "concerns": [
        {"claim": "x", "issue": "wrong", "confidence": 0.9, "lines": [2]},
        {"claim": "y", "issue": "maybe", "confidence": 0.3, "lines": [1]},
    ],
}


def state(**kw):
    t = TopicNode(title="Photosynthesis", subtopics=[TopicNode(title="Definition")])
    s = LectureState(session_id="t", setup=LectureSetup(subject="Biology", grade_level="7"), outline=[t],
                     current_topic_id=t.id, current_subtopic_id=t.subtopics[0].id, **kw)
    return s


LINES = [BufferedLine("a", "First the leaf absorbs sunlight.", 0, 2),
         BufferedLine("b", "Then water is split.", 2, 4, maybe_meta=True)]


def test_prompt_contains_bounded_context_only():
    p = build_prompt(state(rolling_summary="Plants make food."), LINES, dynamic_budget=1200, total_budget=2600)
    user = p.messages[1]["content"]
    assert "CURRENT: topic=Photosynthesis; subtopic=Definition" in user
    assert "[1] First the leaf absorbs sunlight." in user and "[2] (maybe-meta) Then water is split." in user
    assert "RECENT SUMMARY: Plants make food." in user and "grade=7" in user
    assert p.tokens == approx_tokens(user) + approx_tokens(SYSTEM_PROMPT) <= 2600


def test_prompt_trims_outline_and_summary_to_budget():
    s = state(rolling_summary="word " * 400)
    for i in range(20):
        s.outline.append(TopicNode(title=f"Topic number {i} with a long title", last_seen=i,
                                   subtopics=[TopicNode(title=f"Sub {j} of {i}") for j in range(8)]))
    p = build_prompt(s, LINES, dynamic_budget=1200, total_budget=2600)
    user = p.messages[1]["content"]
    assert p.dynamic_tokens <= 1200
    outline = user.split("OUTLINE (topic: subtopics):\n")[1].split("\nCURRENT:")[0]
    assert approx_tokens(outline) <= 150 and outline.startswith("- Photosynthesis")  # current topic first
    summary = user.split("RECENT SUMMARY: ")[1].split("\nNEW LINES:")[0]
    assert approx_tokens(summary) <= 120


def test_prompt_over_budget_raises():
    big = [BufferedLine("x", "word " * 2000, 0, 60)]
    with pytest.raises(PromptBudgetError):
        build_prompt(state(), big, dynamic_budget=1200, total_budget=2600)


def test_parse_tolerates_fences_case_and_shapes():
    raw = dict(VALID, relation="Sibling Concept", representation_hint="flowchart")
    raw["acts"] = [{"act": "Comparison", "lines": [1], "items": {
        "compare": "photosynthesis vs respiration",
        "pairs": [["light", "needs sunlight", "all the time"]],
        "points": "single point"}}, {"act": "musing", "lines": []}]
    it = parse_interpretation("```json\n" + json.dumps(raw) + "\n```")
    assert it.relation == "sibling_concept" and it.representation_hint == "none"
    items = it.acts[0].items
    assert items.compare == ["photosynthesis", "respiration"]
    assert items.pairs[0].aspect == "light" and items.pairs[0].right == "all the time"
    assert items.points == ["single point"] and it.acts[1].act == "other"


@pytest.mark.parametrize("bad", ["no json here", '{"topic": "x"', '{"topic": "", "relation": "same_concept"}',
                                 '{"topic": "x", "relation": "teleport"}'])
def test_parse_rejects_invalid(bad):
    with pytest.raises(InvalidInterpretation):
        parse_interpretation(bad)


def router_with(responses, seen=None):
    """A real router whose HTTP layer returns the given contents in order."""
    queue = list(responses)

    def handler(req):
        if seen is not None:
            seen.append(json.loads(req.content)["messages"])
        content = queue.pop(0)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    entry = Entry(OpenAICompatProvider(ProviderConfig(name="p", base_url="https://p.test/v1", model="m"), "k", client),
                  RateLimiter(100, 100000))
    return LLMRouter([entry], RouterSettings(timeout_s=2.0, retries=0))


async def test_valid_output_is_sanitised():
    res = await Interpreter(router_with([json.dumps(VALID)])).interpret(state(), LINES)
    assert not res.fallback and res.provider == "p" and res.prompt_tokens > 0
    assert res.interpretation.acts[0].lines == [1, 2]            # line 9 does not exist
    assert [c.claim for c in res.interpretation.concerns] == ["x"]  # 0.3 < min confidence


async def test_one_repair_then_success():
    seen = []
    res = await Interpreter(router_with(["not json", json.dumps(VALID)], seen)).interpret(state(), LINES)
    assert not res.fallback and res.repaired
    assert seen[1][-2] == {"role": "assistant", "content": "not json"}
    assert "invalid" in seen[1][-1]["content"]


async def test_invalid_twice_falls_back_deterministically():
    res = await Interpreter(router_with(["nope", "still nope"])).interpret(state(), LINES)
    assert res.fallback and "after repair" in res.fallback_reason
    it = res.interpretation
    assert it.topic == "Photosynthesis" and it.subtopic == "Definition" and it.relation == "same_concept"
    assert it.acts[0].items.points == ["First the leaf absorbs sunlight"]  # maybe-meta line not displayed; tidied


async def test_no_router_and_provider_failure_fall_back():
    res = await Interpreter(None).interpret(state(), LINES)
    assert res.fallback and "no LLM" in res.fallback_reason

    def handler(req):
        return httpx.Response(500, text="down")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    entry = Entry(OpenAICompatProvider(ProviderConfig(name="p", base_url="https://p.test/v1", model="m"), "k", client),
                  RateLimiter(100, 100000))
    res = await Interpreter(LLMRouter([entry], RouterSettings(timeout_s=1.0)), InterpreterSettings()).interpret(
        LectureState(session_id="t", setup=LectureSetup(expected_topic="Cells")), LINES)
    assert res.fallback and res.fallback_reason.startswith("llm:")
    assert res.interpretation.topic == "Cells" and res.interpretation.relation == "new_topic"


async def test_sibling_with_unchanged_subtopic_becomes_same_concept():
    raw = dict(VALID, subtopic="Definition", relation="sibling_concept")
    res = await Interpreter(router_with([json.dumps(raw)])).interpret(state(), LINES)
    assert res.interpretation.relation == "same_concept"
    raw = dict(VALID, subtopic="Requirements", relation="sibling_concept")
    res = await Interpreter(router_with([json.dumps(raw)])).interpret(state(), LINES)
    assert res.interpretation.relation == "sibling_concept"


@pytest.mark.parametrize("hint", [["key_points"], {"x": 1}, 3])
def test_non_string_hint_is_normalised_not_crashing(hint):
    assert parse_interpretation(json.dumps(dict(VALID, representation_hint=hint))).representation_hint == "none"


def test_odd_shapes_become_invalid_interpretation():
    with pytest.raises(InvalidInterpretation):
        parse_interpretation(json.dumps(dict(VALID, acts=[{"act": "process", "items": {"pairs": 5, "steps": 7}}])))


async def test_repair_prompt_stays_within_budget():
    seen = []
    huge_invalid = "{" + "x" * 20000
    settings = InterpreterSettings(prompt_budget_tokens=2600)
    res = await Interpreter(router_with([huge_invalid, json.dumps(VALID)], seen), settings).interpret(state(), LINES)
    assert res.repaired
    repair = seen[1]
    assert sum(approx_tokens(m["content"]) for m in repair) <= 2600



def test_announced_subject_is_tagged_for_the_model():
    from copilot.understanding.prompt import announced_subject
    assert announced_subject("Now let's talk about galaxies.") == "galaxies"
    assert announced_subject("Let's learn about atoms and molecules.") == "atoms and molecules"
    assert announced_subject("Now, the next topic is respiration in plants, which is different") == "respiration in plants"
    assert announced_subject("Now let's see how the process actually happens step by step.") == "process actually happens step by step"
    assert announced_subject("Plants make food using light.") == ""



def test_fallback_shows_only_complete_sentences():
    from copilot.understanding.interpreter import fallback_interpretation
    lines = [BufferedLine("a", "also called natural satellites which are the moons which revolve around the planet.", 0, 1),
             BufferedLine("b", "diatomic triatomic or catastrophic", 1, 2),
             BufferedLine("c", "So Our universe has billions of galaxies. Why is it so?", 2, 3)]
    it = fallback_interpretation(LectureState(session_id="s"), lines)
    assert it.acts[0].items.points == ["Our universe has billions of galaxies"]



def test_fallback_recognises_definitions_and_announced_subtopics():
    from copilot.core.state import TopicNode
    from copilot.understanding.interpreter import fallback_interpretation
    t = TopicNode(title="Chemistry")
    st = LectureState(session_id="s", outline=[t], current_topic_id=t.id)
    lines = [BufferedLine("a", "Let's learn about atoms and molecules. Atoms are the smallest particles of an element "
                               "which can take part in a chemical reaction.", 0, 9)]
    it = fallback_interpretation(st, lines)
    assert it.subtopic == "Atoms and Molecules" and it.relation == "sibling_concept"
    d = it.acts[0]
    assert d.act == "definition" and d.items.term == "Atoms"
    assert d.items.definition.startswith("the smallest particles of an element")
    assert all("learn about" not in p for a in it.acts for p in a.items.points)


def test_fallback_names_the_topic_when_the_lecture_opens_with_an_announcement():
    """Verify lecture 20261005-110717-dc56: every LLM rate-limited, the deck was titled 'Lecture' although the
    teacher opened with 'Let us learn about states of matter'."""
    from copilot.understanding.interpreter import fallback_interpretation
    lines = [BufferedLine("a", "Let us learn about states of matter. There are five states of matter. Solid, liquid, "
                               "gas, plasma and Bose-Einstein condensate.", 0, 9)]
    it = fallback_interpretation(LectureState(session_id="s"), lines)
    assert it.topic == "States of Matter" and it.relation == "new_topic" and it.subtopic == ""
