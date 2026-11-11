---
status: active
tags: [statement]
---
# converted-excludes-negations

A status counts as converted when it contains the whole word "converted" with no "not", "non" or "un" in front. "Converted", "Shipment Converted" and "AI-Booking: Converted" count. "Not converted", "Non-converted" and "Unconverted" do not. The old check was a plain substring match and counted all of them.

The same rule is in `is_converted_status` (backend) and `isConvertedStatus` in `Dashboard.jsx`, which only colours the status pill.

## Concepts
- [[MALSTAR Ops]]

## Source
- [[Session: Ops dashboard accuracy fixes]]
