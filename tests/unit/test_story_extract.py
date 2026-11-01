"""V3 ST3 story beat reading: the gate, the validator, and the held line on the controller (recorded answers, 0 tokens)."""
from __future__ import annotations

import json

import pytest

from copilot.story import beats
from copilot.story import extract as sx
from copilot.story.extract import ReplayStoryExtractor
from tests.unit.test_story import story_lecture, story_on


def gate(text):
    return sx.needs_llm(text, beats.speech(text), beats.beat(text))


# ---- the gate ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, why", [
    ("We have said, let us work together.", "speech unread"),            # test53 STT for "Pierre said"
    ("The farmer adds the boy. Where is the cow?", "speech unread"),     # test53 STT for "asks"
    ("A decade after that, Ravi became a teacher.", "time unread"),
    ("Then the drop slips into a narrow crack.", "place unread"),
    ("Pierre said, let us work together.", ""),                         # the fast path read it whole
    ("In 1905, a young clerk in Bern wrote four papers.", ""),
    ("Ravi said that he was tired.", ""),                               # indirect speech: narration, no call
    ("Okay, let's get back to the slides.", ""),
    ("She studied physics at the university.", ""),
])
def test_the_gate_calls_only_for_what_the_fast_path_left_unread(text, why):
    assert gate(text) == why


# ---- the validator ----------------------------------------------------------------------------------------------
def chk(ans, line, cast=("Marie Curie", "Pierre Curie")):
    return sx.check(ans, line, list(cast), beats.beat(line))


def test_a_speech_answer_is_taken_with_a_cast_name_and_said_words():
    ans, why = chk({"type": "speech", "who": "Pierre Curie", "to": "", "kind": "say", "words": "let us work together"},
                   "We have said, let us work together.")
    assert why == "" and ans["who"] == "Pierre Curie"


@pytest.mark.parametrize("ans, why", [
    ({"type": "speech", "who": "Pierre Curie", "kind": "say", "words": "let us work hard together"}, "words not"),
    ({"type": "speech", "who": "We", "kind": "say", "words": "let us work together"}, "speaker"),
    ({"type": "speech", "who": "Albert", "kind": "say", "words": "let us work together"}, "speaker"),  # not said
    ({"type": "speech", "who": "Pierre Curie", "kind": "sing", "words": "let us work together"}, "kind"),
    ({"type": "narration", "when": "in 1896", "where": "", "people": []}, "not in the line"),           # a number
    ({"type": "narration", "when": "", "where": "Paris", "people": []}, "not in the line"),
    ({"type": "dance"}, "type"),
    ("not json", "no answer"),
])
def test_an_answer_with_any_word_not_said_is_refused_whole(ans, why):
    got, bad = chk(ans, "We have said, let us work together.")
    assert got is None and why in bad


def test_record_run_fixes_everyone_is_no_addressee_and_a_place_drops_its_preposition():
    line = "Then the farmer told everyone, let us look in the garden."
    ans, _ = chk({"type": "speech", "who": "the farmer", "to": "everyone", "kind": "say", "words": "let us look in the garden."},
                 line, ("farmer",))
    assert ans is not None and ans["to"] == ""
    line = "That winter, they worked day and night in a cold shed."
    ans, _ = chk({"type": "narration", "when": "That winter", "where": "in a cold shed", "people": []}, line)
    assert ans["where"] == "a cold shed"
    line = "Sorry, let me move this to the next page."
    assert chk({"type": "narration", "when": "", "where": "", "people": ["Sorry"]}, line)[0] is None


def test_review_what_is_shown_is_cut_from_the_line():
    line = "Ravi said, it was 2.5 degrees outside."
    ans, _ = chk({"type": "speech", "who": "Ravi", "kind": "say", "words": "-2/5 degrees"}, line, ("Ravi",))
    assert ans["words"] == "2.5 degrees"                                   # never the model's "-" or "/"
    assert chk({"type": "speech", "who": "Ravi", "kind": "say", "words": "नमस्ते Ravi"}, line, ("Ravi",))[0] is None
    # a cast name not said in this line is no newly named person; a story line is no aside
    assert chk({"type": "narration", "people": ["Ravi"]}, "Then they ran home.", ("Ravi",))[0] is None
    assert chk({"type": "aside"}, "The water rushed into the old mill.")[0] is None


async def test_review_a_fault_in_one_reading_never_blocks_the_next_lines(monkeypatch):
    deck, eng, clock, talk, ext = await curie({})

    def broken(*a, **k):
        raise ValueError("a bug outside the call")
    monkeypatch.setattr(sx, "messages", broken)
    await talk.say(WE)
    await eng._story.settle()
    assert WE in story_on(deck).scenes[-1].lines                          # its fast reading
    monkeypatch.undo()
    await eng._story.settle()
    line = "Then they walked home."
    await talk.say(line)
    await eng._story.settle()
    assert line in story_on(deck).scenes[-1].lines and not eng._story.open.queue


@pytest.mark.parametrize("text, who, kind, words", [
    ("The girl was shouting. It is in the garden.", "The girl", "shout", "It is in the garden."),   # test55 STT
    ("She was asking him, are you tired?", "She", "ask", "Are you tired?"),
    ("Pierre was saying, this metal glows.", "Pierre", "say", "This metal glows."),
])
def test55_progressive_speech_is_read_on_the_fast_path(text, who, kind, words):
    s = beats.speech(text)
    assert s is not None and (s.who, s.kind, s.words) == (who, kind, words) and gate(text) == ""


def test55_fast_path_times_and_no_name_from_a_verb():
    assert beats.beat("That winter, they worked day and night in the cold shed.").when == "that winter"
    assert beats.beat("A decade later that Mary thought...").when == "a decade later"
    assert beats.beat("Seeing these metal glues in the dark.").names == []
    assert beats.speech("The girl was shouting at the dog.") is None and beats.speech("Perry was saying this glows.") is None


def test55_back_to_the_slides_is_no_lecture_content():
    from copilot.understanding.filter import UtteranceFilter
    f = UtteranceFilter()
    assert f.classify("Back to the slides.").kind == "meta"
    assert f.classify("The bus went back to the station.").kind == "content"


async def test55_a_lone_place_word_is_the_open_scenes_place_and_the_search_is_the_person():
    deck, eng, clock, talk, ext = await curie({})
    clock.t += 8
    await talk.say("A decade later, Mary thought.")
    await talk.say("Sorbonne.")
    s = story_on(deck)
    assert [c.name for c in s.cast] == ["Marie Curie", "Pierre Curie"]          # "Sorbonne" is no person
    assert s.scenes[-1].where == "Sorbonne" and s.scenes[-1].query == "Sorbonne"
    assert s.scenes[-1].when == "a decade later"


async def test56_a_lone_yeah_makes_no_scene():
    deck, eng, clock, talk, ext = await curie({})
    n = len(story_on(deck).scenes)
    clock.t += 8
    await talk.say("Yeah.")
    assert len(story_on(deck).scenes) == n


async def test55_a_repeated_speech_line_is_one_bubble():
    deck, eng, clock, talk, ext = await curie({})
    for _ in range(2):
        await talk.say("Pierre said, let us work together.")
    assert len(story_on(deck).scenes[-1].bubbles) == 1


def test_aside_only_when_the_line_has_no_story_words():
    assert chk({"type": "aside"}, "Okay, everyone, listen carefully now.")[0] == {"type": "aside"}
    assert chk({"type": "aside"}, "She studied physics in Paris.")[0] is None


def test_the_prompt_is_bounded_and_its_prefix_never_changes():
    a = sx.messages([("Marie Curie", "she")], "1895 · the lab", ["l1", "l2", "l3"], "line", "")
    b = sx.messages([], "", [], "other", "narration")
    assert a[0] == b[0] and a[0]["content"] == sx.PREFIX
    assert "l1" not in a[1]["content"] and "l2 / l3" in a[1]["content"]


# ---- the controller ---------------------------------------------------------------------------------------------
CURIE = ["Let me tell you the story of Marie Curie.", "In 1891, Marie moved to Paris.",
         "She studied physics at the university.", "In 1895, she met Pierre Curie in the lab."]
WE = "We have said, let us work together."
SPEECH = json.dumps({"type": "speech", "who": "Pierre Curie", "to": "", "kind": "say", "words": "let us work together"})


async def curie(answers, delay_s=0.0):
    bus, deck, eng, clock, talk, asked = await story_lecture()
    eng._story.extractor = ext = ReplayStoryExtractor(answers, delay_s=delay_s)
    for line in CURIE:
        clock.t += 8
        await talk.say(line)
    return deck, eng, clock, talk, ext


async def test53_a_garbled_speaker_is_read_as_pierre_and_his_bubble_shows():
    deck, eng, clock, talk, ext = await curie({WE: SPEECH})
    assert len(ext.calls) == 0                     # the four lines were read whole: 0 tokens
    await talk.say(WE)
    await eng._story.settle()
    s = story_on(deck)
    bub = s.scenes[-1].bubbles[-1]
    assert s.member(bub.speaker).name == "Pierre Curie" and bub.text == "Let us work together"
    assert WE not in s.scenes[-1].lines and len(ext.calls) == 1
    await talk.say("She replied, yes, let us find new elements.")
    await eng._story.settle()
    s = story_on(deck)
    assert s.member(s.scenes[-1].bubbles[-1].speaker).name == "Marie Curie"


async def test_lines_said_while_one_waits_land_after_it_in_said_order():
    deck, eng, clock, talk, ext = await curie({WE: SPEECH}, delay_s=0.05)
    await talk.say(WE)
    await talk.say("She replied, yes, let us find new elements.")   # no call, but it queues behind
    assert not story_on(deck).scenes[-1].bubbles                     # nothing yet: the first one waits
    await eng._story.settle()
    names = [story_on(deck).member(b.speaker).name for b in story_on(deck).scenes[-1].bubbles]
    assert names == ["Pierre Curie", "Marie Curie"] and len(ext.calls) == 1


async def test_a_refused_or_failed_answer_leaves_the_fast_reading():
    bad = json.dumps({"type": "speech", "who": "Albert", "kind": "say", "words": "let us work together"})
    deck, eng, clock, talk, ext = await curie({WE: bad})
    await talk.say(WE)
    await eng._story.settle()
    s = story_on(deck)
    assert not s.scenes[-1].bubbles and WE in s.scenes[-1].lines       # narration, as without the LLM
    assert eng._story.stats.llm_refused == 1 and "Albert" not in [c.name for c in s.cast]

    class Down:
        async def read(self, msgs, line):
            raise RuntimeError("every model failed")
    eng._story.extractor = Down()
    line = "Then they walked into a dusty shed."
    await talk.say(line)
    await eng._story.settle()
    assert line in story_on(deck).scenes[-1].lines and eng._story.stats.llm_failed == 1


async def test_a_narration_answer_adds_its_said_time_and_place():
    line = "A decade after that, they worked in a tiny shed."
    ans = json.dumps({"type": "narration", "when": "A decade after that", "where": "a tiny shed", "people": [],
                      "new_scene": True})
    deck, eng, clock, talk, ext = await curie({line: ans})
    n = len(story_on(deck).scenes)
    clock.t += 8
    await talk.say(line)
    await eng._story.settle()
    s = story_on(deck)
    assert len(s.scenes) == n + 1 and s.scenes[-1].when == "a decade after that" and s.scenes[-1].where == "a tiny shed"


async def test_the_end_cue_while_a_line_waits_puts_it_in_the_recap():
    line = "A decade after that, they worked in a tiny shed."
    deck, eng, clock, talk, ext = await curie({line: json.dumps({"type": "aside"})}, delay_s=0.2)
    await talk.say(line)
    await talk.say("That's the end of the story.")
    await eng._story.settle()
    assert eng._sims.mode is None
    text = str(next(x for x in deck.slides if x.title.startswith("Recap")).model_dump())
    assert "tiny shed" in text


async def test_an_aside_is_not_a_story_line():
    line = "Okay everyone, look at the board now."
    deck, eng, clock, talk, ext = await curie({line: json.dumps({"type": "aside"})})
    assert gate(line) == ""                       # "the board" is no place: no call at all
    await talk.say(line)
    await eng._story.settle()
    assert len(ext.calls) == 0
