---
title: Participant Embargo Consent State Machine
status: active
description: >
  Design decisions for tracking per-participant embargo acceptance; consent
  state machine and implementation patterns.
related_specs:
  - specs/case-management.yaml
related_notes:
  - notes/stub-objects.md
relevant_packages:
  - transitions
  - vultron/bt/embargo_management
  - vultron/core/use_cases
---

# Participant Embargo Consent State Machine

**Status**: Design decision — not yet implemented
**Source**: `notes/demo-review-26042001.md` + architectural review 2026-04-20
**See also**: `specs/case-management.yaml` CM-03-008, CM-04-003; `notes/stub-objects.md`

---

## Background

The shared `CaseStatus.em_state` tracks the collective embargo state of a
`VulnerabilityCase` using the standard EM states: `NONE`, `PROPOSED`,
`ACTIVE`, `REVISE`, `EXITED`. This is a global, case-level view.

Each `CaseParticipant`, however, has their own relationship to the embargo:
they may have accepted the current terms, declined them, or not yet responded.
The existing `ParticipantStatus.embargo_adherence: bool` field is the
mechanism for tracking this — but it needs a formal state machine behind it
to handle the nuances of embargo lifecycle (proposals, revisions, lapses, and
pocket vetoes).

---

## The 5-State Participant Embargo Consent Machine

| State | Meaning |
|---|---|
| `NO_EMBARGO` | No embargo active for this case (initial state) |
| `INVITED` | Received embargo invitation; awaiting response |
| `SIGNATORY` | Has accepted current embargo terms |
| `LAPSED` | Was signatory; embargo revised; not yet re-accepted |
| `DECLINED` | Has explicitly declined, or timed out without responding |

`embargo_adherence: bool` is a **derived property**: `True` iff the
participant's consent state is `SIGNATORY`; `False` for all other states.

---

## Transition Table

| From | Trigger | To |
|---|---|---|
| `NO_EMBARGO` | Embargo proposed; participant invited | `INVITED` |
| `INVITED` | `Accept(Invite(Embargo))` received | `SIGNATORY` |
| `INVITED` | `Reject(Invite(Embargo))` received | `DECLINED` |
| `INVITED` | Invitation timeout (pocket veto) | `DECLINED` |
| `SIGNATORY` | Shared EM enters `REVISE` state | `LAPSED` |
| `LAPSED` | Re-invitation extended for revised terms | `INVITED` |
| `LAPSED` | Direct `Accept` of revised embargo terms | `SIGNATORY` |
| `LAPSED` | Re-acceptance timeout (pocket veto) | `DECLINED` |
| `DECLINED` | Case owner re-extends invitation | `INVITED` |
| Any | Shared EM exits (`EXITED`) | `NO_EMBARGO` |

---

## Pocket Veto (Timer-Based Transitions)

The `INVITED → DECLINED` and `LAPSED → DECLINED` transitions are timer-based.
A configurable **embargo invitation timeout** policy window starts when the
invitation is received (timestamp of `Invite` activity). If the participant
does not respond within the window, they automatically move to `DECLINED`.

- The timeout is a **configurable policy option** (per-case or global setting)
- Implementation: background scheduled task checking `INVITED`/`LAPSED`
  participants against the timeout policy
- When the timer fires, the system records a local state transition to
  `DECLINED`; it MAY also emit a protocol notification to inform the case owner

---

## Embargo Meta-Protocol Delivery to Non-Signatories

To avoid the **deadlock scenario** (non-signatories cannot re-accept embargo
terms they never see), embargo **meta-protocol messages** MUST be delivered
even to `DECLINED` and `LAPSED` participants:

- `Offer(EmbargoEvent)` — a new embargo proposal
- `Invite(target=case, object=EmbargoEvent)` — embargo invitation
- `Announce(EmbargoEvent)` — embargo status notification
- Responses to the above: `Accept`, `Reject`, `TentativeReject`

Only **case content** (vulnerability report details, fix status, technical
notes with sensitive information) is gated on `embargo_adherence=True`.

---

## Implementation Notes

- The state machine SHOULD be implemented using the `transitions` library,
  consistent with the RM, EM, and CS state machines elsewhere in the codebase
- The machine name is `ParticipantEmbargoConsent`
- Define states and triggers in a new module:
  `vultron/core/states/participant_embargo_consent.py`
- `VultronParticipantStatus.embargo_adherence: bool` should become a
  `@property` that returns `self._consent_state == "SIGNATORY"` (or equivalent)
- Alternatively, retain `embargo_adherence: bool` as a plain stored field for
  backward compatibility, but enforce transitions via use-case logic
- The stored field value should mirror the derived property on every update

---

## Implications for DR-06 (Accept Embargo Handler)

The `AcceptEmbargoReceivedUseCase` MUST:

1. Determine if the sending actor is the case owner
   (`VulnerabilityCase.attributed_to == actor_id`)
2. If case owner: transition shared `CaseStatus.em_state → ACTIVE`
3. For all accepting actors (owner or non-owner): transition their
   `ParticipantStatus.embargo_adherence` consent state to `SIGNATORY`
4. Idempotent: if already `SIGNATORY`, succeed silently (HTTP 2xx)
5. When shared EM enters `REVISE`: transition all `SIGNATORY` participants
   to `LAPSED` (bulk operation, not per-participant message)

### Trigger-Side Ownership Gate (BUG-26042101, 2026-04-22)

The same owner-vs-participant split applies to **trigger-side** embargo
responses, not just receive-side handlers:

- **Case owner** (`case.attributed_to == actor_id`): drives shared EM
  transitions (`EM.ACTIVE`, `EM.EXITED`, etc.)
- **Non-owner participant**: mutates only their own consent state in
  `CaseParticipant`; does NOT advance shared EM

**Fallback for legacy cases**: When `case.attributed_to is None` (older
single-actor fixtures, seed data created before the attribution field was
introduced), treat the triggering actor as the case owner. Without this
fallback, existing single-actor embargo triggers silently stop advancing
the shared EM state.

**Idempotent PEC transitions**: Participant-only accept/reject updates SHOULD
NOT re-run the PEC machine when the participant is already in the target state
(`SIGNATORY` / `DECLINED`). Idempotent repeats MUST NOT generate
invalid-transition warnings.

### Full Case Delivery Precondition

The case owner MUST only send `Announce(VulnerabilityCase)` with full case
details when a participant satisfies **both**:

1. `rm_state == ACCEPTED` (accepted the case invitation)
2. `embargo_adherence == True` (is a signatory) OR no active embargo

This check MUST live in the BT subtree for `AcceptInviteActorToCase`, not
in post-BT procedural code. See `specs/message-validation.yaml` MV-10-005.

---

## Open Questions

- Should `DECLINED` participants be automatically removed from the case, or
  left in the case but excluded from embargo-protected content?
- Should the case actor notify the case owner when a participant's consent
  state transitions to `DECLINED` (via timeout or explicit rejection)?
- What is the default embargo invitation timeout? (Suggested: 7 days, policy
  configurable)
