---
source: ISSUE-848
timestamp: '2026-06-11T18:36:56.331850+00:00'
title: 'BTBridge migration for embargo revision: DataLayerAction node pattern and
  mypy variable naming'
type: learning
---

## 2026-06-09 ISSUE-848 — BTBridge migration for embargo revision use case

- The pre-condition EM state check (ACTIVE/REVISE guard) can move cleanly
  into a `DataLayerAction` node (`ValidateEmbargoRevisionStateNode`) that
  reads the case, checks `current_status.em_state`, and writes the domain
  error into `result_out["error"]` for re-raise by the use case.
- Avoid reusing a local variable `error` across two branches with different
  concrete types (e.g., `VultronValidationError` then
  `VultronInvalidStateTransitionError`) — mypy infers the type from the first
  assignment and flags the second as incompatible. Use distinct variable names
  per branch.
- The counter-revision path (EM.REVISE → EM.REVISE) must be tested separately
  from ACTIVE → REVISE because `_cascade_pec_revise` only fires on the
  ACTIVE → REVISE transition; a counter-revision must leave PEC states
  unchanged.

**Promoted**: 2026-06-11 — captured in `AGENTS.md` pitfalls "mypy Infers
Type From First Branch Assignment" and "Counter-Revision EM Path Must Be
Tested Separately". BT result channel pattern captured in
`notes/bt-integration.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/900>.
