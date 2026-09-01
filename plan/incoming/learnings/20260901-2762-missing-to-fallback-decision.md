---
title: Chose WARNING-and-degrade over fail-fast for an embargo invite with no to:
type: learning
timestamp: 2026-09-01
source: ISSUE-2762
signal: design-question
---

`InviteToEmbargoOnCaseReceivedUseCase` now reads the invitee from
`request.invitee_id` (the activity's `to:` recipient). That leaves a question
the issue did not cover: what to do when `to:` is absent.

Three options were put to the user. The chosen one (option 1) logs a WARNING
naming it as the OX-08-001 violation it is, then falls back to the receiving
actor.

Why not strict fail-fast, which ARCH-15-001 would otherwise suggest:

- On the direct-delivery path the receiving actor genuinely *is* the addressee,
  so the fallback is correct there rather than a fabrication.
- Skipping the PEC and deadline writes would also discard the canonical ledger
  commit the message is entitled to — the guarded-commit branch sits inside the
  same single tree (ADR-0022), so there is no way to skip one without skipping
  the other.
- The WARNING makes the violation visible, which is the property the fallback
  previously lacked.

The residual risk: a malformed invite still mutates a participant record, just
loudly. If OX-08-001 enforcement ever moves to the inbox edge (rejecting
activities with no `to:` before dispatch), this fallback becomes dead code and
should be deleted rather than kept as defence in depth.
