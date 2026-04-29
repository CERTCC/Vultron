---
title: "TECHDEBT-34 \u2014 EM state transition guards (2026-03-24)"
type: implementation
date: '2026-03-24'
source: TECHDEBT-34
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2949
legacy_heading: "TECHDEBT-34 \u2014 EM state transition guards (2026-03-24)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-24'
---

## TECHDEBT-34 — EM state transition guards (2026-03-24)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2949`
**Canonical date**: 2026-03-24 (git blame)
**Legacy heading**

```text
TECHDEBT-34 — EM state transition guards (2026-03-24)
```

**Legacy heading dates**: 2026-03-24

**Task**: Verify and add guards to unguarded direct `em_state =` assignments
in `vultron/core/`.

### What was done

Audited all direct `em_state =` and `rm_state =` assignments in
`vultron/core/use_cases/` and `vultron/core/behaviors/`.

**EM sites addressed (3 unguarded `em_state = EM.ACTIVE`):**

1. `SvcEvaluateEmbargoUseCase` (`triggers/embargo.py`) — trigger-side: replaced
   direct assignment with `EMAdapter` + `create_em_machine()` + `adapter.accept()`
   pattern. `MachineError` now raises `VultronConflictError`. Consistent with
   `SvcProposeEmbargoUseCase` and `SvcTerminateEmbargoUseCase`.

2. `AddEmbargoEventToCaseReceivedUseCase` (`embargo.py`) — receive-side: added
   `is_valid_em_transition()` check with WARNING log on non-standard transition.
   Proceeds regardless (documented justification: state-sync override when
   local state lags behind sender's state).

3. `AcceptInviteToEmbargoOnCaseReceivedUseCase` (`embargo.py`) — receive-side:
   same pattern as #2.

**RM sites (no changes needed):** All `rm_state=RM.XXX` in core are
constructor arguments for new `VultronParticipantStatus` objects — initial-state
constructions, not transitions. The `append_rm_state()` method already enforces
`is_valid_rm_transition()` for all state-mutation paths.

Added `is_valid_em_transition` import to `embargo.py`.

Updated 2 existing tests to start from `EM.PROPOSED` (correct pre-condition
for the `PROPOSED → ACTIVE` transition). Added 3 new tests:

- `test_add_embargo_event_to_case_warns_on_non_standard_transition`
- `test_accept_invite_to_embargo_warns_on_non_standard_transition`
- `test_evaluate_embargo_raises_conflict_when_em_state_invalid`

### Test results

988 passed, 5581 subtests passed.
