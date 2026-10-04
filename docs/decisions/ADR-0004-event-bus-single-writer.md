# ADR-0004: In-process asyncio event bus + single-writer state
Status: accepted (2026-10-05)

**Decision.** One Python process, one asyncio loop. Components communicate through a typed `EventBus`
(per-subscriber bounded queues). `LectureStateStore` is the only mutator of `LectureState`. Heavy ML runs in worker threads.
All events go to an append-only SQLite log.

**Why.** Simple, debuggable, deterministic ordering, easy replay testing, no broker to run on a laptop.
Avoids the old problem of UI and processing being tangled together.

**Consequences.** Not distributed — not needed. A slow subscriber cannot block others (bounded queue + overflow
policy per subscriber: block, drop-oldest, or latest-only).
