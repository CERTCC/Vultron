---
source: CONCERN-2739
timestamp: '2026-08-28T14:23:51.266552+00:00'
title: save ordering in case_status.py — dimension may not be persisted
type: note
---

Closed as duplicate of CONCERN-2700. Both concerns described the same stale `add_dimension`-before-save ordering issue in `case_status.py`. The pattern they flagged was eliminated by the ISSUE-2256 per-dimension filter refactor; no separate code fix was needed.

Resolved by PR #2805 (<https://github.com/CERTCC/Vultron/pull/2805>), which removed the superseded `ValidateCaseStatusTransitionNode` and `CheckParticipantRMNotClosedNode` nodes entirely.
