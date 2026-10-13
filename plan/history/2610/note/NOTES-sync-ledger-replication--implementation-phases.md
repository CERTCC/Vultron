---
source: NOTES-sync-ledger-replication--implementation-phases
timestamp: '2026-10-12T19:32:53.328264+00:00'
title: Implementation Phases
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered: AppendOnlyLedger through PeerLedgerSync are built; multi-node content moved to notes/case-actor-cluster.md
**Superseded by:** vultron/core/behaviors/sync/; specs/sync-ledger-replication.yaml; notes/case-actor-cluster.md

---

## Implementation Phases

| Phase  | Description                                               |
|--------|-----------------------------------------------------------|
| AppendOnlyLedger | Local append-only log with hash-chain indexing            |
| LedgerFanout | One-way replication from the CASE_MANAGER to Participant Actors  |
| LedgerReconciliation | Full sync loop with retry/backoff                         |
| PeerLedgerSync | Multi-peer synchronization (completes single-node CaseActor participant replication) |

### AppendOnlyLedger Scope

The canonical `CaseLedgerEntry` model (see `notes/case-ledger-authority.md`)
provides the foundation. AppendOnlyLedger extended it toward a true canonical recorded
log with hash-chain indexing; the richer long-term content model is described
in `notes/case-ledger-authority.md`.

Note: the earlier `CaseEvent` lightweight event model and
`VulnerabilityCase.record_event()` helper were removed in #792 once
canonical `CaseLedgerEntry` fully covered protocol-significant history.

Core domain classes (transport-agnostic):

- `CaseLedger` — append-only log; enforces immutability and hash-chain
- `ReplicationState` — per-peer last-acknowledged hash

`CaseLedgerEntry` fields for AppendOnlyLedger:

- `log_index` — gapless, monotonically increasing integer scoped to the case,
  starting at 0 for the genesis entry (MUST; see SYNC-01-002, CLP-14-010). Added in AppendOnlyLedger so downstream code and wire format are
  index-aware from the start.
- `term` — Raft term number (OPTIONAL in AppendOnlyLedger; defaults to `null` or `0`
  in single-node deployments; becomes required when multi-node CaseActor
  cluster is introduced in Phase 3).

Adapter responsibilities:

- AS2 `Announce` activity mapping (outbound replication message)
- Inbound handler for `Announce` (participant receiving a log entry)
- File/database log storage

### LedgerFanout Scope

One-way replication from the CASE_MANAGER to each Participant Actor:

- Strict conflict handling: reject mismatched `prev_log_hash`, respond
  with last-accepted hash
- Sender retries from the entry following the reported last-accepted hash

Design Decision (blocks LedgerFanout): Reconcile "replication leadership" with
"Case Ownership". Case Ownership governs who controls the case lifecycle
(e.g., closing the case, transferring ownership). Replication leadership
governs which node currently accepts writes to the log. These are distinct:

- A case ownership transfer implies a replication leadership change.
- A replication leadership change alone does NOT imply an ownership transfer.

---
