# F-010c — UI polish after the group B review (V2)

Status: done (2026-10-12), verified — see STATE.md. User review of F-010b, 8 items, answers given with the request (no open doubts).
0 LLM tokens: nothing here calls the LLM. All changes are in `/control` (`web/control/app.js`, `control.css`).

| # | Request | Decision |
|---|---|---|
| 1 | Drag & drop in the Lectures tab: show where it lands | Native HTML5 drag (browser ghost, no feedback) → **pointer drag with FLIP**: the row / chapter lifts (shadow, follows the pointer vertically), a gap opens where it will land and the other rows **slide** to it (positions measured before and after each change, animated back from the old place, 200 ms). Lectures: the gap opens in the chapter under the pointer, at the place the lecture will take in that chapter's **current sort** (date / name) — lectures have no manual order inside a chapter, so the gap is truthful; a collapsed chapter lights up instead. Chapters: all chapters fold to their headers while one is dragged (the list gets short), the gap follows the pointer; the numbers change after the drop. Chapters move only in the Date sort (by name the list is not the chapter order) and not while searching. The lifted copy lives on `<body>` (the side panel is a size container, which would pin a fixed element to it). Drop → `lecture_move` / `chapter_move` (unchanged commands); the row stays where it was dropped until the server's list agrees (no jump back). Esc cancels. Near the list's top / bottom edge the list scrolls. Mouse and pen only (touch keeps scrolling). A 4 px threshold, so a click still opens the lecture. |
| 2 | "From: Pick lectures / Pick chapters" reads badly | **From: This lecture · Lectures · Chapters** (tips: "Choose lectures, this one included" / "Every lecture in the chapters you choose"). Same picker for the quiz / test (F-011). |
| 3 | Tooltip too quick (450 ms) | **850 ms**; moving from one tipped control to the next within 400 ms shows the next tip at once (the usual tooltip "warm" rule), so scanning the dock is not slow. |
| 4 | Start icon hollow | A **filled**, slightly rounded play triangle (`fill` path, no stroke). |
| 5 | "Ready to start" too basic | Eyebrow with a calm accent dot "Lecture ready" + date · time; heading **"Start your lecture"** (display font, 24 px, tight); one muted line (the topic when known, else "Slides build as you speak."); hairline; Chapter picker; Start; "or press Enter in the terminal" hint. Accent: a thin gradient line on the card's top edge + a soft accent glow in one corner, both from theme tokens (light + dark). |
| 6 | "On project" sounds bad | **"On screen"** with a small live dot; the tip says "Showing on the projector and to students · click or Esc for the slide". |
| 7 | Delete a doc from the notes menu | Each doc row in the DocMenu gets a bin button (shown on hover / focus); confirm "Remove … from your notes?" → `notes_remove` (existing command). The open doc can also be removed there. |
| 8 | Tasteful animations | One motion vocabulary (tokens `--ease-out` cubic-bezier(.2,.8,.2,1), 140 / 200 ms): buttons press to 0.97 and ease colour / shadow; segmented controls and the side tabs get a **sliding thumb**; menus open with fade + scale from their button; the tooltip fades up 2 px; materials options / made rows / chapter lists appear with a short rise; toggles keep their knob slide. `prefers-reduced-motion: reduce` → transitions and animations off (CSS) and no FLIP / thumb motion (JS checks the media query). |

## Round 2 (user 2026-10-12, before the commit)
| # | Request | Decision |
|---|---|---|
| 1 | Notes menu: a bin on hover, one click removes (like a slide point) | The bin sits inside the row's highlight, in place of the type label, shown on hover; **one click removes, no dialog** (the stored copy in `data/notes`; the teacher's original file is untouched). The bin in the open doc's header still asks. |
| 2 | Chapter drag: the tiles must slide as I drag, preview where it drops | After the fold the lifted header **snaps onto its slot** (the list scrolls the slot under it when it can), then moves 1:1 with the pointer; its **centre** picks the slot (one swap per tile height), the other tiles slide (FLIP); the slot shows a **faint copy** of what lands there. Root cause of the old feel: the slot was measured mid-entrance (scaleY 0.6 → 8 px off), so the first swap needed extra travel → slot fades in without scaling. Lecture slots preview the row the same way. |
| 3 | Start card: heading too basic; remove "Lecture ready" and the Enter line | Serif display heading "Start your *lecture*" (Sitka Display → Iowan / Palatino / Georgia), "lecture" in accent italic; eyebrow + date and the Enter hint removed; card style kept. |
| 4 | Materials made list: show one kind; by chapter / lecture; sort | Kind chips (All · Summaries · Key concepts · Notes · Assignments · Slides, with counts, only kinds present); **Group: Chapters · Lectures · All** (collapsible groups; chapters in their order, then Unsorted, then "Across chapters" for items from several chapters; lectures newest first, then "Several lectures"); sort Date / Name ↑↓. Choices remembered per browser (localStorage). |

## Round 3 (user 2026-10-12, before the commit)
| # | Request | Decision |
|---|---|---|
| 1 | Made list: one button that opens the kinds | **Show menu** (`KindMenu`): "All materials ▾" → All · Summaries · Key concepts · Notes · Assignments · Slides with counts; a picked kind tints the button. Chips removed. |
| 2a | Chapter "holds away from the pointer" | The lifted header **never leaves the pointer**: after the fold the folded list is brought to it (scrolled up when it can, the rest by a spacer above the chapters), so its slot lies right under it and the other headers gather around it. The round-2 snap (header moved onto the slot) is gone. |
| 2b | No dashed rectangle; something else | The slot is a **soft sunken well** (no border); the lifted header and every other header show their **new chapter number live** (a small tick animation when it changes). |
| 2c | Sliding slightly too fast; lifted too much | FLIP 220 → **320 ms**, ease-out-quint; lift = soft close shadow, **no scale**. |
| 2d | Remove "Drag lectures here" | Empty chapters show nothing (the count says 0); Unsorted's "Every lecture is in a chapter" too. |
| 2e | Lag when a lecture moves between Unsorted and a chapter | Traced in Edge: each slot change forced a **~50 ms layout of all 94 Unsorted rows** inside the pointer handler (8 long tasks per drag). Rows now use `content-visibility: auto` (off-screen rows skip layout), FLIP reads / writes in separate passes and animates only rows near the view, rows re-render only when their lecture changes → **0 long tasks** on the real archive. |

## Tests
- Browser (Edge), new `tests/e2e/test_polish_browser.py` (all fail on the F-010b web files):
  - lecture drag: mid-drag a `.drop-gap` exists in the target chapter at the sorted index, the lifted row floats,
    rows below the gap moved (FLIP); drop → `lecture_move`; Esc mid-drag → nothing sent;
  - chapter drag: chapters fold, the gap moves with the pointer, drop → `chapter_move` with the new index;
  - From labels; tooltip not shown at 500 ms, shown by 1.2 s; filled Start icon (computed `fill` ≠ none);
    start card heading; "On screen"; DocMenu delete with confirm → the doc is gone; sliding thumb moves;
    reduced motion (emulated) → no animations on the thumb.
  - Esc before the drop → nothing sent. The settle animation is 220 ms, so the test waits for it before grabbing a row again.
- Existing browser tests: `drag_to` on lecture rows keeps working (pointer events), labels updated where the user
  renamed them ("Pick chapters" → "Chapters" — a requirement change).
- Runtime: the real app (`--simulate … --demo-slides --no-understanding`), screenshots both themes, looked at.
