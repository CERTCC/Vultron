---
source: CONCERN-1011
timestamp: '2026-06-16T19:26:10.332308+00:00'
title: Fix BT-06-006 ledger-commit violations in received use cases
type: learning
---

## Problem

Case-ledger commits (persist + `Announce(CaseLedgerEntry)` fan-out) are not
consistently routed through BT nodes.

### 1. BT-06-006 violations: received use cases calling `commit_log_entry_trigger()` directly from `execute()`

Three received-side use cases call `commit_log_entry_trigger()` procedurally,
bypassing BT entirely:

- `vultron/core/use_cases/received/embargo.py` — `_cascade_embargo_log_entry()` called from `execute()`
- `vultron/core/use_cases/received/note.py::AddNoteToCaseReceivedUseCase._commit_log_entry()` — called from `execute()`
- `vultron/core/use_cases/received/status.py::AddParticipantStatusReceivedUseCase._cascade_log_entry()` — called from `execute()`

The `Announce(CaseLedgerEntry)` fan-out is protocol-visible behavior (SYNC-02-002,
BT-15-001). It MUST live in a BT leaf node, not in procedural `execute()` code.

### 2. Two BT node implementations for the same job

- `CommitCaseLedgerEntryNode` (`behaviors/case/nodes/lifecycle.py`) — reads from blackboard,
  sub-composes `create_commit_log_entry_tree()` via `BTBridge.execute_with_setup()`. Used in
  case create / accept_invite / receive_report / prioritize trees.
- `CommitLogCascadeNode` (`behaviors/embargo/nodes/cascade.py`) — takes `case_id/object_id/event_type`
  as constructor params, calls `commit_log_entry_trigger()` directly inside `update()`. Used in
  embargo teardown trees.

### 3. Demo-era `commit_log_entry` trigger endpoint

`TriggerActivityService.commit_log_entry()` in `triggers/service.py` is surfaced as
`POST /{actor_id}/demo/commit-log-entry` in `demo_triggers.py`. Only caller is the demo
router — no production or BT path calls it.

## Resolution

**Resolved**: 2026-06-16 — implementation tracked in #1013.

Docs PR: [#1012](https://github.com/CERTCC/Vultron/pull/1012).
