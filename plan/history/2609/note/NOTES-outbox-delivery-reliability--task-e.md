---
source: NOTES-outbox-delivery-reliability--task-e
timestamp: '2026-09-17T17:32:39.925791+00:00'
title: Task E — Ledger entry correlation (OX-14)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** OX-14 ledger correlation, PR #3317

---

## Task E — Ledger entry correlation (OX-14) ✅ IMPLEMENTED

**Implemented in PR #3317 (2026-09-17). See ADR-0066 §OX-14-001–003.**

Correlates an exhausted `Announce(CaseLedgerEntry)` activity to its canonical
`CaseLedgerEntry` by adding a `ledger_entry_id` field to `OutboxDeadLetterEntry`.

**Implementation files:**

- `vultron/adapters/outbox_dead_letter.py` — new `ledger_entry_id: NonEmptyString | None = None`
  field on `OutboxDeadLetterEntry`; `dead_letter_append` Protocol signature updated
- `vultron/adapters/driven/datalayer_sqlite/queues.py` — `dead_letter_append` accepts
  and persists `ledger_entry_id`
- `vultron/adapters/driven/datalayer_sqlite/datalayer.py` — forwards `ledger_entry_id`
  through to `queues.dead_letter_append`
- `vultron/adapters/driving/fastapi/outbox_handler.py` — new `_resolve_ledger_entry_id`
  helper; exhaustion branch calls it before `dead_letter_append`
- `test/adapters/driven/test_sqlite_outbox_dead_letter.py` — 3 new OX-14 tests
- `test/adapters/driving/fastapi/test_outbox_handler.py` — 6 new OX-14 tests

**Key design choices:**

- `_resolve_ledger_entry_id(activity_id, dl)` reads the activity from the DataLayer
  and inspects `object_.type_` at exhaustion time. Returns `None` for non-ledger
  activities so they dead-letter unchanged (OX-14-001 AC-4).
- The emit-after-commit invariant (OX-14-002) guarantees the `CaseLedgerEntry` is
  always persisted before the `Announce` is queued, so `dl.read(activity_id)` is
  always resolvable when `_resolve_ledger_entry_id` runs.
- `ledger_entry_id` is `NonEmptyString | None = None` — satisfies CS-08-001 (no
  empty-string values allowed in optional fields).

---
