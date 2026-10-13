---
source: NOTES-peer-broadcast-failure-semantics--scope-boundary
timestamp: '2026-10-12T19:32:54.935521+00:00'
title: Scope Boundary
type: note
---

**Archived:** 2026-10-12
**Reason:** stale phase-scoping text; delivery guarantees are owned by the outbox notes and OX specs
**Superseded by:** notes/outbox-delivery-reliability.md

---

## Scope Boundary

This guidance addresses fail-fast semantics and consistency of existing
broadcast paths.

Out of scope for this phase:

- Protocol-level delivery guarantees (`at-least-once`, `exactly-once`)
- Queue durability redesign
- Full dead-letter pipeline design

Those can be layered later without reintroducing silent success behavior.
