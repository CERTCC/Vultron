---
title: Participant Embargo Consent (per-Embargo Rows)
status: active
description: >
  Design decisions for tracking per-participant embargo consent as one row per
  (participant, embargo); consent transitions and implementation patterns.
related_specs:
  - specs/case-ledger-processing.yaml
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
  - notes/bt-integration.md
  - notes/domain-validation.md
relevant_packages:
  - transitions
  - vultron/bt/embargo_management
  - vultron/core/behaviors/embargo
  - vultron/core/models/case_participant.py
  - vultron/core/use_cases
---

# Participant Embargo Consent (per-Embargo Rows)

**Status**: Implemented — `vultron/core/states/participant_embargo_consent.py`
(row states and transition table), `EmbargoConsent` in
`vultron/core/models/embargo_consent.py`, `CaseParticipant.embargo_consents`
(persistence and lookups)
**Source**: `archived_notes/demo-review-26042001.md` + architectural review
2026-04-20; the scalar machine was revised by ADR-0048 (Issue #1714), ADR-0093
(Concern #3884) and ADR-0118 (Issue #4153), and replaced by the per-embargo rows of
ADR-0122 (Issue #4178)
**See also**: `specs/case-management.yaml` CM-10-001, CM-18 (authoritative);
`docs/adr/0122-per-embargo-participant-consent.md`; `notes/stub-objects.md`

---

## Background

The shared `CaseStatus.em_state` tracks the collective embargo state of a
`VulnerabilityCase` using the standard EM states: `NONE`, `PROPOSED`,
`ACTIVE`, `REVISE`, `EXITED`. This is a global, case-level view.

Each `CaseParticipant`, however, has their own relationship to each embargo they
have been asked about: they may have accepted it, declined it, let the invitation
expire, or not yet responded. That is what this note's machinery records.

Before ADR-0122 the record was a hybrid — a per-embargo list
(`accepted_embargo_ids`) plus one scalar seven-state value that answered only
"am I bound by the *active* embargo?". The two disagreed (Concern #3884) and three
reconciliation rules plus a first-proposal special case kept them in step. The
maintainer ruled the hybrid a model mismatch; **consent is now recorded once, per
(participant, embargo)**. If you find a note, comment or test describing
`SIGNATORY`, `LAPSED`, `UNBOUND` or `UNBOUND_EXITED` as a stored state, it predates
ADR-0122.

---

## The Consent Rows

`CaseParticipant.embargo_consents` holds one `EmbargoConsent(embargo_id, state)`
row for each embargo the participant was asked about. No row means never asked.

| Row state | Meaning |
|---|---|
| `INVITED` | Asked about this embargo; no answer yet |
| `ACCEPTED` | Accepted it — explicitly, or by containment (EP-05-001) |
| `DECLINED` | Explicitly refused it, or withdrew from it (ADR-0093) |
| `EXPIRED` | Invited; the RSVP deadline passed with no answer (pocket veto, ADR-0118) |

The transition table is the whole machine:

| Trigger | Source row | Destination | Trigger source |
|---|---|---|---|
| `INVITE` | none, `DECLINED`, `EXPIRED` | `INVITED` | Wire: `EP` / `INVITE_TO_EMBARGO_ON_CASE`, relayed by the CASE_MANAGER |
| `ACCEPT` | none, `INVITED`, `EXPIRED` | `ACCEPTED` | Wire: `EA` / `ACCEPT_INVITE_TO_EMBARGO_ON_CASE`; direct / implicit / self-determined consent; containment carry-over |
| `DECLINE` | none, `INVITED`, `ACCEPTED`, `EXPIRED` | `DECLINED` | Wire: `ER` / `REJECT_INVITE_TO_EMBARGO_ON_CASE` |
| `EXPIRE` | `INVITED` | `EXPIRED` | Timer: lazy, CASE_MANAGER-authored ledger entry (CM-28-005) |

`ACCEPTED` refuses `INVITE` and `DECLINED` refuses `ACCEPT`: a consent already given
is not silently undone and a refusal is not silently reversed; a decliner is
re-invited first (`DECLINED → INVITED`). An illegal trigger raises (CM-18-009).

Normative: `specs/case-management.yaml` CM-18-003. Decisions: ADR-0048, ADR-0093,
ADR-0118, ADR-0122. MSM coupling: `specs/message-semantics-mapping.yaml` MSM-07.

### What Is Derived, Not Stored

| Position | How it is read |
|---|---|
| **Signatory** | the row for `case.active_embargo_id` is `ACCEPTED` (`CaseParticipant.is_signatory()`) |
| **Lapsed** | the participant holds an `ACCEPTED` row for another embargo and no accepting (or declining) row for the active one (`CaseParticipant.has_lapsed()`) |
| **Exited** | the case's EM is `EXITED` and `active_embargo` is cleared, so nobody is a signatory |
| **Bound for the content gate** | `VulnerabilityCase.is_active_participant` reads `is_signatory(active_embargo_id)` (CM-10-004) |

`ParticipantStatus` carries no consent and `embargo_adherence` no longer exists
(ADR-0122 supersedes ADR-0056): both projected a scalar that is gone. The wire
keys `emConsentState`, `embargoAdherence`, `embargoConsentState` and
`acceptedEmbargoIds` are refused inbound by name (`RETIRED_NAMES`).

---

## Consent Is Per Embargo

*Spec: CM-10-001, CM-18-001, CM-18-016, MSM-07-003, MSM-07-004, MSM-07-005, EP-05.
Decisions: ADR-0093, ADR-0122.*

Consent is given to specific terms — an `EmbargoEvent` — and there is one record of
it: the row. An Accept is always a statement about the embargo it names, so it always
marks that embargo's row, whether that embargo is in force, a first proposal or a
revision. There is no "advance at accept time" for a first proposal and no
list-only write for a revision.

A participant can be `ACCEPTED` to active embargo A and `ACCEPTED` to B, a proposed
revision, at the same time; it is a signatory to A until B is the active embargo.

The rule that follows: **a participant cannot lapse until the embargo on the case
differs from the one it agreed to.**

| Event | Effect on the rows |
|---|---|
| Revision B proposed (`ACTIVE → REVISE`, or a counter `REVISE → REVISE`) | the proposer's row for B becomes `ACCEPTED`; nothing else |
| A participant — the owner included — accepts the Invite to B while REVISE | its row for B becomes `ACCEPTED` (`INVITED`/none/`EXPIRED` → `ACCEPTED`); its row for A is untouched |
| A participant — the owner included — rejects the Invite to B while REVISE | its row for B becomes `DECLINED`; its row for A is untouched — refusing B is not withdrawing from A |
| A non-owner sends `Leave(EmbargoEvent)` for the *active* embargo (MSM-07-010; planned, #4388) | withdrawal: its row for A becomes `DECLINED`, and so does every open proposal's row it had accepted. Today a Reject of the active embargo does this |
| Owner rejects B for the case (`Reject(EmbargoEvent)`, EJ, `REVISE → ACTIVE` under A) | nothing — the owner is choosing to keep A, not declining it |
| Owner activates B (`Accept(EmbargoEvent)`), and B ends **no later than** A | the owner's row for B becomes `ACCEPTED`, and so does B's row for every participant whose row for A is `ACCEPTED` (containment carry-over, where `ACCEPT` is legal) |
| Owner activates B, and B ends **later than** A | the owner's row for B becomes `ACCEPTED`; nothing else is written — a signatory without an `ACCEPTED` row for B has lapsed by derivation |
| Owner activates B (either arm); a participant already holds `ACCEPTED` for B | nothing — it is B's signatory by lookup (its proposer, an early acceptor) |
| Termination (`→ EXITED`) | nothing — the active embargo is cleared, so nobody is a signatory |

The asymmetry is the same containment argument that makes shortest-wins safe
(EP-04-003): agreeing to N days is agreeing to every shorter period, so a shorter
revision asks nothing new of an existing signatory and their acceptance is carried
over, while a longer one asks for more than they promised. Only the case owner's
decision changes the embargo on the case, and it has activities of its own —
`Accept`/`Reject(EmbargoEvent, target=Case)` (MSM-07-008/009, ADR-0122). Every
`Accept`/`Reject` of an Invite, the owner's included, is the sender's consent
(MSM-07-003/004); those answers arrive first and inform the decision.

The containment carry-over is the one activation write left
(`_carry_signatories_over`). Lapse, advance and exit are reads, not writes
(CM-18-016). Code that writes a row to record one of them re-creates the second
record ADR-0122 removed.

### Pitfall: Never Write Consent on Propose, Lapse, Advance or Exit

The original design lapsed every `SIGNATORY` the moment EM entered `REVISE`
(`_cascade_pec_revise()` inside `propose_embargo()`). That contradicted the EM
model, in which coverage never breaks during a revision, and it had concrete
costs: a rejected revision stranded every signatory; participants still bound by A
and still receiving embargoed content read as not bound; the proposer lapsed too; and
the owner's own EJ recorded the owner as `DECLINED`. The per-embargo rows remove the
whole class: a proposal only ever adds a row for the proposed embargo. Treat any
code that changes a participant's consent to the embargo *in force* inside a
*proposal* path as a defect.

### A Revision Invite Asks a Signatory; It Does Not Change Their Binding

The CASE_MANAGER relays every revision proposal to every participant except the
proposer as an `Invite(EmbargoEvent)` (EP-09-002; see `embargo-lifecycle.md`
§ "Revision Negotiation Relays Through the CASE_MANAGER"). `INVITE` is applied to
the invitee's row for the *revision*. A participant with no row (or `DECLINED` /
`EXPIRED`) is invited into the revised terms (`INVITED`). A signatory gains an
`INVITED` row for the revision and keeps its `ACCEPTED` row for the active
embargo, so its binding is untouched (EP-09-004) — the Invite lands on its own row
and cannot touch the row that binds it. Their answer lands on the revision's row
only, exactly as the table above says.

The `INVITE` write belongs to the CASE_MANAGER's commit of each Invite emission —
`RelayEmbargoInviteToEachNode._invite_where_legal()`
(`vultron/core/behaviors/embargo/nodes/relay.py`) — and to the replay node that
reconstructs it on replicas, `ApplyEmbargoInviteFromLedgerNode`
(`vultron/core/behaviors/embargo/nodes/relay_effect.py`). Both reach it through
`EmbargoLifecycle.record_embargo_invite(embargo_id=...)`, which applies the
trigger with `CaseParticipant.apply_pec_transition_if_legal()`: the one sanctioned
"apply where legal" shape, so an `ACCEPTED` or already-`INVITED` row is a recorded
no-op rather than a fault and every other caller stays fail-closed. The participant
replica writes no consent on receipt at all (EP-09-003).

Two further rules from the same decision matter to consent:

- **A participant writes no consent on receipt of an Invite** (EP-09-003). It
  stores the Invite and answers the CASE_MANAGER; the CASE_MANAGER's commit of
  the answer is what moves consent, and the replica learns it from the ledger.
  An `Announce(CaseLedgerEntry)` carrying a proposal or an Invite never asks a
  participant to answer anything.
- **The owner MAY decide without waiting and SHOULD wait to gauge consensus**
  (EP-09-005, EP-09-006). The Invites are not a vote; they gather the consent
  rows that the EP-05-001 carry-over reads, which is why they are sent even
  though the owner may act by fiat. No quorum or voting rule is defined at the
  protocol level — the waiting policy is the actor's.

---

## Consent Is Set by the CASE_MANAGER, Not Self-Reported

*Spec: CM-28-003. MSM-07.*

This is the key distinction between PEC and the other per-participant state machines:

- **RM state** is self-reported by the participant (e.g., "I accept this report").
- **VF/D state** is self-reported by the vendor/deployer (e.g., "I built the fix").
- **Consent rows** are set by the **CASE_MANAGER** based on *observed* participant
  behavior and replayed by every replica:
  - The CASE_MANAGER observes an inbound `Accept(Invite(EmbargoEvent))` and marks
    the sending participant's row for that embargo `ACCEPTED`.
  - The CASE_MANAGER observes a `Reject(...)` and marks the row `DECLINED`.
  - The CASE_MANAGER enforces the pocket-veto deadline and marks `INVITED` rows
    `EXPIRED` on expiry.
  - When the owner activates a shorter-or-equal revision, the CASE_MANAGER carries
    the signatories' acceptance over to it.

The participant never pushes its own consent value. There is no "I am now a
signatory" self-report activity; the participant's intent is inferred from the
Accept/Reject activity it sent, and the CASE_MANAGER records the conclusion. This
is why consent transitions do not require a dedicated wire message partition in the
formal set — the signal is already in the EM wire activities.

### A Participant Refuses a P/X/A Revision with ER, Never ET

*Spec: EMB-03-003, EMB-01-002, HP-01-005. Decision: ADR-0118.*

A participant that is neither the case owner nor the CASE_MANAGER and receives a
revision Invite while P/X/A is set answers it with ER to the CASE_MANAGER. It
does not emit ET and does not move its own EM state: termination is the owner's
decision, or the delegated CASE_MANAGER's (EP-09-003, EP-09-008, CM-24). The ER
duty binds only the addressee; a store that is neither the sender nor in `to` or
`cc` refuses the copy at the door (`unaddressed_copy_refusal()`) and answers
nothing. This is the one statement of the rule in this note.

---

## No Row Means Not Bound by Any Embargo Terms

*Spec: CM-18-001, CM-18-003. Decisions: ADR-0048, ADR-0091, ADR-0122.*

A participant with no row for an embargo is **not bound by it**. That does *not*
mean "has not consented yet, and an invitation is owed". Read the second way, it
implies every consent must be preceded by an invitation — which is false:

- A Finder who creates a case for their own finding and sets its default
  embargo has **no inviter**.
- Participants added during case initialization (ADR-0041) already have an
  embargo in scope from the moment they exist, because the CASE_MANAGER
  initializes the default embargo in the same BT sequence.
- The reporter's consent is **implicit** in submitting the report (CM-14-005);
  no invitation is ever sent.

So `ACCEPT` and `DECLINE` are valid directly from no row. Requiring a synthetic
`INVITED` hop for these paths would write an invitation event into the canonical
ledger that never occurred (contra ADR-0019). `CaseParticipant.sign_embargo()` is
that seeding shape: `ACCEPT` where legal, and a no-op (no row written) when no embargo
is in force.

**What this costs:** the machine does not enforce "consent implies a prior
invitation". That invariant was never true of self-determined embargoes, so the
enforcement would have been spurious — but treat any code that leaned on it as
suspect.

---

## Pitfall: Never Assign `embargo_consents` by Direct Assignment

*Spec: CM-18-005, CM-18-006.*

Record a consent change by applying a `PEC_Trigger` through
`CaseParticipant.apply_pec_transition(embargo_id, trigger)` and persisting the
participant. Prefer a shared helper over open-coding it.

Assigning the rows directly is a plain Pydantic write. It bypasses the transition
table, so a row can reach a state no trigger leads to and the content gate
(CM-10-004) can admit an actor the protocol never bound.
`apply_pec_transition()` raises `VultronInvalidStateTransitionError` on an illegal
trigger, which makes consent writes fail-closed regardless of whether the upstream
BT guard is correct — the fail-open concern raised for `CreateParticipantStatusNode`
in ISSUE-1825.

Note: `apply_pec_trigger()` (the legacy soft-fail helper that returned the
current state unchanged on an invalid trigger instead of raising) has been
removed (CONCERN-1871).

Consent-write sites (every one routes through `apply_pec_transition()` or
`apply_pec_transition_if_legal()`):

| Site | Entry point |
|---|---|
| `case/nodes/proposal_consent.py` | `sign_embargo()` |
| `case/nodes/participant/participant_add.py` | `sign_embargo()` |
| `case/nodes/invite_embargo_consent.py` | `sign_embargo()` |
| `embargo/nodes/relay.py`, `relay_effect.py`, `reinvite.py` | `record_embargo_invite()` |
| `embargo/nodes/proposal.py` | `record_embargo_rejection()` |
| `embargo/nodes/expiry.py` | `record_invite_expiry()`, `honour_late_accept()` |
| `services/embargo_lifecycle/` (`pec.py`, `pec_activation.py`, `consent.py`) | the lifecycle operations themselves |

`EmbargoLifecycle` is the intended long-term owner of all consent transitions (see
[embargo-lifecycle.md](embargo-lifecycle.md) and #538), so its sites remain the most
critical to keep correct. The received `Reject(Invite)` tree writes consent through
`RecordParticipantRejectionNode` → `record_embargo_rejection`, so the MSM-07-004
classification lives in the service once (`_assert_rejectable`) rather than in a
node.

Rules that keep the rows and the content gate in agreement:

- **A `DECLINED` row holds no acceptance.** `_record_actor_acceptance` records
  nothing for a `DECLINED` row: `ACCEPT` is not legal from `DECLINED` (CM-18-003),
  and writing `ACCEPTED` would admit through the gate an actor whose row says
  declined. It is re-invited first (`DECLINED → INVITED`).
- **Nothing is recorded after termination.** Once EM is `EXITED`, an Accept or Reject
  writes no row: there is no embargo left to consent to and none can be re-invited
  (ADR-0118).
- **Withdrawal leaves the revisions too.** A `DECLINE` that names the active
  embargo (today a Reject of it; `Leave(EmbargoEvent)` once MSM-07-010 lands)
  also declines every open proposal's row the actor had accepted (every
  open proposal is a revision of the one active embargo, ADR-0113). When *no*
  embargo is in force a Reject of a proposal declines that proposal's row only —
  it withdraws from nothing.

---

## Pocket Veto (Timer-Based Transitions)

*Spec: CM-18-002, CM-28. Decisions: ADR-0065, ADR-0118.*

The `INVITED → EXPIRED` transition (`EXPIRE` trigger) is timer-based.
A configurable **embargo invitation timeout** policy window bounds how long an
invitation stays open. If the participant does not respond within the window,
they move to `EXPIRED` so one non-responsive invitee cannot stall coordination
indefinitely. Silence is not a decision, so it is never recorded as `DECLINED`,
which only an explicit refusal reaches (CM-28-004).

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
  `detect_and_apply_expiry()` reads the record of the actor whose expiry is
  being evaluated. Those two must name the same participant or enforcement silently
  never fires — see "Whose record holds the deadline" below
- Enforcement is **lazy**, not scheduled, and it is the **CASE_MANAGER's alone**
  (CM-28-014): expiry is derived from `(end_time, now)` when an inbound `Accept`
  is processed at the manager. No scheduler is required for correctness.
  The `EmbargoTimerExpired` Sentinel (#1893) is an optional proactive accelerator
- When an expiry is detected, the CASE_MANAGER authors an
  `invite_to_embargo_on_case_expired` ledger entry (CM-28-005, CM-28-009,
  `INVITE_EXPIRED_EVENT_TYPE`) distinguishing it from an explicit refusal,
  then applies `EXPIRE` (`INVITED → EXPIRED`, ADR-0118).
  The evaluation follows the guard→commit→effect order (CLP-10-006):
  `assess_invite_expiry()` is read-only (no writes); a separate commit node
  persists the entry; `record_invite_expiry()` applies the `EXPIRE` trigger
  after a successful commit.
  A failed commit leaves the invitee in `INVITED` — no consent change is
  persisted without a ledger record.
  The entry is role-gated: a non-manager that processes a late `Accept` writes
  nothing and returns a refusal; the invitee's consent is left as it was.
  Replicas replay the entry through `ApplyInviteExpiryFromLedgerNode` in
  `create_announce_log_entry_tree`, which applies `EXPIRE` idempotently and
  reads no clock or deadline — a replica learns an expiry and never computes one

> **Provenance note**: the header of this file cites
> `archived_notes/demo-review-26042001.md` as a source. The term "pocket veto"
> does **not** appear in that file — it entered the design via the architectural
> review of 2026-04-20, also cited there. Treat the demo-review citation as
> covering the rest of this document, not this section.

### Pitfall: A Lapse Is Not the Timer Destination

The timer path ends at `EXPIRED`, and only from an `INVITED` row. A participant has
lapsed only when the case owner activated longer terms it has not accepted — it
means neither "timed out" nor "a revision was proposed", and it is read from the
rows, never written. A lapsed participant has no deadline until it is re-invited (an
`INVITED` row for the embargo in force), at which point the invitation's deadline
applies. The deadline is one per participant, so when it passes every row still
`INVITED` expires. CM-18-001 and CM-18-002 both flag conflating these as a known
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

The stamp is `stamp_invite_rsvp_deadline()`
(`vultron/core/behaviors/embargo/rsvp_stamp.py`), driven by the sender's
`ActorConfig` (`default_rsvp_window`, floor `min_rsvp_window`). Every embargo
Invite the CASE_MANAGER sends goes through it: each relayed revision
(`RelayEmbargoInviteToEachNode`) and the EMB-17-003 re-invite of a stale late
accepter, which carries a fresh deadline (ASK-03-004) and is committed under its
own `event_type` (`ReinviteStaleAccepterNode`, EMB-17-011), so the replica
records the same deadline (#4137). The relay
passes the stamp to `propose_embargo()` as `rsvp_deadline`, `published` and
`min_rsvp_window`, so the factory checks the same floor the stamp used. It then
records the deadline read back from the sealed body — the value the committed
entry carries as `endTime` and the replica's `record_embargo_invite()` reads.

**The EP-07-001 receiver-side fallback is not the normal case.** The wire
extractor (`_effective_rsvp_deadline` in `vultron/wire/as2/extractor/_extract.py`)
still computes an effective deadline for every inbound embargo Invite —
applying the default window when `end_time` is absent and clamping per EP-07-003,
logging each clamp (EP-07-005) — and surfaces it on the event, where it is
logged and never stored: no received use case writes it (CM-28-013), and a
deadline enters a record only from the manager's commit or the replay of that
commit. Under the relay its default-window arm is reached only by an Invite that
arrives with no `end_time`: a misrouting, or a foreign implementation that does
not stamp.

Before the relay, no trigger set `end_time`, so every receiving store fell to
the EP-07-001 fallback and derived its own deadline from its own `ActorConfig` —
two replicas could disagree about when one invitation closed.
`EmbargoLifecycle.detect_and_apply_expiry()` reads the record of the actor whose
expiry it is evaluating. If the write and the read name different participants,
enforcement cannot fire and nothing raises: the invitee has no deadline to
expire against, and the record that *did* receive one is not the one being
checked.

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
| Accepted embargo **is** the current embargo (EM `ACTIVE` **or** `REVISE`) | Honour it; the row → `ACCEPTED` — directly from `EXPIRED`, via a re-invite from `DECLINED` (EMB-17-001/002) |
| Accepted embargo is **stale** (revised/replaced) | Send a **fresh invite** carrying the current embargo; do not record stale consent (EMB-17-003) |
| Case has **no** current embargo (EM `EXITED`/`NONE`) | Acknowledge as a no-op; consent rows unchanged; **keep** their case participation (EMB-17-004) |

The third row follows the EMB-07-003 precedent for post-terminal messages
(acknowledge without transitioning). EMB-13-002 already forbade accepting new
embargoes when CS is P/X/A; EMB-17-004 closes the remaining gap where EM has
`EXITED` but CS is not yet P/X/A.

### Synthesised Ledger Entries for Expiry and Late-Accept Routing

Four CASE_MANAGER-authored entries record the outcomes of the lazy expiry
evaluation (all in `vultron/core/models/rsvp_deadline.py`, all CASE_MANAGER-gated,
RSH-08-004, ADR-0118):

| `event_type` constant | `snapshot_type` | When committed | Replayed by |
|---|---|---|---|
| `INVITE_EXPIRED_EVENT_TYPE` | `InviteExpired` | `INVITED` past deadline → `EXPIRED` | `ApplyInviteExpiryFromLedgerNode` |
| `HONOUR_LATE_ACCEPT_EVENT_TYPE` | `HonourLateAccept` | EMB-17-001: active/matching embargo still current | `ApplyHonourLateAcceptFromLedgerNode` |
| `INVITE_EXPIRED_NOOP_EVENT_TYPE` | `InviteExpiredNoop` | EMB-17-004: EM `EXITED`/`NONE` — no consent change | no effect node needed (state is already terminal) |
| `EMBARGO_REINVITE_EVENT_TYPE` | `Invite` (no `attributedTo`) | EMB-17-003: accepted embargo is stale — fresh Invite to the current one | `ApplyEmbargoReinviteFromLedgerNode` |

Each entry uses the guard→commit→effect order (CLP-10-006).
`create_invite_expiry_tree`, `create_honour_late_accept_tree`, and
`create_noop_ledger_entry_tree` and `create_reinvite_stale_accepter_tree` (all in
`vultron/core/behaviors/embargo/expiry_tree.py`) are CASE_MANAGER-gated
factories; a non-manager processing a late `Accept` gets `REFUSED` from the
gate and applies no consent change.

The `honour_late_accept()` service method (`consent.py`) handles both the
`EXPIRED → ACCEPTED` direct path and the `DECLINED → INVITED → ACCEPTED`
two-step (CM-18-003: `ACCEPT` is not legal from `DECLINED`).
The replay node `ApplyHonourLateAcceptFromLedgerNode` extracts
`actor_id` from `entry.payload_snapshot["actor"]` and `embargo_id` from
`entry.payload_snapshot["object"]["object"]["id"]`, then calls the same
`honour_late_accept()` so the manager and replica always apply the same logic.

### Why `EXPIRED` Is a State, Not Provenance

ADR-0065 first recorded an expired invite as `DECLINED` and kept the
difference in the ledger only. ADR-0118 reversed that: code, logs, demos and
every replica read the state, not ledger provenance, so a silent invitee
was reported as having refused. `EXPIRED` behaves like `DECLINED` where the two
should agree — both are re-invitable and both are excluded from embargoed
content — and differs where they should not: a late `Accept` the CASE_MANAGER
honours moves `EXPIRED → ACCEPTED` directly, while a `DECLINED` participant is
re-invited first (`ACCEPT` is illegal from `DECLINED`).

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
even to `DECLINED` and lapsed participants:

- `Offer(EmbargoEvent)` — a new embargo proposal
- `Invite(target=case, object=EmbargoEvent)` — embargo invitation
- `Announce(EmbargoEvent)` — embargo status notification
- Responses to the above: `Accept`, `Reject`, `TentativeReject`

Only **case content** (vulnerability report details, fix status, technical
notes with sensitive information) is gated on the participant being a signatory to
the active embargo (CM-10-004).

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
  participant that is not a signatory to it is sent no ledger entries,
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

## Answering the Embargo in Force (EP-09-012)

**Status**: Planned — tracked by #4373 and #4388. Today the triggers resolve
open proposals only, and withdrawal is a Reject of the active embargo.

Activation takes a proposal out of `pending_embargo_proposal_index` (EP-08-003),
so the accept and reject triggers cannot reach the embargo in force through it.
A participant whose row for that embargo is still `INVITED` or `EXPIRED` can
still answer it: the receive side marks the row of whatever embargo the
`Accept(Invite(EmbargoEvent))` names, active or not (MSM-07-003, EMB-17-002).

- The answer goes through the relayed `Invite(EmbargoEvent)`, never the
  full-case Invite. Replies to the full-case Invite move only the RM state
  (CM-11-011) and carry no embargo consent.
- A joiner that accepts the stub Invite is already `ACCEPTED` for the active
  embargo (CM-11-001). A joiner's `INVITED` row from the stub Invite
  (CM-11-006) has no `Invite(EmbargoEvent)` behind it, so only a participant
  that never answered a relayed `Invite(EmbargoEvent)` (EP-09-011) needs this.
- The caller names the Invite. With no name the trigger picks among open
  proposals only (EP-08-002) and never falls back to the embargo in force,
  because answering an embargo is an intentional act and a fallback could
  consent to terms the caller did not mean.
- Do not re-add the active embargo to the open-proposal index to make the
  trigger find it; that breaks EP-08-003 and EP-08-002's selection.
- Withdrawing is not answering. A signatory leaves the embargo in force by
  sending `Leave(EmbargoEvent)` through its own trigger (EP-09-013, #4388,
  MSM-07-010), which needs no Invite, so the reporter and a joiner can use it.
  The reject trigger never withdraws, and a Reject of the active embargo from
  an `ACCEPTED` row is refused (MSM-07-004). ADR-0122 records why `Leave` was
  chosen over `Reject(Invite)`, `Undo(Accept)` and `Reject(EmbargoEvent)`.

*Spec: EP-09-012, EP-09-013, EP-08-003, MSM-07-003, MSM-07-010. Decision: ADR-0122.*

## Implications for DR-06 (Accept Embargo Handler)

The owner's decision and each participant's consent are different messages
(ADR-0122), so no handler branches on the sender to know what a message means:

1. `AcceptInviteToEmbargoOnCaseReceivedUseCase` (`Accept(Invite(EmbargoEvent))`)
   marks the sender's consent row for the accepted embargo `ACCEPTED`, whoever the
   sender is, and moves no register entry.
2. `ActivateEmbargoOnCaseReceivedUseCase` (`Accept(EmbargoEvent, target=Case)`,
   the case owner only) activates the proposal — EM derives `ACTIVE` — and marks
   the owner's row `ACCEPTED` unless it already is.
3. Idempotent: if the row is already `ACCEPTED`, succeed silently (HTTP 2xx).
4. When the owner's activation replaces the active embargo with a revision that
   ends no later: carry every signatory over by marking the revision's row
   `ACCEPTED` for each. A *longer* replacement writes nothing — signatories
   without the revision's row have lapsed by derivation. A proposal changes
   nobody's consent to the embargo in force.

### Trigger-Side Ownership Gate (BUG-26042101, 2026-04-22)

The same owner-vs-participant split applies to **trigger-side** embargo
responses, where it picks the activity, not its meaning:

- **Case owner**: `accept-embargo` and `reject-embargo` send its decision for
  the case, `Accept`/`Reject(EmbargoEvent, target=Case)`, which drive shared EM
  (`EM.ACTIVE`, or back to the prior terms).
- **Non-owner participant**: they send `Accept`/`Reject(Invite(EmbargoEvent))`,
  which mutate only their own consent row; they do NOT advance shared EM.

A case that names no owner (`attributed_to is None`) has no owner decision to
send: `is_case_owner()` answers `False`, so every trigger sends consent.

**Idempotent PEC transitions**: Participant-only accept/reject updates SHOULD
NOT re-run the PEC machine when the row is already in the target state
(`ACCEPTED` / `DECLINED`). Idempotent repeats MUST NOT generate
invalid-transition warnings, and a retried accept/reject MUST NOT downgrade
consent the participant already holds. Guard the call site with
`if participant.consent_for(embargo_id) != EmbargoConsentState.<TARGET>:` before
`apply_pec_transition()`.

### Full Case Delivery Precondition

The case owner MUST only send `Announce(VulnerabilityCase)` with full case
details when a participant satisfies **both**:

1. `rm_state == ACCEPTED` (accepted the case invitation)
2. the participant is a signatory to the active embargo
   (`is_signatory(active_embargo_id)`) OR there is no active embargo

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
  state transitions to `DECLINED` or `EXPIRED`?
  *Partially resolved*: CM-28-005 requires a CASE_MANAGER-authored ledger entry for
  an expiry, which makes it visible to the owner via the ledger. Whether a
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
  attaches only to a case-scoped `Invite(EmbargoEvent)`. See ADR-0096, which
  rules out a pre-case embargo phase.
