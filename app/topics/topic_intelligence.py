from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

@dataclass
class TopicDecision:
    topic: str
    embedding: object
    is_new_topic: bool
    similarity: float


class TopicIntelligence:
    """
    Detects whether the lecturer has started a new topic
    using semantic similarity.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        threshold: float = 0.55,
    ):

        print("[Topic] Loading embedding model...")

        self.model = SentenceTransformer(model_name)

        self.threshold = threshold

        print("[Topic] Ready")

    def process(
        self,
        latest_text: str,
        rolling_context: str,
        current_topic: Optional[str],
        current_embedding,
    ) -> TopicDecision:

        print("[Topic] process() called")

        text = latest_text.strip()

        if not text:
            return TopicDecision(
                topic=current_topic or "",
                embedding=current_embedding,
                is_new_topic=False,
                similarity=1.0,
            )

        print("[Topic] Encoding transcript...")

        embedding = self.model.encode(
            text,
            convert_to_tensor=True,
        )

        print("[Topic] Transcript encoded")

        if current_embedding is None:

            return TopicDecision(
                topic=text,
                embedding=embedding,
                is_new_topic=True,
                similarity=0.0,
            )

        similarity = float(
            cos_sim(current_embedding, embedding).item()
        )

        is_new = similarity < self.threshold

        topic = text if is_new else (current_topic or text)

        print(
            f"[Topic] Similarity = {similarity:.3f} | "
            f"{'NEW TOPIC' if is_new else 'CONTINUE'}"
        )

        return TopicDecision(
            topic=topic,
            embedding=embedding,
            is_new_topic=is_new,
            similarity=similarity,
        )


topic_intelligence = TopicIntelligence()