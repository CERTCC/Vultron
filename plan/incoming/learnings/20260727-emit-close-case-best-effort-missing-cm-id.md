---
title: "EmitCloseCaseNode: best-effort SUCCESS when case_manager_id absent from blackboard"
type: learning
timestamp: "2026-07-27"
source: ISSUE-1716
signal: design-question
---

`EmitCloseCaseNode.update()` returns `SUCCESS` (not `FAILURE`) when
`case_manager_id` is not present on the py_trees blackboard, consistent with
the best-effort semantics used by `SendAnnounceEmbargoEventNode` and the
former `AutoCloseBranchNode._emit_close_case()`.

Rationale: receive-side BT paths intentionally omit `trigger_activity_factory`;
treating a missing `case_manager_id` as `FAILURE` would propagate up through the
`AutoCloseSequence` and cause the `CaseManagerAutoClose` subtree to fail, which
could block subsequent ticks.  Best-effort SUCCESS keeps the tree moving and logs
a WARNING.

The same pattern should be applied consistently wherever `DataLayerAction` nodes
read optional blackboard keys.

**Promoted**: 2026-07-28 — captured in notes/peer-broadcast-failure-semantics.md § Best-Effort Override Exception.
Docs PR: TBD.
