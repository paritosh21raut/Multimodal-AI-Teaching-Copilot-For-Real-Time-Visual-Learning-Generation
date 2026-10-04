from copilot.stt.engine import guard


def test_accepts_normal_speech():
    assert guard("Plants make food using sunlight.", 3.0, -0.3, 0.05, 1.3) is None


def test_rejects_empty_and_no_speech():
    assert guard("  ", 2.0, -0.2, 0.0, 1.0) == "empty"
    assert guard("Hmm okay", 1.0, -1.5, 0.8, 1.0) == "no_speech"


def test_rejects_repetition_loops():
    assert guard("the the the the the the the the", 5.0, -0.4, 0.1, 3.1) == "repetitive"


def test_filler_hallucination_only_for_short_audio():
    assert guard("Thank you.", 1.2, -0.5, 0.3, 1.0) == "filler_hallucination"
    assert guard("Thank you.", 4.0, -0.5, 0.3, 1.0) is None  # long, real speech can say this
