---
source: CONCERN-3103
timestamp: '2026-09-14T14:17:22.885933+00:00'
title: ValidateTriggerTransitionsNode.update() does not catch VultronValidationError
  from resolve_participant_state_from_dl
type: learning
---

## Summary

`resolve_participant_state_from_dl()` raises `VultronValidationError` when the latest `ParticipantStatus` is not core-shaped (ARCH-15-001/002). The call site at `trigger_validation.py:185` was inside `ValidateTriggerTransitionsNode.update()` with no enclosing `try/except`, so a corrupted or wire-shaped participant record caused the exception to propagate out of `update()` rather than returning `Status.FAILURE`.

## Impact

`py_trees` surfaced the uncaught exception through the parent Sequence; `SvcBTTriggerBase.execute()` never reached its result-check; the HTTP caller received an unhandled 500 instead of a 422 `VultronValidationError` response.

## Suggested fix

Wrap the `resolve_participant_state_from_dl` call in a `try/except VultronValidationError` block and return `Status.FAILURE` with a descriptive `feedback_message`.

## References

- `vultron/core/behaviors/case/nodes/participant/trigger_validation.py:185`
- `vultron/core/behaviors/case/nodes/participant/common.py:217`
- Surfaced by code review of PR #3102 (issue #3057)

**Resolved**: 2026-09-02 — already fixed in commit cbfddc8e6 as a first-order finding discovered during PR #3102 review. `resolve_transition_context_or_report()` in `common.py` catches `VultronValidationError` and returns `Status.FAILURE` with a descriptive `feedback_message`. Two regression tests added to `test/core/use_cases/triggers/case/test_add_participant_status.py`.
