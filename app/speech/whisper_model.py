from __future__ import annotations

import threading
import math

import numpy as np
from faster_whisper import WhisperModel as FWModel

from app.utils.logger import app_logger


class WhisperModel:
    """
    Single serialized Faster-Whisper model with confidence scoring.

    Production configuration:
        model = small
        device = cpu
        compute_type = int8
        language = en
        beam_size = 5

    Additional decoding safeguards:
        - repetitive transcription reduction
        - hallucination prevention
        - confidence scoring for downstream systems
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "en",
        beam_size: int = 5,
    ):

        app_logger.info("Loading Whisper Model...")

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size

        app_logger.info(f"Whisper Model : {self.model_size}")
        app_logger.info(f"Whisper Device : {self.device}")
        app_logger.info(f"Whisper Compute : {self.compute_type}")

        self.model = FWModel(
            model_size_or_path=model_size,
            device=device,
            compute_type=compute_type,
        )

        self._lock = threading.Lock()

        app_logger.success("Whisper Ready")

    @staticmethod
    def normalize_audio(audio_data):
        """Normalize audio to float32 mono"""
        if audio_data is None:
            return None

        audio = np.asarray(audio_data, dtype=np.float32)

        if audio.size == 0:
            return None

        if audio.ndim == 2:
            if audio.shape[1] == 1:
                audio = audio[:, 0]
            else:
                audio = np.mean(audio, axis=1, dtype=np.float32)
        elif audio.ndim != 1:
            audio = audio.reshape(-1)

        if not np.all(np.isfinite(audio)):
            audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)

        if audio.size == 0:
            return None

        audio = np.clip(audio, -1.0, 1.0)

        return np.ascontiguousarray(audio, dtype=np.float32)

    @staticmethod
    def _clean_transcript(text: str):
        """Clean transcript from immediate repetitions"""
        if not text:
            return ""

        text = " ".join(text.split()).strip()

        if not text:
            return ""

        words = text.split()

        if len(words) < 8:
            return text

        # Detect immediate repeated phrase patterns
        max_pattern_words = min(30, len(words) // 2)

        for pattern_size in range(max_pattern_words, 2, -1):
            first = words[:pattern_size]
            second = words[pattern_size:pattern_size * 2]

            if first == second:
                words = words[:pattern_size] + words[pattern_size * 2:]
                text = " ".join(words).strip()
                break

        return text

    def _calculate_confidence(
        self,
        avg_logprob: float,
        no_speech_prob: float,
        compression_ratio: float = 1.0,
    ) -> dict:
        """
        Calculate multi-factor confidence score.
        
        Returns:
            dict with:
                - acoustic_confidence: 0-1 score from logprob
                - speech_confidence: 0-1 score from no_speech_prob
                - overall_confidence: combined score
                - avg_logprob: raw value
                - no_speech_prob: raw value
        """
        # Map avg_logprob to confidence
        # Typical values: -0.5 (good) to -1.5 (poor)
        # Use sigmoid-like mapping
        acoustic_confidence = 1.0 / (1.0 + math.exp(-(avg_logprob + 0.5) * 4))
        
        # Map no_speech_prob to confidence
        # no_speech_prob close to 0 means definitely speech
        # no_speech_prob close to 1 means likely silence/noise
        speech_confidence = 1.0 - min(1.0, max(0.0, no_speech_prob))
        
        # Compression ratio penalty
        # High compression ratio suggests repetition/hallucination
        if compression_ratio > 2.4:
            compression_penalty = 0.5
        elif compression_ratio > 2.0:
            compression_penalty = 0.3
        else:
            compression_penalty = 0.0
        
        # Overall confidence
        overall = (
            acoustic_confidence * 0.5 +
            speech_confidence * 0.3 +
            (1.0 - compression_penalty) * 0.2
        )
        
        return {
            "acoustic_confidence": round(min(1.0, max(0.0, acoustic_confidence)), 3),
            "speech_confidence": round(min(1.0, max(0.0, speech_confidence)), 3),
            "overall_confidence": round(min(1.0, max(0.0, overall)), 3),
            "avg_logprob": round(avg_logprob, 3),
            "no_speech_prob": round(no_speech_prob, 3),
        }

    def _transcribe_array(self, audio):
        """Transcribe audio and return (text, confidence_dict)"""
        
        segments, info = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=self.beam_size,
            vad_filter=False,
            condition_on_previous_text=False,
            temperature=0.0,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            repetition_penalty=1.05,
        )

        transcript_parts = []
        word_confidence_scores = []
        avg_logprob_sum = 0.0
        segment_count = 0

        for segment in segments:
            text = segment.text.strip()
            
            if text:
                transcript_parts.append(text)
                
                # Collect confidence from segment
                if hasattr(segment, 'avg_logprob'):
                    avg_logprob_sum += segment.avg_logprob
                    segment_count += 1
                
                # Collect word-level confidence if available
                if hasattr(segment, 'words') and segment.words:
                    for word in segment.words:
                        if hasattr(word, 'probability'):
                            word_confidence_scores.append(word.probability)

        transcript = " ".join(transcript_parts).strip()
        transcript = self._clean_transcript(transcript)

        # Calculate average logprob
        avg_logprob = avg_logprob_sum / segment_count if segment_count > 0 else -1.0
        
        # Get no_speech_prob from info
        no_speech_prob = getattr(info, 'no_speech_prob', 0.0) if info else 0.0
        
        # Get compression ratio
        compression_ratio = getattr(info, 'compression_ratio', 1.0) if info else 1.0
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            avg_logprob,
            no_speech_prob,
            compression_ratio,
        )

        if info is not None:
            language = getattr(info, "language", None)
            probability = getattr(info, "language_probability", None)

            if language is not None:
                app_logger.info(f"Detected Language : {language}")
                if probability is not None:
                    app_logger.info(f"Language Probability : {probability:.2f}")

        return transcript, confidence

    def transcribe(self, audio_path):
        """Transcribe audio file (returns text only for backward compat)"""
        app_logger.info("Starting Whisper Transcription...")

        with self._lock:
            transcript, confidence = self._transcribe_array(audio_path)

        app_logger.success("Whisper Transcription Completed")

        return transcript

    def transcribe_audio(self, audio_data):
        """Transcribe audio array (returns text only for backward compat)"""
        audio = self.normalize_audio(audio_data)

        if audio is None:
            return ""

        with self._lock:
            transcript, confidence = self._transcribe_array(audio)

        return transcript

    def transcribe_with_confidence(self, audio_data):
        """
        Transcribe audio and return (text, confidence_dict).
        
        New method that provides confidence scores for downstream use.
        """
        audio = self.normalize_audio(audio_data)

        if audio is None:
            return "", {
                "acoustic_confidence": 0.0,
                "speech_confidence": 0.0,
                "overall_confidence": 0.0,
                "avg_logprob": -99.0,
                "no_speech_prob": 1.0,
            }

        with self._lock:
            return self._transcribe_array(audio)