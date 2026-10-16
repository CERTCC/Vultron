---
title: Participant Embargo Consent (per-Embargo Rows)
status: active
kind: guidance
description: >
  Rules for per-participant embargo consent, recorded as one row per
  (participant, embargo register entry): which writes create and move rows,
  what is derived rather than stored, why only the CASE_MANAGER sets consent,
  pocket veto and RSVP deadlines, the expiry sweep before an owner decision,
  how the owner learns of a decline or timeout, late accepts, and the content gate.
related_specs:
  - specs/case-ledger-processing.yaml
  - specs/case-management.yaml
  - specs/embargo-policy.yaml
  - specs/em-behavior.yaml
  - specs/handler-protocol.yaml
  - specs/message-semantics-mapping.yaml
  - specs/message-validation.yaml
  - specs/protocol-asks.yaml
  - specs/sync-ledger-replication.yaml
  - specs/vultron-as2-mapping.yaml
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
  - notes/case-ledger-authority.md
relevant_packages:
  - transitions
  - vultron/bt/embargo_management
  - vultron/core/behaviors/embargo
  - vultron/core/models/case_participant.py
  - vultron/core/models/embargo_apply.py
  - vultron/core/behaviors/sync/nodes
  - vultron/core/use_cases
---

# Participant Embargo Consent (per-Embargo Rows)

Consent is recorded once, per (participant, embargo): `CaseParticipant.embargo_consents`
holds one `EmbargoConsent(embargo_id, state, rsvp_deadline)` row for **every entry
in the case's embargo register** (CM-18, ADR-0122). The machine is in
`vultron/core/states/participant_embargo_consent.py`; the normative transition
table is CM-18-003.

A note, comment or test that describes `SIGNATORY`, `LAPSED`, `UNBOUND`,
`ACCEPTED` or `EXPIRED` as a stored consent state, or "no row" as "never asked",
predates ADR-0122 and is wrong.

---

## The Consent Rows

| Row state | Meaning |
|---|---|
| `UNINVITED` | Not asked about this embargo. The start state |
| `INVITED` | Asked; no answer yet. Carries the invitation's RSVP deadline |
| `AGREED` | Agreed — explicitly, as proposer, by seeding (CM-14-003, CM-14-005), or by carry-over (EP-05-001) |
| `DECLINED` | Explicitly refused it, or withdrew from it (ADR-0093) |
| `TIMED_OUT` | Invited; the RSVP deadline passed with no answer (pocket veto, ADR-0118) |

- **Asking again does not undo an answer.** `AGREED` refuses `INVITE`. An
  illegal trigger raises (CM-18-009).
- **A participant can change its answer.** `AGREE` is legal from `DECLINED`:
  a participant that declined and then accepts has just said it accepts, so its
  row moves straight to `AGREED`, with no new invitation first (CM-18-003,
  #4597). Only the participant's own answer does this. Seeding (CM-14-003,
  CM-14-005) and the Accept of the full-case Invite leave a `DECLINED` row as it
  is, because they are not answers the participant gave.
- **`CARRY_OVER` agrees for a participant without its asking.** Agreeing to N
  days is agreeing to every shorter period, so a signatory of the replaced
  embargo is bound by a shorter revision even if it declined the revision
  (EP-05-001).
- **Answers to a closed embargo version can no longer change.** Each embargo
  version has its own record of each participant's answer. Once a version is
  replaced (`SUPERSEDED`), rejected (`REJECTED`), cancelled (`CANCELLED`) or ended
  (`TERMINATED`), answers to it can no longer change: `apply_pec_transition()`
  takes the entry status (`entry_status=`) and refuses every trigger. This also
  covers "nothing is recorded after termination". A late Accept of stale terms is
  answered with an invitation to the current embargo (EMB-17-003).

### Every Row Is Written (CM-18-001)

Two writes create rows, both at `UNINVITED`, and neither records an answer:

- **A proposal** (a `PROPOSE` register step) writes a row for the new embargo on
  every current participant, in `_LifecycleBase._apply_register_step()`, so every
  path that proposes gets them.
- **A participant joining the roster** gets a row for every entry already in the
  register: `VulnerabilityCase.add_participant()` calls `write_uninvited_rows()`.
  So attach a participant to the case first, then persist it.

`consent_for()`, `is_signatory()` and `has_lapsed()` raise
`VultronNotFoundError` on a missing row. A missing row is a defect at the write,
never "not asked".

A late joiner is invited only to the `ACTIVE` embargo (the stub Invite's
`INVITED` row, CM-11-006) and to open revisions (`RelayOpenProposalsToJoinerNode`).

**`UNINVITED` does not mean an invitation is owed.** `AGREE` and `DECLINE` are
legal from it because consent is not always mediated by an invitation (the
reporter's consent is implicit in the report, CM-14-005; participants seated at
case initialization already have the embargo in scope, ADR-0041). Do not add a
synthetic `INVITED` hop; it records an invitation that never happened.
`CaseParticipant.sign_embargo()` is that seeding shape.

### What Is Derived, Not Stored (CM-18-016)

| Position | How it is read |
|---|---|
| **Signatory** | the row for the `ACTIVE` entry is `AGREED` (`is_signatory(case.active_embargo_id)`) |
| **Lapsed** | an entry is `ACTIVE`, its row is neither `AGREED` nor `DECLINED`, and the first entry back along `replaces` whose row is `AGREED` or `DECLINED` is `AGREED` (`has_lapsed(case.embargo_register)`) |
| **Exited** | no entry is `ACTIVE`, so nobody is a signatory and nobody has lapsed |
| **Bound for the content gate** | `VulnerabilityCase.is_active_participant` reads `is_signatory(active_embargo_id)` (CM-10-004) |

Lapsed follows `replaces`, so only an embargo once in force can bind; the cases
are pinned in `test/core/models/test_case_participant.py`. Signatory, lapsed
and exited are reads; code that writes a row to record one re-creates the second
record ADR-0122 removed.

`ParticipantStatus` carries no consent and `embargo_adherence` is gone
(ADR-0122 supersedes ADR-0056). The wire keys `emConsentState`,
`embargoAdherence`, `embargoConsentState` and `acceptedEmbargoIds` are refused
inbound by name (`RETIRED_NAMES`).

---

## Consent Is Per Embargo

An Accept is always a statement about the embargo it names, so it marks that
embargo's row, whether the embargo is in force, a first proposal or a revision
(MSM-07-003). A participant can hold `AGREED` for active embargo A and for
proposed revision B at once; it is a signatory to A until B is active. So **a
participant cannot lapse until the embargo on the case differs from the one it
agreed to.**

| Event | Effect on the rows |
|---|---|
| Revision B proposed | every participant gets an `UNINVITED` row for B; the proposer's becomes `AGREED`; nothing else |
| A participant (owner included) accepts the Invite to B | its row for B becomes `AGREED`; its row for A is untouched |
| A participant (owner included) rejects the Invite to B | its row for B becomes `DECLINED`; refusing B is not withdrawing from A |
| A non-owner withdraws from the *active* embargo | its row for A becomes `DECLINED`, and so does every open proposal's row it had agreed to (MSM-07-010) |
| A participant that declined an embargo accepts its Invite | its row for that embargo becomes `AGREED` directly; no new invitation first (CM-18-003) |
| Owner rejects B for the case (`Reject(EmbargoEvent)`) | nothing — the owner is keeping A, not declining it |
| Owner activates B, and B ends **no later than** A | owner's row for B → `AGREED`; `CARRY_OVER` makes B's row `AGREED` for every signatory of A, a `DECLINED` row for B included |
| Owner activates B, and B ends **later than** A | owner's row for B → `AGREED`; nothing else — signatories without an `AGREED` row for B have lapsed by derivation |
| Owner activates B while its own row for B is `DECLINED` | the owner has changed its answer: its row for B → `AGREED` and B is activated, with no re-invite first |
| Termination | nothing — no entry is `ACTIVE`, and answers to the ended embargo can no longer change |

**Withdrawal is `Leave(EmbargoEvent)`, never a Reject** (MSM-07-004, MSM-07-010).
A Reject of the active embargo from an `AGREED` row is refused; from any other
row it declines that row only and cascades to no revision. One predicate in
`vultron/core/services/embargo_lifecycle/pec.py` decides each refusal, and the
received guard, the trigger and the lifecycle write all call it, so they cannot
drift: `reject_is_withdrawal_refusal` for the Reject, `embargo_withdrawal_refusal`
for the Leave (not in force, not `AGREED`, or the case owner). Answering the
embargo in force names its relayed `Invite(EmbargoEvent)`, never the full-case
Invite, and never falls back to it when no Invite is named (EP-09-012, #4373;
see § "Answering the Embargo in Force").

Only the owner's decision changes the embargo on the case, through
`Accept`/`Reject(EmbargoEvent, target=Case)` (MSM-07-008/009). Every
`Accept`/`Reject` of an Invite, the owner's included, is the sender's consent
(MSM-07-003/004). The only activation writes are the owner's own agreement and
the carry-over (`_consent_at_activation`, `_carry_signatories_over`).

**Never write consent on propose, lapse, advance or exit.** A proposal only adds
rows for the proposed embargo. Code that changes a participant's consent to the
embargo *in force* inside a proposal path is a defect: coverage never breaks
during a revision, and a rejected revision must not strand its signatories.

**A revision Invite lands on the revision's own row** (EP-09-004). It cannot
touch the `AGREED` row that binds a signatory. The `INVITE` is decided at the
CASE_MANAGER's commit of each relayed Invite (`RelayEmbargoInviteToEachNode`),
through `EmbargoLifecycle.record_embargo_invite()` on a staged store, and is
committed as its own `Update(EmbargoConsent)` entry right after the Invite's,
which every replica copies (the Invite's own slot writes no row). The decision uses
`apply_pec_transition_if_legal()`, the one sanctioned "apply where legal" shape:
an `AGREED` or already-`INVITED` row is a recorded no-op; every other caller
stays fail-closed. Re-inviting a row still `INVITED` replaces its deadline
(`restamp_rsvp_deadline()`).

**A participant writes no consent on receipt of an Invite** (EP-09-003). It
stores the Invite and answers the CASE_MANAGER; the replica learns the outcome
from the ledger.

**The owner MAY decide without waiting and SHOULD wait to gauge consensus**
(EP-09-005, EP-09-006). The Invites are not a vote; they gather the rows the
carry-over reads. The waiting policy is the actor's.

---

## Consent Is Set by the CASE_MANAGER, Not Self-Reported (CM-28-003)

RM and VF/D are self-reported. Consent rows are set by the CASE_MANAGER from
*observed* behaviour and replayed by every replica: it marks `AGREED` on an
inbound `Accept(Invite(EmbargoEvent))`, `DECLINED` on a `Reject`, `TIMED_OUT`
when a deadline passes, and carries signatories over on activation. There is no
"I am now a signatory" activity, which is why consent needs no wire message
partition of its own.

**A participant refuses a P/X/A revision with ER, never ET** (EMB-03-003,
ADR-0118). A participant that is neither owner nor CASE_MANAGER answers a
revision Invite with ER to the CASE_MANAGER and does not move its own EM state;
termination is the owner's (or delegated CASE_MANAGER's) decision. A store that
is not the sender and not in `to` refuses the copy at the door
(`unaddressed_copy_refusal()`) and answers nothing; `cc` addresses nobody
(ADR-0109).

---

## Pitfall: Never Assign `embargo_consents` Directly (CM-18-005)

Change consent by applying a `PEC_Trigger` through
`CaseParticipant.apply_pec_transition(embargo_id, trigger, entry_status=...)`,
preferably through `EmbargoLifecycle`'s `_apply_where_legal()`, and persist the
participant. `write_uninvited_rows()` and the copy write below are the only other
row writes; the first records no answer. Direct assignment bypasses the
transition table, so the content gate (CM-10-004) can admit an actor the protocol
never bound; `apply_pec_transition()` raises
`VultronInvalidStateTransitionError` instead, so consent writes are fail-closed
even when an upstream guard is wrong.

Keep the MSM-07-004 classification in the service (`_assert_rejectable`,
`reject_is_withdrawal_refusal`), not in a node: the received `Reject(Invite)`
tree writes through `RecordParticipantRejectionNode` →
`record_embargo_rejection()`, and its read-only guard `RejectIsNotWithdrawalNode`
calls the service's predicate rather than restating it.

- **A `DECLINED` row holds no agreement.** `_record_actor_acceptance` records
  nothing for it; writing `AGREED` would admit through the gate an actor whose
  row says declined. Only `CARRY_OVER` lifts it.
- **Withdrawal leaves the revisions too.** `record_embargo_withdrawal` (the
  `Leave`) declines the active row and every open proposal's row the actor had
  agreed to (every open proposal revises the active embargo, EP-08-004). A
  Reject never cascades: it declines the named row only.

### The copy write: one apply function (ADR-0124, #4713)

`CaseParticipant.copy_consent_row()` is the third row write, and the only one
a replica may use: it stores a row exactly as a ledger entry carries it. It is
called only from `apply_embargo_change()` (`vultron/core/models/embargo_apply.py`),
the one apply function the CASE_MANAGER's trial apply and every replica share.
That function checks the starting state first (a `Create` row is new; an
`Update` row is held and one consent transition, or a fresh `INVITED`
deadline, reaches the carried state; a final entry's rows are frozen) and
raises `VultronEntryRefusedError` otherwise. It never runs `apply_pec_transition`.

- **Entries follow activity/object pairs.** A register step rides on the
  act's own activity (`RegisterStep`: the `Accept(EmbargoEvent, target=Case)`
  is `ACTIVATE` with its supersede, the `Remove` is `TERMINATE` with its
  cancels); each changed consent row is its own CASE_MANAGER
  `Create`/`Update(EmbargoConsent)` entry (`ConsentRowChange`, event types in
  `embargo_consent_event_types.py`).
- **A row is an AS2 object.** `EmbargoConsent` has `type`, a derived `id`
  (`EmbargoConsent.build_id(embargo_id, actor_id)`) and `attributedTo`, the
  participant's actor. A participant record stamps its actor on every row it
  holds, so compare rows with `attributed_to` set, or compare states.
- **The CASE_MANAGER side** is `commit_and_apply_embargo_entries()`
  (`vultron/core/behaviors/embargo/copy_commit.py`): it trial-applies every
  planned entry, commits them in order, then saves the result; a refused trial
  commits nothing, and a failed commit saves only the changes whose entries
  committed. `consent_row_entry()` builds the planned entry for one row.
- **The replica side** subclasses `ApplyEmbargoChangeFromLedgerNode`
  (`sync/nodes/embargo_copy_effect.py`) and names its entry's change in
  `_change()`; a refused entry is held in `LedgerGapBuffer` and the announce is
  reported deferred, never patched over. An entry whose result the replica
  already holds (saved, but not yet stored, before a stop) is an idempotent
  no-op (`change_is_in_place()`); the CASE_MANAGER's trial still refuses an
  entry that would change nothing. So is a refused entry the case file is
  already past (`case_file_is_past()`): a joiner's seed is taken after entries
  it then replays from genesis, so replay moves forward only (CM-23-016,
  ADR-0114). A missing register entry, participant or row stays a refusal.
- **Decide on a stage, record by diff** (#4715). An arm whose decision is an
  existing `EmbargoLifecycle` operation runs it on a `StagedCasePersistence`
  and lets `decided_entries.py` turn what it would have written into the
  entries: the act's register step, then one row entry per changed row, in
  roster order. The proposal's rows are `Create`s (the proposer's `AGREED`,
  every other `UNINVITED`); a relayed Invite's, the manager's policy
  consent's and a re-issued stub's are `Update`s. A participant's
  `Accept`/`Reject(Invite(EmbargoEvent))` is the exception ADR-0122 names: its
  own entry carries the row it states (`ConsentRowChange.answer()`), so no
  second entry follows, and a received answer that would record nothing the
  case can take is refused among its guards (`EmbargoAnswerAppliesNode`)
  before it is committed. A decision that wrote anything no entry carries
  raises `VultronBTInternalError`.
- **Fan-out follows the commit.** Every entry of an act is committed before
  the act is applied, so each is fanned out to the participants entitled
  before the act: a signatory that an activation lapses still receives the
  activation's entries, as on the received path.

---

## Pocket Veto and RSVP Deadlines (CM-28, EP-07, EMB-17)

`INVITED → TIMED_OUT` is timer-based, so one silent invitee cannot stall the
case. Silence is never recorded as `DECLINED`, which only an explicit refusal
reaches (CM-28-004). `TIMED_OUT` is a state, not ledger provenance, because code,
logs and replicas read the state: a silent invitee must not read as a refuser
(ADR-0118). Both are re-invitable and excluded from embargoed content, and
both move straight to `AGREED` on an Accept.

**The pocket veto and the RSVP deadline are one mechanism.** An `Invite.end_time`
is authoritative (CM-28-002); the configured window is the fallback for an Invite
without one (EP-07-001, default 7 days). Do not add a second timeout notion.

**A lapse is not the timer destination.** The timer ends at `TIMED_OUT`, and only
from an `INVITED` row; lapsed is a read (the owner activated longer terms). Each
invitation has its own deadline on its own row, so only that row times out
(CM-18-001, CM-18-002).

### The Two-`end_time` Hazard

An embargo invitation carries two `end_time` fields one level apart. Read them
independently; never substitute one for the other.

| Field | Meaning |
|---|---|
| `Invite.end_time` | RSVP-by — when the *invitation* stops being open |
| `Invite.object_.end_time` | Embargo expiry — when the *embargo* ends (required, no default) |

### Whose record holds the deadline

The deadline belongs to the **invited participant**, the Invite's sole `to:`
recipient (EP-09-010) — never to whichever store processes the message. The
CASE_MANAGER stamps `Invite.end_time` on every embargo Invite it sends with
`stamp_invite_rsvp_deadline()` (`vultron/core/behaviors/embargo/rsvp_stamp.py`,
CM-28-012) and writes it on the invitee's `INVITED` row at its commit; the replica
replay writes the same value (CM-28-013). Record the deadline read back from the
sealed body, which is what the committed entry carries.

- **Write and read must name the same participant.** `detect_and_apply_expiry()`
  reads the row of the actor it evaluates; if the write landed on another record,
  enforcement never fires and nothing raises. Deriving the invitee from the
  receiving actor would put the deadline on the enforcer's own record.
- **`resolve_invitee_id()` refuses an Invite with zero or several recipients** as
  a misrouting, rather than guessing. The CASE_MANAGER is the adjudicator of a
  proposal addressed to it, not its invitee, so its own row never takes the
  deadline. See [bt-integration.md](bt-integration.md) § "The message subject is
  a fourth identity, and it must stay separate".
- **The receiver-side fallback is logged, never stored.** The wire extractor
  (`_effective_rsvp_deadline`) computes an effective deadline for every inbound
  embargo Invite, applying the default window and clamps (EP-07-003, EP-07-005),
  but no received use case writes it (CM-28-013).

Only `Invite(EmbargoEvent)` is enforced; there is no `Offer` in the embargo path.

### Expiry is lazy, and only the CASE_MANAGER's (CM-28-014)

Expiry is derived from `(end_time, now)` when the CASE_MANAGER processes an
inbound `Accept`; no scheduler is needed (an `EmbargoTimerExpired` Sentinel
would only accelerate it, #1893). The outcomes are four CASE_MANAGER-authored
ledger entries (`vultron/core/models/rsvp_deadline.py`, trees in
`vultron/core/behaviors/embargo/expiry_tree.py`):

| Situation | Behaviour |
|---|---|
| `INVITED` row past its deadline | entry `INVITE_EXPIRED_EVENT_TYPE`, then `TIME_OUT` on that row only (CM-28-005) |
| Accepted embargo is still current (EM `ACTIVE` or `REVISE`) | honour it: row → `AGREED`, directly from `TIMED_OUT` or `DECLINED` (EMB-17-001/002) |
| Accepted embargo is stale | send a fresh Invite to the current embargo with a fresh deadline; the answer recorded for the stale terms can no longer change (EMB-17-003) |
| No current embargo (EM `EXITED`/`NONE`) | acknowledge as a no-op; rows and case participation unchanged (EMB-17-004) |

A late Accept is never refused (EMB-17): the accepter has signalled willingness
to coordinate. Each entry follows guard → commit → effect (CLP-10-006): a failed
commit leaves the row `INVITED`. A non-manager writes nothing and gets `REFUSED`
from the gate. Replicas replay each entry through the same service method the
manager used (`honour_late_accept()`, `record_invite_expiry()`), reading no
clock: a replica learns an expiry and never computes one.

### Sweep due expiries before the owner decides (CM-28-015)

An invitee that never answers sends nothing, so a late-`Accept` check never sees
it: its row stays `INVITED` until owner close expires it (CM-23-014). The
CASE_MANAGER therefore expires every overdue `INVITED` row of an open proposal or
the embargo in force before it commits the owner's decision, and on every other
received embargo activity, after all of the activity's refusal checks, so a
refused activity writes nothing (CM-28-015). Rows of a replaced, rejected,
cancelled or ended embargo are frozen: skip them. Reuse the owner-close settle
step's commit → effect pair, filtered to rows past their deadline, rather than
writing a second expiry path (`create_commit_and_record_expiry_tree`).

### The ledger fan-out is the owner's notification (MSM-07-007)

The owner learns of a `DECLINED` or `TIMED_OUT` answer from the entry itself. An
active owner gets the `Announce(CaseLedgerEntry)`, because `ledger_entry_recipients`
includes every active participant; an owner holding CASE_MANAGER is excluded from
its own fan-out but already holds the entry. Do not add a separate notification
activity: it would duplicate the entry, and for a `Reject` it would be the
acknowledgement EP-09-009 forbids (#4548).

### Clamp, don't reject (EP-07-002, EP-07-003)

A sub-floor deadline is raised to the floor on receipt, never refused: refusing
would hand a hostile sender an invite that never takes effect. The floor is
relative (ADR-0096): the lesser of the configured window (72h default) and the
time left in the embargo, because EP-07-006 clamps any deadline down to the
embargo's own `end_time`. Receivers with different windows compute different
deadlines; the clamp guarantees safety, not identical arithmetic. Normalize an
inbound `end_time` to UTC before comparing (CM-28-006).

---

## Embargo Messages Reach Non-Signatories

Embargo meta-protocol messages — proposals, Invites, `Announce(EmbargoEvent)`
and the responses to them — MUST reach `DECLINED` and lapsed participants, or a
non-signatory could never accept terms it never sees. Only case content is gated
on being a signatory (CM-10-004).

**Ledger fan-out is case content** (CM-10-005, CM-10-006), gated per participant
**stream**, not per entry: a payload is hashed into the chain, so it cannot be
redacted per recipient, and a skipped entry would be replayed on the replica's
gap Reject. So while an embargo is active a non-signatory is sent no ledger
entries, by fan-out or replay; when the gate admits it, the CASE_MANAGER sends
the withheld suffix in log order. The predicate is the shared selection in
`vultron/core/participants/recipients.py` (CM-10-007); the pause mechanics are in
[sync-ledger-replication.md](sync-ledger-replication.md) § "Fan-Out Recipients
and the Embargo Gate". Invites are addressed directly, so the pause cannot lock a
participant out of accepting.

---

## Answering the Embargo in Force (EP-09-012)

Activation takes a proposal out of `pending_embargo_proposal_index` (EP-08-003),
so the accept and reject triggers cannot reach the embargo in force through it.
A participant whose row for that embargo is still `INVITED` or `TIMED_OUT` still
answers it, because the receive side marks the row of whatever embargo the
`Accept(Invite(EmbargoEvent))` names, active or not (MSM-07-003, EMB-17-002).

`_resolve_embargo_proposal` (`vultron/core/use_cases/triggers/_helpers.py`) looks
in the open-proposal index first, then reads a named id as the actor's received
Invite (`read_received_activity`). It accepts only an `Invite` whose sole `to`
recipient is the actor (EP-09-010), whose object is the active embargo, held
under its own id too (the answer wraps that copy), and for which the actor's row
is `INVITED` or `TIMED_OUT`. Anything else raises `VultronNotFoundError`.

- The answer goes through the relayed `Invite(EmbargoEvent)`, never the
  full-case Invite, whose replies move only RM state (CM-11-011).
- A joiner that accepts the stub Invite is already `AGREED` for the active
  embargo (CM-11-001); only a participant that never answered a relayed
  `Invite(EmbargoEvent)` (EP-09-011) needs this path.
- **The caller names the Invite.** With no name the trigger picks among open
  proposals only (EP-08-002) and never falls back to the embargo in force: a
  fallback could consent to terms the caller did not mean.
- Do not re-add the active embargo to the open-proposal index to make the
  trigger find it; that breaks EP-08-003 and EP-08-002's selection.
- **Withdrawing is not answering.** A signatory leaves through
  `Leave(EmbargoEvent)` (EP-09-013, MSM-07-010), which needs no Invite: the
  withdraw-embargo trigger resolves the embargo from the case's active embargo
  (`resolve_embargo_to_withdraw`, beside `_resolve_embargo_proposal` in the
  same module), so a signatory made by seeding or joining can leave too. The
  reject trigger never withdraws (MSM-07-004; ADR-0122).

---

## Handlers and Triggers

The owner's decision and each participant's consent are different messages
(ADR-0122), so no handler branches on the sender to learn what a message means:

- `AcceptInviteToEmbargoOnCaseReceivedUseCase` (`Accept(Invite(EmbargoEvent))`)
  marks the sender's row for that embargo `AGREED` and moves no register entry.
- `WithdrawFromEmbargoOnCaseReceivedUseCase` (`Leave(EmbargoEvent)`) declines
  the sender's `AGREED` row for the embargo in force and its agreed revisions,
  and moves no register entry. Its guards sit ahead of the commit, the
  CASE_MANAGER's staged decision among them, so a refused Leave is never
  ledgered. The Leave's entry carries no row: each declined row follows as the
  CASE_MANAGER's own `Update(EmbargoConsent)` entry, which every replica copies
  (ADR-0124, #4717). The withdrawer's replica still receives the Leave and every
  row entry, because each is committed before the rows make it inactive.
  A redelivery of a Leave the ledger already records is `SKIPPED`, not
  refused (HP-01-003); a new Leave after the withdrawal is still refused.
- `ActivateEmbargoOnCaseReceivedUseCase` (`Accept(EmbargoEvent, target=Case)`,
  owner only) activates the proposal (EM derives `ACTIVE`, or `REVISE` while
  another proposal stays open, ADR-0130), marks the owner's row `AGREED` unless it
  already is, and applies the carry-over above.
- **Triggers pick the activity by ownership.** The case owner's
  `accept-embargo`/`reject-embargo` send `Accept`/`Reject(EmbargoEvent,
  target=Case)`; a non-owner's send `Accept`/`Reject(Invite(EmbargoEvent))`,
  which move only its own row. A case with no owner (`attributed_to is None`)
  has no owner decision, so every trigger sends consent.
- **A repeated answer changes nothing.** A repeat of the same answer from the
  same participant (Accept after Accept, Reject after Reject, under any activity
  id) changes nothing. It logs no invalid-transition warning, and the
  CASE_MANAGER commits no ledger entry and sends nothing:
  `EmbargoAnswerNotRecordedNode` reads `consent_for(embargo_id)` ahead of the
  commit and the handler reports `SKIPPED` (CM-13-005, HP-01-003, #4597). A
  change of answer is normal, not a repeat, and is recorded with one ledger
  entry: withdrawal (a Reject until #4388 adds `Leave`), or an Accept after a
  Reject, which moves the row straight to `AGREED`.
- **Full case delivery needs both** `rm_state == ACCEPTED` and signatory status
  (or no active embargo), checked in the `AcceptInviteActorToCase` BT subtree,
  not in post-BT code (MV-10-005).
