---
source: ISSUE-1866
timestamp: '2026-08-03T16:51:09.310944+00:00'
title: 'fix(pec): route consent writes through PecDimension.transition()'
type: implementation
---

## Issue #1866 — fix(pec): route consent writes through PecDimension.transition() (CM-18-005)

All 10 embargo_consent_state write sites converted to CaseParticipant.apply_pec_transition(trigger). The helper is fail-closed (raises VultronInvalidStateTransitionError on illegal trigger) and calls _sync_latest_status_metadata() to keep ParticipantStatus.consent in sync with embargo_consent_state. Idempotent seed nodes guarded against re-applying ACCEPT to already-SIGNATORY participants. Tests added for AC-3 through AC-7. 5982 passed.

PR: <https://github.com/CERTCC/Vultron/pull/1920>
