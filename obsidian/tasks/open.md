---
aliases: ["Open tasks"]
tags: [tasks]
---
# Open tasks

## Active

- **Azure deploy fails at login** ("No subscriptions found"). Every push to `main` since 2026-10-29 has built and passed tests but not deployed. Fix in Azure portal: MALSTAR-Toolkit → Deployment Center → reconnect GitHub (recreates the login credentials), then re-run the failed workflow. Source: [[Session: Ops dashboard accuracy fixes]]
- **Confirm the repeat rule** with the team: same message id and order number (current), or any repeated message id. See [[repeat-is-same-message-and-order]].

## Parked

Ops dashboard roadmap, in suggested order:

1. **Keep upload history.** Import replaces all rows (`DELETE FROM DashboardBookings`). Merge on message id + order number, record an import batch, show upload history with undo.
2. **Business-hours wait.** Overnight and weekend gaps count as wait, and the 2880-min rule then drops the worst rows. Use working hours and the China holiday list (`chinaHolidays.js`, move to backend).
3. **Better analytics.** Change vs previous period on cards, daily trend lines, median and P90 beside averages, target lines with "% within target", hour × weekday heatmap, handler scorecard table, backlog age for processing rows, per-mailbox split inside GSC.
4. **Usability.** Click a chart to filter the rows, filters in the URL, quick date ranges, flag rule tooltips, CSV export of flagged rows, roster editor as chips with "unknown handlers" warning.
5. **Cleanup.** Remove unused `/api/dashboard/export.pdf` and `services/ops_pdf.py` (UI uses browser export), drop leftover `DashboardReportSchedule` table, share the date/mailbox argument parsing, move GSC mailboxes and default roster to settings.
