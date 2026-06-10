---
source: ISSUE-746
timestamp: '2026-06-04T16:53:19.217525+00:00'
title: 'EmbargoLifecycle scaffold: service module + types + propose_embargo (STRICT)'
type: implementation
---

## Issue #746 — EmbargoLifecycle scaffold: service module + types + propose_embargo (STRICT)

Scaffolded the `EmbargoLifecycle` service as the first delivery of Epic #538
(RFC: Introduce EmbargoLifecycle service).

### New files

- `vultron/core/services/__init__.py` — new `core/services/` package
- `vultron/core/services/embargo_lifecycle.py` — `TransitionMode`,
  `ParticipantPECChange`, `EmbargoLifecycleResult`, `EmbargoLifecycle`
- `test/core/services/__init__.py` — test package marker
- `test/core/services/test_embargo_lifecycle.py` — 8 boundary tests via
  in-memory `SqliteDataLayer`

### What was implemented

- `TransitionMode(StrEnum)`: `STRICT` | `OBSERVED`
- `EmbargoLifecycleResult(BaseModel)`: full result model with `em_before`,
  `em_after`, `case_changed`, `case_embargo_changed`, `pec_reset`,
  `participant_changes`
- `EmbargoLifecycle.propose_embargo()` (STRICT mode): drives EM state machine
  via `EMAdapter`; cascades PEC `SIGNATORY→LAPSED` on `ACTIVE→REVISE`;
  raises `VultronInvalidStateTransitionError` on invalid transitions;
  raises `NotImplementedError` for OBSERVED mode (deferred to #747);
  no ownership gate — authorization is caller responsibility

### Test coverage (AC-5)

8 boundary tests: NONE→PROPOSED, idempotent re-propose (no duplicate entry),
ACTIVE→REVISE PEC cascade, REVISE→REVISE (no cascade), EXITED raises
`VultronInvalidStateTransitionError`, OBSERVED mode raises `NotImplementedError`,
owner actor succeeds, non-owner actor also succeeds.

### Key design decisions

- `_as_id()` duplicated from `use_cases/_helpers.py` with a TODO to consolidate
  in `vultron.core.utils` — avoids services→use_cases cross-package dependency
- `case_changed` is derived from actual mutations (em_state changed OR
  embargo_id newly appended), not hardcoded True
- `case_embargo_changed = False` for propose (active_embargo set only on accept)

PR: [#777](https://github.com/CERTCC/Vultron/pull/777)
