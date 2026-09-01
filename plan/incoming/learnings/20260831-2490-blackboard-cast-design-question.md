---
title: "Design decision: cast() for blackboard-sourced VulnerabilityCase type narrowing after isinstance removal"
type: learning
timestamp: 2026-08-31T18:00:00Z
source: ISSUE-2490
signal: design-question
---

When removing `isinstance(x, VulnerabilityCase)` guards from BT nodes that read
`VulnerabilityCase` from the py_trees blackboard (via `_try_get_input("participant_case")`,
`data_type=object` ports), the isinstance removal left `stored_case` typed as `object`.

**Decision**: Use `cast(VulnerabilityCase, stored_case)` after the `is None` guard.
This satisfies static type checkers (mypy/pyright) without adding a runtime isinstance
check. The blackboard contract is enforced by BT composition rather than runtime type
checking — the writer always stores a `VulnerabilityCase` in these slots.

**Tradeoff**: A non-None wrong-type object in the blackboard slot would raise
`AttributeError` instead of returning `Status.FAILURE` cleanly. Filed as #2908 to
tighten `data_type=object` → `data_type=VulnerabilityCase` in port declarations.

**Affected files**: `participant_add.py` (CaseHasActiveEmbargoNode,
CaseHasNoActiveEmbargoNode, RecordParticipantAddedEventNode), `owner.py`
(PersistOwnerCaseNode).
