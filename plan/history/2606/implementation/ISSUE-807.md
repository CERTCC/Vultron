---
source: ISSUE-807
timestamp: '2026-06-10T14:45:04.557114+00:00'
title: Remove stale ReplicationState from case_log.py
type: implementation
---

## Issue #807 — Remove stale ReplicationState(BaseModel) from case_log.py

Removed the stale `ReplicationState(BaseModel)` class from
`vultron/core/models/case_log.py`. The class was superseded by
`VultronReplicationState(VultronObject)` in
`vultron/core/models/replication_state.py`, which has a stable
auto-computed `id_` and is properly in the shared-base hierarchy
(ARCH-12-007, source issue #804).

Changes:

- Removed `ReplicationState` class from `case_log.py`; updated module
  docstring to reference `VultronReplicationState` instead
- Fixed stale `CaseLogEntry` reference in a `ValueError` message (class
  was renamed to `HashChainLogRecord` in #806)
- Updated `test/core/models/test_case_log.py` to import and test
  `VultronReplicationState` (with required `case_id` + `peer_id` fields
  and `by_alias=True` in the round-trip test)

All 3124 unit tests pass; Black, flake8, mypy, pyright all clean.

PR: <https://github.com/CERTCC/Vultron/pull/869>
