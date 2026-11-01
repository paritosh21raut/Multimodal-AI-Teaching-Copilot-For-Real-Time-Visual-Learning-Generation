"""V3 ST1 story core: cues, beats, speech bubbles, scenes, pictures, the mode and its end (0 tokens)."""
from __future__ import annotations

import pytest

from copilot.core.events import Command, CommandReceived, ImageReady, ImageRequested
from copilot.scene.detector import SceneDetector
from copilot.simulation.detector import SimulationDetector
from copilot.story import beats
from copilot.story.detector import StoryDetector, cue, ends
from copilot.presentation.story import DWELL_S, protagonist, title_of
from tests.unit.test_presentation_engine import act, make, ready, send
from tests.unit.test_simulation import Lines


# ---- detector ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, want", [
    ("Let me tell you the story of Albert Einstein.", "strong"),
    ("Once upon a time there was a little boy called Ravi.", "strong"),
    ("Imagine you are a red blood cell in the heart.", "strong"),
    ("Let us follow a drop of water through the water cycle.", "strong"),
    ("In 1905, a young clerk in Bern wrote four papers.", "weak"),
    ("Imagine you are a passenger in a bus that brakes suddenly.", ""),   # the stage's physics
    ("Imagine you are pushing a box with a force of 10 newtons.", ""),
    ("The mitochondria is the powerhouse of the cell.", ""),
    ("Follow the steps on the slide.", ""),
])
def test_story_cues(text, want):
    assert cue(text) == want


def test_end_cues():
    assert ends("And that's the end of the story.") and ends("The end.")
    assert not ends("At the end of the day the drop falls as rain.")


# ---- speech -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, who, kind, to, words", [
    ('A said, "I love playing football."', "A", "say", "", "I love playing football."),
    ('B says, "Me too!"', "B", "say", "", "Me too!"),
    ("Ravi said, I love playing football.", "Ravi", "say", "", "I love playing football."),
    ('"Me too," said Asha.', "Asha", "say", "", "Me too"),
    ("Ravi asked Asha, do you play cricket?", "Ravi", "ask", "Asha", "Do you play cricket?"),
    ("Asha said to Ravi, let us play.", "Asha", "say", "Ravi", "Let us play."),
    ("The boy shouted, run!", "The boy", "shout", "", "Run!"),
    ("He replied, yes every day.", "He", "reply", "", "Yes every day."),
])
def test_speech_is_found_with_or_without_quote_marks(text, who, kind, to, words):
    s = beats.speech(text)
    assert s is not None and (s.who, s.kind, s.to, s.words) == (who, kind, to, words)


@pytest.mark.parametrize("text", ["Ravi said that he was tired.", "Ravi told him a story.",
                                  "The teacher said nothing.", "A drop of water starts in the ocean.",
                                  "Ravi laughed at the joke."])
def test_narration_is_not_speech(text):
    assert beats.speech(text) is None


def test_a_speaker_alone_waits_for_the_words():
    s = beats.speech("Ravi said,")
    assert s is not None and s.who == "Ravi" and s.words == ""


# ---- beats ------------------------------------------------------------------------------------------------------
def test_beats_carry_said_time_place_and_people():
    b = beats.beat("In 1905, a young clerk in Bern wrote four papers.")
    assert (b.when, b.where, b.people, b.cuts) == ("1905", "Bern", ["a young clerk"], True)
    b = beats.beat("Then the drop rises into the clouds.")
    assert (b.marker, b.where) == ("then", "the clouds")
    b = beats.beat("Years later, Albert Einstein moved to Berlin.")
    assert b.names == ["Albert Einstein"] and b.where == "Berlin" and b.when == "years later"
    assert not beats.beat("The sun heats the water.").cuts


def test_captions_are_the_said_words_shortened():
    assert beats.caption("Okay so let me tell you a story. A boy lived in a village.") == "A boy lived in a village."
    long = "The drop " + "travels very far " * 12 + "away."
    c = beats.caption(long)
    assert len(c) <= beats.CAPTION_MAX + 1 and c.endswith("…") and c.startswith("The drop travels")


def test_protagonist_and_title_from_the_cue():
    assert protagonist("Let us follow a drop of water through the water cycle.") == "a drop of water"
    assert protagonist("Let me tell you the story of Albert Einstein.") == "Albert Einstein"
    assert protagonist("Imagine you are a red blood cell in the heart.") == "a red blood cell"
    assert title_of("Once upon a time there was a boy.") == "Story"
    assert title_of("Let us follow a drop of water through the sky.") == "A drop of water"


def test_picture_nouns_never_guess_a_face_from_a_name():
    assert [beats.picture_noun(x) for x in ("a drop of water", "a young clerk", "Albert Einstein", "Ravi",
                                            "the boy")] == ["droplet", "office worker", "person", "person", "boy"]


# ---- the controller ---------------------------------------------------------------------------------------------
async def story_lecture(**settings):
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False, stage=False, **settings)
    sim, scene = SimulationDetector(bus), SceneDetector(bus)
    sim.story_cues = scene.story_cues = True
    sim.attach()
    scene.attach()
    StoryDetector(bus).attach()
    eng._story.fetch_pictures = False
    asked: list[ImageRequested] = []

    async def keep(ev):
        asked.append(ev)
    bus.subscribe("test_images", keep, [ImageRequested])
    await send(bus, ready("Physics history", "Physics history", [act("explanation", points=["Physics changed"])],
                          relation="new_topic"))
    return bus, deck, eng, clock, Lines(bus), asked


def story_on(deck):
    return next((b.story for b in deck.live.blocks if b.type == "story"), None)


async def test_a_cue_opens_a_story_slide_and_beats_make_scenes():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let me tell you the story of Albert Einstein.")
    s = story_on(deck)
    assert s is not None and deck.sim_mode == deck.live.id and deck.live.title == "Albert Einstein"
    assert [c.name for c in s.cast] == ["Albert Einstein"] and len(s.scenes) == 1
    await talk.say("In 1905, a young clerk in Bern wrote four papers.")
    s = story_on(deck)
    assert len(s.scenes) == 2 and s.scenes[1].when == "1905" and s.scenes[1].where == "Bern"
    assert s.scenes[1].caption == "In 1905, a young clerk in Bern wrote four papers."
    assert s.scenes[1].query == "Bern" and any(r.query == "Bern" and r.reason.startswith("story:") for r in asked)
    await talk.say("He worked six days a week.")           # no marker: the same scene
    assert len(story_on(deck).scenes) == 2 and story_on(deck).scenes[1].caption == "He worked six days a week."


async def test_a_newer_scene_waits_for_the_dwell_time():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let us follow a drop of water through the water cycle.")
    await talk.say("The drop starts in the ocean.")
    await talk.say("Then the sun heats it and it rises into the sky.")
    s = story_on(deck)
    assert len(s.scenes) >= 2 and s.shown < len(s.scenes) - 1
    clock.t += DWELL_S + 0.5
    await eng._story.tick()
    assert story_on(deck).shown == len(story_on(deck).scenes) - 1  # the dwell passed: the newest scene
    assert all(eng._story.open.protagonist in sc.cast for sc in story_on(deck).scenes if sc.lines)


async def test_dialogue_makes_bubbles_at_each_speaker_and_no_scene():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Once upon a time, two friends played in a park.")
    n = len(story_on(deck).scenes)
    await talk.say('A said, "I love playing football."')
    await talk.say('B says, "Me too!"')
    s = story_on(deck)
    assert len(s.scenes) == n
    sc = s.scenes[s.shown]
    a, b = (s.member(x.speaker) for x in sc.bubbles)
    assert [x.text for x in sc.bubbles] == ["I love playing football.", "Me too!"]
    assert (a.name, b.name) == ("A", "B") and a.id in sc.cast and b.id in sc.cast
    assert all("football" not in x for x in (sc.caption,))   # speech never goes into the caption


async def test_split_speech_and_a_pronoun_reply():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Once upon a time, Ravi met Asha at the park.")
    await talk.say("Ravi asked Asha,")
    await talk.say("Do you like football?")
    await talk.say("She replied, yes I love it.")
    s = story_on(deck)
    sc = s.scenes[-1]
    assert [(s.member(x.speaker).name, x.kind, x.text) for x in sc.bubbles] == [
        ("Ravi", "ask", "Do you like football?"), ("Asha", "reply", "Yes I love it.")]
    assert s.member(sc.bubbles[0].to).name == "Asha"


async def test_an_image_lands_in_its_scene_and_the_same_place_reuses_it():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let me tell you the story of Albert Einstein.")
    await talk.say("In 1905, a young clerk in Bern wrote four papers.")
    req = next(r for r in asked if r.query == "Bern")
    await send(bus, ImageReady(request_id=req.request_id, slide_id=req.slide_id, query="Bern",
                               images=[{"id": "abc123ef", "width": 800, "height": 600, "alt": "Bern old town",
                                        "source": "commons", "licence": "CC BY-SA 4.0", "author": "X"}]))
    sc = next(x for x in story_on(deck).scenes if x.query == "Bern")
    assert sc.image == "/media/abc123ef.jpg" and "commons" in sc.credit
    assert eng._sims.mode is not None and eng._sims.mode.kind == "story"   # the slide's own image path untouched


async def test_end_cue_ends_the_story_and_slides_resume():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let me tell you the story of Albert Einstein.")
    slide = deck.live.id
    await talk.say("In 1905, a young clerk in Bern wrote four papers.")
    await talk.say("And that's the end of the story.")
    await eng._story.tick()
    assert deck.sim_mode is None and eng._sims.mode is None
    spec = eng._spec(slide)
    assert next(b for b in spec.blocks if b.type == "story").still


async def test_back_to_the_slides_ends_it_too_and_a_scene_cue_inside_is_the_storys():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Imagine you are a red blood cell in the heart.")
    assert story_on(deck) is not None
    await talk.say("Now imagine a square of side 4 cm.")      # inside a story: a line of the story
    assert eng._sims.mode.kind == "story"
    await talk.say("Okay, let's get back to the slides.")
    assert eng._sims.mode is None


async def test_a_weak_opener_is_a_suggest_chip_and_accept_opens_it():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("In 1905, a young clerk in Bern wrote four papers.")
    assert eng._sims.mode is None and eng._story.suggestion is not None
    sid = eng._story.suggestion.id
    await send(bus, CommandReceived(command=Command(kind="sim_accept", args={"id": sid})))
    s = story_on(deck)
    assert s is not None and s.scenes[0].where == "Bern"


async def test_teacher_prev_next_steps_the_shown_scene():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let us follow a drop of water through the water cycle.")
    await talk.say("The drop starts in the ocean.")
    clock.t += DWELL_S + 1
    await talk.say("Then the drop rises into the clouds.")
    s = story_on(deck)
    last = len(s.scenes) - 1
    assert s.shown == last
    await send(bus, CommandReceived(command=Command(kind="sim_prev", args={"slide_id": deck.live.id})))
    assert story_on(deck).shown == last - 1
    clock.t += DWELL_S + 1
    await eng._story.tick()
    assert story_on(deck).shown == last - 1          # held by the teacher
    await send(bus, CommandReceived(command=Command(kind="sim_next", args={"slide_id": deck.live.id})))
    assert story_on(deck).shown == last


async def test_setting_off_shows_no_story():
    bus, deck, eng, clock, talk, asked = await story_lecture(simulations="off")
    await talk.say("Let me tell you the story of Albert Einstein.")
    assert story_on(deck) is None and eng._sims.mode is None


async def test_another_story_cue_starts_the_next_story_and_the_place_is_the_backdrop():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let us follow a drop of water through the water cycle.")
    first = deck.live.id
    await talk.say("Once upon a time, Ravi met Asha at the park.")
    s = story_on(deck)
    assert deck.live.id != first and [c.name for c in s.cast] == ["Ravi", "Asha"]
    assert s.scenes[-1].query == "park"                       # the place, not a speaker
    assert next(b for b in eng._spec(first).blocks if b.type == "story").still


async def test_a_repeated_line_changes_nothing_and_a_lead_word_keeps_the_speech():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let us follow a drop of water through the water cycle.")
    await talk.say("The drop starts in the ocean.")
    clock.t += DWELL_S + 1
    await talk.say("Then the sun heats it and it rises into the sky.")
    before = story_on(deck)
    await talk.say("The drop starts in the ocean.")
    assert story_on(deck) == before
    s = beats.speech("Then a student asked Einstein, what is time?")
    assert s is not None and (s.who, s.kind, s.to, s.words) == ("a student", "ask", "Einstein", "What is time?")


# ---- review fixes -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", ["Follow the current through the circuit.", "Follow the arrows from left to right.",
                                  "Let us follow the electron through the wire.", "Now follow the steps from the textbook.",
                                  "Today we look at the life of a star.", "The life of plants depends on water.",
                                  "In 1990 the population increased sharply."])
def test_ordinary_lecture_lines_are_not_story_cues(text):
    assert cue(text) == ""


async def test_a_journey_line_inside_the_story_is_the_same_story():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let us follow a drop of water through the water cycle.")
    slide = deck.live.id
    await talk.say("The journey of the drop continues through the river.")
    assert deck.live.id == slide and [c.name for c in story_on(deck).cast] == ["a drop of water"]


async def test_an_image_after_the_story_ended_is_not_put_on_the_slide():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let me tell you the story of Albert Einstein.")
    slide = deck.live.id
    await talk.say("In 1905, a young clerk in Bern wrote four papers.")
    await talk.say("And that's the end of the story.")
    await eng._story.tick()
    req = next(r for r in asked if r.query == "Bern")
    await send(bus, ImageReady(request_id=req.request_id, slide_id=req.slide_id, query="Bern",
                               images=[{"id": "abc123ef", "width": 800, "height": 600, "alt": "Bern"}]))
    assert [b.type for b in eng._spec(slide).blocks] == ["story"]


async def test_a_seventh_speaker_still_gets_a_drawn_bubble():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Once upon a time, Ravi, Asha, Meena, Arjun, Kabir and Zoya met at the park.")
    await talk.say("Tom said, hello everyone.")
    s = story_on(deck)
    sc = s.scenes[s.shown]
    tom = sc.bubbles[-1].speaker
    assert s.member(tom).name == "Tom" and tom in sc.cast and len(sc.cast) <= 6


# ---- test51 fixes (the test's own STT words) --------------------------------------------------------------------
async def test51_a_cut_off_year_joins_its_sentence_and_patents_office_is_a_place():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let me tell you a story of Albert Einstein.")
    await talk.say("In 1905,")
    await talk.say("A young clerk in Bern wrote four famous papers.")
    s = story_on(deck)
    assert len(s.scenes) == 2 and s.scenes[1].caption == "In 1905, a young clerk in Bern wrote four famous papers."
    assert (s.scenes[1].when, s.scenes[1].where) == ("1905", "Bern")
    assert beats.beat("He works 6 days a week at the patent's office.").where == "the patent office"


async def test51_the_same_place_again_shows_that_scene_and_a_misheard_name_is_the_one_in_the_scene():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let us follow a drop of water through the water cycle.")
    await talk.say("The water drops in the ocean.")
    clock.t += DWELL_S + 1
    await talk.say("Then the sun hits it and it rises into the sky.")
    await talk.say("The drop starts in the ocean.")
    s = story_on(deck)
    assert len(s.scenes) == 3 and s.scenes[s.shown].where == "the ocean"
    await talk.say("Once upon a time, Ravi met Asha at the park.")
    await talk.say("Ravi said, I love playing football.")
    await talk.say("Harsha said, me too.")
    s = story_on(deck)
    assert [c.name for c in s.cast] == ["Ravi", "Asha"]
    assert [s.member(b.speaker).name for b in s.scenes[-1].bubbles] == ["Ravi", "Asha"]


async def test51_a_failed_download_is_tried_once_more():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    await talk.say("Let me tell you the story of Albert Einstein.")
    await talk.say("Years later, Einstein moved to Berlin.")
    req = next(r for r in asked if r.query == "Berlin")
    for _ in range(2):
        r = [x for x in asked if x.query == "Berlin"][-1]
        await send(bus, ImageReady(request_id=r.request_id, slide_id=r.slide_id, query="Berlin",
                                   reason="downloads failed"))
    assert len([x for x in asked if x.query == "Berlin"]) == 2 and req is not None
