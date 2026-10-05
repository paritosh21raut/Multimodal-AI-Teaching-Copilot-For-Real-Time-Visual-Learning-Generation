"""PresentationEngine with the real bus, state store and deck; fake lecture clock (F-005)."""
import asyncio

from copilot.core.bus import EventBus
from copilot.core.events import (
    Command, CommandReceived, ConceptSignal, InterpretationReady, Lifecycle, LifecycleChanged, SlideOverflow,
)
from copilot.core.interpretation import ConcernItem, ContentItems, DiscourseAct, Formula, Interpretation
from copilot.core.state import LectureSetup, LectureStateStore
from copilot.presentation.deck import Deck
from copilot.presentation.engine import PresentationEngine, PresentationSettings, provisional_text, replace_spoken


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


def ready(topic, sub, acts, relation="same_concept", segs=None, concerns=()):
    global _n
    _n += 1
    segs = segs or [f"seg{_n}-{i}" for i in range(1, 4)]
    return InterpretationReady(request_id=f"r{_n}", segment_ids=segs, provider="m", interpretation=Interpretation(
        topic=topic, subtopic=sub, relation=relation, acts=list(acts), concerns=list(concerns)))


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
            out.append(b.latex)
    return out


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
    await send(bus, ready("Photosynthesis", "Process", [act("process", lines=(1,), steps=["Water is split"])]))
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
    assert len(deck.slides) == 2 and deck.slides[1].title == "Comparison of Respiration"
    assert deck.slides[1].continuation_of is None                            # a new topic, not a continuation
    await eng.stop()


async def test_boundary_signal_confirms_new_topic_at_once():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Importance", [act("explanation", points=["Food"])], relation="new_topic"))
    r = ready("Respiration", "", [act("explanation", points=["Happens all the time"])], relation="new_topic")
    await send(bus, ConceptSignal(segment_id=r.segment_ids[0], shift_score=0.4, boundary=True), r)
    assert [s.title for s in deck.slides] == ["Why photosynthesis matters", "Respiration"]
    await eng.stop()


async def test_concern_linked_content_is_held_until_the_teacher_decides():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Process", [act("process", steps=["Light is absorbed"])],
                          relation="new_topic"))
    wrong = "Plants take in oxygen and give out carbon dioxide"
    c = ConcernItem(claim=wrong + " during photosynthesis", issue="reversed", confidence=0.95, lines=[2],
                    suggested_correction="Plants take in carbon dioxide and give out oxygen")
    await send(bus, ready("Photosynthesis", "Process", [act("process", lines=(1,), steps=["Oxygen is released"]),
                                                        act("explanation", lines=(2,), points=[wrong])],
                          concerns=[c]))
    s = deck.slides[0]
    assert texts(s) == ["Light is absorbed", "Oxygen is released"]           # the wrong claim is not shown
    concern = store.snapshot().concerns[0]
    assert concern.status == "open" and concern.segment_ids
    await send(bus, CommandReceived(command=Command(kind="resolve_concern",
                                                    args={"id": concern.id, "action": "accept"})))
    shown = [t for sl in deck.slides for t in texts(sl)] + [b.text for sl in deck.slides for b in sl.blocks
                                                            if b.type == "callout"]
    assert "Plants take in carbon dioxide and give out oxygen" in shown and wrong not in shown
    await eng.stop()


async def test_keep_and_dismiss():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    for action, expect_shown in (("keep", True), ("dismiss", False)):
        claim = f"The Sun orbits the Earth ({action})"
        c = ConcernItem(claim=claim, issue="wrong", suggested_correction="The Earth orbits the Sun", confidence=0.9,
                        lines=[1])
        await send(bus, ready("Astronomy", "", [act("explanation", points=[claim])], relation="new_topic",
                              concerns=[c]))
        cid = next(x.id for x in store.snapshot().concerns if x.claim == claim)
        await send(bus, CommandReceived(command=Command(kind="resolve_concern", args={"id": cid, "action": action})))
        shown = [t for sl in deck.slides for t in texts(sl)]
        assert (claim in shown) == expect_shown
        assert "The Earth orbits the Sun" not in shown
    await eng.stop()


async def test_transcription_concern_accept_replaces_the_spoken_token():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    c = ConcernItem(claim="6H2", issue="mis-heard?", suggested_correction="6H2O", confidence=0.5, lines=[1],
                    kind="transcription")
    await send(bus, ready("Photosynthesis", "Equation", [act("formula", formula=Formula(
        expression="6CO2 + 6H2 + light -> C6H12O6 + 6O2"))], relation="new_topic", concerns=[c]))
    assert deck.slides == []                                                  # nothing else to show yet
    cid = store.snapshot().concerns[0].id
    await send(bus, CommandReceived(command=Command(kind="resolve_concern", args={"id": cid, "action": "accept"})))
    assert texts(deck.slides[0]) == ["6CO2 + 6H2O + light -> C6H12O6 + 6O2"]
    await eng.stop()


async def test_force_new_slide_pinned_and_overflow():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Sunlight"])],
                          relation="new_topic"))
    first = deck.live_id
    await send(bus, CommandReceived(command=Command(kind="force_new_slide")))
    assert len(deck.slides) == 2 and deck.live_id == deck.slides[1].id and deck.slides[1].blocks == []
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Water"])]))
    assert texts(deck.slides[1]) == ["Water"]                                 # fills the forced slide
    # pinned: new slides queue behind the pinned live slide
    await send(bus, CommandReceived(command=Command(kind="goto", args={"slide_id": first})),
               CommandReceived(command=Command(kind="pin")))
    await send(bus, ready("Photosynthesis", "Process", [act("process", steps=["Light is absorbed"])],
                          relation="sibling_concept"))
    assert len(deck.slides) == 3 and deck.live_id == first
    # overflow reported by the display: the next content goes to a new slide
    proc = deck.slides[2]
    await send(bus, SlideOverflow(slide_id=proc.id, version=proc.version))
    await send(bus, ready("Photosynthesis", "Process", [act("process", steps=["Water is split"])]))
    assert texts(deck.get(proc.id)) == ["Light is absorbed"] and texts(deck.slides[3]) == ["Water is split"]
    assert deck.slides[3].title.endswith("(cont.)")
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


def test_helpers():
    assert provisional_text(["bacteria convert sunlight", "convert sunlight water", "photosynthesis photosynthesis",
                             "biological process"]) == "bacteria convert sunlight · biological process"
    assert replace_spoken("6CO2 + 6H2 + light", "6H2", "6H2O") == "6CO2 + 6H2O + light"


# ---- M4 independent review regressions ------------------------------------------------------------------

async def _resolve(bus, cid, action):
    await send(bus, CommandReceived(command=Command(kind="resolve_concern", args={"id": cid, "action": action})))


async def test_review1_piece_waits_for_every_linked_concern():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Def", [act("explanation", points=["Plants make food"])],
                          relation="new_topic"))
    await send(bus, ready("Photosynthesis", "Def", [act("explanation", lines=(1, 2, 3),
                                                        points=["Oxygen comes from CO2", "Needs 6H2"])],
                          concerns=[ConcernItem(claim="6H2", issue="x", suggested_correction="6H2O", confidence=0.9,
                                                lines=[3], kind="transcription"),
                                    ConcernItem(claim="Oxygen comes from CO2", issue="wrong", confidence=0.9,
                                                suggested_correction="Oxygen comes from water", lines=[2])]))
    cs = store.snapshot().concerns
    tr = next(c for c in cs if c.kind == "transcription")
    fa = next(c for c in cs if c.kind == "factual")
    assert texts(deck.live) == ["Plants make food"]
    await _resolve(bus, tr.id, "keep")
    assert "Oxygen comes from CO2" not in texts(deck.live)          # factual concern still open
    await _resolve(bus, fa.id, "dismiss")
    assert "Oxygen comes from CO2" not in texts(deck.live) and "Needs 6H2" in texts(deck.live)
    await eng.stop()


async def test_review2_accept_replaces_only_the_disputed_point():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Def", [act("explanation", points=["Plants make food"])],
                          relation="new_topic"))
    await send(bus, ready("Photosynthesis", "Def", [act("explanation", lines=(2, 3), points=[
        "Happens in chloroplasts", "Oxygen comes from CO2", "Uses sunlight"])], concerns=[ConcernItem(
            claim="Oxygen comes from CO2", issue="wrong", suggested_correction="Oxygen comes from water",
            confidence=0.9, lines=[3])]))
    assert texts(deck.live) == ["Plants make food", "Happens in chloroplasts", "Uses sunlight"]  # undisputed shown
    await _resolve(bus, store.snapshot().concerns[0].id, "accept")
    assert texts(deck.live) == ["Plants make food", "Happens in chloroplasts", "Uses sunlight",
                                "Oxygen comes from water"]
    await eng.stop()


async def test_review3_and_4_provisional_never_left_behind_nor_blocks_a_real_point():
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
    from copilot.presentation.composer import frame_slide, merge, set_provisional
    from copilot.presentation.content import Piece
    s, _ = merge(frame_slide("P", "R"), Piece("points", texts=("Sunlight",)))
    s = set_provisional(s, "chlorophyll pigment · light energy")
    s, left = merge(s, Piece("points", texts=("Chlorophyll pigment",)))
    assert "Chlorophyll pigment" in [i.text for i in s.blocks[0].items if not i.provisional]
    await eng.stop()


async def test_review5_late_release_does_not_take_the_screen_or_the_working_slide():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    c = ConcernItem(claim="Plants need oxygen to photosynthesize", issue="wrong", confidence=0.9, lines=[1])
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Sunlight"])],
                          relation="new_topic"))
    await send(bus, ready("Photosynthesis", "Requirements",
                          [act("explanation", points=["Plants need oxygen to photosynthesize"])], concerns=[c]))
    r = ready("Respiration", "", [act("explanation", points=["Uses glucose"])], relation="new_topic")
    await send(bus, ConceptSignal(segment_id=r.segment_ids[0], shift_score=0.2, boundary=True), r)
    resp = deck.live_id
    await _resolve(bus, store.snapshot().concerns[0].id, "keep")
    assert deck.live_id == resp
    await send(bus, ready("Respiration", "", [act("explanation", points=["Produces ATP"])]))
    assert texts(deck.get(resp)) == ["Uses glucose", "Produces ATP"]
    assert "Plants need oxygen to photosynthesize" in texts(deck.slides[0])   # back on its own slide
    await eng.stop()


async def test_review6_confirmed_topic_with_all_content_held_still_opens_next():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Importance", [act("explanation", points=["Food for all"])],
                          relation="new_topic"))
    r = ready("Respiration", "", [act("explanation", points=["Respiration makes oxygen"])], relation="new_topic",
              concerns=[ConcernItem(claim="Respiration makes oxygen", issue="wrong", confidence=0.9, lines=[1])])
    await send(bus, ConceptSignal(segment_id=r.segment_ids[0], shift_score=0.2, boundary=True), r)
    await send(bus, ready("Respiration", "", [act("explanation", points=["Happens in mitochondria"])]))
    assert [s.title for s in deck.slides] == ["Why photosynthesis matters", "Respiration"]
    await eng.stop()


async def test_review_concern_resolved_before_the_engine_saw_it_is_applied():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Astronomy", "", [act("explanation", points=["Stars are suns"])], relation="new_topic"))
    r = ready("Astronomy", "", [act("explanation", points=["The Sun orbits the Earth"])],
              concerns=[ConcernItem(claim="The Sun orbits the Earth", issue="wrong", confidence=0.9, lines=[1])])
    orig = store.snapshot

    def snap():  # engine backlog: the teacher already dismissed it when the engine reads the state
        s = orig()
        s.concerns = [c.model_copy(update={"status": "dismissed"}) for c in s.concerns]
        return s
    store.snapshot = snap
    await send(bus, r)
    assert texts(deck.live) == ["Stars are suns"]
    await eng.stop()


async def test_concern_without_extracted_content_still_shows_the_teachers_choice():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Process", [act("process", steps=["Light is absorbed"])],
                          relation="new_topic"))
    claim = "Plants take in oxygen during photosynthesis"
    await send(bus, ready("Photosynthesis", "Process", [act("explanation", lines=(1,))], concerns=[ConcernItem(
        claim=claim, issue="reversed", suggested_correction="Plants take in carbon dioxide", confidence=0.95,
        lines=[1])]))
    assert claim not in str([texts(s) for s in deck.slides])
    await _resolve(bus, store.snapshot().concerns[0].id, "accept")
    shown = [b.text for s in deck.slides for b in s.blocks if b.type == "callout"] + \
        [t for s in deck.slides for t in texts(s)]
    assert "Plants take in carbon dioxide" in shown and claim not in shown
    await eng.stop()


async def test_no_fast_path_teaser_after_an_uninterpreted_boundary():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Sunlight"])],
                          relation="new_topic"))
    await send(bus, ConceptSignal(segment_id="b1", shift_score=0.4, boundary=True, cues=["now let's"]),
               ConceptSignal(segment_id="b2", shift_score=0.3, keyphrases=["hydrogen combines", "carbon dioxide"]))
    assert not any(i.provisional for i in deck.live.blocks[0].items)
    await send(bus, ready("Photosynthesis", "Requirements", [act("explanation", points=["Water"])], segs=["b1"]))
    await send(bus, ConceptSignal(segment_id="b3", shift_score=0.3, keyphrases=["leaf pores", "stomata"]))
    assert deck.live.blocks[0].items[-1].provisional          # boundary interpreted: teasers resume
    await eng.stop()


def test_display_case_and_term_notes():
    from copilot.presentation.composer import frame_slide, merge
    from copilot.presentation.content import Piece
    s, _ = merge(frame_slide("Photosynthesis", "Definition"),
                 Piece("definition", term="photosynthesis", definition="how plants make food"))
    s, _ = merge(s, Piece("definition", term="photo", definition="means light"))
    assert s.blocks[0].term == "Photosynthesis" and s.blocks[0].notes[0].text == "photo means light"
    c, _ = merge(frame_slide("Respiration", "Comparison"), Piece("comparison", columns=("photosynthesis", "respiration"),
                                                                rows=(("light", ("needed", "not needed")),)))
    assert [x.heading for x in c.blocks[0].columns] == ["Photosynthesis", "Respiration"]
    assert c.blocks[0].rows[0].aspect == "Light"


def test_continuation_titles():
    from copilot.presentation.composer import frame_slide
    from copilot.presentation.content import FormulaData, Piece
    from copilot.presentation.engine import continuation_title
    q = frame_slide("Respiration in Plants", "Definition").model_copy(update={"layout": "definition"})
    assert continuation_title(q.title, q, Piece("comparison", columns=("A", "B"))) == "Respiration in Plants: compared"
    w = frame_slide("Photosynthesis", "Process").model_copy(update={"layout": "process_flow"})
    assert continuation_title(w.title, w, Piece("formula", formula=FormulaData("x"))) == \
        "How photosynthesis works: the equation"
    assert continuation_title(w.title, w, Piece("steps", texts=("a",))) == "How photosynthesis works (cont.)"
