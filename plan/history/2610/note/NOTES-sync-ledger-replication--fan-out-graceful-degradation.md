---
source: NOTES-sync-ledger-replication--fan-out-graceful-degradation
timestamp: '2026-10-02T04:37:14.328229+00:00'
title: 'Superseded: Fan-Out Graceful Degradation (sync-ledger-replication)'
type: note
---

Archived because #4113 made a missing sync port a wiring fault on the commit
path: the rule below (fan-out may skip silently without a port) let
CASE_MANAGER commits from received use cases go unannounced.

Superseded by `notes/sync-ledger-replication.md` § "A Missing Sync Port Is
a Wiring Fault".

---

## Fan-Out Graceful Degradation

`_fan_out_log_entry` (in `vultron/core/use_cases/triggers/sync.py`) queues one
`Announce(CaseLedgerEntry)` per peer participant. `sync_port` is an **optional**
injection: when it is absent (single-actor context, tests, or configurations
without a `SyncActivityAdapter`), the function logs at `DEBUG` level and
returns immediately instead of raising.

This differs from the two functions that **require** `sync_port`:

- `_send_rejection` — must be able to send a rejection; raises `VultronError`
  if `sync_port` is absent.
- `replay_missing_entries_trigger` — replaying entries to a peer requires an
  outbound channel; raises `VultronError` if `sync_port` is absent.

**Rule**: fan-out is optional behaviour — skipping it silently is correct when
no sync port is configured. Rejection and replay paths are not optional; they
MUST raise if the port is missing.

This means BT node tests and single-actor integration tests do **not** need a
`sync_port` injected on the blackboard or as a use-case parameter — the absence
is handled gracefully without patching.

---
