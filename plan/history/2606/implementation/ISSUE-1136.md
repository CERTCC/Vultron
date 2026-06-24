---
source: ISSUE-1136
timestamp: '2026-06-24T21:05:41.496673+00:00'
title: Add PendingCreateCaseActivity durable marker
type: implementation
---

## Issue #1136 — CP-05-005 (part 1): Add PendingCreateCaseActivity durable marker and wire into received BT tree

Added a durable `PendingCreateCaseActivity` DataLayer marker and wired it
into the `CreateCaseProposalReceivedBT` tree to satisfy CP-05-005.

### What was done

- Created `vultron/core/models/pending_create_case_activity.py`: new
  `VultronObject` subclass with `proposal_id`, `case_actor_id`, `vendor_uri`,
  and `create_activity_payload` fields; stable `id_` derived from `proposal_id`
  via `build_id()`.
- Created `vultron/wire/as2/vocab/objects/pending_create_case_activity.py`:
  registers `PendingCreateCaseActivity` in the wire `VOCABULARY` so SQLite
  DataLayer can deserialize it.
- Extended `case_proposal_received_tree.py` from a 3-node to a 5-node
  Sequence: `_WriteCreateCaseMarkerNode` (writes marker after Accept, before
  Create) and `_ClearCreateCaseMarkerNode` (clears on Create success; always
  returns SUCCESS).
- Added 13 unit tests in `test/core/behaviors/case/test_case_proposal_received_tree.py`
  covering model round-trips, marker write/clear, and partial-failure paths.
- All 4334 unit tests pass; Black, flake8, mypy, pyright clean.

PR: [#1154](https://github.com/CERTCC/Vultron/pull/1154)
