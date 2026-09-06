from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORTS
# ============================================================

from app.audio.audio_pipeline import AudioPipeline
from app.audio.live_transcript_manager import LiveTranscriptManager
from app.speech.transcript_intelligence import transcript_intelligence


# ============================================================
# LIVE AUDIO TEST
# ============================================================

class LiveAudioTest:

    def __init__(self):
        self.output_dir = (
            PROJECT_ROOT
            / "outputs"
            / "live_audio_test"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.final_segments: list[dict[str, Any]] = []
        self.preview_count = 0

        # Incremental analysis performed during the live test.
        self.analysis_chunks: list[dict[str, Any]] = []

        # Final refinement of the complete authoritative transcript.
        self.final_analysis: dict[str, Any] | None = None

        self.start_time = 0.0
        self.end_time = 0.0

        self.transcript_manager = LiveTranscriptManager()

    # ========================================================
    # MAIN
    # ========================================================

    def run(self):

        print()
        print("=" * 70)
        print("LIVE AUDIO + TRANSCRIPT INTELLIGENCE TEST")
        print("=" * 70)
        print()
        print("Read your research paper naturally.")
        print()
        print("IMPORTANT:")
        print("- Speak continuously.")
        print("- Do not intentionally repeat sentences.")
        print("- Include technical terminology.")
        print("- Speak for at least 2-5 minutes.")
        print("- Pause naturally between sentences.")
        print()

        input("Press ENTER when you are ready.")

        pipeline = AudioPipeline(
            on_preview_transcript=self._handle_preview,
            on_final_transcript=self._handle_final,
        )

        self.start_time = time.time()

        try:
            print()
            print("[TEST] Starting microphone...")
            print("[TEST] START READING")
            print()

            pipeline.start()

        except KeyboardInterrupt:
            print()
            print("[TEST] Keyboard interrupt received.")

        except Exception as error:
            print()
            print(f"[TEST] Pipeline error: {error}")

        finally:
            self.end_time = time.time()

        print()
        print("[TEST] Stopping audio pipeline...")
        print()

        elapsed = self.end_time - self.start_time

        self.evaluate(
            pipeline,
            elapsed,
        )

    # ========================================================
    # PREVIEW CALLBACK
    # ========================================================

    def _handle_preview(
        self,
        preview_text: str,
        authoritative_transcript: str,
    ):

        preview_text = (
            preview_text or ""
        ).strip()

        if not preview_text:
            return

        self.preview_count += 1

        print()
        print("[LIVE PREVIEW]")
        print("-" * 70)
        print(preview_text)

    # ========================================================
    # FINAL CALLBACK
    # ========================================================

    def _handle_final(
        self,
        segment_text: str,
        full_transcript: str,
        segment_id: int,
    ):

        segment_text = (
            segment_text or ""
        ).strip()

        full_transcript = (
            full_transcript or ""
        ).strip()

        if not segment_text:
            return

        self.final_segments.append(
            {
                "segment_id": segment_id,
                "text": segment_text,
                "characters": len(segment_text),
                "words": len(segment_text.split()),
            }
        )

        print()
        print("=" * 70)
        print(f"[FINAL SEGMENT {segment_id}]")
        print("=" * 70)
        print(segment_text)

        # ====================================================
        # BUILD THE SAME ANALYSIS INPUT USED BY APPLICATION
        # ====================================================

        self.transcript_manager.update(
            full_transcript
        )

        raw_chunk = (
            self.transcript_manager.get_new_analysis_text(
                full_transcript
            )
        )

        if not raw_chunk:
            print()
            print(
                "[TRANSCRIPT INTELLIGENCE]"
            )
            print(
                "No new complete analysis chunk."
            )
            return

        context = (
            self.transcript_manager.get_analysis_context(
                transcript=full_transcript,
                analysis_text=raw_chunk,
            )
        )

        print()
        print("[TRANSCRIPT INTELLIGENCE INPUT]")
        print("-" * 70)
        print("RAW ANALYSIS CHUNK:")
        print(raw_chunk)

        print()
        print("CONTEXT:")
        print(
            context
            if context
            else "(No previous context)"
        )

        try:

            result = transcript_intelligence.refine(
                raw_chunk,
                context=context,
            )

            refined_text = (
                result.refined_text or ""
            ).strip()

            self.analysis_chunks.append(
                {
                    "segment_id": segment_id,
                    "raw": raw_chunk,
                    "context": context,
                    "refined": refined_text,
                    "quality_score": result.quality_score,
                    "corrections": self._make_json_safe(
                        result.corrections
                    ),
                }
            )

            # =================================================
            # IMPORTANT:
            # Mark the raw analysis chunk as processed.
            #
            # Without this, get_new_analysis_text() sees the
            # same complete sentences again on the next final
            # segment and returns them repeatedly.
            # =================================================

            self.transcript_manager.mark_analyzed(
                raw_chunk
            )

            print()
            print("REFINED:")
            print(refined_text)

            print()
            print(
                f"QUALITY SCORE: "
                f"{result.quality_score:.3f}"
            )

            print()
            print(
                "[TRANSCRIPT INTELLIGENCE]"
            )
            print(
                "Analysis chunk marked as processed."
            )

        except Exception as error:

            print()
            print(
                "[TRANSCRIPT INTELLIGENCE ERROR]"
            )
            print(error)

    # ========================================================
    # EVALUATION
    # ========================================================

    def evaluate(
        self,
        pipeline: AudioPipeline,
        elapsed: float,
    ):

        print()
        print("=" * 70)
        print("AUDIO CAPTURE COMPLETE")
        print("=" * 70)

        raw_transcript = (
            pipeline.get_transcript() or ""
        ).strip()

        metrics = pipeline.get_metrics()

        print()
        print("=" * 70)
        print("RAW AUTHORITATIVE TRANSCRIPT")
        print("=" * 70)
        print(raw_transcript)

        # ====================================================
        # FINAL FULL-TRANSCRIPT REFINEMENT
        # ====================================================

        print()
        print("=" * 70)
        print("FINAL CONTEXT-AWARE TRANSCRIPT INTELLIGENCE")
        print("=" * 70)

        final_refined_text = raw_transcript
        final_quality_score = 0.0
        final_corrections: list[Any] = []

        self.transcript_manager.update(
            raw_transcript
        )

        # Use the complete authoritative transcript as the
        # final evaluation input.
        final_context = (
            self.transcript_manager.get_analysis_context(
                transcript=raw_transcript,
                analysis_text=raw_transcript,
            )
        )

        print()
        print("FINAL RAW TRANSCRIPT:")
        print(raw_transcript)

        print()
        print("FINAL CONTEXT:")
        print(
            final_context
            if final_context
            else "(No previous context)"
        )

        if raw_transcript:

            try:

                final_analysis_result = (
                    transcript_intelligence.refine(
                        raw_transcript,
                        context=final_context,
                    )
                )

                final_refined_text = (
                    final_analysis_result.refined_text
                    or ""
                ).strip()

                final_quality_score = (
                    final_analysis_result.quality_score
                )

                final_corrections = (
                    self._make_json_safe(
                        final_analysis_result.corrections
                    )
                )

                self.final_analysis = {
                    "raw": raw_transcript,
                    "context": final_context,
                    "refined": final_refined_text,
                    "quality_score": final_quality_score,
                    "corrections": final_corrections,
                }

                print()
                print("FINAL REFINED TRANSCRIPT:")
                print(final_refined_text)

                print()
                print(
                    f"FINAL QUALITY SCORE: "
                    f"{final_quality_score:.3f}"
                )

            except Exception as error:

                print()
                print(
                    "[FINAL TRANSCRIPT INTELLIGENCE ERROR]"
                )
                print(error)

                # Keep the authoritative transcript as the
                # fallback instead of inventing a replacement.
                final_refined_text = raw_transcript

        # ====================================================
        # EVALUATION
        # ====================================================

        all_corrections: list[Any] = []

        for item in self.analysis_chunks:

            all_corrections.extend(
                item.get(
                    "corrections",
                    [],
                )
            )

        all_corrections.extend(
            final_corrections
        )

        original_length = len(
            raw_transcript
        )

        refined_length = len(
            final_refined_text
        )

        original_words = len(
            raw_transcript.split()
        )

        refined_words = len(
            final_refined_text.split()
        )

        changed = (
            raw_transcript
            != final_refined_text
        )

        print()
        print("=" * 70)
        print("CONTEXT-AWARE EVALUATION")
        print("=" * 70)

        print()
        print(
            f"ANALYSIS CHUNKS : "
            f"{len(self.analysis_chunks)}"
        )

        print(
            f"ORIGINAL LENGTH : "
            f"{original_length}"
        )

        print(
            f"REFINED LENGTH  : "
            f"{refined_length}"
        )

        print(
            f"ORIGINAL WORDS  : "
            f"{original_words}"
        )

        print(
            f"REFINED WORDS   : "
            f"{refined_words}"
        )

        print(
            f"CHANGED         : "
            f"{changed}"
        )

        print(
            f"FINAL QUALITY   : "
            f"{final_quality_score:.3f}"
        )

        print()
        print("CORRECTIONS:")

        if all_corrections:

            for correction in all_corrections:

                print(
                    f"  - {correction}"
                )

        else:

            print("  - None")

        print()
        print("=" * 70)
        print("REFINED TRANSCRIPT")
        print("=" * 70)
        print(final_refined_text)

        # ====================================================
        # REPORT
        # ====================================================

        report = {
            "test": {
                "name": (
                    "Live Audio + "
                    "Context-Aware Transcript Intelligence"
                ),
                "timestamp": time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            },

            "timing": {
                "elapsed_seconds": round(
                    elapsed,
                    3,
                ),
            },

            "audio": {
                "final_segments": len(
                    self.final_segments
                ),
                "preview_count": (
                    self.preview_count
                ),
                "metrics": self._make_json_safe(
                    metrics
                ),
            },

            "transcript": {
                "raw": raw_transcript,

                "refined": final_refined_text,

                "original_characters": (
                    original_length
                ),

                "refined_characters": (
                    refined_length
                ),

                "original_words": (
                    original_words
                ),

                "refined_words": (
                    refined_words
                ),

                "changed": changed,

                "characters_removed": max(
                    0,
                    original_length
                    - refined_length,
                ),

                "words_removed": max(
                    0,
                    original_words
                    - refined_words,
                ),
            },

            "transcript_intelligence": {
                "analysis_chunks": len(
                    self.analysis_chunks
                ),

                "final_quality_score": (
                    final_quality_score
                ),

                "average_live_chunk_quality": (
                    self._average_live_chunk_quality()
                ),

                "corrections": (
                    self._make_json_safe(
                        all_corrections
                    )
                ),

                "chunk_results": (
                    self._make_json_safe(
                        self.analysis_chunks
                    )
                ),

                "final_analysis": (
                    self._make_json_safe(
                        self.final_analysis
                    )
                ),
            },

            "segments": self._make_json_safe(
                self.final_segments
            ),
        }

        self.save_report(
            report
        )

        print()
        print("=" * 70)
        print("REPORT SAVED")
        print("=" * 70)

        print(
            f"JSON : "
            f"{self.output_dir / 'live_audio_transcript_report.json'}"
        )

        print(
            f"TXT  : "
            f"{self.output_dir / 'live_audio_transcript_report.txt'}"
        )

    # ========================================================
    # QUALITY
    # ========================================================

    def _average_live_chunk_quality(
        self,
    ) -> float:

        quality_scores = [
            item["quality_score"]
            for item in self.analysis_chunks
            if isinstance(
                item.get("quality_score"),
                (int, float),
            )
        ]

        if not quality_scores:
            return 0.0

        return (
            sum(quality_scores)
            / len(quality_scores)
        )

    # ========================================================
    # JSON SAFE CONVERSION
    # ========================================================

    def _make_json_safe(
        self,
        value: Any,
    ) -> Any:

        if is_dataclass(
            value
        ) and not isinstance(
            value,
            type,
        ):

            return self._make_json_safe(
                asdict(value)
            )

        if isinstance(
            value,
            dict,
        ):

            return {
                str(key): self._make_json_safe(
                    item
                )
                for key, item in value.items()
            }

        if isinstance(
            value,
            (list, tuple),
        ):

            return [
                self._make_json_safe(
                    item
                )
                for item in value
            ]

        if isinstance(
            value,
            set,
        ):

            return [
                self._make_json_safe(
                    item
                )
                for item in value
            ]

        if isinstance(
            value,
            Path,
        ):

            return str(value)

        if hasattr(
            value,
            "item",
        ) and callable(
            value.item
        ):

            try:

                return value.item()

            except Exception:
                pass

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ) or value is None:

            return value

        return str(value)

    # ========================================================
    # SAVE REPORT
    # ========================================================

    def save_report(
        self,
        report: dict[str, Any],
    ):

        json_path = (
            self.output_dir
            / "live_audio_transcript_report.json"
        )

        txt_path = (
            self.output_dir
            / "live_audio_transcript_report.txt"
        )

        safe_report = self._make_json_safe(
            report
        )

        with json_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                safe_report,
                file,
                indent=2,
                ensure_ascii=False,
            )

        self._save_text_report(
            txt_path,
            safe_report,
        )

    # ========================================================
    # TEXT REPORT
    # ========================================================

    def _save_text_report(
        self,
        path: Path,
        report: dict[str, Any],
    ):

        transcript = report.get(
            "transcript",
            {},
        )

        intelligence = report.get(
            "transcript_intelligence",
            {},
        )

        audio = report.get(
            "audio",
            {},
        )

        timing = report.get(
            "timing",
            {},
        )

        lines: list[str] = []

        lines.append("=" * 70)
        lines.append(
            "LIVE AUDIO + CONTEXT-AWARE "
            "TRANSCRIPT INTELLIGENCE REPORT"
        )
        lines.append("=" * 70)
        lines.append("")

        # ----------------------------------------------------
        # TIMING
        # ----------------------------------------------------

        lines.append("TIMING")
        lines.append("-" * 70)

        lines.append(
            f"Elapsed seconds : "
            f"{timing.get('elapsed_seconds', 0)}"
        )

        lines.append("")

        # ----------------------------------------------------
        # AUDIO
        # ----------------------------------------------------

        lines.append("AUDIO")
        lines.append("-" * 70)

        lines.append(
            f"Final segments : "
            f"{audio.get('final_segments', 0)}"
        )

        lines.append(
            f"Preview count  : "
            f"{audio.get('preview_count', 0)}"
        )

        lines.append("")

        # ----------------------------------------------------
        # TRANSCRIPT
        # ----------------------------------------------------

        lines.append("TRANSCRIPT")
        lines.append("-" * 70)

        lines.append(
            f"Original characters : "
            f"{transcript.get('original_characters', 0)}"
        )

        lines.append(
            f"Refined characters  : "
            f"{transcript.get('refined_characters', 0)}"
        )

        lines.append(
            f"Original words      : "
            f"{transcript.get('original_words', 0)}"
        )

        lines.append(
            f"Refined words       : "
            f"{transcript.get('refined_words', 0)}"
        )

        lines.append(
            f"Changed             : "
            f"{transcript.get('changed', False)}"
        )

        lines.append(
            f"Characters removed  : "
            f"{transcript.get('characters_removed', 0)}"
        )

        lines.append(
            f"Words removed       : "
            f"{transcript.get('words_removed', 0)}"
        )

        lines.append("")

        # ----------------------------------------------------
        # QUALITY
        # ----------------------------------------------------

        lines.append("QUALITY")
        lines.append("-" * 70)

        lines.append(
            f"Live analysis chunks : "
            f"{intelligence.get('analysis_chunks', 0)}"
        )

        lines.append(
            f"Live average quality: "
            f"{intelligence.get('average_live_chunk_quality', 0):.3f}"
        )

        lines.append(
            f"Final quality       : "
            f"{intelligence.get('final_quality_score', 0):.3f}"
        )

        lines.append("")

        # ----------------------------------------------------
        # CORRECTIONS
        # ----------------------------------------------------

        lines.append("CORRECTIONS")
        lines.append("-" * 70)

        corrections = intelligence.get(
            "corrections",
            [],
        )

        if corrections:

            for correction in corrections:

                if isinstance(
                    correction,
                    dict,
                ):

                    confidence = correction.get(
                        "confidence",
                        0,
                    )

                    if not isinstance(
                        confidence,
                        (int, float),
                    ):

                        confidence = 0

                    lines.append(
                        f"- "
                        f"{correction.get('correction_type', '')}: "
                        f"{correction.get('original', '')} "
                        f"-> "
                        f"{correction.get('replacement', '')} "
                        f"(confidence="
                        f"{confidence:.2f})"
                    )

                else:

                    lines.append(
                        f"- {correction}"
                    )

        else:

            lines.append(
                "- None"
            )

        lines.append("")

        # ----------------------------------------------------
        # ANALYSIS CHUNKS
        # ----------------------------------------------------

        lines.append(
            "CONTEXT-AWARE LIVE ANALYSIS CHUNKS"
        )

        lines.append("=" * 70)

        for index, chunk in enumerate(
            intelligence.get(
                "chunk_results",
                [],
            ),
            start=1,
        ):

            lines.append(
                f"[ANALYSIS CHUNK {index}]"
            )

            lines.append("")

            lines.append(
                f"SEGMENT ID: "
                f"{chunk.get('segment_id', '?')}"
            )

            lines.append("")

            lines.append("RAW:")
            lines.append(
                chunk.get(
                    "raw",
                    "",
                )
            )

            lines.append("")

            lines.append("CONTEXT:")
            lines.append(
                chunk.get(
                    "context",
                    "",
                )
                or "(No previous context)"
            )

            lines.append("")

            lines.append("REFINED:")
            lines.append(
                chunk.get(
                    "refined",
                    "",
                )
            )

            lines.append("")

            quality = chunk.get(
                "quality_score",
                0,
            )

            if not isinstance(
                quality,
                (int, float),
            ):

                quality = 0

            lines.append(
                f"QUALITY: "
                f"{quality:.3f}"
            )

            lines.append("")
            lines.append("-" * 70)
            lines.append("")

        # ----------------------------------------------------
        # FINAL ANALYSIS
        # ----------------------------------------------------

        final_analysis = intelligence.get(
            "final_analysis",
        )

        lines.append(
            "FINAL FULL-TRANSCRIPT ANALYSIS"
        )

        lines.append("=" * 70)

        if final_analysis:

            lines.append("")

            lines.append("RAW:")
            lines.append(
                final_analysis.get(
                    "raw",
                    "",
                )
            )

            lines.append("")

            lines.append("CONTEXT:")
            lines.append(
                final_analysis.get(
                    "context",
                    "",
                )
                or "(No previous context)"
            )

            lines.append("")

            lines.append("REFINED:")
            lines.append(
                final_analysis.get(
                    "refined",
                    "",
                )
            )

            lines.append("")

            final_quality = final_analysis.get(
                "quality_score",
                0,
            )

            if not isinstance(
                final_quality,
                (int, float),
            ):

                final_quality = 0

            lines.append(
                f"QUALITY: "
                f"{final_quality:.3f}"
            )

        else:

            lines.append(
                "Final analysis unavailable."
            )

        lines.append("")

        # ----------------------------------------------------
        # RAW TRANSCRIPT
        # ----------------------------------------------------

        lines.append(
            "RAW AUTHORITATIVE TRANSCRIPT"
        )

        lines.append("=" * 70)

        lines.append(
            transcript.get(
                "raw",
                "",
            )
        )

        lines.append("")

        # ----------------------------------------------------
        # REFINED TRANSCRIPT
        # ----------------------------------------------------

        lines.append(
            "REFINED TRANSCRIPT"
        )

        lines.append("=" * 70)

        lines.append(
            transcript.get(
                "refined",
                "",
            )
        )

        lines.append("")

        # ----------------------------------------------------
        # FINAL SEGMENTS
        # ----------------------------------------------------

        lines.append(
            "FINAL SEGMENTS"
        )

        lines.append("=" * 70)

        for segment in report.get(
            "segments",
            [],
        ):

            if isinstance(
                segment,
                dict,
            ):

                lines.append(
                    f"[SEGMENT "
                    f"{segment.get('segment_id', '?')}]"
                )

                lines.append(
                    segment.get(
                        "text",
                        "",
                    )
                )

                lines.append("")

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:

            file.write(
                "\n".join(lines)
            )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    LiveAudioTest().run()