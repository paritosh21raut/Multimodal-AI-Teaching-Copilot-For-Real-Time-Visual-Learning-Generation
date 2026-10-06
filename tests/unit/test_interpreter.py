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


# ---- live multi-topic test 2026-10-06 (session 20261006-112149-411e): fallback units ---------------------------
def _atoms_state():
    from copilot.core.state import TopicNode
    t = TopicNode(title="Atoms", subtopics=[TopicNode(title="Definition")])
    return LectureState(session_id="s", outline=[t], current_topic_id=t.id, current_subtopic_id=t.subtopics[0].id,
                        slide_context="Atom: basic building block of matter; nucleus holds protons and neutrons")


def _lines(*texts):
    return [BufferedLine(str(i), t, i, i + 1) for i, t in enumerate(texts)]


def test_fallback_ignores_a_misheard_announcement_the_unit_does_not_talk_about():
    """"Let's learn about matter" heard as "MATLAB": the fallback made a slide titled MATLAB."""
    from copilot.understanding.interpreter import fallback_interpretation
    it = fallback_interpretation(_atoms_state(), _lines("Let's learn about MATLAB."))
    assert it.subtopic == "Definition" and it.relation == "same_concept" and not it.acts
    it = fallback_interpretation(_atoms_state(), _lines(
        "Let's learn about MATLAB.", "Anything which occupies some space and has some mass is called matter."))
    assert it.subtopic == "Definition"
    # ... while an announcement the unit goes on to explain still names the subtopic
    it = fallback_interpretation(_atoms_state(), _lines(
        "Let's learn about isotopes. Isotopes are the atoms of one element with different numbers of neutrons."))
    assert it.subtopic == "Isotopes" and it.acts[0].items.term == "Isotopes"


def test_fallback_reads_is_called_as_a_definition():
    from copilot.understanding.interpreter import fallback_interpretation
    it = fallback_interpretation(_atoms_state(), _lines(
        "Anything which occupies some space and has some mass is called matter. It is made up of small particles "
        "which have space between them."))
    d = it.acts[0]
    assert d.act == "definition" and d.items.term == "Matter"
    assert d.items.definition == "Anything which occupies some space and has some mass"
    assert it.acts[1].items.points == ["It is made up of small particles which have space between them"]


def test_fallback_leaves_out_thanks_asides_and_first_person_remarks():
    """The MATLAB slide showed "Thank you very much" and "It's a waste of time"; another unit made a definition of
    "I think Blackboard"."""
    from copilot.understanding.interpreter import fallback_interpretation
    for texts in (["Thank you very much."], ["No, it's not. It's a waste of time."],
                  ["I think Blackboard is a good idea. I think it's a good idea to make 3 months a year."]):
        assert fallback_interpretation(_atoms_state(), _lines(*texts)).acts == [], texts
    # a short sentence about the lecture's subject stays
    it = fallback_interpretation(_atoms_state(), _lines("Neutrons have no charge."))
    assert it.acts[0].items.points == ["Neutrons have no charge"]


def test_fallback_keeps_a_sentence_after_a_fragment_and_joins_split_sentences():
    """"the basic concepts of chemistry. Chemistry is the branch of science ..." was dropped whole because the line
    started with a lower-case fragment."""
    from copilot.understanding.interpreter import fallback_interpretation
    it = fallback_interpretation(_atoms_state(), _lines(
        "the basic concepts of chemistry. Chemistry is the branch of science which deals with the composition "
        "structure and properties of matter.", "branch of chemistry"))
    assert it.acts[0].items.term == "Chemistry"
    assert it.acts[0].items.definition.startswith("the branch of science which deals with")
    it = fallback_interpretation(_atoms_state(), _lines(
        "Electrons are tiny negatively charged particles that", "move around the nucleus in an electron cloud."))
    assert it.acts[0].items.points == ["Electrons are tiny negatively charged particles that move around the nucleus "
                                       "in an electron cloud"]


# ---- live chemistry test 2026-10-05 (sessions 20261005-230039-f084 / -231113-abfe) ----------------------------
MATTER_LINE = ("Anything which occupies some space and has some mass is called matter. It is only up to the small "
               "particles which have space between them. The matter particles attract each other and are in the "
               "state of continuous motion.")


def test_relation_given_as_an_act_name_is_accepted_without_repair():
    data = dict(VALID, relation="transition")
    assert parse_interpretation(json.dumps(data)).relation == "same_concept"
    with pytest.raises(InvalidInterpretation):  # anything else stays invalid
        parse_interpretation(json.dumps(dict(VALID, relation="banana")))


def test_sentence_the_model_left_out_is_shown_as_said():
    from copilot.understanding.interpreter import _cover_dropped_sentences

    it = parse_interpretation(json.dumps({
        "topic": "Chemistry", "subtopic": "Matter", "relation": "sibling_concept", "acts": [
            {"act": "definition", "lines": [1], "items": {"term": "Matter",
                                                          "definition": "Anything which occupies some space and has some mass"}},
            {"act": "explanation", "lines": [2], "items": {"points": ["Matter can be classified"]}}]}))
    lines = [BufferedLine("a", MATTER_LINE, 0, 14), BufferedLine("b", "Classification of matter", 14, 16)]
    out = _cover_dropped_sentences(it, lines, "")
    added = out.acts[-1]
    assert len(out.acts) == 3 and added.act == "explanation" and added.lines == [1]
    # the mis-heard fragment ("It is only up to ...") has too little content to show; the definition is covered
    assert added.items.points == ["The matter particles attract each other and are in the state of continuous motion"]


def test_covered_or_digression_or_meta_sentences_are_not_added():
    from copilot.understanding.interpreter import _cover_dropped_sentences

    covered = parse_interpretation(json.dumps({
        "topic": "Chemistry", "subtopic": "Matter", "relation": "same_concept", "acts": [
            {"act": "explanation", "lines": [1], "items": {"points": ["Matter particles attract each other",
                                                                      "Particles are in continuous motion"]}}]}))
    line = [BufferedLine("a", "The matter particles attract each other and are in the state of continuous motion.", 0, 5)]
    assert _cover_dropped_sentences(covered, line, "") == covered
    empty = covered.model_copy(update={"acts": []})
    assert _cover_dropped_sentences(empty, line, "Matter: [S1] Matter particles attract each other; "
                                                 "[S2] they are in continuous motion state") == empty  # already shown
    assert _cover_dropped_sentences(empty.model_copy(update={"relation": "digression"}), line, "").acts == []
    assert _cover_dropped_sentences(empty.model_copy(update={"meta_lines": [1]}), line, "").acts == []
    meta = [BufferedLine("a", line[0].text, 0, 5, maybe_meta=True)]
    assert _cover_dropped_sentences(empty, meta, "").acts == []


def test_paraphrased_or_split_sentences_are_not_shown_twice():
    """Live test 2026-10-06: the Benefits and Microcontroller slides showed the same statement twice: once from the
    model, once 'as said' by the guard (word forms differed; Whisper ended the sentence early)."""
    from copilot.understanding.interpreter import _cover_dropped_sentences

    benefits = parse_interpretation(json.dumps({
        "topic": "Computer Networks", "subtopic": "Benefits", "relation": "sibling_concept", "acts": [
            {"act": "explanation", "lines": [1, 2, 3], "items": {"points": [
                "Resource sharing lowers hardware costs", "Enables fast data and communication",
                "Provides scalable cloud access"]}}]}))
    lines = _lines("Resource sharing allows multiple users to share hardware like printers or storage devices to "
                   "lower cost.", "Data and communication enables fast files exchange web browsing emails and video "
                   "calls", "Cloud access provides scalable access to remote services applications and remote services.")
    assert _cover_dropped_sentences(benefits, lines, "") == benefits

    mcu = parse_interpretation(json.dumps({
        "topic": "Microcontroller", "subtopic": "Introduction", "relation": "new_topic", "acts": [
            {"act": "definition", "lines": [1, 2, 3], "items": {"term": "Microcontroller (MCU)", "definition":
                "Small computer on a single integrated circuit controlling specific electronic tasks"}},
            {"act": "explanation", "lines": [1, 2, 3], "items": {"points": [
                "Combines CPU, memory, and input-output interfaces", "All components located on a single chip"]}}]}))
    lines = _lines("A microcontroller or MCU is a small computer on a single integrated circuit that is designed to "
                   "control specific tasks with electronic systems. It combines the functions of Central Processing "
                   "Unit CPU.", "memory and input-output interfaces.", "All on a single chip")
    assert _cover_dropped_sentences(mcu, lines, "") == mcu


@pytest.mark.parametrize("said", [
    "Today we are going to learn about the systems of the human body.",
    "Let me quickly recap what we learned today about digestion.",
    "When I was in college, I ran a race and my heart was beating fast.",
])
def test_announcements_and_anecdotes_are_not_recovered(said):
    """Offline replay of 128 recorded units: these were the guard's false positives before the exclusions."""
    from copilot.understanding.interpreter import _cover_dropped_sentences

    it = parse_interpretation(json.dumps({"topic": "Human Body", "subtopic": "Heart", "relation": "same_concept",
                                          "acts": []}))
    assert _cover_dropped_sentences(it, [BufferedLine("a", said, 0, 5)], "").acts == []


def test_line_used_only_for_a_transition_is_not_recovered():
    from copilot.understanding.interpreter import _cover_dropped_sentences

    it = parse_interpretation(json.dumps({"topic": "Chemistry", "subtopic": "Matter", "relation": "same_concept",
                                          "acts": [{"act": "transition", "lines": [1]}]}))
    line = [BufferedLine("a", "After this the classification of different matter types comes next in sequence.", 0, 5)]
    assert _cover_dropped_sentences(it, line, "").acts == it.acts
