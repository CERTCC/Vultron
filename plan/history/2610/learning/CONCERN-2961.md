---
source: CONCERN-2961
timestamp: '2026-10-22T14:50:19.587070+00:00'
title: 'Proactive replication-gap detection: participants state their ledger position'
type: learning
---

## Summary

`VultronReplicationState` records `last_acknowledged_hash` and `updated_at` per peer, keyed by `{case_id}/replication/{peer_id}`. The CaseActor knows its own ledger tail hash at all times. The comparison needed to detect a silently-lagging replica is therefore trivially available: if a peer's `last_acknowledged_hash != current_tail_hash`, that peer is behind.

What is absent is anything that performs this check proactively. `replay_missing_entries_trigger()` (`vultron/core/use_cases/triggers/sync.py`) can push the missing suffix to a named peer, but it is only ever invoked reactively from `RejectLedgerEntryReceivedUseCase` — i.e. only when a peer sends a `Reject(CaseLedgerEntry)`. If a replayed `Announce(CaseLedgerEntry)` batch is lost in transit, the peer stops sending Rejects (it received nothing new to reject), the CaseActor has no signal to retry, and the replica stays permanently diverged.

SYNC-00-003 requires a "full synchronisation loop, retry, and backoff". SYNC-00-007 requires gap detection. SYNC-00-008 requires retrying until the peer's tail hash converges. The reactive model satisfies these under normal packet loss but not under persistent delivery failure where Rejects also stop arriving.

## Design decision needed

Two viable approaches:

**Option A — opportunistic on-commit sweep**: After `FanOutLogEntryNode` commits and fans out entry N, iterate all `VultronReplicationState` objects for the case and call `replay_missing_entries_trigger()` for any peer whose `last_acknowledged_hash != entry_N.entry_hash`. Rate-limit via the existing `replay_guard` cooldown. Simple, no new infrastructure.

**Option B — Sentinel-shaped watcher**: A persistent background Sentinel that periodically reads all per-peer replication states for active cases, compares each peer's `last_acknowledged_hash` to the current ledger tail, and replays to lagging peers. More powerful (catches gaps even when no new entries are being committed), but requires a scheduler or heartbeat mechanism — Vultron has no current scheduler.

The existing `updated_at` field on `VultronReplicationState` already provides the staleness signal needed by either option.

## Acceptance Criteria

- [ ] AC-1: A design decision is recorded — Option A (opportunistic) or Option B (Sentinel) — in a spec entry or ADR amendment covering SYNC-00-003/007/008.
- [ ] AC-2: The chosen mechanism detects when a peer's `last_acknowledged_hash` diverges from the CaseActor ledger tail.
- [ ] AC-3: `replay_missing_entries_trigger()` is called for lagging peers via the chosen mechanism, subject to the existing `replay_guard` cooldown.
- [ ] AC-4: A test covers the scenario where a peer's Reject is never received (delivery failure) and verifies that the proactive mechanism still converges the replica.

## Reference

Model: `vultron/core/models/replication_state.py` (`VultronReplicationState.last_acknowledged_hash`, `updated_at`)
Trigger helper: `vultron/core/use_cases/triggers/sync.py:replay_missing_entries_trigger()`
Reactive call site: `vultron/core/use_cases/received/sync.py:RejectLedgerEntryReceivedUseCase`
Rate-limit guard: `vultron/core/behaviors/sync/nodes/replay_guard.py`
Spec: `specs/sync-ledger-replication.yaml` SYNC-00-003, SYNC-00-007, SYNC-00-008

**Resolved**: 2026-10-22 — implementation tracked in #5098, #5099.
The premise of both options shifted: the CASE_MANAGER has no positive acknowledgement
(`last_acknowledged_hash` is written only by a `Reject`), and
`replay_missing_entries_trigger()` has no production caller. The chosen design
(ADR-0155) has participants state their ledger position — `ledgerTail` on every
activity to the CASE_MANAGER, and `Read(CaseLedgerEntry)` when they choose — and the
CASE_MANAGER replays to an active participant that is behind, under the existing
replay rate bound. No CASE_MANAGER sweep.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5101>.
Spec: `specs/sync-ledger-replication.yaml`.
Notes: `notes/sync-ledger-replication.md`.
