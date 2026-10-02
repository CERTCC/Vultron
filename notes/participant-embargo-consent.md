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
  - specs/protocol-asks.yaml
  - specs/sync-ledger-replication.yaml
related_notes:
  - notes/stub-objects.md
  - notes/embargo-lifecycle.md
  - notes/embargo-default-semantics.md
  - notes/case-communication-model.md
  - notes/message-type-reference.md
  - notes/protocol-asks.md
  - notes/sync-ledger-replication.md
  - notes/case-joining.md
relevant_packages:
  - transitions
  - vultron/bt/embargo_management
  - vultron/core/behaviors/embargo
  - vultron/core/models/case_participant.py
  - vultron/core/use_cases
---

# Participant Embargo Consent State Machine

**Status**: Implemented — `vultron/core/states/participant_embargo_consent.py`
(machine), `PecDimension` in `vultron/core/models/dimensions.py` (validated
transitions), `ParticipantStatus.consent` (persistence)
**Source**: `archived_notes/demo-review-26042001.md` + architectural review
2026-04-20; transition table revised by ADR-0048 (Issue #1714); lapse timing
revised by ADR-0093 (Concern #3884)
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
| `UNBOUND` | This participant is not bound by any embargo terms (initial state) |
| `INVITED` | Received embargo invitation; awaiting response |
| `SIGNATORY` | Has accepted current embargo terms |
| `LAPSED` | Was signatory; the case owner activated longer terms it has not accepted |
| `DECLINED` | Has explicitly declined, or timed out without responding |

`embargo_adherence: bool` is a **derived property**: `True` iff the
participant's consent state is `SIGNATORY`; `False` for all other states.

---

## Transition Table

"Trigger source" column classifies each transition by what drives it:
**Wire** = inbound wire activity (CASE_MANAGER observes the message and updates PEC);
**Cascade** = automatic side-effect of a shared EM state change (no outbound PEC message);
**Timer** = pocket-veto lapse enforced lazily by the CASE_MANAGER (CM-28-003, no wire message).

| From | Event | To | Trigger source |
|---|---|---|---|
| `UNBOUND` | Participant invited to embargo | `INVITED` | Wire: `EP` / `INVITE_TO_EMBARGO_ON_CASE` |
| `UNBOUND` | Direct / implicit / self-determined consent | `SIGNATORY` | Wire: `EA` / `ACCEPT_INVITE_TO_EMBARGO_ON_CASE` |
| `UNBOUND` | Refusal without a formal invitation | `DECLINED` | Wire: `ER` / `REJECT_INVITE_TO_EMBARGO_ON_CASE` |
| `INVITED` | `Accept(Invite(Embargo))` received | `SIGNATORY` | Wire: `EA` / `ACCEPT_INVITE_TO_EMBARGO_ON_CASE` |
| `INVITED` | `Reject(Invite(Embargo))` received | `DECLINED` | Wire: `ER` / `REJECT_INVITE_TO_EMBARGO_ON_CASE` |
| `INVITED` | Invitation deadline passed (pocket veto) | `DECLINED` | Timer: no wire message; CASE_MANAGER authors ledger entry (CM-28-005) |
| `SIGNATORY` | Case owner activates revised terms ending later than the accepted ones; this participant has not accepted them | `LAPSED` | Cascade: `EC` side-effect at activation; no outbound PEC message |
| `SIGNATORY` | Explicit consent withdrawal: rejects the *active* embargo (per VP-13-007/008) | `DECLINED` | Wire: `ER` / `REJECT_INVITE_TO_EMBARGO_ON_CASE` (ADR-0093) |
| `LAPSED` | Re-invited for revised embargo terms | `INVITED` | Wire: `EP` / `INVITE_TO_EMBARGO_ON_CASE` |
| `LAPSED` | Direct `Accept` of revised terms | `SIGNATORY` | Wire: `EA` / `ACCEPT_INVITE_TO_EMBARGO_ON_CASE` |
| `DECLINED` | Case owner re-extends invitation | `INVITED` | Wire: `EP` / `INVITE_TO_EMBARGO_ON_CASE` |
| Any | Shared EM exits (`EXITED`) | `UNBOUND` | Cascade: `ET` side-effect; no outbound PEC message |

The stub Invite that brings an actor into a case (ADR-0114) drives the same
states when an embargo is active: sending it records the new participant at
`INVITED` (CM-11-006), `Accept(Invite(stub))` moves it to `SIGNATORY`
(CM-11-001), and `Reject(Invite(stub))` to `DECLINED` (CM-11-007). An expired
stub Invite changes no participant state (CM-11-014). See
[case-joining.md](case-joining.md).

Normative: `specs/case-management.yaml` CM-18-003. Decision: ADR-0048.
MSM coupling: `specs/message-semantics-mapping.yaml` MSM-07.

---

## Consent Is Per Embargo; Lapse Fires at Activation

*Spec: CM-18-001, CM-18-002, MSM-07-003, MSM-07-004, MSM-07-005, EP-05.
Decision: ADR-0093 (revised 2026-09-29, Concern #3884).*

Consent is given to specific terms — an `EmbargoEvent` — and there are two
records of it. `CaseParticipant.accepted_embargo_ids` (CM-10-001) lists every
embargo, active or proposed, the participant has accepted. The scalar PEC state
answers one question only: *is this participant bound by the active embargo?*
— and that is what the content gate reads
(`VulnerabilityCase.is_active_participant`, CM-10-004, #4046), so the rules
below that keep the two records in agreement are what make the gate right.
A participant can be `SIGNATORY` to active embargo A and have B, a proposed
revision, in its list at the same time.

The rule that follows: **a participant cannot lapse until the embargo on the
case differs from the one it agreed to.**

| Event | Effect on consent |
|---|---|
| Revision B proposed (`ACTIVE → REVISE`, or a counter `REVISE → REVISE`) | none; the proposer's list gains B |
| Non-owner signatory accepts B while REVISE | list gains B; state unchanged (still signatory to A) |
| Non-owner signatory rejects B while REVISE | B absent from list; state unchanged — refusing B is not withdrawing from A |
| Non-signatory (`INVITED`/`UNBOUND`/`LAPSED`) accepts B while REVISE | list gains B; state unchanged until B activates |
| Non-signatory rejects B while REVISE | `DECLINE` → `DECLINED` — there is no consent to A for the refusal to leave intact (MSM-07-004) |
| Any participant rejects the *active* embargo | `DECLINE`: `SIGNATORY → DECLINED` (withdrawal, ADR-0093) |
| Owner rejects B (EJ, `REVISE → ACTIVE` under A) | none — the owner is choosing to keep A, not declining it |
| Owner activates B, and B ends **no later than** A | every A-signatory carried over: B added to their list, state unchanged |
| Owner activates B, and B ends **later than** A | every `SIGNATORY` whose list lacks B → `LAPSED` (`REVISE` trigger); those with B stay |
| Owner activates B (either arm); a non-signatory's list already holds B | `ACCEPT` → `SIGNATORY`: it accepted the embargo now in force |
| Owner activates B; participant already `LAPSED` or `INVITED` to A without B | unchanged — only A-signatories are carried over; re-invite (`LAPSED → INVITED`, or the stale-terms path, EMB-17) |
| Termination (`→ EXITED`) | `RESET` everyone to `UNBOUND` (unchanged) |

The asymmetry is the same containment argument that makes shortest-wins safe
(EP-04-003) and lets termination reset consent without asking: agreeing to N
days is agreeing to every shorter period, so a shorter revision asks nothing
new of an existing signatory, while a longer one asks for more than they
promised. Only the case owner's accept or reject changes the embargo on the
case (MSM-07-003/004); the other participants' answers arrive first and inform
that decision.

### Pitfall: Never Cascade on Propose

The original design lapsed every `SIGNATORY` the moment EM entered `REVISE`
(`_cascade_pec_revise()` inside `propose_embargo()`). That contradicted the EM
model, in which coverage never breaks during a revision, and it had concrete
costs: a rejected revision stranded every signatory (no trigger restores
`LAPSED → SIGNATORY`, and the `LAPSED → DECLINED` timer was never
implemented); `embargo_adherence` read false for participants still bound by A
and still receiving embargoed content, because the gate then read the list and not
the scalar; the proposer lapsed too; and the owner's own EJ recorded the owner
as `DECLINED`. The cascade also ran only in the proposer's store, because at the
time no received path moved any other store's EM to `REVISE` (#3892; closed by
the relay in EP-09 / ADR-0113, under which the CASE_MANAGER moves the canonical
case and replicas replay it). Treat any code that changes a participant's
consent inside a *proposal* path as a defect.

### A Revision Invite Asks a Signatory; It Does Not Re-Invite Them

The CASE_MANAGER relays every revision proposal to every participant except the
proposer as an `Invite(EmbargoEvent)` (EP-09-002; see `embargo-lifecycle.md`
§ "Revision Negotiation Relays Through the CASE_MANAGER"). For a participant not
yet bound (`UNBOUND`, `LAPSED`, `DECLINED`) that Invite is an invitation into the
revised terms and `INVITE` applies. For a `SIGNATORY` it is a question about
terms they are not yet bound by, and it changes **nothing** in the consent state
(EP-09-004): `INVITE` is illegal from `SIGNATORY` (CM-18-003), and a proposal
changes no consent (EP-05-002). Their answer lands in `accepted_embargo_ids`
only, exactly as the table above says. A receive tree that applies `INVITE`
unconditionally therefore faults on precisely the participants a revision most
concerns. The `INVITE` write belongs to the CASE_MANAGER's commit of each Invite
emission — built in #3913 as `RelayEmbargoInviteToEachNode._invite_where_legal()`
(`vultron/core/behaviors/embargo/nodes/relay.py`) — and to the replay node that
reconstructs it on replicas, `ApplyEmbargoInviteFromLedgerNode`
(`vultron/core/behaviors/embargo/nodes/relay_effect.py`, #3915); *that* is
where the state check lives. The check is
`CaseParticipant.apply_pec_transition_if_legal()`: the one sanctioned "apply
where legal" shape, which asks `accepts_pec_trigger()` first and then routes
through `apply_pec_transition()`, so an illegal trigger is a recorded no-op
rather than a fault and every other caller stays fail-closed. Both stores reach
it through `EmbargoLifecycle.record_embargo_invite()`, and the participant
replica writes no consent on receipt at all (EP-09-003).

Two further rules from the same decision matter to consent:

- **A participant writes no consent on receipt of an Invite** (EP-09-003). It
  stores the Invite and answers the CASE_MANAGER; the CASE_MANAGER's commit of
  the answer is what moves consent, and the replica learns it from the ledger.
  An `Announce(CaseLedgerEntry)` carrying a proposal or an Invite never asks a
  participant to answer anything.
- **The owner MAY decide without waiting and SHOULD wait to gauge consensus**
  (EP-09-005, EP-09-006). The Invites are not a vote; they gather the consent
  records that the EP-05-001 activation cascade reads, which is why they are
  sent even though the owner may act by fiat. No quorum or voting rule is
  defined at the protocol level — the waiting policy is the actor's.

---

## PEC Is Set by the CASE_MANAGER, Not Self-Reported

*Spec: CM-28-003. MSM-07.*

This is the key distinction between PEC and the other per-participant state machines:

- **RM state** is self-reported by the participant (e.g., "I accept this report").
- **VF/D state** is self-reported by the vendor/deployer (e.g., "I built the fix").
- **PEC state** is set by the **CASE_MANAGER** based on *observed* participant behavior:
  - The CASE_MANAGER observes an inbound `Accept(Invite(EmbargoEvent))` and records
    `SIGNATORY` for the sending participant.
  - The CASE_MANAGER observes a `Reject(...)` and records `DECLINED`.
  - The CASE_MANAGER enforces the pocket-veto deadline and records `DECLINED` on lapse.
  - The CASE_MANAGER cascades `LAPSED` to every SIGNATORY that has not accepted a
    longer revision when the owner activates it, and `UNBOUND` to all when EM exits.

The participant never pushes their own PEC value. There is no "I am now SIGNATORY"
self-report activity; the participant's intent is inferred from the Accept/Reject
activity they sent, and the CASE_MANAGER records the conclusion. This is why PEC
transitions do not require a dedicated wire message partition in the formal set —
the signal is already in the EM wire activities.

---

## `UNBOUND` Means Not Bound by Any Embargo Terms

*Spec: CM-18-001, CM-18-003. Decisions: ADR-0048, ADR-0091.*

`UNBOUND` means **this participant is not bound by any embargo terms**. It does
*not* mean "has not consented yet". Read the second way, it implies every
consent must be preceded by an invitation — which is false:

- A Finder who creates a case for their own finding and sets its default
  embargo has **no inviter**.
- Participants added during case initialization (ADR-0041) already have an
  embargo in scope from the moment they exist, because the CASE_MANAGER
  initializes the default embargo in the same BT sequence.
- The reporter's consent is **implicit** in submitting the report (CM-14-005);
  no invitation is ever sent.

So `ACCEPT` and `DECLINE` are valid directly from `UNBOUND`. Requiring a
synthetic `INVITED` hop for these paths would write an invitation event into the
canonical ledger that never occurred (contra ADR-0019).

`UNBOUND` keeps two real jobs: it is correct for a participant in a case with
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
snapshot: {"embargoAdherence": true, "emConsentState": "UNBOUND"}
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

Consent-write sites (every one routes through `apply_pec_transition()`):

| Site | Uses `apply_pec_transition()`? | Syncs status? |
|---|---|---|
| `case/nodes/proposal_consent.py` | yes | yes |
| `case/nodes/embargo_signatory.py` | yes | yes |
| `case/nodes/participant/participant_add.py` | yes | yes |
| `case/nodes/invite_embargo_consent.py` | yes | yes |
| `embargo/nodes/proposal.py` | yes | yes |
| `embargo/nodes/relay.py` (via `apply_pec_transition_if_legal()`) | yes | yes |
| `use_cases/_helpers.py` | yes | yes |
| `services/embargo_lifecycle/` (`pec.py`, `consent.py`) | yes | yes |

Every site uses `apply_pec_transition()` as the single authoritative
consent-write path (CM-18-005). `EmbargoLifecycle` is the intended long-term
owner of all PEC transitions (see [embargo-lifecycle.md](embargo-lifecycle.md)
and #538), so its sites remain the most critical to keep correct. In
`pec.py` every cascade goes through one `_cascade_pec(trigger, select)` loop —
the RESET cascade, the activation-time REVISE cascade (signatories lacking the
revised id) and the activation-time ACCEPT pass (non-signatories holding it) are
each a `select` predicate, never a loop of their own. The received `Reject(Invite)` tree
writes consent through `RecordParticipantRejectionNode` →
`record_embargo_rejection`, so the MSM-07-004 classification lives in the
service once (`_assert_rejectable`) rather than in a node.

Three rules keep the scalar state and `accepted_embargo_ids` in agreement
about who is bound by the active embargo (the disagreement Concern #3884
found; the content gate `is_active_participant` reads the *scalar*):

- **Every activation advances the holders of the new id.**
  `_consent_at_activation` is the one consent effect of an activation, shared
  by the owner path of `accept_embargo_invite` and by `activate_embargo`. On a
  replacement it records the owner's acceptance first and then runs the
  EP-05-001 arms; on *every* activation, first or replacement, it advances a
  non-signatory whose list already holds the id (`_advance_holders_of`) —
  the proposer of a first embargo holds its id list-only until then.
- **A `DECLINED` participant holds no consent.** `_record_actor_pec_acceptance`
  records nothing for a `DECLINED` actor, list included: `ACCEPT` is not legal
  from `DECLINED` (CM-18-003), so an id on its list would admit through the
  gate an actor whose state says declined. It is re-invited first.
- **Withdrawal leaves the revisions too.** A `DECLINE` that names the active
  embargo also drops every open proposal's id from the actor's list (every
  open proposal is a revision of the one active embargo, ADR-0113). When *no*
  embargo is in force a Reject of a proposal is withdrawal from any state —
  there is nothing for a `SIGNATORY` to stay signatory to.

---

## Pocket Veto (Timer-Based Transitions)

*Spec: CM-18-002, CM-28. Decision: ADR-0065.*

The `INVITED → DECLINED` transition is timer-based.
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
- Enforcement authority is the CASE_MANAGER (CM-28-003)
- The deadline is stored on the **invited participant's** record
  (`CaseParticipant.invite_rsvp_deadline`) by the CASE_MANAGER at its commit of
  the relayed Invite, and reaches replicas by replay (CM-28-013);
  `detect_and_apply_lapse()` reads the record of the actor whose lapse is being
  evaluated. Those two must name the same participant or enforcement silently
  never fires — see "Whose record holds the deadline" below
- Enforcement is **lazy**, not scheduled, and it is the **CASE_MANAGER's alone**
  (CM-28-014): lapse is derived from `(end_time, now)` whenever PEC state is
  read or an inbound `Accept`/`Reject` is processed at the manager. No scheduler
  is required for correctness. The `EmbargoTimerExpired` Sentinel (#1893) is an
  optional proactive accelerator
- When a lapse is detected, the CASE_MANAGER records the `DECLINE` transition and
  authors a ledger entry distinguishing it from an explicit refusal (CM-28-005);
  the entry is role-gated and replayed, so a replica learns a lapse and never
  computes one

> **Provenance note**: the header of this file cites
> `archived_notes/demo-review-26042001.md` as a source. The term "pocket veto"
> does **not** appear in that file — it entered the design via the architectural
> review of 2026-04-20, also cited there. Treat the demo-review citation as
> covering the rest of this document, not this section.

### Pitfall: `LAPSED` Is Not the Timer Destination

The timer path ends at `DECLINED`, and only from `INVITED`. `LAPSED` is reached
only from `SIGNATORY` via the `REVISE` trigger, fired when the case owner
activates longer terms the participant has not accepted — it means neither
"timed out" nor "a revision was proposed". A lapsed participant has no deadline
until it is re-invited (`LAPSED → INVITED`), at which point the invitation's
deadline applies. CM-18-001 and CM-18-002 both flag conflating these as a known
documentation pitfall.

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

The nested one is the `as_EmbargoEvent` (`vultron/core/models/embargo_event.py`;
`end_time` is required, with no default duration — #3404). Read them
independently; never substitute one for the other. `end_time` is inherited from `as_Object`
(`vultron/wire/as2/vocab/base/objects/base.py`), so no vocabulary extension was
needed to add this.

### Whose record holds the deadline

*Source: ISSUE-2762; revised for #3918 (ADR-0113).*

The RSVP deadline and the `PEC_Trigger.INVITE` transition both belong to the
**invited participant** — the actor the `Invite` names in `to:` — not to
whichever actor's replica happens to be processing the message. Under the relay
the deadline is set once: the CASE_MANAGER stamps `Invite.end_time` on each
relayed Invite as its `published` plus the configured window (CM-28-012), and
writes `invite_rsvp_deadline` on the invitee's record at its commit of that
emission; the replica apply node writes the same value (CM-28-013). A
participant that receives an Invite stores it and derives nothing (EP-09-003).
Before the relay, no trigger set `end_time`, so every receiving store fell to
the EP-07-001 fallback and derived its own deadline from its own `ActorConfig` —
two replicas could disagree about when one invitation closed.
`EmbargoLifecycle.detect_and_apply_lapse()` reads the record of the actor whose
lapse it is evaluating. If the write and the read name different participants,
enforcement cannot fire and nothing raises: the invitee has no deadline to lapse
against, and the record that *did* receive one is not the one being checked.

The failure is silent in both directions, which is why it survived for a
release: the participant lookup on that path was lenient by design and the PEC
write returned SUCCESS when no participant was found. CM-28-003 makes the
CASE_MANAGER the enforcement authority for invite expiry, so deriving the invitee from the receiving actor puts the deadline on
the enforcer's own record and disarms exactly the actor responsible for acting
on it.

The invitee is the Invite's **sole** `to:` recipient (EP-09-010). Every emitter
sends a single-recipient Invite — a participant to the CASE_MANAGER, the
CASE_MANAGER to one participant per relayed Invite — so `resolve_invitee_id()`
takes that one recipient and refuses an Invite with none or several as a
misrouting, naming the count, rather than guessing from the receiving actor. A
proposal addressed to the CASE_MANAGER names the manager as its sole recipient,
but the manager is that Invite's adjudicator, not its invitee: its own record
never takes the deadline. See also `notes/bt-integration.md` § "The message
subject is a fourth identity, and it must stay separate".

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
| Accepted embargo **is** the current embargo (EM `ACTIVE` **or** `REVISE`) | Honour it; PEC → `SIGNATORY` (EMB-17-001/002) |
| Accepted embargo is **stale** (revised/replaced) | Send a **fresh invite** carrying the current embargo; do not record stale consent (EMB-17-003) |
| Case has **no** current embargo (EM `EXITED`/`NONE`) | Acknowledge as a no-op; PEC stays `UNBOUND`; **keep** their case participation (EMB-17-004) |

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
CASE_MANAGER-authored lapse entry. A `reason` field on `PecDimension` (which holds
only `state`) would be a second source of truth able to drift from the ledger.
Encoding it as a sixth state would put path history into the machine and
re-expand the table ADR-0048 deliberately simplified.

### Abuse Mitigation: Clamp, Don't Reject

A coercively short deadline ("respond within 60 seconds") formally invites a
participant while guaranteeing they cannot answer. The mitigation is a minimum
window (EP-07-002) plus **clamp-on-receipt** (EP-07-003): a
receiver that gets a sub-floor deadline raises it to the floor rather than
rejecting the invitation. Rejecting would hand a hostile sender exactly what
they want — an invite that never takes effect — and would penalise the invitee
for the inviter's misbehaviour.

The floor is **relative, not absolute** (ADR-0096). It is the lesser of the
configured window — 72h by default — and the time remaining in the embargo the
invitation concerns. An absolute floor would contradict the ceiling of EP-07-006,
which clamps a deadline **down** to the embargo's `end_time`: a 12-hour agreed
embargo is reachable (EP-04-007), and a 72-hour floor on it would place the
respond-by instant 60 hours after the embargo ended. An invitee to a 12-hour
embargo gets a 12-hour window, which still serves the rationale above — the floor
exists to stop an *unreasonably* short deadline, and a deadline equal to the whole
embargo is not unreasonable.

Caveat: because the configured window is set per deployment, a receiver whose
window differs from the sender's computes a different effective deadline. The clamp
guarantees safety, not identical arithmetic.

### UTC Handling

CS-13-001 through CS-13-005 already govern all datetime handling (tz-aware,
UTC, `now_utc()`, `days_from_now_utc(n)`, RFC 3339 with explicit offset on the
wire). CS-13-001 covers
datetimes the application *produces*; an inbound `Invite.end_time` comes from a
remote peer and may carry a non-UTC offset, so CM-28-006 requires normalising it
to UTC before comparison. ADR-0032's `validate_datetime` normalises naive values
to UTC at the wire edge (rather than rejecting them in the extractor).

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

### Ledger Fan-Out Is Case Content (CM-10-005, CM-10-006)

*Source: Concern #3917 (2026-10-01). The fan-out recipients come from the
shared selection in `vultron/core/participants/recipients.py` (#4046); the
replay gate, the pause and the backfill on admission are implemented in #4042.*

The gate (CM-10-004) was first applied only to
`Announce(VulnerabilityCase)`. The `Announce(CaseLedgerEntry)` fan-out, which
is how participants actually learn of an added report or note, filtered on
RM-closed alone, so a non-signatory received every entry's payload verbatim.

Ledger fan-out is case content, and the gate applies to it — but per
participant **stream**, not per entry:

- **No per-recipient redaction.** An entry's payload is hashed into the chain;
  stripping it for one recipient breaks verification.
- **No per-entry skip.** A replica that misses entry N buffers N+1 as a
  forward gap and Rejects to ask for N (SYNC-14-002), so the CASE_MANAGER's
  replay would send the withheld entry anyway. The replay path therefore needs
  the gate as much as fan-out does.
- **So: pause, then backfill in order.** While an embargo is active, a
  participant that is not `SIGNATORY` to it is sent no ledger entries,
  by fan-out or by replay; its replica is a contiguous prefix ending where the
  pause began. When the gate admits it — it accepts, or the embargo ends — the
  CASE_MANAGER sends the withheld suffix in log order, starting with the first
  entry withheld, so the catch-up gate (SYNC-10-004) never sees a gap.

The predicate is the shared active-participant selection in
`vultron/core/participants/recipients.py` (CM-10-007), the one the case-update
broadcast, the ledger fan-out, the replay and the genesis pre-seed all ask.
Where the pause is recorded and the points that catch admission are in
[sync-ledger-replication.md](sync-ledger-replication.md) § "Fan-Out Recipients
and the Embargo Gate".

The embargo meta-protocol above is unaffected: Invites and their responses
are addressed to the participant directly, not fanned out from the ledger, so
the pause cannot deadlock the participant out of accepting.

---

## Implications for DR-06 (Accept Embargo Handler)

The `AcceptEmbargoReceivedUseCase` MUST:

1. Determine if the sending actor is the case owner
   (`VulnerabilityCase.attributed_to == actor_id`)
2. If case owner: transition shared `CaseStatus.em_state → ACTIVE`
3. For all accepting actors (owner or non-owner): transition their
   `ParticipantStatus.embargo_adherence` consent state to `SIGNATORY`
4. Idempotent: if already `SIGNATORY`, succeed silently (HTTP 2xx)
5. When the owner's accept replaces the active embargo with *longer* terms:
   transition every `SIGNATORY` whose list lacks the new id to `LAPSED` (bulk
   operation, not per-participant message); a replacement that ends no later
   carries every signatory over. A proposal changes nobody's consent.

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
  *Partially resolved*: CM-28-005 requires a CASE_MANAGER-authored ledger entry for
  a lapse, which makes it visible to the owner via the ledger. Whether a
  *separate* notification activity is also warranted is still open.
- ~~What is the default embargo invitation timeout?~~ **Resolved**: EP-07-001
  sets the fallback default at 7 days (matching CM-18-002), superseded by
  `Invite.end_time` when present (CM-28-002). The minimum window is the lesser of
  the configured window (72h by default) and the time remaining in the embargo
  (EP-07-002, amended by ADR-0096), and whichever deadline results is clamped down
  to the embargo's own `end_time` (EP-07-006, CM-28-011). Neither the explicit
  `Invite.end_time` nor the policy window escapes that ceiling — see
  `notes/embargo-default-semantics.md` § "An RSVP Deadline May Not Outlive Its
  Embargo".
- No mechanism exists to **rescind** an unanswered invitation before its
  deadline. `as_Undo` is already in the vocabulary
  (`vultron/wire/as2/vocab/base/objects/activities/transitive.py`), so
  `Undo(Invite(EmbargoEvent))` needs no new noun — but it does need a pattern,
  extractor entry, and use case. Deferred from ADR-0065; tracked as its own
  Idea under epic #2088.
- ~~Embargo negotiation **before** report submission is documented as permitted
  but has no implemented mechanics.~~ **Resolved** by ADR-0096 (CONCERN-2215):
  there is no pre-case EM phase, and there cannot be one. EM is a per-case machine,
  so a `propose` transition before a case exists names a machine instance that
  cannot exist — the defect was unrepresentability, not a lagging implementation.
  `rm_em.md` now states the EM process SHALL NOT begin before a case exists. The
  need it served is met two other ways: a short protocol default means a sender
  always knows the floor (EP-04-005), and a sender states its own terms by
  embedding a proposed `EmbargoEvent` on the report offer (EP-04-004). The second
  of those *does* give pre-case terms a home, so there is no deadline-without-a-case
  problem to solve: the proposal is not an invitation, and the RSVP deadline still
  attaches only to a case-scoped `Invite(EmbargoEvent)`. See
  `notes/embargo-default-semantics.md` § "No Pre-Case Embargo Phase".
