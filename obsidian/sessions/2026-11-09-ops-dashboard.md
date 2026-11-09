---
date: 2026-11-09
chat: Ops dashboard GSC Area and PDF
tags: [session]
---
# Session: Ops dashboard GSC Area and PDF

## Summary
Learned the 2026-11-08 LCL daily report (1948 rows, 21 mailboxes) and rebuilt MALSTAR Ops around a GSC versus Area overview, a configurable handler roster, short section conclusions, and a chart PDF. Pushed to `main` at `4a92384`, then continued on `cursor/hallmark-restyle-4da3` through PDF layout, overview frames, and the flagged-row subject column.

## Decisions
- [[gsc-five-mailboxes]] — Europe box is `CUSLCLEUR`, not `CUSLCLLEUR`.
- [[area-is-everyone-else]] — blank mailboxes stay in Area.
- [[handler-charts-use-roster]] — only the saved ten names enter the lower handler charts.
- [[ops-conclusions-are-six-sections]] — handler lines stay short; volume adds weekday peaks.
- [[ops-pdf-leads-with-conclusions]] — conclusions first, then every chart.
- [[email-schedule-removed]] — no daily or monthly mail.
- [[flagged-rows-omit-subject]] — subject column removed so rows stay one line high.
- [[non-mod-hidden-on-ops]] — Non-Modification is not shown at the bottom of Ops.

## Concepts
- [[MALSTAR Ops]]
- [[GSC and Area]]
- [[Handler roster]]
- [[Ops PDF export]]

## Open tasks
- None.

## Continuity
- Export to PDF sits in the top bar, immediately left of Upload CSV, and uses the same primary button color.
- Overview is two framed columns (GSC, then Area) with a wide gap.
- The server still has `/api/non-mod` and a text PDF route; the button the user clicks builds the chart PDF in the browser.
