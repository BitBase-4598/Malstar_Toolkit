---
status: active
tags: [statement]
---
# repeat-is-same-message-and-order

A booking row is a repeat when another row has the same message id **and** the same order number. The last copy (by date, handling time, id) is kept for metrics. Rows with no message id are never repeats. One email that produced several different orders counts as several bookings.

Repeats are left out of KPIs, GSC/Area cards, handler charts and volume by hour. They stay in the row list with `isRepeat: true`, `kpis.repeatRows` gives their count, and they are still flagged "Duplicate message id".

Open question for the team: if any repeated message id should count once, change `drop_repeated_rows` to key on message id only.

## Concepts
- [[Booking repeats]]

## Source
- [[Session: Ops dashboard accuracy fixes]]
