---
source: NOTES-outbox-delivery-reliability--task-d
timestamp: '2026-09-17T17:32:39.601831+00:00'
title: Task D — Per-activity attempt counter + dead-letter
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** MAX_TOTAL_ATTEMPTS=12 + dead-letter store

---

## Task D — Per-activity attempt counter + dead-letter store ✅ IMPLEMENTED

**Implemented in PR #2371 (2026-08-19). See ADR-0066.**

**Implementation files:**

- `vultron/adapters/outbox_dead_letter.py` — `OutboxDeadLetterEntry` model and
  `OutboxRetryStore` Protocol (adapter layer, not core port)
- `vultron/adapters/driven/datalayer_sqlite/queues.py` — `get_outbox_attempt_count`,
  `set_outbox_attempt_count`, `clear_outbox_attempt_count`, `dead_letter_append`,
  `dead_letter_list`
- `vultron/adapters/driven/datalayer_sqlite/schema.py` — `OutboxAttemptEntry` SQLModel
  table (`vultron_outbox_attempts`)
- `vultron/adapters/driving/fastapi/outbox_handler.py` — `MAX_TOTAL_ATTEMPTS = 12`,
  exhaustion branch, `cast(OutboxRetryStore, dl)` pattern
- `test/adapters/driven/test_sqlite_outbox_dead_letter.py` — 13 tests (OX-13-001–004)
- `test/adapters/driving/fastapi/test_outbox_handler.py` — 4 new handler tests

**Design choices (supersedes guidance above):**

- Side-table approach used (`OutboxAttemptEntry` SQLModel, `vultron_outbox_attempts`),
  keeping queue API unchanged.
- `OutboxRetryStore` is an adapter-level Protocol; `SqliteDataLayer` satisfies it
  structurally. `outbox_handler` uses `cast(OutboxRetryStore, dl)` to access the
  delivery-infrastructure methods without polluting the core `CasePersistence` /
  `CaseOutboxPersistence` ports. (This said `ActorScopedDataLayer`; that protocol
  refinement was deleted by ADR-0073 — no DataLayer is unscoped, so there was
  nothing left for it to distinguish.)
- `MAX_TOTAL_ATTEMPTS = 12` is a module-level constant (not constructor-configurable).
- Counter is cleared when an activity is dead-lettered (OX-13-002) so the side-table
  does not accumulate stale rows.

**Remaining open items:**

- Protocol-level NACK on exhaustion (ADR-0066 Option C) still deferred to #1880.

---
