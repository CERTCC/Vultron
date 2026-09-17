---
source: NOTES-triggerable-behaviors--per-participant-embargo-acceptance-tracking
timestamp: '2026-09-17T17:32:56.388664+00:00'
title: Per-Participant Embargo Acceptance Tracking
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,b) delivered
**Superseded by:** accepted_embargo_ids in case_participant.py; CM-10

---

## Per-Participant Embargo Acceptance Tracking

**Design Decision**: `CaseParticipant` MUST track which embargo(es) a
participant has explicitly accepted. (resolved — see
`specs/case-management.yaml` CM-10-*)

Cases can have a series of embargoes over time (one active at a time).
If embargo terms change, participants who accepted a prior embargo may not
have accepted the new one. The current `CaseParticipant` model tracks RM
state per participant but does not explicitly track embargo acceptance.

Key design constraints:

- All participants MUST be on record as having accepted the active embargo
  at the time they are added to the case. This provides a complete audit
  trail of which participants were aware of which embargo terms.
- Embargo acceptances MUST be timestamped. The CASE_MANAGER applies the
  trusted timestamp (the time the CASE_MANAGER received the acceptance); the
  participant's own claimed timestamp MUST NOT be trusted for audit
  purposes.
- Design option (recommended): Add an `accepted_embargo_ids: list[str]`
  field to `CaseParticipant` (or `ParticipantStatus`) recording the IDs of
  `EmbargoEvent` objects the participant has explicitly accepted.
- An `Accept(Invite(Actor, Case))` is implicitly an acceptance of the
  current embargo; an `Accept(Offer(Embargo))` is an explicit acceptance.

**Implication for notify-others**: Before sharing case updates with a
participant, check that they have accepted the current active embargo. If
not, send a new `Offer(Embargo)` (or equivalent) before continuing. This
addresses VP-05-* items about participants signaling intent to comply
with embargoes.

This is a PRIORITY 300 item (related to `notes/do-work-behaviors.md`
"Reporting Behavior as Central Coordination").

---

> See also: [triggerable-behaviors-resolved.md](triggerable-behaviors-resolved.md) for the continuation of these design notes.
