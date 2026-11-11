---
tags: [concept]
---
# Booking repeats

Rows in the daily report that describe the same booking more than once. Metrics count each booking once; the extra copies remain visible for checking.

## Definition
Same message id and same order number = one booking. `drop_repeated_rows` in `dashboard_analytics.py` keeps the last copy and returns the ids of the rest. Only the metric list (`items`) is de-duplicated. The row list and the "Duplicate message id" flag use every row (`all_items`). `meta.filteredCount` counts every row; `kpis.total` counts bookings.

## Related
- [[MALSTAR Ops]]
- [[repeat-is-same-message-and-order]]

## Sessions
- [[Session: Ops dashboard accuracy fixes]]
