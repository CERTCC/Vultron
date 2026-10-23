---
title: "OX-1.1/1.2/1.3 \u2014 Outbox delivery implementation (2026-03-25)"
type: implementation
timestamp: '2026-03-25T00:00:00+00:00'
source: LEGACY-2026-03-25-ox-1-1-1-2-1-3-outbox-delivery-implementation-20
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3216
legacy_heading: "OX-1.1/1.2/1.3 \u2014 Outbox delivery implementation (2026-03-25)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-25'
---

## OX-1.1/1.2/1.3 — Outbox delivery implementation (2026-03-25)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3216`
**Canonical date**: 2026-03-25 (git blame)
**Legacy heading**

```text
OX-1.1/1.2/1.3 — Outbox delivery implementation (2026-03-25)
```

**Legacy heading dates**: 2026-03-25

**Tasks**: OX-1.1 (local/remote delivery), OX-1.2 (background delivery after
inbox processing), OX-1.3 (inbox idempotency).

**Architecture note**: Each actor runs as an isolated process/container.
Outbox delivery uses HTTP POST to recipient inbox URLs — not direct DataLayer
access. OX-1.3 idempotency is enforced at the receiving inbox endpoint.

### What was done

**`vultron/adapters/driven/delivery_queue.py`** (OX-1.1):

- Replaced stub `emit()` with real HTTP POST delivery using `httpx`.
- Each recipient inbox URL is derived as `{actor_uri}/inbox/` (ActivityPub
  convention).
- Per-recipient failures are logged at ERROR and swallowed so one unreachable
  actor never blocks others.

**`vultron/adapters/driving/fastapi/outbox_handler.py`** (OX-1.1):

- Added `_extract_recipients(activity)` helper — deduplicates `to`/`cc`/
  `bto`/`bcc` fields, handles both string IDs and embedded actor objects.
- Rewrote `handle_outbox_item(actor_id, activity_id, dl, emitter)` — reads
  activity from DataLayer, extracts recipients, calls `emitter.emit()`.
- Updated `outbox_handler(actor_id, dl, shared_dl=None, emitter=None)` to
  accept a shared DataLayer (for reading activity objects) and injectable
  emitter (defaults to `DeliveryQueueAdapter()`).

**`vultron/adapters/driving/fastapi/inbox_handler.py`** (OX-1.2):

- Added `await outbox_handler(actor_id, queue_dl, shared_dl=dl)` at end of
  `inbox_handler` so outbound activities generated during inbox processing
  are delivered immediately after (OX-03-002).

**`vultron/adapters/driving/fastapi/routers/actors.py`** (OX-1.3):

- Added duplicate-activity check in `post_actor_inbox`: if the activity ID is
  already in the actor's inbox queue, returns 202 immediately without
  re-scheduling processing (OX-06-001).
- Updated `post_actor_outbox` to pass shared `dl` as `shared_dl` to
  `outbox_handler`.

**Tests**:

- Updated `test_outbox.py`: new signatures, 6 new delivery-logic tests
  covering `_extract_recipients`, skip-on-no-activity, skip-on-no-recipients,
  deduplication, embedded objects, and emit call verification.
- Updated `test_inbox_handler.py`: added `outbox_list.return_value = []` to
  prevent mock DL issues with the new OX-1.2 outbox trigger.

### Lessons learned

- Outbox delivery must use HTTP POST (not DataLayer access) to support
  isolated-process actors. Each actor manages its own DataLayer; cross-actor
  delivery must go through the HTTP API.
- OX-1.3 idempotency belongs at the inbox endpoint, not the delivery side —
  delivery adapters have no access to remote actor DataLayers.
- The `shared_dl` / `emitter` injectable parameters on `outbox_handler` keep
  the handler testable without requiring real HTTP or real DataLayers.

### Test results

1004 passed, 5581 subtests passed.
