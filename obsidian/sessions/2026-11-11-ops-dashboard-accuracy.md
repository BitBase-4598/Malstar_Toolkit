---
date: 2026-11-11
chat: Ops dashboard accuracy fixes
aliases: ["Session: Ops dashboard accuracy fixes"]
tags: [session]
---
# Session: Ops dashboard accuracy fixes

## Summary
Reviewed the whole toolkit, then the Ops dashboard in depth, and fixed the places where Ops could show a wrong number or a sentence that contradicts the cards. Pushed to `main` as `fd6c787`. Tests: 50 passed locally and in CI (44 existing + 6 new). Frontend build passes. **Not deployed**: the Azure login step fails (see [[Open tasks]]).

## Changes
| Area | Before | After |
| --- | --- | --- |
| Overview lead | Fixed text: GSC always "better" than Area | Built from conversion rate and process time; names the real leader |
| Volume / Flagged leads | Fixed text | Built from the hour split and the most common flag reason |
| Flagged count | Payload cut to 40; conclusion said "40 flagged" | All flagged rows returned and counted; table pages them |
| Repeated rows | Counted in every total and average | Counted once; still listed (`isRepeat`) and flagged |
| Handler bars | One bar per raw email; name variants split | One bar per roster name, matched ignoring case and domain |
| Converted status | Substring match; "Not converted" counted | Whole word, negations excluded |
| Process by handler | Calculated twice (backend and `Dashboard.jsx`) | Backend only |

Files: `backend/services/dashboard_analytics.py`, `frontend/src/Dashboard.jsx`, `backend/tests/test_core.py`.

## Decisions
- [[conclusion-leads-follow-data]]
- [[flagged-rows-uncapped]]
- [[repeat-is-same-message-and-order]] — conservative: same message id **and** order number. Awaiting team confirmation.
- [[handler-charts-group-by-local-part]] — bar labels are now short names, not full emails.
- [[converted-excludes-negations]]
- [[metrics-computed-in-backend-only]]

## Concepts
- [[MALSTAR Ops]]
- [[GSC and Area]]
- [[Handler roster]]
- [[Booking repeats]]
- [[Conclusion leads]]

## Lessons
- **A sentence that states a finding must be computed.** Fixed lead text looked right on the day it was written and silently became wrong on other data. Test both directions: one fixture where GSC wins and one where Area wins.
- **Limit what is shown, never what is counted.** `flagged[:40]` was a display limit that leaked into a reported count. Count everything; let the table page it.
- **One home for each metric rule.** The frontend copy of the cleaning rules could drift from the backend. The UI should draw what the API returns.
- **Group by a normalized key, label with the official spelling.** Raw text from reports has case and domain variants.
- **"Duplicate" is a business definition, not a technical one.** Pick the narrowest safe rule, keep the extra rows visible, and write the choice down.
- **Check performance on real sizes.** A first draft used `list.index` inside a sort, which is quadratic on 5,000 rows; replaced with a set lookup.
- **Green tests do not mean deployed.** CI passed, but every deploy since 2026-10-29 had failed at Azure login without anyone noticing. Check the deploy job after each push.

## Open tasks
See [[Open tasks]].

## Continuity
- Existing test change: handler labels in `test_handler_roster_drops_people_outside_the_list` are now `qing.huang` / `someone.else`.
- Payload additions: `kpis.repeatRows`, `rows[].isRepeat`. `meta.filteredCount` counts all rows; `kpis.total` counts bookings.
- The PDF exporter captures the page, so it picks up the new leads with no change.
