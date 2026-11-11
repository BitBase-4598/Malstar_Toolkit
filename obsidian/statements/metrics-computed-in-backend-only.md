---
status: active
tags: [statement]
---
# metrics-computed-in-backend-only

Ops metrics are computed in `backend/services/dashboard_analytics.py` only. The frontend draws `series.processByHandler` from the API and no longer keeps its own copy of the cleaning rules (`processAverages`, `isValidTimeUsage`). The one remaining calculation in the UI is volume by hour for the weekday filter, which skips `isRepeat` rows.

## Concepts
- [[MALSTAR Ops]]

## Source
- [[Session: Ops dashboard accuracy fixes]]
