"""In-process asyncio event bus (ADR-0004).

Each subscriber owns a bounded queue and a consumer task, so a slow subscriber
cannot block the publisher or other subscribers.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal, Optional

from copilot.core.events import Event

log = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]
Overflow = Literal["block", "drop_oldest"]

_STOP = object()


@dataclass
class Subscription:
    name: str
    types: Optional[frozenset[type[Event]]]  # None = all events
    handler: Handler
    queue: asyncio.Queue
    overflow: Overflow
    dropped: int = 0
    task: Optional[asyncio.Task] = field(default=None, repr=False)

    def accepts(self, event: Event) -> bool:
        return self.types is None or isinstance(event, tuple(self.types))


class EventBus:
    def __init__(self, default_queue_size: int = 1000) -> None:
        self._subs: list[Subscription] = []
        self._default_queue_size = default_queue_size
        self._closed = False
        self.session_id = ""

    def subscribe(
        self,
        name: str,
        handler: Handler,
        types: Optional[list[type[Event]]] = None,
        *,
        queue_size: Optional[int] = None,
        overflow: Overflow = "block",
    ) -> Subscription:
        if self._closed:
            raise RuntimeError("bus is closed")
        sub = Subscription(
            name=name,
            types=frozenset(types) if types else None,
            handler=handler,
            queue=asyncio.Queue(maxsize=queue_size or self._default_queue_size),
            overflow=overflow,
        )
        sub.task = asyncio.create_task(self._consume(sub), name=f"bus:{name}")
        self._subs.append(sub)
        return sub

    async def publish(self, event: Event) -> None:
        if self._closed:
            log.debug("publish after close ignored: %s", event.type)
            return
        if self.session_id and not event.session_id:
            event = event.model_copy(update={"session_id": self.session_id})
        for sub in self._subs:
            if not sub.accepts(event):
                continue
            if sub.overflow == "drop_oldest" and sub.queue.full():
                sub.queue.get_nowait()
                sub.queue.task_done()
                sub.dropped += 1
            await sub.queue.put(event)

    async def drain(self) -> None:
        """Wait until every subscriber has processed everything published so far."""
        await asyncio.gather(*(s.queue.join() for s in self._subs))

    async def close(self) -> None:
        """Drain pending events, then stop all consumers."""
        if self._closed:
            return
        await self.drain()
        self._closed = True
        for sub in self._subs:
            await sub.queue.put(_STOP)
        await asyncio.gather(*(s.task for s in self._subs if s.task), return_exceptions=True)

    async def _consume(self, sub: Subscription) -> None:
        while True:
            item = await sub.queue.get()
            try:
                if item is _STOP:
                    return
                await sub.handler(item)
            except Exception:  # a failing handler must not kill the bus
                log.exception("subscriber %s failed on %s", sub.name, getattr(item, "type", item))
            finally:
                sub.queue.task_done()
