"""F-013 S2: lecture structure - numbered sections, a narrower kind of a subtopic as its child, the members of an
announced set under the set, content filed under the set staying on a member only when it names the member, and an
earlier subtopic title not reused for new content. Cases from the annotated tests (test20, test21, test30)."""
from __future__ import annotations

from copilot.core.events import ConceptSignal, Lifecycle, LifecycleChanged
from copilot.core.interpretation import Interpretation
from copilot.core.memory import is_child_facet, same_subject, same_title, short_name
from copilot.presentation.planner import Frame, Signal, Working, decide
from copilot.understanding.cues import detect, detect_all, section
from copilot.understanding.interpreter import _revisit_name
from copilot.understanding.prompt import SYSTEM_PROMPT, build_prompt, outline_lines, system_prompt
from tests.unit.test_presentation_engine import act, make, ready, send, texts

FR = "French Revolution"
SOLAR = "Solar System"


def sig(seg, **kw):
    return ConceptSignal(segment_id=seg, shift_score=0.0, boundary=bool(kw.get("announce")), **kw)


def with_(ev, **fields):
    return ev.model_copy(update={"interpretation": ev.interpretation.model_copy(update=fields)})


def slides(deck):
    return [(s.title, s.parent, texts(s)) for s in deck.slides if s.layout != "title"]


async def _opened(topic, sub, first):
    bus, store, deck, eng, clock = await make()
    await send(bus, LifecycleChanged(state=Lifecycle.LIVE), sig("a1"), sig("a2"))
    await send(bus, ready(topic, sub, [first], relation="new_topic", segs=["a1", "a2"]))
    clock.t += 60  # past the dwell time
    return bus, store, deck, clock


# ---- title helpers -----------------------------------------------------------------------------------------------

def test_a_qualified_kind_is_a_child_but_a_facet_or_the_full_set_name_is_not():
    assert is_child_facet("Intellectual Causes", "Causes")
    assert is_child_facet("Inner Planets", "Planets")
    assert not is_child_facet("Respiration in Plants", "Respiration")  # a facet of respiration
    assert not is_child_facet("Types of Bonds", "Bonds")               # the same set named in full
    assert not is_child_facet("Causes and Effects", "Effects")
    assert not is_child_facet("Causes", "Causes")


def test_same_title_has_no_one_extra_word_leniency_for_children():
    assert same_title("Requirements", "Requirement")
    assert not same_title("Intellectual Causes", "Causes")
    assert not same_title("Causes of French Revolution", FR)


def test_short_name_and_same_subject_drop_the_topic():
    assert short_name("Causes of French Revolution", FR) == "Causes"
    assert short_name("French Revolution Stages", FR) == "Stages"
    assert short_name(FR, FR) == FR
    assert same_subject("Causes of French Revolution", "Causes", FR)
    assert not same_subject("Social", "Causes", FR)


# ---- numbered sections (cues) ------------------------------------------------------------------------------------

def test_a_numbered_heading_taken_up_by_the_next_sentence_is_a_section():
    assert section("1. Social. The social conditions in France were unequal.") == "Social"
    assert section("2. Opportunity Cost. Opportunity cost is the next best alternative.") == "Opportunity Cost"
    assert section("3. Mixed Economy") == "Mixed Economy"
    cue = detect_all("1. Social. The social conditions in France were unequal.").cues[0]
    assert (cue.kind, cue.name, cue.rule) == ("topic", "Social", "section")


def test_a_numbered_step_said_as_a_sentence_or_a_fragment_is_no_section():
    assert section("1. The user enters a domain name.") == ""
    assert section("Type 2.") == ""  # test10: a fragment
    assert section("Stage 2, the meeting of the estates general began in May.") == "Stage 2"


def test_an_ordinal_topic_is_one_of_a_series():
    cue = detect("The 7th topic is Jupiter").cues[0]
    assert (cue.name, cue.rule) == ("Jupiter", "ordinal")


# ---- planner -----------------------------------------------------------------------------------------------------

def _it(sub, points, summary=""):
    return Interpretation(topic=SOLAR, subtopic=sub, relation="same_concept", summary_delta=summary,
                          acts=[act("explanation", points=points)])


def test_content_the_model_files_under_the_set_stays_on_the_member_only_when_it_names_it():
    venus = Working(Frame(SOLAR, "Venus", parent="Planets"), has_content=True)
    sig0 = [Signal(0.0, False)]
    on = decide(venus, _it("Planets", ["Venus is the hottest planet"]), sig0, None, has_pieces=True)
    assert on.op == "update" and on.frame.facet == "Venus"
    by_summary = decide(venus, _it("Planets", ["Surface: 465 C"], "Venus is very hot."), sig0, None, has_pieces=True)
    assert by_summary.op == "update" and by_summary.frame.facet == "Venus"
    off = decide(venus, _it("Planets", ["Planets orbit the Sun"]), sig0, None, has_pieces=True)
    assert off.frame.facet == "Planets"


def test_a_narrower_kind_of_the_facet_continues_as_its_child():
    causes = Working(Frame(FR, "Causes"), has_content=True)
    it = Interpretation(topic=FR, subtopic="Intellectual Causes", relation="sub_concept",
                        acts=[act("explanation", points=["Thinkers rejected divine right"])])
    d = decide(causes, it, [Signal(0.0, False)], None, has_pieces=True)
    assert d.op == "continue" and d.frame == Frame(FR, "Intellectual Causes", parent="Causes")


def test_a_child_frame_is_not_its_parent():
    assert not Frame(FR, "Sexual Reproduction", "Reproduction").same(Frame(FR, "Reproduction"))
    assert Frame(FR, "Social", "Causes").same(Frame(FR, "Social", "Causes"))


# ---- engine ------------------------------------------------------------------------------------------------------

async def test_numbered_sections_after_a_subtopic_become_its_children():
    """test20: "Causes" then "1. Social. ...", "2. Economic. ..." while the model still says "Causes"."""
    bus, store, deck, clock = await _opened(FR, "Causes", act("explanation", points=["There were several causes"]))
    await send(bus, sig("b1", announce="Social", announce_rule="section"), sig("b2"))
    await send(bus, ready(FR, "Causes", [act("explanation", points=["Social conditions were unequal"])],
                          segs=["b1", "b2"]))
    clock.t += 60
    await send(bus, sig("c1", announce="Economic", announce_rule="section"), sig("c2"))
    await send(bus, ready(FR, "Causes", [act("explanation", points=["Economic strain from wars"])], segs=["c1", "c2"]))
    clock.t += 60
    await send(bus, ready(FR, "Intellectual Causes", [act("explanation", points=["Thinkers rejected divine right"])],
                          relation="sub_concept"))
    assert slides(deck) == [
        ("Causes", None, ["There were several causes"]),
        ("Social", "Causes", ["Social conditions were unequal"]),
        ("Economic", "Causes", ["Economic strain from wars"]),           # not on the Social slide
        ("Intellectual Causes", "Causes", ["Thinkers rejected divine right"]),
    ]


async def test_an_announced_member_of_a_classified_set_is_its_child_and_keeps_its_facts():
    """test21: the planets, then "Mercury": the model keeps saying "Planets"; facts without their subject are
    summarised as Mercury's and stay on its slide; a general point about planets leaves it."""
    bus, store, deck, clock = await _opened(SOLAR, "Planets", act("classification", label="Planets",
                                                                    points=["Mercury", "Venus", "Earth"]))
    await send(bus, sig("b1", announce="Mercury"), sig("b2"))
    await send(bus, ready(SOLAR, "Planets", [act("explanation", points=["Mercury is closest to the Sun"])],
                          segs=["b1", "b2"]))
    clock.t += 60
    await send(bus, with_(ready(SOLAR, "Planets", [act("explanation", facts=[{"label": "Diameter",
                                                                               "value": "4879 km"}])]),
                          summary_delta="Mercury has a diameter of 4879 km."))
    clock.t += 60
    await send(bus, ready(SOLAR, "Planets", [act("explanation", points=["Planets orbit the Sun in ellipses"])]))
    got = slides(deck)
    assert got[1] == ("Mercury", "Planets", ["Mercury is closest to the Sun", "Diameter: 4879 km"])
    assert got[2] == ("Planets", None, ["Planets orbit the Sun in ellipses"])


# ---- state tree + prompt -----------------------------------------------------------------------------------------

async def test_the_outline_keeps_a_child_under_its_parent_and_the_prompt_shows_it():
    bus, store, deck, eng, clock = await make()
    await send(bus, ready(FR, "Causes", [act("explanation", points=["Several causes"])], relation="new_topic"))
    await send(bus, with_(ready(FR, "Social", [act("explanation", points=["Unequal society"])],
                                relation="sub_concept"), parent="Causes"))
    st = store.snapshot()
    topic = st.topic(st.current_topic_id)
    assert [(s.title, [c.title for c in s.subtopics]) for s in topic.subtopics] == [("Causes", ["Social"])]
    assert st.subtopic().title == "Social" and st.subtopic_parent().title == "Causes"
    assert outline_lines(st) == ["- French Revolution: Causes (Social)"]
    user = build_prompt(st, [], dynamic_budget=1200, total_budget=2600).messages[1]["content"]
    assert "subtopic=Social (in Causes)" in user and "Causes (Social)" in user
    # named again without its parent, the child stays where it is
    await send(bus, ready(FR, "Social", [act("explanation", points=["Clergy were privileged"])]))
    st = store.snapshot()
    assert [s.title for s in st.topic(st.current_topic_id).subtopics] == ["Causes"]


def test_the_parent_rule_is_off_in_the_live_prompt():
    assert '"parent"' not in SYSTEM_PROMPT  # its A/B on gpt-oss-120b was worse (2026-10-16)
    assert '"parent": ""' in system_prompt(visual=True, hierarchy=False, named=False, parent=True)


# ---- revisit (interpreter) ---------------------------------------------------------------------------------------

async def test_an_earlier_subtopic_title_is_not_reused_for_a_new_named_concept():
    """test30: photodiode content came back as sibling_concept "Reverse Bias", an outline title from minutes before."""
    bus, store, deck, eng, clock = await make()
    semi = "Semiconductor Devices"
    await send(bus, ready(semi, "Reverse Bias", [act("explanation", points=["Current is tiny"])], relation="new_topic"))
    await send(bus, ready(semi, "Zener Diode", [act("explanation", points=["Breaks down at a set voltage"])],
                          relation="sibling_concept"))
    st = store.snapshot()
    stale = Interpretation(topic=semi, subtopic="Reverse Bias", relation="sibling_concept",
                           acts=[act("definition", term="Photodiode", definition="A diode that converts light")])
    assert _revisit_name(stale, st) == "Photodiode"
    same_term = stale.model_copy(update={"acts": [act("definition", term="Reverse Bias", definition="...")]})
    assert _revisit_name(same_term, st) == "Reverse Bias"
    current = stale.model_copy(update={"subtopic": "Zener Diode"})
    assert _revisit_name(current, st) == "Zener Diode"


# ---- test23 fixes ------------------------------------------------------------------------------------------------

def test_a_series_announcement_is_no_bullet():
    from copilot.presentation.content import is_announcement
    assert is_announcement("The third topic is Integral Calculus")
    assert is_announcement("Next topic is Probability")
    assert not is_announcement("The third planet is Earth")
    assert not is_announcement("The first topic is the derivative, which measures the rate of change of a function "
                               "at a point on its curve")


async def test_a_confirmed_new_topic_takes_the_announced_slide_titled_by_it():
    """test23: "The third topic is Integral Calculus" - filed under Differential Calculus until two interpretations
    agreed - then a second "Integral Calculus" slide right after the first."""
    bus, store, deck, clock = await _opened("Differential Calculus", "Introduction",
                                            act("explanation", points=["The derivative measures rate of change"]))
    await send(bus, sig("b1", announce="Integral Calculus", announce_rule="ordinal"), sig("b2"))
    await send(bus, ready("Integral Calculus", "Introduction", [act("explanation", points=[
        "Integration accumulates small quantities"])], relation="new_topic", segs=["b1", "b2"]))
    clock.t += 60
    await send(bus, ready("Integral Calculus", "Introduction", [act("explanation", points=[
        "Integration is related to differentiation"])], relation="new_topic"))
    got = [(t, p) for t, p, _ in slides(deck)]
    assert got == [("Differential Calculus", None), ("Integral Calculus", None)], got


async def test_a_misheard_topic_announcement_takes_the_models_spelling_and_is_no_member():
    """test23: "Statics" (Statistics misheard) announced a new topic whose first unit the model labelled "Measures of
    Central Tendency": it was shown as a member of that set."""
    bus, store, deck, clock = await _opened("Coordinate Geometry", "Distance Formula",
                                            act("explanation", points=["Distance between two points"]))
    await send(bus, sig("b1", announce="Statics"), sig("b2"))
    await send(bus, ready("Statistics", "Measures of Central Tendency", [act("classification", label="Measures",
                          points=["Mean", "Median", "Mode"])], relation="new_topic", segs=["b1", "b2"]))
    title, parent, _ = slides(deck)[-1]
    assert (title, parent) == ("Statistics", None)


def test_a_parent_named_with_its_subject_counts_by_its_head():
    """Live S2 check: "Political Causes" / "Intellectual Causes" after "Causes of French Revolution" had no parent."""
    assert is_child_facet("Political Causes", "Causes of French Revolution")
    assert is_child_facet("Physical Properties", "Properties of Water")
    assert not is_child_facet("Causes", "Causes of French Revolution")
    assert not is_child_facet("Types of Bonds", "Bonds")
    causes = Working(Frame(FR, "Causes of French Revolution"), has_content=True)
    it = Interpretation(topic=FR, subtopic="Political Causes", relation="sibling_concept",
                        acts=[act("explanation", points=["Louis XVI was autocratic"])])
    d = decide(causes, it, [Signal(0.0, False)], None, has_pieces=True)
    assert d.frame == Frame(FR, "Political Causes", parent="Causes of French Revolution")
