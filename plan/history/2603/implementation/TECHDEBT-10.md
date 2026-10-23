---
title: "TECHDEBT-10 \u2014 Backfill pre-case events in create_case BT (2026-03-10)"
type: implementation
timestamp: '2026-03-10T00:00:00+00:00'
source: TECHDEBT-10
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 852
legacy_heading: "TECHDEBT-10 \u2014 Backfill pre-case events in create_case\
  \ BT (2026-03-10)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-10'
---

## TECHDEBT-10 — Backfill pre-case events in create_case BT (2026-03-10)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:852`
**Canonical date**: 2026-03-10 (git blame)
**Legacy heading**

```text
TECHDEBT-10 — Backfill pre-case events in create_case BT (2026-03-10)
```

**Legacy heading dates**: 2026-03-10

**Task**: Backfill pre-case events into the case event log at case creation
(CM-02-009).

**Implementation**:

- Added `RecordCaseCreationEvents` node to
  `vultron/core/behaviors/case/nodes.py`. The node runs after `PersistCase` in
  the `CreateCaseFlow` sequence.
- The node records two events using `case.record_event()`:
  1. `"offer_received"` — only when the triggering activity has an
     `in_reply_to` reference (the originating Offer that led to case
     creation). The `object_id` is set to the Offer's `as_id`.
  2. `"case_created"` — always recorded; `object_id` is set to the case ID.
- The node reads `activity` from the global py_trees blackboard storage
  (`Blackboard.storage.get("/activity", None)`) rather than registering it as
  a required key. This avoids a `KeyError` when the tree is invoked without an
  inbound activity (e.g. in tests that pass `activity=None`).
- `create_tree.py` updated to import and include `RecordCaseCreationEvents` in
  the sequence.
- 6 new tests added to `test/core/behaviors/case/test_create_tree.py`.

**Key design note**: `received_at` in `CaseEvent` is set by
`default_factory=_now_utc`, satisfying CM-02-009's trusted-timestamp
requirement automatically. The node never copies a timestamp from the
incoming activity.

**866 tests pass.**
