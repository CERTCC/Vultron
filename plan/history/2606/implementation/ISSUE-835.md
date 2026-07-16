---
source: ISSUE-835
timestamp: '2026-06-18T18:56:48.219939+00:00'
title: Migrate status and embargo BT broadcast paths to fail-fast semantics
type: implementation
---

## Issue #835 — Migrate status and embargo BT broadcast paths to fail-fast semantics

Migrated the status and embargo behavior tree broadcast paths to fail-fast
semantics per spec BT-14-001: protocol-visible peer broadcast fan-out nodes
now return `FAILURE` on delivery errors instead of silently swallowing them.

**Embargo path** (`TerminateEmbargoNode`): `_dispatch_activity()` return type
changed from `None` to `Status`; returns `FAILURE` when factory unavailable,
`case_manager_id` missing, or dispatch raises; returns `SUCCESS` on successful
enqueue. `update()` now propagates the result rather than always returning
`SUCCESS`.

**Status path** (`BroadcastStatusToPeersNode`): already migrated by #834 to
use the shared fail-fast `peer_broadcast_bt` helper. Removed dead
`CreateStatusBroadcastActivityNode` class and all associated test classes.

**Test updates**: embargo lifecycle tests updated from `SUCCESS→FAILURE` for
no-factory cases; new `test_returns_failure_when_factory_raises` added; status
test files cleaned of dead class; `test_add_participant_status_bt.py` updated
to use `CreateBroadcastActivityNode` and added `SUCCESS` path test with mock
factory.

PR: [#1046](https://github.com/CERTCC/Vultron/pull/1046)
