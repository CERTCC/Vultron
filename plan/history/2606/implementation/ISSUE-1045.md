---
source: ISSUE-1045
timestamp: '2026-06-18T19:29:11.752304+00:00'
title: Remove BroadcastStatusToPeersNode (step 3) and delete peer_broadcast_bt infrastructure
type: implementation
---

## Issue #1045 — Remove BroadcastStatusToPeersNode (step 3) and delete peer_broadcast_bt infrastructure

Removed the pre-SYNC raw `Add(ParticipantStatus)` re-broadcast step (step 3 of
DEMOMA-07-003) from `add_participant_status_tree` and deleted the entire
`vultron/core/behaviors/broadcast/` package. The `Announce(CaseLedgerEntry)`
fan-out in `_commit_log_cascade_bt` already propagates status updates to all
participants, making the raw re-broadcast a redundant pre-SYNC artefact that
caused every peer to process the same update twice. Per DEMOMA-07-005.

**Changes delivered:**

- Removed `BroadcastStatusToPeersNode` from step 3 of `add_participant_status_tree`
- Simplified `status/nodes/broadcast.py` to only `_find_case_manager_id` (still
  needed by `lifecycle.py`); defined inline instead of re-exporting from the
  deleted broadcast package
- Removed broadcast node exports from `status/nodes/__init__.py`
- Deleted `vultron/core/behaviors/broadcast/` package (3 modules) — no remaining
  callers after step 3 removal
- Deleted `test/core/behaviors/broadcast/` (2 files) and
  `test/core/behaviors/status/nodes/test_broadcast.py`
- Removed step 3 test sections from `test_add_participant_status_bt.py`;
  updated one test assertion to match PR #1046 fail-fast semantics for
  `TerminateEmbargoNode`

**Verification:** 3421 unit tests pass; Black, flake8, mypy, pyright clean.

PR: [https://github.com/CERTCC/Vultron/pull/1053](https://github.com/CERTCC/Vultron/pull/1053)
