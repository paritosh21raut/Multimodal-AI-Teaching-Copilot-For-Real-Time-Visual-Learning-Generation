"""F-013 S1b: live text while the teacher speaks (partials) -> instant title, growing list, faded definition; the final
line's interpretation replaces them."""
from copilot.audio.segmenter import SegmenterConfig, UtteranceSegmenter
from copilot.core.events import ConceptSignal, LiveCue
from copilot.stt.pipeline import stable_prefix
from copilot.understanding.cues import live_definition
from tests.unit.test_presentation_cues import _on_topic
from tests.unit.test_presentation_engine import act, make, ready, send, texts

import numpy as np


def test_stable_prefix_is_what_two_passes_agree_on():
    assert stable_prefix("", "Let us study") == ""
    assert stable_prefix("Let us study", "Let us study about basic.") == "Let us study"
    assert stable_prefix("Let us study about basic.", "Let us study about basic concepts") == "Let us study about basic"
    # Whisper revises a word: the agreed part stops there
    assert stable_prefix("Chemistry is the branch of signs", "Chemistry is the branch of science which") == \
        "Chemistry is the branch of"
    # an earlier agreement is kept while the new pass still starts with it
    assert stable_prefix("Let us", "Let us study about basic concepts", kept="Let us study about") == \
        "Let us study about"


def test_segmenter_numbers_utterances_and_snapshots_the_one_in_progress():
    seg = UtteranceSegmenter(SegmenterConfig())
    frame = np.zeros(512, np.float32)
    assert seg.snapshot() is None
    for _ in range(20):
        seg.push(frame, 0.9)
    n, start, audio = seg.snapshot()
    assert n == 1 and len(audio) >= 20 * 512
    out = []
    for _ in range(40):
        out += seg.push(frame, 0.0)
    assert out and out[0].number == 1 and seg.snapshot() is None
    seg.push(frame, 0.9)
    assert seg.snapshot()[0] == 2


def test_live_definition_only_for_a_named_term():
    assert live_definition("Chemistry is the branch of science which deals with") == \
        ("Chemistry", "The branch of science which deals with")
    assert live_definition("It is made up of small particles") == ("", "")
    assert live_definition("An element can be a metal") == ("", "")  # a list, not a definition


async def test_title_grows_as_it_is_said_then_the_final_line_takes_over():
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)
    await send(bus, LiveCue(utterance=7, announce="Basic concepts"))
    cue_id = deck.live_id
    assert deck.live.title == "Basic concepts" and deck.live.pending
    await send(bus, LiveCue(utterance=7, announce="Basic concepts of chemistry"))
    assert deck.live_id == cue_id and deck.live.title == "Basic concepts of chemistry"
    # the final line of that utterance: same slide, now linked to its segment for the interpretation
    await send(bus, ConceptSignal(segment_id="f7", shift_score=0, boundary=True, utterance=7,
                                  announce="Basic concepts of chemistry"))
    assert len(deck.slides) == 2
    await send(bus, ready("Chemistry", "Basic Concepts of Chemistry", [act("explanation", points=["Chapter one"])],
                          relation="new_topic", segs=["f7"]))
    assert deck.live_id == cue_id and not deck.live.pending


async def test_definition_shows_while_said_and_the_interpretation_replaces_it():
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)
    await send(bus, LiveCue(utterance=9, announce="Chemistry"))
    await send(bus, LiveCue(utterance=10, term="Chemistry", definition="The branch of science which deals"))
    d = [b for b in deck.live.blocks if b.type == "definition"]
    assert len(d) == 1 and d[0].provisional and d[0].definition == "The branch of science which deals"
    await send(bus, LiveCue(utterance=10, term="Chemistry",
                            definition="The branch of science which deals with the composition of matter"))
    d = [b for b in deck.live.blocks if b.type == "definition"]
    assert len(d) == 1 and d[0].definition.endswith("composition of matter")
    await send(bus, ConceptSignal(segment_id="f10", shift_score=0, utterance=10))
    await send(bus, ready("Chemistry", "Chemistry",
                          [act("definition", term="Chemistry", definition="The study of the composition of matter")],
                          relation="new_topic", segs=["f10"]))
    d = [b for b in deck.live.blocks if b.type == "definition"]
    assert len(d) == 1 and not d[0].provisional and d[0].definition == "The study of the composition of matter"


async def test_no_live_definition_for_a_term_off_the_slide():
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)  # slide "Matter", content shown
    await send(bus, LiveCue(utterance=3, term="Electron", definition="A negatively charged particle"))
    assert not any(getattr(b, "provisional", False) for b in deck.live.blocks)


async def test_list_names_append_as_they_are_said():
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)
    await send(bus, LiveCue(utterance=4, list_head="Branches of chemistry", list_items=["Inorganic", "Organic"]))
    tree = next(b for b in deck.live.blocks if b.type == "hierarchy")
    assert [c.label for c in tree.root.children] == ["Inorganic", "Organic"]
    await send(bus, LiveCue(utterance=4, list_head="Branches of chemistry",
                            list_items=["Inorganic", "Organic", "Physical"]))
    trees = [b for b in deck.live.blocks if b.type == "hierarchy"]
    assert len(trees) == 1 and [c.label for c in trees[0].root.children] == ["Inorganic", "Organic", "Physical"]
    await send(bus, ConceptSignal(segment_id="f4", shift_score=0, utterance=4, list_head="Branches of chemistry",
                                  list_items=["Inorganic", "Organic", "Physical", "Analytical"]))
    await send(bus, ready("Matter", "Definition", [act("classification", label="Branches of chemistry",
                                                       points=["Inorganic", "Organic", "Physical", "Analytical"])],
                          segs=["f4"]))
    trees = [b for b in deck.live.blocks if b.type == "hierarchy"]
    assert len(trees) == 1 and not trees[0].provisional and len(trees[0].root.children) == 4


def test_sentence_split_point_waits_until_the_speaker_goes_on():
    from copilot.stt.pipeline import sentence_split_point
    words = [("Matter", 0.0, 0.4), ("is", 0.4, 0.5), ("anything.", 0.5, 1.2), ("It", 1.6, 1.7), ("is", 1.7, 1.8),
             ("made", 1.8, 2.0)]
    assert sentence_split_point("Matter is anything.", words) is None          # nothing after it yet
    assert sentence_split_point("Matter is anything. It", words) is None       # one word: not sure yet
    assert sentence_split_point("Matter is anything. It is", words) == 1.2     # the end of "anything."


def test_segmenter_splits_at_a_sentence_end_and_numbers_the_rest():
    seg = UtteranceSegmenter(SegmenterConfig())
    frame = np.zeros(512, np.float32)
    for i in range(100):  # ~3.2 s of speech, a dip at ~1.6 s
        seg.push(frame, 0.2 if 48 <= i <= 51 else 0.9)
    u = seg.split_at(1, 1.6)
    assert u is not None and u.number == 1 and 1.4 <= u.duration <= 1.9
    assert seg.in_speech and seg.number == 2 and seg.split_at(1, 1.0) is None


def test_cues_found_in_any_sentence_of_a_joined_line():
    from copilot.understanding.cues import detect_all
    line = ("Well there you went, let us start with our first chapter, basic concepts of chemistry. "
            "Let us understand what chemistry is. Chemistry is the branch")
    assert detect_all(line).of("topic").name == "Basic concepts of chemistry"
    assert detect_all(line, latest_first=True).of("topic").name == "Chemistry"  # the one being said
