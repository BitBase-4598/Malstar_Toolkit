---
tags: [concept]
---
# Conclusion leads

The bold first sentence above a conclusion section on Ops. It states the finding; the section text below gives the figures.

## Definition
Built by `overview_lead`, `volume_lead` and `flagged_lead` in `dashboard_analytics.py` and sent as the `lead` field of each conclusion. A lead must never claim something the numbers for the current filter do not show. The handler group has no lead.

| Section | Lead says |
| --- | --- |
| Overview | Who converts the larger share and who processes faster; "only GSC/Area" when one side is empty |
| Volume by hour | Share of mail before or after noon; whether weekday peaks match |
| Flagged rows | Most common flag reason, "Most" when it is over half |

## Related
- [[MALSTAR Ops]]
- [[GSC and Area]]
- [[conclusion-leads-follow-data]]
- [[ops-conclusions-are-six-sections]]

## Sessions
- [[Session: Ops dashboard accuracy fixes]]
