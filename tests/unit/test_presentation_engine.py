"""PresentationEngine with the real bus, state store and deck; fake lecture clock (F-005)."""
import asyncio

from copilot.core.bus import EventBus
from copilot.core.events import (
    Command, CommandReceived, ConceptSignal, InterpretationReady, Lifecycle, LifecycleChanged, SlideOverflow,
)
from copilot.core.interpretation import (
    ConcernItem, ContentItems, DiscourseAct, Fact, Group, Interpretation, Revision,
)
from copilot.core.state import LectureSetup, LectureStateStore
from copilot.presentation.deck import Deck
from copilot.presentation.engine import PresentationEngine, PresentationSettings, provisional_text


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


async def make(expected_topic="", **settings):
    bus = EventBus()
    store = LectureStateStore(bus, "s", LectureSetup(expected_topic=expected_topic, subject="Biology", grade_level="7"))
    store.attach()
    deck = Deck(bus)
    deck.attach()
    clock = Clock()
    eng = PresentationEngine(bus, store, deck, PresentationSettings(**settings), clock=clock)
    eng.attach()
    return bus, store, deck, eng, clock


def act(kind, lines=(1,), **items):
    return DiscourseAct(act=kind, lines=list(lines), items=ContentItems(**items))


_n = 0


def ready(topic, sub, acts, relation="same_concept", segs=None, concerns=(), revisions=(), refs=None):
    global _n
    _n += 1
    segs = segs or [f"seg{_n}-{i}" for i in range(1, 4)]
    return InterpretationReady(request_id=f"r{_n}", segment_ids=segs, provider="m", slide_refs=refs or {},
                               interpretation=Interpretation(topic=topic, subtopic=sub, relation=relation,
                                                             acts=list(acts), concerns=list(concerns),
                                                             revisions=list(revisions)))


async def send(bus, *events):
    for e in events:
        await bus.publish(e)
        await bus.drain()
    await bus.drain()


def texts(spec):
    out = []
    for b in spec.blocks:
        if b.type == "points":
            out += [i.text for i in b.items]
        elif b.type == "process":
            out += [s.label for s in b.steps]
        elif b.type == "definition":
            out += [b.term] + [n.text for n in b.notes]
        elif b.type == "formula":
            out.append(b.spoken)  # the formula text as shown (latex is now the KaTeX source)
        elif b.type == "facts":
            out += [f"{f.label}: {f.value}" for f in b.facts]
        elif b.type == "callout":
            out.append(b.text)
    return out


async def _resolve(bus, cid, action):
    await send(bus, CommandReceived(command=Command(kind="resolve_concern", args={"id": cid, "action": action})))


async def test_title_slide_then_first_content_slide_and_in_place_update():
    bus, store, deck, eng, clock = await make(expected_topic="Photosynthesis")
    await send(bus, LifecycleChanged(state=Lifecycle.LIVE))
    assert [s.layout for s in deck.slides] == ["title"] and deck.slides[0].subtitle == "Biology · Grade 7"
    await send(bus, ready("Photosynthesis", "Definition",
                          [act("definition", term="Photosynthesis", definition="Plants make food using light")],
                          relation="new_topic"))
    assert len(deck.slides) == 2 and deck.live_id == deck.slides[1].id       # no dwell after a title slide
    s = deck.slides[1]
    assert s.layout == "definition" and s.title == "What is photosynthesis?"
    clock.t = 5.0
    await send(bus, ready("Photosynthesis", "Definition", [act("explanation", points=["photo = light"])]))
    s2 = deck.get(s.id)
    assert len(deck.slides) == 2 and s2.version == s.version + 1
    assert s2.blocks[0].id == s.blocks[0].id and texts(s2) == ["Photosynthesis", "photo = light"]
    assert "photo = light" in store.snapshot().slide_context                  # prompt sees the current slide
    assert list(store.snapshot().slide_refs) == ["S1", "S2"]                   # ... with revisable refs
    await eng.stop()


async def test_new_facet_waits_for_min_dwell_then_appears():
    bus, store, deck, eng, clock = await make(min_dwell_s=15.0)
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Sunlight", "Water"])],
                          relation="new_topic"))
    first = deck.live_id
    clock.t = 5.0
    await send(bus, ready("Photosynthesis", "Process", [act("process", steps=["Light is absorbed"])],
                          relation="sibling_concept"))
    assert len(deck.slides) == 1 and deck.live_id == first                   # pending: dwell not over
    clock.t = 8.0
    await send(bus, ready("Photosynthesis", "Process", [act("process", steps=["Water is split"])]))
    clock.t = 15.5
    await asyncio.sleep(0.4)                                                  # ticker releases it
    await bus.drain()
    assert len(deck.slides) == 2 and deck.live_id == deck.slides[1].id
    proc = deck.slides[1]
    assert proc.layout == "process_flow" and texts(proc) == ["Light is absorbed", "Water is split"]
    assert proc.continuation_of == first and proc.facet == "Process"
    await eng.stop()


async def test_unconfirmed_topic_change_stays_then_second_agreeing_interpretation_moves():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Importance", [act("explanation", points=["Food for all"])],
                          relation="new_topic"))
    r = ready("Respiration", "", [act("explanation", points=["Respiration happens all the time"])],
              relation="new_topic")
    await send(bus, *[ConceptSignal(segment_id=s, shift_score=0.3) for s in r.segment_ids], r)
    assert len(deck.slides) == 1 and "Respiration happens all the time" in texts(deck.slides[0])
    await send(bus, ready("Respiration", "Comparison", [act("explanation", points=["Uses oxygen"])]))
    assert len(deck.slides) == 2 and deck.slides[1].title == "Comparison"   # no "Comparison of Respiration"
    assert deck.slides[1].subtitle == "Respiration" and deck.slides[1].continuation_of is None
    await eng.stop()


async def test_boundary_signal_confirms_new_topic_at_once():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Importance", [act("explanation", points=["Food"])], relation="new_topic"))
    r = ready("Respiration", "", [act("explanation", points=["Happens all the time"])], relation="new_topic")
    await send(bus, ConceptSignal(segment_id=r.segment_ids[0], shift_score=0.4, boundary=True), r)
    assert [s.title for s in deck.slides] == ["Why photosynthesis matters", "Respiration"]
    await eng.stop()


# ---- truthful slides ------------------------------------------------------------------------------------

async def test_confident_factual_correction_is_shown_and_teacher_can_switch_back():
    """Acts carry the corrected content; the slide shows it; "Show as I said" puts back the teacher's words."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    c = ConcernItem(claim="Neptune is the hottest planet", issue="Venus is the hottest", confidence=0.95,
                    suggested_correction="Venus is the hottest planet", wrong="Neptune", right="Venus", lines=[1])
    await send(bus, ready("Solar System", "Planets", [act("explanation", facts=[
        Fact(label="Hottest planet", value="Venus"), Fact(label="Largest planet", value="Jupiter")])],
        relation="new_topic", concerns=[c]))
    assert texts(deck.live) == ["Hottest planet: Venus", "Largest planet: Jupiter"]
    concern = store.snapshot().concerns[0]
    assert concern.applied and concern.wrong == "Neptune"
    await _resolve(bus, concern.id, "keep")
    assert texts(deck.live) == ["Hottest planet: Neptune", "Largest planet: Jupiter"]
    await eng.stop()


async def test_low_confidence_correction_shows_what_was_said_until_accepted():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    c = ConcernItem(claim="Neptune is the coldest planet", issue="Uranus has the lowest recorded temperature",
                    confidence=0.6, suggested_correction="Uranus is the coldest planet", wrong="Neptune",
                    right="Uranus", lines=[1])
    await send(bus, ready("Solar System", "Planets", [act("explanation", points=["Uranus is the coldest planet"])],
                          relation="new_topic", concerns=[c]))
    assert texts(deck.live) == ["Neptune is the coldest planet"]             # never omitted: shown as said
    concern = store.snapshot().concerns[0]
    assert not concern.applied
    await _resolve(bus, concern.id, "accept")
    assert texts(deck.live) == ["Uranus is the coldest planet"]
    await eng.stop()


async def test_mis_heard_word_is_shown_corrected():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    c = ConcernItem(claim="Omo atomic", issue="mis-heard", suggested_correction="monoatomic", wrong="Omo atomic",
                    right="monoatomic", confidence=0.5, lines=[1], kind="transcription")
    await send(bus, ready("Chemistry", "Molecules", [act("classification", label="Types of molecules",
                                                         points=["Monoatomic", "Diatomic", "Polyatomic"])],
                          relation="new_topic", concerns=[c]))
    tree = deck.live.blocks[0]
    assert tree.type == "hierarchy" and [n.label for n in tree.root.children] == ["Monoatomic", "Diatomic",
                                                                                   "Polyatomic"]
    await _resolve(bus, store.snapshot().concerns[0].id, "keep")
    assert [n.label for n in deck.live.blocks[0].root.children][0] == "Omo atomic"
    await eng.stop()


# ---- structure ------------------------------------------------------------------------------------------

async def test_revision_rewrites_a_fragment_in_place():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Galaxies", "Black Holes", [act("explanation", points=["Black hole at the centre",
                                                                                "Black hole has huge gravity"])],
                          relation="new_topic"))
    item = deck.live.blocks[0].items[1]
    refs = dict(store.snapshot().slide_refs)
    assert refs["S2"].endswith("/" + item.id)
    await send(bus, ready("Galaxies", "Black Holes", [], revisions=[
        Revision(ref="S2", text="Its gravity is so strong that light cannot escape")], refs=refs))
    items = deck.live.blocks[0].items
    assert items[1].id == item.id and items[1].text == "Its gravity is so strong that light cannot escape"
    assert len(items) == 2
    await eng.stop()


async def test_definition_spoken_across_units_is_completed_in_place():
    """Live chemistry test (session 20261005-230039-f084): "Chemistry is the branch of science which deals" /
    "with the consumption" / "composition, structure and properties of matter". The definition had no [S#] ref, so
    the model's completion was dropped as an unknown ref and the slide kept "the branch of science which deals"."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Chemistry", "Basic Concepts", [act("definition", term="Chemistry",
                                                             definition="the branch of science which deals")],
                          relation="new_topic"))
    d = deck.live.blocks[0]
    snap = store.snapshot()
    assert "[S1] (definition) Chemistry: the branch of science which deals" in snap.slide_context
    refs = dict(snap.slide_refs)
    assert refs["S1"].endswith("/" + d.id)
    await send(bus, ready("Chemistry", "Basic Concepts", [], revisions=[Revision(
        ref="S1", text="Chemistry: the branch of science which deals with the composition, structure and properties "
                       "of matter")], refs=refs))
    d2 = deck.live.blocks[0]
    assert d2.id == d.id and d2.term == "Chemistry"
    assert d2.definition == "the branch of science which deals with the composition, structure and properties of matter"
    assert len(deck.slides) == 1
    await eng.stop()


async def test_solar_system_facts_stay_together_on_one_slide():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Solar System", "Overview", [
        act("definition", term="Solar System", definition="The Sun and the eight planets that revolve around it")],
        relation="new_topic"))
    await send(bus, ready("Solar System", "Overview", [
        act("classification", groups=[Group(label="Inner planets", items=["Mercury", "Venus", "Earth", "Mars"]),
                                      Group(label="Outer planets", items=["Jupiter", "Saturn", "Uranus", "Neptune"])]),
        act("explanation", lines=(2,), facts=[Fact(label="Smallest planet", value="Mercury"),
                                              Fact(label="Largest planet", value="Jupiter")])]))
    await send(bus, ready("Solar System", "Overview", [act("explanation", facts=[
        Fact(label="Hottest planet", value="Venus"), Fact(label="Saturn", value="Has rings")])]))
    assert len(deck.slides) == 1
    s = deck.slides[0]
    assert [b.type for b in s.blocks] == ["definition", "groups", "facts"]
    assert not any(b.type == "example" for b in s.blocks)
    assert len(s.blocks[2].facts) == 4
    await eng.stop()


async def test_two_concepts_defined_together_sit_side_by_side():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Chemistry", "Elements and Compounds", [
        act("definition", term="Element", definition="Simplest pure substance; cannot be broken down chemically"),
        act("definition", lines=(2,), term="Compound",
            definition="Two or more elements combined in a fixed ratio by mass")], relation="new_topic"))
    s = deck.live
    assert [b.type for b in s.blocks] == ["definition", "definition"] and s.layout == "concept"
    assert s.title == "Elements and Compounds"
    await eng.stop()


async def test_overflow_continues_with_a_part_badge_not_cont():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    long = [f"Galaxy fact number {i} with a fairly long explanation attached to it" for i in range(12)]
    await send(bus, ready("Galaxies", "", [act("explanation", points=long)], relation="new_topic"))
    titles = [s.title for s in deck.slides]
    assert len(deck.slides) >= 2 and all(t == "Galaxies" for t in titles)
    assert [s.part for s in deck.slides] == list(range(1, len(deck.slides) + 1))
    assert all("cont" not in t for t in titles)
    assert sum(len(texts(s)) for s in deck.slides) == 12                      # nothing lost
    await eng.stop()


async def test_announcements_never_reach_the_slide():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Chemistry", "Matter", [
        act("transition", points=["Now let's learn about matter"]),
        act("definition", lines=(2,), term="Matter", definition="Anything that occupies space and has mass"),
        act("explanation", lines=(3,), points=["Let's learn about elements", "Particles are always moving"])],
        relation="new_topic"))
    shown = texts(deck.live)
    assert not any("learn about" in t.lower() for t in shown) and "Particles are always moving" in shown
    await eng.stop()


async def test_force_new_slide_navigated_back_and_overflow():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Sunlight"])],
                          relation="new_topic"))
    first = deck.live_id
    await send(bus, CommandReceived(command=Command(kind="force_new_slide")))
    assert len(deck.slides) == 2 and deck.live_id == deck.slides[1].id and deck.slides[1].blocks == []
    assert deck.slides[1].part == 2 and deck.get(first).part == 1           # same frame: part badge
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Water"])]))
    assert texts(deck.slides[1]) == ["Water"]                                 # fills the forced slide
    await send(bus, CommandReceived(command=Command(kind="goto", args={"slide_id": first})))
    await send(bus, ready("Photosynthesis", "Process", [act("process", steps=["Light is absorbed"])],
                          relation="sibling_concept"))
    assert len(deck.slides) == 3 and deck.live_id == first                   # navigated back: queued behind
    proc = deck.slides[2]
    await send(bus, SlideOverflow(slide_id=proc.id, version=proc.version))
    await send(bus, ready("Photosynthesis", "Process", [act("process", steps=["Water is split"])]))
    assert texts(deck.get(proc.id)) == ["Light is absorbed"] and texts(deck.slides[3]) == ["Water is split"]
    assert deck.slides[3].title == proc.title and deck.slides[3].part == 2
    await eng.stop()


async def test_teacher_navigated_back_slide_is_updated_in_place():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Sunlight"])],
                          relation="new_topic"))
    req = deck.live_id
    await send(bus, ready("Photosynthesis", "Process", [act("process", steps=["Light is absorbed"])],
                          relation="sibling_concept"))
    await send(bus, CommandReceived(command=Command(kind="prev")))
    assert deck.live_id == req and not deck.following
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Water"])],
                          relation="sibling_concept"))
    assert texts(deck.get(req)) == ["Sunlight", "Water"] and len(deck.slides) == 2
    await eng.stop()


async def test_provisional_fast_path_is_replaced_by_the_interpretation():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Sunlight"])],
                          relation="new_topic"))
    s = deck.slides[0]
    await send(bus, ConceptSignal(segment_id="segX", shift_score=0.3, keyphrases=["carbon dioxide", "leaf pores", "air"]))
    items = deck.get(s.id).blocks[0].items
    assert items[-1].provisional and items[-1].text == "carbon dioxide · leaf pores"
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Carbon dioxide via stomata"])],
                          segs=["segX"]))
    items = deck.get(s.id).blocks[0].items
    assert [i.text for i in items] == ["Sunlight", "Carbon dioxide via stomata"] and not any(i.provisional for i in items)
    await eng.stop()


async def test_provisional_never_left_behind_and_no_teaser_after_a_boundary():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Sunlight"])],
                          relation="new_topic"))
    a = deck.live_id
    await send(bus, ConceptSignal(segment_id="s1", shift_score=0.2, keyphrases=["carbon dioxide intake", "stomata"]))
    await send(bus, ready("Photosynthesis", "Process", [act("process", steps=["Light is absorbed"])],
                          relation="sibling_concept"))
    await send(bus, ready("Photosynthesis", "Process", [act("explanation", points=["Chlorophyll pigment"])]))
    await send(bus, ConceptSignal(segment_id="s2", shift_score=0.2, keyphrases=["light energy"]))
    assert not any(i.provisional for b in deck.get(a).blocks if b.type == "points" for i in b.items)
    bus2, store2, deck2, eng2, _ = await make(min_dwell_s=0.0)
    await send(bus2, ready("P", "R", [act("explanation", points=["Sunlight"])], relation="new_topic"))
    await send(bus2, ConceptSignal(segment_id="b1", shift_score=0.4, boundary=True, cues=["now let's"]),
               ConceptSignal(segment_id="b2", shift_score=0.3, keyphrases=["hydrogen combines", "carbon dioxide"]))
    assert not any(i.provisional for i in deck2.live.blocks[0].items)
    await eng.stop()
    await eng2.stop()


def test_helpers():
    assert provisional_text(["bacteria convert sunlight", "convert sunlight water", "photosynthesis photosynthesis",
                             "biological process"]) == "bacteria convert sunlight · biological process"


async def test_unconfirmed_topic_items_move_to_the_new_topic_slide_once_confirmed():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Solar System", "Natural Satellites", [act("definition", term="Natural satellites",
                                                                   definition="Moons that revolve around a planet")],
                          relation="new_topic"))
    sat = deck.live_id
    await send(bus, ready("Galaxies", "", [act("explanation", points=["The universe has billions of galaxies",
                                                                      "The Milky Way is our galaxy"])],
                          relation="new_topic"))                              # no cue: not yet confirmed
    assert "The Milky Way is our galaxy" in texts(deck.get(sat))             # shown meanwhile (never omitted)
    await send(bus, ready("Galaxies", "", [act("explanation", points=["A black hole sits at the centre"])]))
    gal = deck.slides[-1]
    assert texts(gal) == ["The universe has billions of galaxies", "The Milky Way is our galaxy",
                          "A black hole sits at the centre"]
    assert texts(deck.get(sat)) == ["Natural satellites"]                    # moved off the previous slide
    await eng.stop()


async def test_one_small_leftover_is_squeezed_in_not_put_on_its_own_part():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Chemistry", "Elements and Compounds", [
        act("definition", term="Element", definition="The simplest pure substance; it cannot be broken down or built "
            "from simpler substances by ordinary physical or chemical methods"),
        act("definition", lines=(2,), term="Compound",
            definition="Two or more elements combined in a definite ratio by mass"),
        act("classification", lines=(3,), label="Types of compounds",
            points=["Inorganic compounds", "Organic compounds"])], relation="new_topic"))
    await send(bus, ready("Chemistry", "Elements and Compounds", [act("example", examples=["Water is a compound"])]))
    assert len(deck.slides) == 1 and any(b.type == "example" for b in deck.slides[0].blocks)
    await eng.stop()



async def test_correction_the_model_did_not_apply_is_enforced():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    c = ConcernItem(claim="catastrophic", issue="mis-heard", suggested_correction="polyatomic", wrong="catastrophic",
                    right="Polyatomic", confidence=0.6, lines=[1], kind="transcription")
    await send(bus, ready("Chemistry", "Molecules", [act("classification", label="Types of molecules",
                                                         points=["Diatomic", "Triatomic", "Catastrophic"])],
                          relation="new_topic", concerns=[c]))
    assert [n.label for n in deck.live.blocks[0].root.children] == ["Diatomic", "Triatomic", "Polyatomic"]
    await _resolve(bus, store.snapshot().concerns[0].id, "keep")      # the teacher can still put back what was heard
    assert [n.label for n in deck.live.blocks[0].root.children][-1] == "Catastrophic"  # case follows the item
    await eng.stop()


async def test_teaser_note_does_not_block_side_by_side_definitions():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Chemistry", "Atoms and Molecules", [act("definition", term="Atom",
                          definition="Smallest particle of an element that can take part in a reaction")],
                          relation="new_topic"))
    await send(bus, ConceptSignal(segment_id="t1", shift_score=0.2, keyphrases=["independent existence", "molecule"]))
    assert any(n.provisional for n in deck.live.blocks[0].notes)
    await send(bus, ready("Chemistry", "Atoms and Molecules", [act("definition", term="Molecule",
                          definition="Simplest particle of matter with independent existence")], segs=["t0"]))
    assert len(deck.slides) == 1 and [b.type for b in deck.live.blocks] == ["definition", "definition"]
    assert not any(n.provisional for b in deck.live.blocks for n in b.notes)
    await eng.stop()


async def test_definition_slide_title_uses_the_term():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Basic Concepts of Chemistry", "Definition", [act("definition", term="Chemistry",
                          definition="The science of matter")], relation="new_topic"))
    assert deck.live.title == "What is chemistry?"
    await eng.stop()



# ---- second independent review (truthful-slides rework) ----------------------------------------------------

async def test_review_correction_targets_only_the_concerns_own_lines():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    c = ConcernItem(claim="Mercury is the largest planet", issue="smallest", confidence=0.95, lines=[1],
                    suggested_correction="Mercury is the smallest planet", wrong="largest", right="smallest")
    await send(bus, ready("Solar System", "Planets", [
        act("explanation", lines=(1,), points=["Mercury is the largest planet"]),       # model left the wrong word
        act("explanation", lines=(2,), points=["Jupiter is the largest planet"])], relation="new_topic",
        concerns=[c]))
    assert texts(deck.live) == ["Mercury is the smallest planet", "Jupiter is the largest planet"]
    await eng.stop()


async def test_review_as_said_does_not_touch_other_lines_and_accept_works_when_words_were_left():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    low = ConcernItem(claim="Plants take in oxygen", issue="reversed", confidence=0.62, lines=[1],
                      suggested_correction="Plants take in carbon dioxide", wrong="oxygen", right="carbon dioxide")
    await send(bus, ready("Photosynthesis", "Gases", [
        act("explanation", lines=(1,), points=["Plants take in carbon dioxide"]),
        act("explanation", lines=(2,), points=["Leaves release carbon dioxide at night too"])],
        relation="new_topic", concerns=[low]))
    assert texts(deck.live) == ["Plants take in oxygen", "Leaves release carbon dioxide at night too"]
    await _resolve(bus, store.snapshot().concerns[0].id, "accept")
    assert texts(deck.live)[0] == "Plants take in carbon dioxide"
    # unapplied concern whose wrong words the model left in: "Show correction" must still work
    bus2, store2, deck2, eng2, _ = await make(min_dwell_s=0.0)
    c2 = ConcernItem(claim="Venus has two moons", issue="no moons", confidence=0.5, lines=[1],
                     suggested_correction="Venus has no moons", wrong="two", right="no")
    await send(bus2, ready("Planets", "", [act("explanation", points=["Venus has two moons"])], relation="new_topic",
                           concerns=[c2]))
    assert texts(deck2.live) == ["Venus has two moons"]
    await _resolve(bus2, store2.snapshot().concerns[0].id, "accept")
    assert texts(deck2.live) == ["Venus has no moons"]
    await eng.stop()
    await eng2.stop()


async def test_review_backslash_correction_and_switching_twice():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    c = ConcernItem(claim="Delta H", issue="symbol", confidence=0.9, lines=[1], suggested_correction="\\Delta G",
                    wrong="Delta H", right="\\Delta G", kind="transcription")
    await send(bus, ready("Thermo", "", [act("explanation", points=["Free energy is \\Delta G"])],
                          relation="new_topic", concerns=[c]))
    cid = store.snapshot().concerns[0].id
    await _resolve(bus, cid, "keep")
    assert texts(deck.live) == ["Free energy is Delta H"]
    await _resolve(bus, cid, "accept")                                   # the teacher switches back
    assert texts(deck.live) == ["Free energy is \\Delta G"]
    await eng.stop()


async def test_review_tentative_diagram_moves_without_duplicates():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Solar System", "Moons", [act("explanation", points=["Moons orbit planets"])],
                          relation="new_topic"))
    first = deck.live_id
    await send(bus, ready("Galaxies", "", [act("classification", label="Types of galaxies",
                                               points=["Spiral", "Elliptical", "Irregular"])], relation="new_topic"))
    assert any(b.type == "hierarchy" for b in deck.get(first).blocks)
    await send(bus, ready("Galaxies", "", [act("explanation", points=["The Milky Way is a spiral galaxy"])]))
    assert [b.type for b in deck.get(first).blocks] == ["points"]       # the tree left the old slide
    gal = deck.slides[-1]
    assert sum(1 for b in gal.blocks if b.type == "hierarchy") == 1
    assert sum(1 for s in deck.slides for b in s.blocks if b.type == "hierarchy") == 1
    await eng.stop()



# ---- verify round 3 -------------------------------------------------------------------------------------------

async def test_sparse_definition_slide_keeps_its_supporting_classification():
    bus, store, deck, eng, clock = await make(min_dwell_s=15.0)
    await send(bus, ready("Chemistry", "Definition", [act("definition", term="Chemistry",
                          definition="The branch of science that deals with the composition, structure and properties "
                                     "of matter")], relation="new_topic"))
    clock.t = 5.0
    await send(bus, ready("Chemistry", "Branches of Chemistry", [act("classification", label="Branches of chemistry",
                          points=["Inorganic", "Organic", "Physical", "Analytical"])], relation="sibling_concept"))
    assert len(deck.slides) == 1 and [b.type for b in deck.live.blocks] == ["definition", "hierarchy"]
    # a new definition is not absorbed: it deserves its own space
    await send(bus, ready("Chemistry", "Matter", [act("definition", term="Matter",
                          definition="Anything that occupies space and has mass")], relation="sibling_concept"))
    assert len(eng._pending) == 1 and eng._pending[0].blocks[0].term == "Matter"
    await eng.stop()


async def test_next_part_waits_only_the_short_part_dwell():
    bus, store, deck, eng, clock = await make(min_dwell_s=15.0, part_dwell_s=6.0)
    long = [f"Planet fact {i} explained with a reasonably long sentence for the slide" for i in range(12)]
    await send(bus, ready("Solar System", "Planets", [act("explanation", points=long[:2])], relation="new_topic"))
    clock.t = 1.0
    await send(bus, ready("Solar System", "Planets", [act("explanation", points=long[2:])]))
    assert len(eng._pending) == 1                                     # part II waits ...
    clock.t = 7.5
    await asyncio.sleep(0.4)
    await bus.drain()
    assert not eng._pending and deck.live.part == 2                   # ... 6 s, not 15 s
    await eng.stop()



async def test_slide_emptied_by_a_tentative_move_is_removed():
    """Verify round 4: 'What is chemistry? II' stayed in the deck with no content after Matter moved out."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    long = [f"Chemistry fact {i} with a reasonably long explanation for the slide" for i in range(8)]
    await send(bus, ready("Chemistry", "Definition", [act("explanation", points=long)], relation="new_topic"))
    n_before = len(deck.slides)
    await send(bus, ready("Matter", "Definition", [act("explanation", points=[
        "Matter occupies space", "Matter has mass", "Particles attract each other", "Particles keep moving",
        "Particles have space between them"])], relation="new_topic"))             # unconfirmed: shown meanwhile
    await send(bus, ready("Matter", "Definition", [act("explanation", points=["Matter is made of particles"])]))
    assert all(s.blocks for s in deck.slides)                                    # no empty slide left behind
    assert deck.slides[-1].title.startswith("What is matter") and len(deck.slides) <= n_before + 1
    await eng.stop()
