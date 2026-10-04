# ADR-0005: Frontend without a build toolchain
Status: accepted (2026-10-05)

**Decision.** Native ES modules, Preact + htm vendored in `web/vendor/`, KaTeX vendored, hand-written CSS design tokens,
SVG components. No Node/npm required.

**Why.** Node is not installed; a build step adds friction across sessions; the UI is a small set of layout components.
Preact+htm gives component structure and efficient diffing without JSX compilation.

**Revisit if** the UI grows beyond ~40 components or needs TypeScript tooling.
