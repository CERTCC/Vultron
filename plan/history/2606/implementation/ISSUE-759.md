---
source: ISSUE-759
timestamp: '2026-06-04T17:18:13.153754+00:00'
title: Add BTs to CreateReport, AckReport, CloseReport, InvalidateReport received
  use cases
type: implementation
---

## Issue #759 — Add BTs to report received use cases: CreateReport, AckReport, CloseReport, InvalidateReport

Wrapped the four procedural received-side report use cases in Behavior Trees,
following the pattern established in #758.

### Delivered

**New files:**

- `vultron/core/behaviors/report/nodes/storage.py` — `StoreReportNode` and
  `StoreActivityNode` (idempotent storage nodes)
- `vultron/core/behaviors/report/received_report_trees.py` — four BT factory
  functions

**Modified files:**

- `vultron/core/behaviors/report/nodes/rm_transitions.py` — added
  `TransitionCaseParticipantRMtoClosed` and `TransitionCaseParticipantRMtoInvalid`
  with shared `_transition_case_participant_rm()` helper (soft-pass on no-case-found;
  FAILURE only when transition is blocked)
- `vultron/core/behaviors/report/nodes/__init__.py` — re-exports new node classes
- `vultron/core/use_cases/received/report.py` — all four target use cases delegate
  to BTBridge (deferred imports pattern)
- `test/core/behaviors/report/conftest.py` — adds `make_payload` fixture
- `test/core/behaviors/report/test_received_report_trees.py` — 33 tests covering
  node, tree, and use-case levels

### Key learnings

`StoreActivityNode` uses a narrow `ValueError` catch instead of the
`_idempotent_create()` pattern because `dl.read()` cannot retrieve
`VultronActivity` by URI — they are stored in type-keyed collections (e.g.
`"Create"`, `"Read"`). The `ValueError` from `dl.create()` always means
"duplicate" for activities. `StoreReportNode` correctly uses
`_idempotent_create()` since `dl.read()` works for `VulnerabilityReport`.

### Outcome

2823 tests passing, all 4 linters clean.

PR: [#779](https://github.com/CERTCC/Vultron/pull/779)
