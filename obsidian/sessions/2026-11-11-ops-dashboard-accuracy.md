---
date: 2026-11-11
chat: Ops dashboard accuracy fixes
tags: [session]
---
# Session: Ops dashboard accuracy fixes

## Summary
Fixed numbers and sentences on MALSTAR Ops that could be wrong for a given upload.

## Decisions
- Conclusion leads (Overview, Volume by hour, Flagged rows) are built from the numbers. Overview names whichever of GSC or Area actually converts more and processes faster.
- Flagged rows are no longer capped at 40; the conclusion count and the table show all of them.
- Metrics count each booking once. A repeat is a row with the same message id **and** order number; the last copy wins. One email with several different orders still counts as several bookings. Repeats stay in the row list (`isRepeat`) and are still flagged as "Duplicate message id".
- Handler charts group by the text before `@`, ignoring case, and use the roster spelling as the label.
- A status counts as converted only when it contains the word "converted" without "not", "non" or "un" in front.
- Handler process averages come from the backend only; the frontend no longer recomputes them.

## Concepts
- [[MALSTAR Ops]]
- [[GSC and Area]]
- [[Handler roster]]
