---
source: CONCERN-1871
timestamp: '2026-08-21T17:47:13.925793+00:00'
title: 'concern(pec): apply_pec_trigger is fail-open — invalid triggers silently no-op
  and get reported as success'
type: learning
---

`apply_pec_trigger` (`vultron/core/states/participant_embargo_consent.py`) returned the **unchanged** state on an invalid trigger, logging a warning instead of raising. Every caller that did not compare the result against the input therefore reported success while recording nothing. This is a fail-open API contract.

Six production call sites were audited; the most concerning were in `services/embargo_lifecycle.py` which set `changed = True` **unconditionally** after the call and then emitted a `ParticipantPECChange` record whose `pec_after` equals `pec_before`.

Three resolution options were considered:

1. Make `apply_pec_trigger` raise `VultronInvalidStateTransitionError`
2. Return `PEC | None` and force callers to handle failure explicitly
3. Deprecate `apply_pec_trigger` in favour of `PecDimension.transition()` (chosen)

All production sites were migrated to `CaseParticipant.apply_pec_transition()` which delegates to `PecDimension.transition()` (fail-closed) in #1865 and #1866. The related `CreateParticipantStatusNode` fail-open path was tracked and resolved as #1896 (implementation in #2081, #2082). `apply_pec_trigger` remains in the module but is only used in tests; its removal is tracked in #2472.

**Resolved**: 2026-08-21 — implementation tracked in #2472.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2471>.
Spec: `specs/case-management.yaml` CM-18-005.
Notes: `notes/participant-embargo-consent.md`.
