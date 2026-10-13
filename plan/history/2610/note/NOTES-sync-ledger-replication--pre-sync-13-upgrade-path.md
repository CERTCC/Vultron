---
source: NOTES-sync-ledger-replication--pre-sync-13-upgrade-path
timestamp: '2026-10-12T19:32:53.913449+00:00'
title: Pre-SYNC-13 Upgrade Path
type: note
---

**Archived:** 2026-10-12
**Reason:** decided (accept, no repair path; no deployed nodes) and closed
**Superseded by:** SYNC-13; #1446

---

## Pre-SYNC-13 Upgrade Path

Nodes that ran pre-SYNC-13 code may hold stale `{entry: stored, effects: not-applied}`
state. This arises because `_store_nested_inbox_object` formerly persisted a
`CaseLedgerEntry` during parse without applying the entry's domain effects. When such
a node later receives the same `Announce(CaseLedgerEntry)`, `CheckLedgerEntryAlreadyStoredNode`
(SYNC-12-003) fires SUCCESS and the entire `ProcessAndStore` subtree — including
`LogEntryEventEffects` — is skipped. The entry's effects are never applied, and the
node's derived state (e.g., participant list, EM state) remains stale.

**Resolution: Accept.** No repair path is implemented. The pre-SYNC-13 code was a
bug in pre-production code with no extant deployed nodes or cases. The correct recovery
for any node in this state is to wipe its local DataLayer for the affected case and
re-sync from the CASE_MANAGER. Re-sync replays all `Announce(CaseLedgerEntry)` entries
from the beginning; each entry passes the `CheckLedgerEntryAlreadyStoredNode` gate
(FAILURE — not yet stored), so `ProcessAndStore` runs and effects are applied correctly.

This is tracked as issue #1446.
