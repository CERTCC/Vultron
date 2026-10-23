---
source: ISSUE-949
timestamp: '2026-06-15T16:08:02.335839+00:00'
title: Add INFO/DEBUG logging for case-ledger commit events
type: implementation
---

## Issue #949 — Track B: Add INFO-level logging for case-ledger commit events

Added structured INFO and DEBUG logging at the two ledger-commit points to
fill the missing layer-3 diagnostic gap ("was it committed to the ledger?")
for Demo Integration CI failures.

### Changes

- `vultron/core/models/case_ledger.py`: added module logger; `CaseLedger.append()`
  now emits `logger.info()` (case_id, event_type, log_index, disposition) and
  `logger.debug()` (entry_hash prefix, payload_snapshot) after each hash-chain commit
- `vultron/core/behaviors/sync/nodes/chain.py`: enhanced `PersistLogEntryNode.update()`
  INFO log to include case_id, event_type, log_index, actor_id; added DEBUG log with
  entry_hash prefix and payload_snapshot
- `test/core/models/test_case_ledger.py`: added `TestCaseLedgerAppendLogging` (7 tests)
  covering INFO and DEBUG emission from `CaseLedger.append()`
- `test/core/behaviors/sync/nodes/test_chain.py`: added `TestPersistLogEntryNodeLogging`
  (5 tests) verifying INFO fields (event_type, log_index, actor_id) and DEBUG
  entry_hash prefix in `PersistLogEntryNode`

### Outcome

All 3220 unit tests pass (12 new).
PR: [#953](https://github.com/CERTCC/Vultron/pull/953)
