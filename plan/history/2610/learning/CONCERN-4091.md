---
source: CONCERN-4091
timestamp: '2026-10-05T17:54:56.958978+00:00'
title: Close-case fan-out on a lagging replica may write an RM step the ledger never
  recorded
type: learning
---

## Concern

The close-case fan-out (`ApplyCloseCaseFromLedgerNode`) closes each actor through `RMClosureWriter`, which walks `rm_closure_path()` from the replica's own stored RM state for that actor, not from the steps the CASE_MANAGER committed.

A replica that lags (it still has the actor at VALID when the manager had the actor at DEFERRED) writes V → D → C locally. The manager wrote only D → C. The end state is CLOSED in both cases, but the replica's per-participant RM history now holds a DEFERRED write that no ledger entry backs.

The ledger is meant to be the authority for shared state (CM-23-005, CLP-07). A replica history the ledger does not back can confuse audit, the RSH-06 anomaly reporting, and later reconciliation.

Directions named: drive the replica's closure from committed entries, or mark the local-only step as derived. Surfaced by PR #4090 (#4044). Governing specs: CM-23-005, SYNC-12, RSH-06.

**Resolved**: 2026-10-05 — implementation tracked in #4210.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4209>.

## Decision

The ledger carries each move. After the `close_case` receipt entry, the CASE_MANAGER commits one participant-status entry per RM transition it writes for the leaving actor (a Leave from Valid is two entries). Replicas apply them in order and never derive a path.

Planning found the issue's premise partly off: the ledger held only one `close_case` entry for the departing actor, and `CommitCaseActorRMClosedEntryNode` records only the CASE_MANAGER's own closure. Other decisions:

- The RM table is unchanged (VP-02-004). Allowing V → C was rejected again, and START → RECEIVED → CLOSED would stay multi-step anyway.
- CLP-07-002 is reworded: an act and its recorded consequences are separate facts.
- Ledgers in the old form are obsolete (prototype).
- A failed step commit stays a best-effort WARNING.

Spec: `specs/case-management.yaml` CM-23-001.
Notes: `notes/domain-validation.md`, `notes/case-ledger-authority.md`.
