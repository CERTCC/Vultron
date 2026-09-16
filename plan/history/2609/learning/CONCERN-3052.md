---
source: CONCERN-3052
timestamp: '2026-09-15T16:09:46.324702+00:00'
title: ADR-0037 and ADR-0059 claim the SYNC-10 catch-up gate re-syncs the gap buffer
  after restart; it cannot
type: learning
---

Three Consequences entries in ADR-0037, ADR-0059, and notes/sync-ledger-replication.md claimed the SYNC-10 catch-up gate re-syncs the LedgerGapBuffer after a restart. The claim is wrong: is_ledger_fresh_for_case() is a purely local predicate that queries only the actor's own DataLayer and sends nothing. After restart the committed prefix is intact and the gate returns (True, ""); dropped forward-gap entries re-enter via the ordinary diverge/reject/replay path (SYNC-14-002, SYNC-08-005). The decisions themselves (buffer ephemeral, no durability required) are unchanged — only the stated causal mechanism is corrected. CheckLedgerFreshnessNode is exported and tested but not wired into any BT; SYNC-10-001/002 are therefore not enforced at runtime.

**Resolved**: 2026-09-15 — implementation tracked in #3263.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3262>.
