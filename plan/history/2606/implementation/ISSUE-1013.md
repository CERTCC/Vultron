---
source: ISSUE-1013
timestamp: '2026-06-16T20:21:14.106814+00:00'
title: 'Fix BT-06-006: unify ledger commits on CommitCaseLedgerEntryNode'
type: implementation
---

## Issue #1013 — Fix BT-06-006 ledger-commit violations: unify on CommitCaseLedgerEntryNode, remove CommitLogCascadeNode and demo endpoint

Eliminated all BT-06-006 violations by routing every case-ledger commit
through `CommitCaseLedgerEntryNode` via `BTBridge.execute_with_setup()`.

### Changes made

- **`embargo/announce_teardown_tree.py`**: Replaced `CommitLogCascadeNode`
  with `CommitCaseLedgerEntryNode(case_id=case_id)` in all 4 teardown tree
  factories; removed `payload_snapshot` parameters
- **`embargo/nodes/cascade.py`**: Deleted `CommitLogCascadeNode` class;
  removed from all `__init__.py` exports
- **`received/embargo.py`**: Removed `_commit_embargo_log_cascade()`;
  added `BTBridge+CommitCaseLedgerEntryNode` for RemoveEmbargo always-commit
  pattern; passed `sync_port` to all `execute_with_setup` calls
- **`received/note.py`**: Removed `_commit_log_cascade()`; replaced with
  inline `BTBridge+CommitCaseLedgerEntryNode` with `sync_port`
- **`received/status.py`**: Replaced `_commit_log_cascade()` with
  `_commit_log_cascade_bt()` using `BTBridge+CommitCaseLedgerEntryNode`
- **`triggers/service.py` + `ports/trigger_service.py`**: Removed
  `commit_log_entry()` method
- **`triggers/sync.py`**: Removed `commit_log_entry_trigger` and all helpers;
  only `replay_missing_entries_trigger` remains
- **`demo_triggers.py` + `trigger_models.py`**: Removed `demo_sync_log_entry`
  endpoint and `SyncLogEntryRequest` model
- **`sync/nodes/chain.py`**: Added 3 missing canonical payload signatures:
  `(Add, EmbargoEvent)`, `(Remove, EmbargoEvent)`, `(Invite, EmbargoEvent)`
- Updated all affected tests; fixed `_to_persistable_entry` imports to use
  canonical location (`vultron.core.behaviors.sync.nodes.chain`)

### Outcome

All 3402 tests pass, all 4 linters clean.

PR: [#1017](https://github.com/CERTCC/Vultron/pull/1017)
