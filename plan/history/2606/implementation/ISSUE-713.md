---
source: ISSUE-713
timestamp: '2026-06-04T13:51:56.471093+00:00'
title: Fix BT layer boundary violations BT-IDM-01 and BT-IDM-02
type: implementation
---

## Issue #713 — Fix BT layer boundary violations BT-IDM-01 and BT-IDM-02

Resolved two Behavior Tree anti-patterns that violated the `use_cases/ →
behaviors/` dependency direction rule.

### BT-IDM-02: `ApplyEmbargoTeardownNode` lazy import removed

Consolidated two functionally-identical PEC reset helpers —
`_reset_case_participant_embargo_consent()` in `received/embargo.py` and
`_cascade_pec_reset()` in `triggers/embargo.py` — into a single canonical
`reset_case_participant_embargo_consent()` in `use_cases/_helpers.py`
(neutral shared utilities layer). `ApplyEmbargoTeardownNode` now imports
from `_helpers` (not from a use-case module), eliminating the lazy import.

### BT-IDM-01: `PublicDisclosureBranchNode` converted to composite

Converted `PublicDisclosureBranchNode` from a `DataLayerAction` leaf (which
lazy-imported and directly called `SvcTerminateEmbargoUseCase`) to a
`py_trees.composites.Selector` with two children:

- `_PublicDisclosureSkipConditionNode` — returns SUCCESS (skip) unless
  sender is CASE_OWNER with public-aware CS.P status
- `TerminateEmbargoNode` (new) — `DataLayerAction` applying the EM state
  machine `ACTIVE/REVISE → EXITED` transition, resetting PEC state for all
  participants, and queuing a `Terminate(EmbargoEvent)` activity to the case
  manager's outbox

`TerminateEmbargoNode` correctly resolves the case manager ID via
`_resolve_case_manager_id()` (not `self.actor_id`, which is the status
sender). Non-fatal: returns SUCCESS for all error conditions.

### Tests added

- 8 new `TestTerminateEmbargoNode` tests (ACTIVE→EXITED, REVISE→EXITED,
  no-embargo skip, invalid transition, missing case, case_id=None, PEC reset,
  activity factory call)
- 3 new `TestPublicDisclosureBranchNode` tests (skip non-CASE_OWNER, skip
  non-public-aware, full teardown trigger path AC-4)
- 2659 unit tests pass; Black, flake8, mypy, pyright all clean

**PR**: [#745](https://github.com/CERTCC/Vultron/pull/745)
