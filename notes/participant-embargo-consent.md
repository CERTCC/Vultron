---
title: Participant Embargo Consent State Machine
status: active
description: >
  Design decisions for tracking per-participant embargo acceptance; consent
  state machine and implementation patterns.
related_specs:
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
  - specs/em-behavior.yaml
  - specs/message-semantics-mapping.yaml
related_notes:
  - notes/stub-objects.md
  - notes/embargo-lifecycle.md
  - notes/message-type-reference.md
relevant_packages:
  - transitions
  - vultron/bt/embargo_management
  - vultron/core/use_cases
---

# Participant Embargo Consent State Machine

**Status**: Implemented — `vultron/core/states/participant_embargo_consent.py`
(machine), `PecDimension` in `vultron/core/models/dimensions.py` (validated
transitions), `ParticipantStatus.consent` (persistence)
**Source**: `archived_notes/demo-review-26042001.md` + architectural review
2026-04-20; transition table revised by ADR-0048 (Issue #1714)
**See also**: `specs/case-management.yaml` CM-18 (authoritative), CM-03-008,
CM-04-003; `docs/adr/0048-pec-no-embargo-is-absence-not-pre-consent.md`;
`notes/stub-objects.md`

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

"Trigger source" column classifies each transition by what drives it:
**Wire** = inbound wire activity (CaseActor observes the message and updates PEC);
**Cascade** = automatic side-effect of a shared EM state change (no outbound PEC message);
**Timer** = pocket-veto lapse enforced lazily by the CaseActor (CM-28-003, no wire message).

| From | Event | To | Trigger source |
|---|---|---|---|
| `NO_EMBARGO` | Participant invited to embargo | `INVITED` | Wire: `EP` / `INVITE_TO_EMBARGO_ON_CASE` |
| `NO_EMBARGO` | Direct / implicit / self-determined consent | `SIGNATORY` | Wire: `EA` / `ACCEPT_INVITE_TO_EMBARGO_ON_CASE` |
| `NO_EMBARGO` | Refusal without a formal invitation | `DECLINED` | Wire: `ER` / `REJECT_INVITE_TO_EMBARGO_ON_CASE` |
| `INVITED` | `Accept(Invite(Embargo))` received | `SIGNATORY` | Wire: `EA` / `ACCEPT_INVITE_TO_EMBARGO_ON_CASE` |
| `INVITED` | `Reject(Invite(Embargo))` received | `DECLINED` | Wire: `ER` / `REJECT_INVITE_TO_EMBARGO_ON_CASE` |
| `INVITED` | Invitation deadline passed (pocket veto) | `DECLINED` | Timer: no wire message; CaseActor authors ledger entry (CM-28-005) |
| `SIGNATORY` | Shared EM enters `REVISE` state | `LAPSED` | Cascade: `EV` side-effect; no outbound PEC message |
| `LAPSED` | Re-invited for revised embargo terms | `INVITED` | Wire: `EP` / `INVITE_TO_EMBARGO_ON_CASE` |
| `LAPSED` | Direct `Accept` of revised terms | `SIGNATORY` | Wire: `EA` / `ACCEPT_INVITE_TO_EMBARGO_ON_CASE` |
| `LAPSED` | Re-acceptance deadline passed (pocket veto) | `DECLINED` | Timer: no wire message; CaseActor authors ledger entry (CM-28-005) |
| `DECLINED` | Case owner re-extends invitation | `INVITED` | Wire: `EP` / `INVITE_TO_EMBARGO_ON_CASE` |
| Any | Shared EM exits (`EXITED`) | `NO_EMBARGO` | Cascade: `ET` side-effect; no outbound PEC message |

Normative: `specs/case-management.yaml` CM-18-003. Decision: ADR-0048.
MSM coupling: `specs/message-semantics-mapping.yaml` MSM-07.

---

## PEC Is Set by the CaseActor, Not Self-Reported

*Spec: CM-28-003. MSM-07.*

This is the key distinction between PEC and the other per-participant state machines:

- **RM state** is self-reported by the participant (e.g., "I accept this report").
- **VF/D state** is self-reported by the vendor/deployer (e.g., "I built the fix").
- **PEC state** is set by the **CaseActor** (holding `CVDRole.CASE_MANAGER`) based on
  *observed* participant behavior:
  - The CaseActor observes an inbound `Accept(Invite(EmbargoEvent))` and records
    `SIGNATORY` for the sending participant.
  - The CaseActor observes a `Reject(...)` and records `DECLINED`.
  - The CaseActor enforces the pocket-veto deadline and records `DECLINED` on lapse.
  - The CaseActor cascades `LAPSED` to all SIGNATORY participants when EM enters
    `REVISE`, and `NO_EMBARGO` to all when EM exits.

The participant never pushes their own PEC value. There is no "I am now SIGNATORY"
self-report activity; the participant's intent is inferred from the Accept/Reject
activity they sent, and the CaseActor records the conclusion. This is why PEC
transitions do not require a dedicated wire message partition in the formal set —
the signal is already in the EM wire activities.

---

## `NO_EMBARGO` Is Absence of Embargo, Not Pre-Consent

*Spec: CM-18-001, CM-18-003. Decision: ADR-0048.*

`NO_EMBARGO` means **no embargo is in scope for this participant**. It does
*not* mean "has not consented yet". Read the second way, it implies every
consent must be preceded by an invitation — which is false:

- A Finder who creates a case for their own finding and sets its default
  embargo has **no inviter**.
- Participants added during case initialization (ADR-0041) already have an
  embargo in scope from the moment they exist, because the CaseActor
  initializes the default embargo in the same BT sequence.
- The reporter's consent is **implicit** in submitting the report (CM-14-005);
  no invitation is ever sent.

So `ACCEPT` and `DECLINE` are valid directly from `NO_EMBARGO`. Requiring a
synthetic `INVITED` hop for these paths would write an invitation event into the
canonical ledger that never occurred (contra ADR-0019).

`NO_EMBARGO` keeps two real jobs: it is correct for a participant in a case with
`EM.NONE`, and it is the `RESET` destination when an embargo is terminated. That
`RESET` semantics is itself evidence for the absence reading — `RESET` fires
when the embargo *goes away*, not when consent is pending.

**What this costs:** the machine no longer enforces "consent implies a prior
invitation". That invariant was never true of self-determined embargoes, so the
enforcement was spurious — but treat any code that leaned on it as suspect.

---

## Pitfall: Never Set `embargo_consent_state` by Direct Assignment

*Spec: CM-18-005, CM-18-006.*

Record a consent change by applying a `PEC_Trigger` through
`PecDimension.transition()` (ADR-0036) and persisting the resulting
`ParticipantStatus`. Prefer a shared helper over open-coding it.

Assigning the scalar field directly:

```python
participant.embargo_consent_state = PEC.SIGNATORY   # WRONG
```

is a plain Pydantic write. It bypasses the state machine **and**
`_sync_latest_status_metadata()`, so the participant's latest
`ParticipantStatus` keeps its old `consent.state`. The emitted ledger snapshot
then contradicts itself:

```text
participant.embargo_consent_state = SIGNATORY
snapshot: {"embargoAdherence": true, "emConsentState": "NO_EMBARGO"}
```

Ledger consumers read `emConsentState` to render per-participant consent
(DRPT-02-008), so they report the stale value. `PecDimension.transition()`
raises `VultronInvalidStateTransitionError` on an illegal trigger, which makes
consent writes fail-closed regardless of whether the upstream BT guard is
correct — the fail-open concern raised for `CreateParticipantStatusNode` in
ISSUE-1825.

Note: `apply_pec_trigger()` (the legacy soft-fail helper that returned the
current state unchanged on an invalid trigger instead of raising) has been
removed from `participant_embargo_consent.py` (CONCERN-1871). Use
`apply_pec_transition()` on `CaseParticipant`, which delegates to
`PecDimension.transition()` and is fail-closed.

Consent-write sites (all ten route through `apply_pec_transition()`):

| Site | Uses `apply_pec_transition()`? | Syncs status? |
|---|---|---|
| `case/case_proposal_received_tree.py` | yes | yes |
| `case/nodes/embargo.py` | yes | yes |
| `case/nodes/participant/participant_add.py` | yes | yes |
| `case/accept_invite_tree.py` | yes | yes |
| `embargo/nodes/proposal.py` | yes | yes |
| `use_cases/_helpers.py` | yes | yes |
| `services/embargo_lifecycle.py` (6 sites) | yes | yes |

All ten sites now use `apply_pec_transition()` as the single authoritative
consent-write path (CM-18-005). `EmbargoLifecycle` is the intended long-term
owner of all PEC transitions (see [embargo-lifecycle.md](embargo-lifecycle.md)
and #538), so its five sites remain the most critical to keep correct.

---

## Pocket Veto (Timer-Based Transitions)

*Spec: CM-18-002, CM-28. Decision: ADR-0065.*

The `INVITED → DECLINED` and `LAPSED → DECLINED` transitions are timer-based.
A configurable **embargo invitation timeout** policy window bounds how long an
invitation stays open. If the participant does not respond within the window,
they move to `DECLINED` — inaction is recorded as rejection so one
non-responsive invitee cannot stall coordination indefinitely.

**The pocket veto and the RSVP deadline are one mechanism, not two.** The
policy window is the *implicit, receiver-local* form; `Invite.end_time` is the
*explicit, bilateral* form. When an invitation carries `Invite.end_time`, that
value is authoritative and supersedes the local window (CM-28-002). The policy
window is the fallback for invitations that omit it (EP-07-001, default 7 days).
Do not introduce a second timeout notion — they will drift.

- The timeout is a **configurable policy option** (per-case or global setting)
- Enforcement authority is the CaseActor holding `CVDRole.CASE_MANAGER`
  (CM-28-003)
- The deadline is stored on the **invited participant's** record
  (`CaseParticipant.invite_rsvp_deadline`), and `detect_and_apply_lapse()`
  reads the record of the actor whose lapse is being evaluated. Those two must
  name the same participant or enforcement silently never fires — see
  "Whose record holds the deadline" below
- Enforcement is **lazy**, not scheduled: lapse is derived from
  `(end_time, now)` whenever PEC state is read or an inbound `Accept`/`Reject`
  is processed. No scheduler is required for correctness. The
  `EmbargoTimerExpired` Sentinel (#1893) is an optional proactive accelerator
- When a lapse is detected, the CaseActor records the `DECLINE` transition and
  authors a ledger entry distinguishing it from an explicit refusal (CM-28-005)

> **Provenance note**: the header of this file cites
> `archived_notes/demo-review-26042001.md` as a source. The term "pocket veto"
> does **not** appear in that file — it entered the design via the architectural
> review of 2026-04-20, also cited there. Treat the demo-review citation as
> covering the rest of this document, not this section.

### Pitfall: `LAPSED` Is Not the Timer Destination

Both timer paths end at `DECLINED`. `LAPSED` is reached only from `SIGNATORY`
via the `REVISE` trigger — it means "terms changed, prior consent no longer
applies", not "timed out". CM-18-001 and CM-18-002 both flag conflating the two
as a known documentation pitfall.

---

## RSVP Deadlines on Embargo Invites

*Spec: CM-28, EP-07, EMB-17. Decision: ADR-0065. Source: IDEA-2066.*

An `Invite(EmbargoEvent)` MAY carry an activity-level `end_time` giving the
invitee an explicit respond-by deadline.

### The Two-`end_time` Hazard

This is the single most important thing to get right. An embargo invitation
carries **two `end_time` fields, one nesting level apart, in the same JSON
document**:

| Field | Meaning |
|---|---|
| `Invite.end_time` | RSVP-by — when the *invitation* stops being open |
| `Invite.object_.end_time` | Embargo expiry — when the *embargo* ends |

The nested one is the `as_EmbargoEvent` (`vultron/core/models/embargo_event.py`,
default 45 days hence). Read them independently; never substitute one for the
other. `end_time` is inherited from `as_Object`
(`vultron/wire/as2/vocab/base/objects/base.py`), so no vocabulary extension was
needed to add this.

### Whose record holds the deadline

*Source: ISSUE-2762.*

The RSVP deadline and the `PEC_Trigger.INVITE` transition both belong to the
**invited participant** — the actor the `Invite` names in `to:` — not to
whichever actor's replica happens to be processing the message.
`_store_invite_deadline()` writes `invite_rsvp_deadline` on the participant
record found via `case.actor_participant_index[invitee_id]`, and
`EmbargoLifecycle.detect_and_apply_lapse()` later reads the record of the actor
whose lapse it is evaluating. If the write and the read name different
participants, enforcement cannot fire and nothing raises: the invitee has no
deadline to lapse against, and the record that *did* receive one is not the one
being checked.

The failure is silent in both directions, which is why it survived for a
release: `OptionalLookupParticipantNode` is lenient by design and
`UpdateParticipantEmbargoPecNode` returns SUCCESS when no participant is on the
blackboard. CM-28-003 makes the CaseActor the enforcement authority for invite
expiry, so deriving the invitee from the receiving actor puts the deadline on
the enforcer's own record and disarms exactly the actor responsible for acting
on it.

Resolve the invitee by addressee membership rather than by position —
`resolve_invitee_id()` in `vultron/core/use_cases/received/embargo.py` — so a
multi-recipient `Invite` is correct in every recipient's replica instead of
only the first one's. See also `notes/bt-integration.md` § "The message subject
is a fourth identity, and it must stay separate".

### It Is an `Invite`, Not an `Offer`

IDEA-2066 was framed as `Offer.end_time`. There is no `Offer` in the embargo
path: `em_propose_embargo_activity()`
(`vultron/wire/as2/factories/embargo.py`) returns `as_Invite`, and
`InviteToEmbargoOnCasePattern` (`vultron/wire/as2/extractor/_instances.py`)
matches `activity_=TAtype.INVITE, object_=AOtype.EVENT,
context_=VULNERABILITY_CASE`. The generic semantic — activity-level `end_time`
on a response-soliciting activity means "respond by" — holds for `Offer` too,
but only `Invite(EmbargoEvent)` is normatively enforced, because it is the only
place the domain currently has a timeout concept.

### Late `Accept` Is Never Refused

The protocol is liberal in what it accepts (EMB-17). A late accepter has
signalled willingness to coordinate, so a missed deadline must not cost the case
a participant:

| Situation | Behaviour |
|---|---|
| Accepted embargo **is** the current embargo | Honour it; PEC → `SIGNATORY` (EMB-17-002) |
| Accepted embargo is **stale** (revised/replaced) | Send a **fresh invite** carrying the current embargo; do not record stale consent (EMB-17-003) |
| Case has **no** current embargo (EM `EXITED`/`NONE`) | Acknowledge as a no-op; PEC stays `NO_EMBARGO`; **keep** their case participation (EMB-17-004) |

The third row follows the EMB-07-003 precedent for post-terminal messages
(acknowledge without transitioning). EMB-13-002 already forbade accepting new
embargoes when CS is P/X/A; EMB-17-004 closes the remaining gap where EM has
`EXITED` but CS is not yet P/X/A.

### Why No New PEC State for "Never Responded"

A lapsed invite records `DECLINED`, the same as an explicit refusal
(CM-28-004). Nothing branches on the difference — re-invitation
(`DECLINED → INVITED`), content gating, and meta-protocol delivery all treat
them identically. The distinction is *provenance*, and the canonical ledger
already carries it (CM-28-005): a `Reject(Invite)` entry versus a
CaseActor-authored lapse entry. A `reason` field on `PecDimension` (which holds
only `state`) would be a second source of truth able to drift from the ledger.
Encoding it as a sixth state would put path history into the machine and
re-expand the table ADR-0048 deliberately simplified.

### Abuse Mitigation: Clamp, Don't Reject

A coercively short deadline ("respond within 60 seconds") formally invites a
participant while guaranteeing they cannot answer. The mitigation is a minimum
window (EP-07-002, default 72h) plus **clamp-on-receipt** (EP-07-003): a
receiver that gets a sub-floor deadline raises it to the floor rather than
rejecting the invitation. Rejecting would hand a hostile sender exactly what
they want — an invite that never takes effect — and would penalise the invitee
for the inviter's misbehaviour.

Caveat: because the floor is configured per deployment, a receiver whose floor
differs from the sender's computes a different effective deadline. The clamp
guarantees safety, not identical arithmetic.

### UTC Handling

CS-13-001 through CS-13-005 already govern all datetime handling (tz-aware,
UTC, `now_utc()`, `days_from_now_utc(n)`, RFC 3339 with explicit offset on the
wire). CS-13-001 covers datetimes the application *produces*; an inbound
`Invite.end_time` comes from a remote peer and may carry a non-UTC offset, so
CM-28-006 requires normalising it to UTC before comparison and rejecting a naive
value rather than assuming UTC.

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
- `ParticipantStatus.embargo_adherence` is a `@computed_field` (Pydantic v2)
  that returns `self.consent is not None and self.consent.state == PEC.SIGNATORY`.
  It MUST NOT be declared as a stored field. Consent writes go through
  `apply_pec_transition()` on `CaseParticipant`; the computed field reflects the
  result automatically. Decision: ADR-0056.

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
  *Partially resolved*: EMB-17-004 establishes that case participation survives
  an embargo no-op, so removal is not automatic on the late-accept path. The
  general `DECLINED` case is still open.
- Should the case actor notify the case owner when a participant's consent
  state transitions to `DECLINED` (via timeout or explicit rejection)?
  *Partially resolved*: CM-28-005 requires a CaseActor-authored ledger entry for
  a lapse, which makes it visible to the owner via the ledger. Whether a
  *separate* notification activity is also warranted is still open.
- ~~What is the default embargo invitation timeout?~~ **Resolved**: EP-07-001
  sets the fallback default at 7 days (matching CM-18-002), superseded by
  `Invite.end_time` when present (CM-28-002). Minimum window is 72h (EP-07-002).
- No mechanism exists to **rescind** an unanswered invitation before its
  deadline. `as_Undo` is already in the vocabulary
  (`vultron/wire/as2/vocab/base/objects/activities/transitive.py`), so
  `Undo(Invite(EmbargoEvent))` needs no new noun — but it does need a pattern,
  extractor entry, and use case. Deferred from ADR-0065; tracked as its own
  Idea under epic #2088.
- Embargo negotiation **before** report submission is documented as permitted
  (`docs/topics/process_models/model_interactions/rm_em.md`: the EM `propose`
  transition MAY occur while `q^rm ∈ S`) but has no implemented mechanics —
  every embargo path is case-scoped (`EmbargoLifecycle.propose_embargo()`
  requires a `case_id`; PEC lives on a `CaseParticipant`), and pre-case there is
  neither. Tracked as a Concern.
