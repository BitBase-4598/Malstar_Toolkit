---
status: active
tags: [statement]
---
# entra-roles-in-audit

Signed-in Entra users are viewer, editor, or admin. Viewers cannot change records. Audit events store the person's name, object id, and role in addition to the IP address. Without Entra headers the process keeps the local default role, editor, unless MALSTAR_AUTH_REQUIRED is set.

## Concepts
- [[MALSTAR Ops]]

## Source
- [[Session: Ops dashboard GSC Area and PDF]]
