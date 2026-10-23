---
source: NOTES-participant-embargo-consent--implementation-notes
timestamp: '2026-09-17T17:32:40.524640+00:00'
title: Implementation Notes
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** vultron/core/behaviors/case/case_participant.py apply_pec_transition

---

## Implementation Notes

- The state machine SHOULD be implemented using the `transitions` library,
  consistent with the RM, EM, and CS state machines elsewhere in the codebase
- The machine name is `ParticipantEmbargoConsent`
- Define states and triggers in a new module:
  `vultron/core/states/participant_embargo_consent.py`
- `ParticipantStatus.embargo_adherence` is a `@computed_field` (Pydantic v2)
  that returns `self.consent is not None and self.consent.state == PEC.SIGNATORY`.
  It MUST NOT be declared as a stored field. Consent writes go through
  `apply_pec_transition()` on `CaseParticipant`; the computed field reflects the
  result automatically. Decision: ADR-0056.

---
