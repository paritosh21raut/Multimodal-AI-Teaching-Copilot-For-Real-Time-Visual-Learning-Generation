"""F-013 S1: spoken structure cues. Lines are taken from the recorded tests 1-30 (verify_results)."""
import pytest

from copilot.understanding.cues import detect


@pytest.mark.parametrize("line, name", [
    ("Let us learn about fluid mechanics.", "Fluid mechanics"),                        # test2
    ("Let us understand what chemistry is.", "Chemistry"),                             # test3
    ("Now let us understand the third law of Newton.", "Third law of Newton"),         # test1
    ("Now let's talk about the Cardiovascular System.", "Cardiovascular System"),      # test12
    ("The second topic is Differential Calculus.", "Differential Calculus"),           # test23
    ("Eleventh topic is Differential Equation. Differential Equation is an equation involving",
     "Differential Equation"),                                                          # test23
    ("7th topic is Jupiter, the largest planet.", "Jupiter"),                          # test21
    ("Fifth topic is What is a kernel?", "Kernel"),                                    # test25
    ("First topic is what is VLSI? VLSI stands for Very Large Scale Integration.", "VLSI"),  # test26
    ("Introduction to Ethical Hacking Ethical hacking is an important branch", "Ethical Hacking"),  # test27
    ("So, 8th topic is how Wi-Fi works.", "How Wi-Fi works"),                          # test24
    ("What is meant by unbalanced force?", "Unbalanced force"),                        # test1
    ("What is Economics?", "Economics"),                                               # test29
    ("The modes of reproduction in plants.", "Modes of reproduction in plants"),       # test11 (heading)
    ("Fifth topic is Deserts and", "Deserts"),                                         # test28 (cut by STT)
])
def test_topic_announcements(line, name):
    cue = detect(line).of("topic")
    assert cue is not None and cue.name == name


@pytest.mark.parametrize("line", [
    "Let us study them individually.",                         # test4: a pronoun, not a topic
    "What is the right side of the book?",                     # test12: a question to the class
    "Chemistry is the branch of science which deals with the composition.",
    "The free electron is repelled to the left.",
    "Let's start with what",
    "What if we push it up the slope with 20 newtons? Let's see what happens.",  # F-014 incline_live run
    "Now let us see whether the block moves.",
])
def test_no_topic(line):
    assert detect(line).of("topic") is None


@pytest.mark.parametrize("line, head, items, count", [
    ("Satellites are classified into two main types, natural satellite and artificial satellites.",
     "Satellites", ("Natural satellite", "Artificial satellites"), 2),                 # test22
    ("Based on flexibility and mobility, joints can be further classified into movable joints and immovable joints.",
     "Based on flexibility and mobility, joints", ("Movable joints", "Immovable joints"), 0),  # test10
    ("An element can be a metal, non-metal or a metalloid.", "Element", ("Metal", "Non-metal", "Metalloid"), 0),
    ("Compounds can be of two types, Inorganic, Organic.", "Compounds", ("Inorganic", "Organic"), 2),
    ("There are two types of pollination, safe glaua pollination and cross-pollination.", "Pollination",
     ("Safe glaua pollination", "Cross-pollination"), 2),                              # test11
    ("Sexual reproduction is divided into three categories.", "Sexual reproduction", (), 3),
])
def test_lists(line, head, items, count):
    cue = detect(line).of("list")
    assert cue is not None
    assert (cue.name, cue.items, cue.count) == (head, items, count)


def test_count_is_a_number_not_an_adjective():
    cue = detect("In chemical classification it can be further classified into pure substances or mixtures.").of("list")
    assert cue is not None and cue.items == ("Pure substances", "Mixtures") and cue.count == 0


@pytest.mark.parametrize("line, items", [
    ("Difference between ethical hacking and penetration testing. Ethical hacking and penetration testing are",
     ("Ethical hacking", "Penetration testing")),                                     # test27
    ("Topic 9 FPGA vs ASIC", ("FPGA", "ASIC")),                                        # test26
    ("Let us compare isotopes, isobars and isotones.", ("Isotopes", "Isobars", "Isotones")),
])
def test_comparisons(line, items):
    cue = detect(line).of("compare")
    assert cue is not None and cue.items == items


@pytest.mark.parametrize("line", [
    # "difference" inside a sentence is not a comparison announcement (tests 8, 30)
    "The loss function is a difference between actual and predicted values.",
    "The voltage across the resistor equals the difference between the source voltage and the Zener voltage.",
])
def test_no_comparison(line):
    assert detect(line).of("compare") is None


@pytest.mark.parametrize("line, item", [
    ("First one is n-type semiconductor.", "N-type semiconductor"),                   # test30
    ("Second is P-type semiconductor.", "P-type semiconductor"),
    ("Third one is time sharing operating system. Time sharing operating system allows", "Time sharing operating system"),
])
def test_ordinal_items(line, item):
    assert detect(line).item == item
