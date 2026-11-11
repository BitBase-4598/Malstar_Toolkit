---
status: active
tags: [statement]
---
# handler-charts-group-by-local-part

Handler charts group bookings by the text before `@`, ignoring case, and label each bar with the spelling saved in the roster. `Qing.Huang@lns.maersk.com` and `qing.huang@maersk.com` are one bar, labelled `qing.huang`. Labels used to be the full raw email, so name variants split into separate bars.

## Concepts
- [[Handler roster]]

## Source
- [[Session: Ops dashboard accuracy fixes]]
