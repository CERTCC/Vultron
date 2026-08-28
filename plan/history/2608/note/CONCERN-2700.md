---
source: CONCERN-2700
timestamp: '2026-08-28T14:24:40.515224+00:00'
title: case_status.py dl.save(case_status) called before add_dimension — dimension
  may not be persisted
type: note
---

Closed as stale. The `add_dimension`-before-save ordering concern described here was eliminated by the ISSUE-2256 per-dimension filter refactor. Current `AppendCaseStatusToCaseNode.update()` save ordering is correct: save filtered status → add to case → save case. No code fix needed.

Resolved by PR #2805 (<https://github.com/CERTCC/Vultron/pull/2805>), which removed the superseded `ValidateCaseStatusTransitionNode` and `CheckParticipantRMNotClosedNode` nodes entirely.
