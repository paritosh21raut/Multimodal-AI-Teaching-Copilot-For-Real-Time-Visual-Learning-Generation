# ADR-0007: Image sources — free APIs + CLIP re-ranking
Status: accepted (2026-10-05)

**Decision.** Wikipedia page images, Wikimedia Commons search, and Openverse (all free, no paid keys), re-ranked by
CLIP text-image similarity with a rejection threshold; disk cache; attribution stored. Generated SVG diagrams
are preferred for processes/structures. Teacher-provided images (V2) get top priority.

**Why.** Free; educational and licensed content; the relevance threshold prevents the "random image" problem seen before.
