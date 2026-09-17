---
source: NOTES-domain-model-separation--actor-isolation-outbox
timestamp: '2026-09-17T17:22:01.249740+00:00'
title: Actor isolation and outbox delivery design decisions
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) captured in ADR-0012 and ADR-0042
**Superseded by:** docs/adr/0012-*; docs/adr/0042-*

---

## Actor Isolation and Outbox Delivery Design Decisions

### Actor Isolation Invariant

Each actor MUST be isolated in its own process and environment (e.g., a
container). All interaction between actors happens exclusively through
sending and receiving Vultron AS2 messages via the HTTP API. No actor can
directly access another actor's DataLayer.

**Consequences:**

- Outbox delivery cannot assume local access to other actors' data or state.
- Outbox delivery MUST use HTTP POST to remote inboxes via the FastAPI
  adapter (`DemoHttpDeliveryAdapter.emit()` POSTs to `{actor_uri}/inbox/`).
- Idempotency cannot be checked by inspecting a remote DataLayer. The inbox
  handler itself MUST handle duplicates — checking `actor.inbox.items` and
  returning HTTP 202 immediately on a duplicate activity ID.

### Outbox Delivery is HTTP POST

`DemoHttpDeliveryAdapter.emit()` delivers outbound activities via async
`httpx.AsyncClient` HTTP POST to `{actor_uri}/inbox/`. Direct DataLayer
writes to recipient inboxes are **not** used.

OX-1.3 idempotency is enforced at `POST /actors/{id}/inbox/`: the endpoint
checks `actor.inbox.items` (the persistent received log) before enqueueing
and returns 202 immediately on a duplicate activity ID.

Trigger use-cases and BT nodes that create outgoing activities call
`dl.record_outbox_item(actor_id, activity_id)` to enqueue items in
`{actor_id}_outbox`, which `outbox_handler` drains.

**Reference:** `plan/IMPLEMENTATION_NOTES.md` entries dated 2026-03-25.
