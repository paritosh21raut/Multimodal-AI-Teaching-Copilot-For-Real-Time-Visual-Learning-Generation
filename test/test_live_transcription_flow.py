from __future__ import annotations

from app.audio.live_transcript_manager import (
    LiveTranscriptManager,
)


class FakeLectureBackend:

    def __init__(self):

        self.current_topic = None
        self.slide_number = 0

    def analyze(self, text: str):

        lower = text.lower()

        # ------------------------------------------------------
        # Ignore obvious irrelevant speech
        # ------------------------------------------------------

        irrelevant_phrases = (
            "previous transcamp",
            "why my previous",
            "my notebook",
            "where is my",
            "sorry",
        )

        if any(
            phrase in lower
            for phrase in irrelevant_phrases
        ):

            return {
                "relevant": False,
                "topic": self.current_topic,
                "confidence": 0.0,
                "slide_action": "KEEP CURRENT SLIDE",
            }

        # ------------------------------------------------------
        # New topic
        # ------------------------------------------------------

        if (
            "types of microcontrollers"
            in lower
        ):

            self.current_topic = (
                "Types of Microcontrollers"
            )

            self.slide_number += 1

            return {
                "relevant": True,
                "topic": self.current_topic,
                "confidence": 0.94,
                "slide_action": "NEW SLIDE",
                "slide_number": self.slide_number,
                "title": "Types of Microcontrollers",
            }

        # ------------------------------------------------------
        # First topic
        # ------------------------------------------------------

        if self.current_topic is None:

            self.current_topic = (
                "Microcontrollers"
            )

            self.slide_number = 1

            return {
                "relevant": True,
                "topic": self.current_topic,
                "confidence": 0.98,
                "slide_action": "NEW SLIDE",
                "slide_number": 1,
                "title": "Introduction to Microcontrollers",
            }

        # ------------------------------------------------------
        # Same topic
        # ------------------------------------------------------

        return {
            "relevant": True,
            "topic": self.current_topic,
            "confidence": 0.91,
            "slide_action": "SAME SLIDE",
            "slide_number": self.slide_number,
        }


def print_analysis(
    backend,
    chunk,
):

    result = backend.analyze(
        chunk
    )

    print()
    print("=" * 70)
    print("BACKEND ANALYSIS REPORT")
    print("=" * 70)

    print(
        f"Input       : {chunk}"
    )

    print(
        f"Relevant    : "
        f"{result['relevant']}"
    )

    print(
        f"Topic       : "
        f"{result['topic']}"
    )

    print(
        f"Confidence  : "
        f"{result['confidence']:.2f}"
    )

    print(
        f"Slide       : "
        f"{result['slide_action']}"
    )

    if "slide_number" in result:

        print(
            f"Slide No.   : "
            f"{result['slide_number']}"
        )

    if "title" in result:

        print(
            f"Title       : "
            f"{result['title']}"
        )

    print(
        "=" * 70
    )


def test_live_transcription_flow():

    manager = (
        LiveTranscriptManager()
    )

    backend = (
        FakeLectureBackend()
    )

    print()
    print("=" * 70)
    print("LIVE TRANSCRIPTION TEST")
    print("=" * 70)

    # ==========================================================
    # SIMULATED LIVE SPEECH
    # ==========================================================

    snapshots = [
        (
            "Today we will learn about "
            "microcontrollers."
        ),

        (
            "Today we will learn about "
            "microcontrollers. "
            "A microcontroller is a small "
            "computer on a single chip."
        ),

        (
            "Today we will learn about "
            "microcontrollers. "
            "A microcontroller is a small "
            "computer on a single chip. "
            "It contains CPU, memory and "
            "input output peripherals."
        ),
    ]

    print()
    print(
        "LIVE TRANSCRIPT:"
    )

    previous_display = ""

    for snapshot in snapshots:

        manager.update(
            snapshot
        )

        # Do not print the same complete
        # transcript multiple times.
        if snapshot != previous_display:

            previous_display = snapshot

            print(
                f"\r{snapshot}",
                end="",
            )

    print()
    print()

    # ==========================================================
    # ANALYZE COMPLETED CONTENT
    # ==========================================================

    chunk = (
        manager.get_new_analysis_text(
            snapshots[-1],
            force=True,
        )
    )

    assert chunk is not None

    manager.mark_analyzed(
        chunk
    )

    print_analysis(
        backend,
        chunk,
    )

    # ==========================================================
    # CONTINUE SAME TOPIC
    # ==========================================================

    same_topic = (
        snapshots[-1]
        + " "
        "Microcontrollers are used "
        "in embedded systems."
    )

    manager.update(
        same_topic
    )

    new_chunk = (
        manager.get_new_analysis_text(
            same_topic,
            force=True,
        )
    )

    if new_chunk:

        manager.mark_analyzed(
            new_chunk
        )

        print_analysis(
            backend,
            new_chunk,
        )

    # ==========================================================
    # NEW TOPIC
    # ==========================================================

    new_topic = (
        same_topic
        + " "
        "Now let's discuss the types "
        "of microcontrollers."
    )

    manager.update(
        new_topic
    )

    new_topic_chunk = (
        manager.get_new_analysis_text(
            new_topic,
            force=True,
        )
    )

    assert new_topic_chunk is not None

    manager.mark_analyzed(
        new_topic_chunk
    )

    print_analysis(
        backend,
        new_topic_chunk,
    )

    # ==========================================================
    # IRRELEVANT SPEECH
    # ==========================================================

    irrelevant = (
        new_topic
        + " "
        "Why my previous transcamp "
        "is not available."
    )

    manager.update(
        irrelevant
    )

    irrelevant_chunk = (
        manager.get_new_analysis_text(
            irrelevant,
            force=True,
        )
    )

    if irrelevant_chunk:

        manager.mark_analyzed(
            irrelevant_chunk
        )

        print_analysis(
            backend,
            irrelevant_chunk,
        )

    # ==========================================================
    # FINAL
    # ==========================================================

    print()
    print("=" * 70)
    print("TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":

    test_live_transcription_flow()