from __future__ import annotations

import threading
from typing import Any, Optional

from app.semantic.semantic_context import SemanticContextBuilder
from app.semantic.semantic_gate import SemanticGate
from app.semantic.semantic_ledger import SemanticLedger
from app.semantic.semantic_queue import SemanticQueue
from app.semantic.semantic_reasoner import SemanticReasoner
from app.semantic.semantic_throttle import SemanticThrottle
from app.semantic.semantic_worker import SemanticWorker
from app.utils.logger import app_logger


class SemanticIntelligence:

    def __init__(
        self,
        *,
        embedding_model,
        lsi_registry_getter,
        reasoner: Optional[SemanticReasoner] = None,
        fallback_reasoner: Optional[SemanticReasoner] = None,
        max_queue_size: int = 64,
        batch_size: int = 2,
        batch_timeout: float = 6.0,
        max_calls_per_minute: int = 2,
        min_interval_seconds: float = 20.0,
        enabled: bool = True,
    ) -> None:

        self._enabled = bool(enabled)

        self._ledger = SemanticLedger()
        self._queue = SemanticQueue(
            max_size=max_queue_size,
            batch_size=batch_size,
            batch_timeout=batch_timeout,
        )
        self._gate = SemanticGate()
        self._throttle = SemanticThrottle(
            max_calls_per_minute=max_calls_per_minute,
            min_interval_seconds=min_interval_seconds,
        )

        self._context_builder = SemanticContextBuilder(
            embedding_model=embedding_model,
            ledger=self._ledger,
            lsi_registry_getter=lsi_registry_getter,
            gate=self._gate,
        )

        self._reasoner = reasoner
        self._fallback_reasoner = fallback_reasoner

        self._worker: Optional[SemanticWorker] = None
        self._worker_lock = threading.Lock()

    # ---------------------------------------------------------- #
    # LIFECYCLE
    # ---------------------------------------------------------- #

    def start(self) -> None:

        if not self._enabled:
            return

        with self._worker_lock:

            if self._worker is not None and self._worker.is_alive():
                return

            self._worker = SemanticWorker(
                queue=self._queue,
                ledger=self._ledger,
                reasoner=self._reasoner,
                fallback_reasoner=self._fallback_reasoner,
                embedding_model=self._context_builder._model,
                lsi_registry_getter=self._context_builder._get_lsi_node,
                throttle=self._throttle,
            )

            self._worker.start()

            app_logger.info(
                "[SemanticIntelligence] sidecar started"
            )

    def stop(self) -> None:

        with self._worker_lock:

            if self._worker is not None:
                self._worker.stop()
                self._worker = None

            app_logger.info(
                "[SemanticIntelligence] sidecar stopped"
            )

    def reset(self) -> None:

        self._ledger.reset()
        self._queue.clear()
        self._throttle.reset()

        app_logger.info(
            "[SemanticIntelligence] reset"
        )

    # ---------------------------------------------------------- #
    # ENQUEUE
    # ---------------------------------------------------------- #

    def enqueue(
        self,
        chunk_text: str,
        topic_decision: Any,
    ) -> None:

        if not self._enabled:
            return

        try:

            relation = getattr(topic_decision, "relation", None)
            node_id = getattr(topic_decision, "node_id", None)
            topic_label = getattr(topic_decision, "topic", None)
            parent_id = getattr(topic_decision, "parent_node_id", None)
            depth = getattr(topic_decision, "depth", None)

            parent_label = None

            if parent_id is not None:
                parent_node = self._context_builder._get_lsi_node(
                    parent_id
                )
                if parent_node is not None:
                    parent_label = getattr(parent_node, "name", None)

            snapshot = self._context_builder.build(
                chunk_text=chunk_text,
                lsi_relation=relation,
                lsi_node_id=node_id,
                lsi_node_label=topic_label,
                lsi_parent_node_id=parent_id,
                lsi_parent_label=parent_label,
                lsi_depth=depth,
            )

            if self._worker is None:
                self.start()

            accepted = self._queue.put(snapshot)

            if not accepted:
                app_logger.warning(
                    "[SemanticIntelligence] queue full; dropped oldest item"
                )

        except Exception as error:

            app_logger.warning(
                f"[SemanticIntelligence] enqueue failure: {error}"
            )

    # ---------------------------------------------------------- #
    # READ-ONLY
    # ---------------------------------------------------------- #

    def snapshot(self) -> dict:
        return self._ledger.snapshot()

    def stats(self) -> dict:
        return {
            "queue": self._queue.stats(),
            "ledger": self._ledger.snapshot().get("counts", {}),
            "throttle": self._throttle.stats(),
            "enabled": self._enabled,
        }