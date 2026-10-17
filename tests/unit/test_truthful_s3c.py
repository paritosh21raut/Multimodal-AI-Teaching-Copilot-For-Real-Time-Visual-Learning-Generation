"""F-013 S3c: truthfulness. E1: a concern whose words are on no element no longer claims "the slide shows the
correction": the engine says what the slides show (CorrectionPlaced) and Show correction can replace items that
state the teacher's version in other words. Real cases from tests 1-30 and the F-012 heart lecture."""
from copilot.core.bus import EventBus
from copilot.core.events import CorrectionPlaced
from copilot.core.interpretation import ConcernItem
from copilot.display.hub import DisplayHub
from copilot.presentation.engine import slide_version
from tests.unit.test_presentation_engine import _resolve, act, make, ready, send, texts


def test_which_version_an_element_states():
    # the heart lecture (F-012 live run, session 20261012-230109): the model's act kept the teacher's words
    assert slide_version("Right atrium, left atrium and one ventricle", "one ventricle", "two ventricles") == "wrong"
    # test4: the model wrote the right definition in its own words
    assert slide_version("Isotopes: same atomic number, different mass numbers", "same number of neutrons",
                         "same atomic number but different mass numbers") == "right"
    # test8: the model's point does not say "AI is deep learning"; it has the correction's "methods"
    assert slide_version("AI uses machine learning and deep learning methods to complete human tasks",
                         "AI is deep learning", "AI includes many methods; deep learning is a subset") == "right"
    # neither version's own words
    assert slide_version("The heart pumps blood", "one ventricle", "two ventricles") == ""
    # test13: "situated above the hypothalamus" for "located precisely below the thalamus"
    assert slide_version("A small essential structure in the limbic system, situated above the hypothalamus",
                         "existential, located precisely below the thalamus",
                         "essential, located above the hypothalamus") == "right"


async def _placed(bus):
    got = []

    async def grab(e):
        got.append(e)
    bus.subscribe("t_placed", grab, [CorrectionPlaced])
    return got


async def test_slide_kept_the_teachers_words_in_other_words_card_says_so_and_show_correction_replaces_them():
    """The F-012 heart bug: the card said "slide shows the correction", the slide kept "one ventricle"."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    placed = await _placed(bus)
    c = ConcernItem(claim="The heart has two atria and one ventricle", issue="The human heart has two ventricles",
                    confidence=0.9, suggested_correction="The heart has two atria and two ventricles",
                    wrong="only one ventricle", right="two ventricles", lines=[1])
    await send(bus, ready("Human Heart", "Chambers", [act("explanation", points=[
        "Right atrium, left atrium and one ventricle", "The heart pumps blood"])],
        relation="new_topic", concerns=[c]))
    assert placed[-1].shows == "said" and placed[-1].elements == 1
    concern = store.snapshot().concerns[0]
    await _resolve(bus, concern.id, "accept")
    assert texts(deck.live) == ["The heart has two atria and two ventricles", "The heart pumps blood"]
    assert placed[-1].shows == "correction"
    await _resolve(bus, concern.id, "keep")  # Show what I said: the item comes back exactly
    assert texts(deck.live) == ["Right atrium, left atrium and one ventricle", "The heart pumps blood"]
    assert placed[-1].shows == "said"
    await eng.stop()


async def test_model_already_wrote_it_correctly_nothing_to_switch():
    """test4: "isotopes ... same number of neutrons" -> the model's point is the right definition, reworded."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    placed = await _placed(bus)
    c = ConcernItem(claim="Isotopes are species having same number of neutrons", issue="same atomic number",
                    confidence=0.95, suggested_correction="Isotopes have the same atomic number but different mass numbers",
                    wrong="same number of neutrons", right="same atomic number but different mass numbers", lines=[1])
    await send(bus, ready("Atomic Structure", "Isotopes", [act("explanation", points=[
        "Isotopes: same atomic number, different mass numbers"])], relation="new_topic", concerns=[c]))
    assert placed[-1].shows == "rewritten" and placed[-1].elements == 0
    assert texts(deck.live) == ["Isotopes: same atomic number, different mass numbers"]
    await eng.stop()


async def test_concern_whose_line_put_nothing_on_the_slide_is_not_on_the_slide():
    """test10: "four bones" -> "brain and spinal cord": the line gave no item (a garbled fragment)."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    placed = await _placed(bus)
    c = ConcernItem(claim="The central nervous system has four bones", issue="CNS = brain and spinal cord",
                    confidence=0.95, suggested_correction="The central nervous system is the brain and spinal cord",
                    wrong="four bones", right="brain and spinal cord", lines=[3])
    await send(bus, ready("Nervous System", "Parts", [act("explanation", lines=[1], points=[
        "Nervous system controls body functions"])], relation="new_topic", concerns=[c]))
    assert placed[-1].shows == "absent"
    await eng.stop()


async def test_exact_words_still_switch_as_before():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    placed = await _placed(bus)
    c = ConcernItem(claim="Neptune is the hottest planet", issue="Venus", confidence=0.95,
                    suggested_correction="Venus is the hottest planet", wrong="Neptune", right="Venus", lines=[1])
    await send(bus, ready("Solar System", "Planets", [act("explanation", points=["Venus is the hottest planet"])],
                          relation="new_topic", concerns=[c]))
    assert placed[-1].shows == "correction" and placed[-1].elements == 1
    await _resolve(bus, store.snapshot().concerns[0].id, "keep")
    assert placed[-1].shows == "said" and texts(deck.live) == ["Neptune is the hottest planet"]
    await eng.stop()


async def test_card_gets_what_the_slide_shows_even_when_the_placement_comes_first():
    from copilot.core.events import ConcernRaised

    bus = EventBus()
    hub = DisplayHub(bus)
    hub.attach()
    ctl = hub.connect("control")
    await ctl.next_batch()
    card = {"id": "c1", "kind": "factual", "status": "open", "applied": True, "claim": "x", "suggested_correction": "y"}
    await bus.publish(CorrectionPlaced(concern_id="c1", shows="absent"))
    await bus.publish(ConcernRaised(concern=card))
    await bus.drain()
    assert hub.concerns["c1"]["shows"] == "absent" and hub.concerns["c1"]["applied"] is False
    await bus.publish(CorrectionPlaced(concern_id="c1", shows="rewritten"))
    await bus.drain()
    assert hub.concerns["c1"]["shows"] == "rewritten" and hub.concerns["c1"]["applied"] is True
    msgs = await ctl.next_batch()
    assert [m["concern"]["shows"] for m in msgs if m["type"] == "concern"][-1] == "rewritten"
    await bus.close()


# ---- E2: what the teacher did not say ----------------------------------------------------------------------------
from copilot.core.interpretation import CompareRow, ContentItems, DiscourseAct, Interpretation, Pair  # noqa: E402
from copilot.understanding.gate import BufferedLine  # noqa: E402
from copilot.understanding.interpreter import _comparison_direction, _drop_cut_off, spoken_order  # noqa: E402
from copilot.understanding.quality import cut_off  # noqa: E402

T15 = ("The kinetic energy of the photoelectrons are much higher for blue light than for green light because blue light "
       "has a greater frequency than green light.")


def test_which_way_a_spoken_comparison_goes():
    assert spoken_order(T15, "Blue light", "Green light") == 1 and spoken_order(T15, "Green light", "Blue light") == -1
    assert spoken_order("For example, the frequency of blue light is greater than the red light.", "blue", "red") == 1
    assert spoken_order("Air is less dense than water.", "Water", "Air") == 1
    assert spoken_order("Mercury is hotter than Mars but Mars is colder than Venus", "Mars", "Venus") == -1
    assert spoken_order("Blue light and green light both eject electrons.", "Blue light", "Green light") == 0


def _unit(text):
    return [BufferedLine("s1", text, 0.0, 4.0)]


def test_reversed_comparison_cells_are_swapped_test15():
    """test15: the model's two-way table said blue "Lower" | green "Higher"."""
    old = Interpretation(topic="Photoelectric Effect", relation="same_concept", acts=[DiscourseAct(act="comparison", lines=[1], items=ContentItems(
        compare=["Blue light", "Green light"], pairs=[Pair(aspect="Kinetic energy", left="Lower", right="Higher")]))])
    new = _comparison_direction(old, _unit(T15))
    assert (new.acts[0].items.pairs[0].left, new.acts[0].items.pairs[0].right) == ("Higher", "Lower")
    rows = old.model_copy(update={"acts": [DiscourseAct(act="comparison", lines=[1], items=ContentItems(
        compare=["Blue light", "Green light"], rows=[CompareRow(aspect="Kinetic energy", values=["much lower", "higher"]),
                                                     CompareRow(aspect="Colour", values=["blue", "green"])]))]})
    out = _comparison_direction(rows, _unit(T15)).acts[0].items.rows
    assert out[0].values == ["higher", "much lower"] and out[1].values == ["blue", "green"]  # only comparatives
    right = _comparison_direction(new, _unit(T15))
    assert right is new  # already the way it was said: untouched


def test_items_cut_off_mid_sentence_leave_the_slide():
    # the S3c A/B (test8#86) and the recorded test30 answer
    assert cut_off("Current neural networks differ from feed-forward networks as the output of")
    assert cut_off("Each dipole has an")
    for fine in ("OS initializes the system when computer turns on", "AND", "Holes attract a valence electron at point A",
                 "Jupiter has no solid surface to stand on", "Physiology deals with the internal"):
        assert not cut_off(fine), fine
    it = Interpretation(topic="ML", relation="same_concept", acts=[DiscourseAct(act="explanation", lines=[1], items=ContentItems(points=[
        "Output layer produces final predictions",
        "Current neural networks differ from feed-forward networks as the output of"]))])
    assert _drop_cut_off(it).acts[0].items.points == ["Output layer produces final predictions"]


def test_the_said_rule_is_in_the_live_prompt():
    from copilot.understanding import prompt as P
    assert "Never state a fact the NEW lines do not say" in P.SYSTEM_PROMPT
    assert "{said_rule}" not in P.system_prompt(said=False) and "Never state" not in P.system_prompt(said=False)


def test_equations_the_library_was_missing_in_tests_1_30():
    from copilot.presentation import equations as Q
    assert Q.named("Kjotch's law implies") == ["kirchhoff_current", "kirchhoff_voltage"]   # test30, misheard
    assert Q.named("Apply Kirchhoff's voltage law and you") == ["kirchhoff_voltage"]
    assert Q.named("O'Hams law") == ["ohm"]                                                # test30, misheard
    assert Q.named("Pascal's law.") == ["pascal"]                                          # test2
    assert Q.named("The straight line can be represented using the equation.") == ["straight_line"]  # test23
    assert Q.named("Over time, third law of thermodynamics, trophy of the perfect crystal") == []    # a statement
