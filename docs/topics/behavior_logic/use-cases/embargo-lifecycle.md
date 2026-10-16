---
stakeholder_type: [platform-developer]
level: 400
introduces: [Embargo Consent, Pocket Veto]
description: >
  Triggers `propose_embargo`, `accept_embargo`, `reject_embargo`, and `terminate_embargo`: negotiating, joining, revising, and ending an embargo.
---

# Embargo Lifecycle

An embargo is an agreement that Participants will not disclose a vulnerability before an agreed moment.
The protocol tracks it twice, at two different scopes, and almost every mistake in this area comes from conflating them.

This page explains the two-scope model, the negotiation steps and what each one commits, where the judgment sits, and the one condition that overrides every other consideration.

---

## Two scopes, not one state

The case carries **one** embargo, and each Participant carries its **own stance** toward it.

| Scope | What it tracks | States |
|---|---|---|
| Embargo Management (EM) | The case's embargo — one per case, computed from the case's embargo register | `NONE`, `PROPOSED`, `ACTIVE`, `REVISE`, `EXITED` |
| Participant Embargo Consent (PEC) | One Participant's answer to each embargo in the register | one row per embargo: `UNINVITED`, `INVITED`, `AGREED`, `DECLINED`, `TIMED_OUT` |

The distinction is not bookkeeping.
"The case is under embargo" and "this Participant is bound by it" are different facts, and a case routinely holds both at once: an active embargo with one Participant who declined it.
The case keeps one embargo register entry for every embargo ever proposed on it, and the EM state is a read of the entries' statuses ([§7.1.1 The Embargo Register in the specification](../../../reference/vultron-spec/tracking-models.md#711-the-embargo-register)).
A Participant is a signatory when its consent row for the register's `ACTIVE` entry is `AGREED`.
That is a lookup, not a second record, so the embargo and the Participant's position can never drift apart ([ADR-0122](../../../adr/0122-per-embargo-participant-consent.md)).
A Participant has lapsed when it agreed to an embargo that has since been replaced by one it has not agreed to.
That too is read from the rows and the register (CM-18-001): an entry is `ACTIVE`, the Participant's row for it is neither `AGREED` nor `DECLINED`, and, following the chain of replaced embargoes back from it, the first row that is `AGREED` or `DECLINED` is `AGREED`.
Neither signatory nor lapsed is a consent state.

Every row is written.
Proposing an embargo gives every current Participant an `UNINVITED` row for it, and a new Participant record gets an `UNINVITED` row for every embargo already in the register (CM-18-001).
`UNINVITED` means *not asked about this embargo*, not "has not answered yet", and a missing row is a defect: reading one raises.
An actor may agree or decline directly from `UNINVITED`, with no intervening invitation ([ADR-0048](../../../adr/0048-pec-no-embargo-is-absence-not-pre-consent.md), CM-18-003).

---

## What starts it

Five different things put an actor on this path.

**Case creation.** A case begins embargoed.
When a case is opened with no explicit proposal on the table, the receiving side applies its published default and the case goes straight to `EM.ACTIVE` — not `EM.PROPOSED` (EP-04-001).
The intermediate `PROPOSED` state is never persisted or observable (EP-04-002).
This is why a normal case trace shows no proposal exchange at all: submitting a report without a counter-proposal is tacit acceptance of the receiver's default.

**A local decision to negotiate.** The `propose_embargo`, `propose_embargo_revision`, and `terminate_embargo` triggers.

**An inbound overture.** Either an Embargo Proposal (EP) carrying terms, or an `Invite(EmbargoEvent)` asking one actor for its consent.
These are the two flows the response decision handles (EMB-15).
An answer to an invitation, `Accept` or `Reject` of the `Invite(EmbargoEvent)`, is always the sender's own consent and moves only that sender's row, the case owner's included (MSM-07-003, MSM-07-004).
The case's embargo moves only when the case owner decides it, with `Accept(EmbargoEvent, target=Case)` or `Reject(EmbargoEvent, target=Case)` (MSM-07-008, MSM-07-009).

**A deadline passing.** An invitation carries a respond-by instant, and an unanswered invitation eventually times out, which is not a refusal — see [Inaction is an answer](#inaction-is-an-answer) below.

**An end time passing.** An embargo in force does not end by itself when its end time passes.
The case manager ends it with the reason `END_TIME_REACHED` the next time it handles the case, whether for an incoming message or one of its own triggers, so no scheduler is needed.
The check runs as part of handling the message or trigger, after the case manager confirms that the sender may send it, so a sender with no standing in the case cannot end the embargo.
A request to end the embargo early made after its end time is recorded as `END_TIME_REACHED` too — see [When the End Time Passes](../../process_models/em/early_termination.md#when-the-end-time-passes).

---

## The mechanical path

Every EM transition runs through the embargo lifecycle service, or through the single function that applies a committed ledger entry, which the case manager and every replica share (ADR-0124).
Termination and activation take the second path: the case manager commits the `Remove`, or the owner's `Accept`, first, then applies it.
The `Accept` records the whole activation, including the replaced embargo's supersession and the owner's own agreement, and each signatory carried over to shorter terms gets its own ledger entry after it.
An invitation that expires unanswered is recorded the same way: the case manager commits the expiry, then the participant's changed consent, and only then writes it.
A behavior tree node never assigns `case.current_status.em` and saves the case as a shortcut (EMB-18-001).
The reason is that a transition is not a field write.
It has to be validated against the state machine, and a failed validation must stop the node rather than log a warning and write anyway (EMB-18-002).
A case also never names an embargo whose record its store does not hold (EMB-18-003).
Activating an embargo reads both the record being activated and the one it replaces, and refuses before any write if either cannot be read.
A sender carries the embargo record inline with the case, and a receiver stores that record before the case that names it, so a case naming an embargo the receiver lacks is refused rather than stored.
A receiver refuses an inline embargo record whose context is a different case, so a sender cannot plant one case's embargo under another's id.

A receiver also checks who sent each embargo message before it changes anything (ADR-0115).
The case manager takes a proposal only from an active participant, and takes an acceptance or rejection only from the actor the recorded invitation was addressed to.
It takes an embargo record being created, added or removed only from the case owner or from itself.
Every other participant takes an embargo message only from the case manager.
A message from any other sender is refused and changes no state.

Each message that changes the case's embargo is one step on the embargo register, and the EM state follows from the register.
Every step must move EM along a transition of the EM state machine, and a step that would not is refused with nothing written (EMB-18-005, EMB-18-006).
The transitions themselves are small and fixed:

| Message received | Register step | EM result |
|---|---|---|
| Embargo Proposal (EP), `Invite(EmbargoEvent)` | a new `PROPOSED` entry | `NONE` to `PROPOSED` (EMB-01-001); stays `PROPOSED` or `REVISE` for a further proposal |
| Embargo Revision (EV), `Invite(EmbargoEvent)` | a new `PROPOSED` entry | `ACTIVE` to `REVISE`; the active embargo stays in force (EMB-03-001) |
| Embargo Acceptance (EA) or Revision Acceptance (EC), the case owner's `Accept(EmbargoEvent, target=Case)` | the named entry becomes `ACTIVE`, superseding any entry in force | to `ACTIVE` once no other proposal is open, otherwise to or staying at `REVISE` (EMB-02-001) |
| Embargo Rejection (ER) or Revision Rejection (EJ), the case owner's `Reject(EmbargoEvent, target=Case)` | the named entry becomes `REJECTED` | `PROPOSED` to `NONE`, or `REVISE` to `ACTIVE`, once no other proposal is open; otherwise unchanged (EMB-06-001) |
| Embargo Termination (ET), `Remove(EmbargoEvent, target=Case)` | the `ACTIVE` entry becomes `TERMINATED`, and every open proposal `CANCELLED` | `ACTIVE` or `REVISE` to `EXITED`, immediately |

The formal protocol has each receiver acknowledge these with EK; in this implementation the case manager's commit and announcement of the received activity is that acknowledgment, and no EK message exists (EP-09-009, MSM-02-009).

`EM.REVISE` is worth a second look.
A revision under negotiation does not suspend the embargo — the existing terms remain binding until the revision is accepted, and every signatory to them remains a signatory.
That is what makes renegotiation safe, and it is why the recommended practice is to accept and then revise rather than to counter-propose.

---

## Which messages move consent

Consent has no messages of its own (MSM-07-001).
Every Participant Embargo Consent change is a side effect of an EM activity or a deadline, and the case manager records it; a Participant never declares its own consent state.

| Activity | Effect on the case's EM state | Effect on consent |
|---|---|---|
| Embargo Proposal (EP) or Revision (EV), `Invite(Event)` on the case | `NONE` to `PROPOSED`, or `ACTIVE` to `REVISE`; a further proposal leaves it where it is | every Participant gets an `UNINVITED` row for the proposed embargo, the proposer's row becomes `AGREED`, because proposing terms is consenting to them, and no row for the embargo in force changes (CM-18-001, MSM-07-005, EP-05-002) |
| A relayed `Invite(Event)` to one Participant | none | the invitee's row for that embargo moves from `UNINVITED`, `DECLINED` or `TIMED_OUT` to `INVITED`, carrying the invitation's RSVP deadline; a signatory asked about a revision keeps its `AGREED` row for the embargo in force (MSM-07-002, EP-09-004, CM-28-013) |
| `Accept(Invite(Event))`, from any Participant, the case owner included | none | the sender's row for those terms becomes `AGREED`; that makes it a signatory only once they are the embargo in force (MSM-07-003) |
| `Reject(Invite(Event))`, from any Participant, the case owner included | none | the sender's row for those terms becomes `DECLINED`; refused from an `AGREED` row for the embargo in force, because that is withdrawal (MSM-07-004) |
| The case owner's `Accept(Event, target=Case)` (EA, or EC for a revision) | to `ACTIVE`, or to `REVISE` while another proposal stays open | the owner's row for the activated embargo becomes `AGREED` unless it already is; a revision that ends no later than the embargo it replaces carries over every Participant whose row for the replaced embargo is `AGREED`, and one that ends later writes nothing, so a signatory that has not agreed to it has lapsed (MSM-07-005, MSM-07-008) |
| The case owner's `Reject(Event, target=Case)` (ER, or EJ for a revision) | `PROPOSED` to `NONE`, or `REVISE` to `ACTIVE` with the prior terms standing, once no other proposal is open; once public disclosure, a public exploit or an attack is known, the rejection of the last open revision ends the embargo instead (ET, EMB-04-002) | none, the owner's included (MSM-07-009) |
| Withdrawal, `Leave(Event)` of the embargo in force | none | the withdrawing Participant's `AGREED` row for the embargo in force becomes `DECLINED`, as does every row it had marked `AGREED` for an open revision; the embargo stays in force for everyone else (MSM-07-010) |
| Embargo Termination (ET), `Remove(Event, target=Case)` | `ACTIVE` or `REVISE` to `EXITED` | none is written: with no `ACTIVE` entry nobody is a signatory, and no further message is sent (MSM-07-006) |
| Invitation deadline passes | none | that invitation's `INVITED` row moves to `TIMED_OUT`, recorded in the case ledger (MSM-07-007) |

One activity can therefore move both scopes at once: the case owner's `Accept(Event, target=Case)` activates the embargo *and* makes the owner a signatory.

Only the case manager records an answer; a Participant handed an Accept or Reject meant for the case manager refuses it, and a Reject of terms that are neither in force nor still proposed is refused rather than recorded.
A Participant asked about the embargo already in force, such as one relayed a proposal that was activated before it answered, or a lapsed signatory, answers that Invite by naming it (EP-09-012).
A signatory leaves the embargo in force with `Leave(Event)`, not with a Reject: the case manager refuses a signatory's Reject of the active embargo (MSM-07-004, MSM-07-010).
A signatory that rejects a *proposed* revision is refusing those terms only: it stays a signatory to the embargo in force.
In neither case does the case's embargo change: an answer to an Invite changes no embargo register entry (MSM-07-003, MSM-07-004).
The protocol-level view of consent is in [§9.2 Transitions and Guards in the specification](../../../reference/vultron-spec/tracking-models.md#92-transitions-and-guards).

---

## The condition that overrides everything

If the vulnerability is public, an exploit is public, or attacks have been observed, there is nothing left to embargo.

This is not a preference the negotiation weighs.
It is mandatory, and it applies at every point in the lifecycle:

- A proposal MUST be refused with ER, regardless of any other assessment (EMB-01-002).
- An EA MUST NOT move the case to `ACTIVE`; the actor emits ER instead (EMB-02-002).
- An EV arriving while the case is public MUST be refused, not adopted, and the embargo ends because the case is public, not because the proposal arrived: the proposal is at most how the actor notices (EMB-03-003).
- An actor sitting at `EM.PROPOSED` that *observes* the case go public MUST abandon the proposal, return to `EM.NONE`, and emit ER (EMB-16-001).
  The case manager makes that abandonment for the case, and its committed ER is what notifies everyone else.
  Only the case owner, or the case manager it delegates to, decides that abandonment.
  Any other participant's status report already tells the case manager the case went public, so it sends no ER as the abandonment, which the case manager would read as that participant declining the proposal (EMB-16-002).
  That rule covers only proposals already open on the case.
  A proposal, Invite or revision a participant *receives* while it believes the case is public is still answered with ER by that participant, as the first item above requires (EMB-01-002).
- An actor at `EM.EXITED` MUST NOT seek or accept a new embargo for a public case (EMB-13-002).

EMB-16-001 is the one implementations forget, because it is not triggered by a message.
Nothing arrives to prompt it.
The actor's own state changed, and the obligation follows from that.

---

## Where judgment enters

This is the richest call-out surface in the protocol, because almost every embargo question is a policy question.
Each point below names its capability shape from the [ADR-0024](../../../adr/0024-coordination-agent-taxonomy.md) taxonomy, and each is answered by an injected backend rather than by logic inside the tree ([ADR-0025](../../../adr/0025-call-out-point-abstraction-layer.md)).
Their service contracts are cataloged in the [Capability Model](../../capability_model/index.md#embargo-management).

**Deciding to negotiate.** `WantToProposeEmbargo` (Evaluator) asks whether to propose at all; `SelectEmbargoOfferTerms` (Composer) asks what terms; `StopProposingEmbargo` (Evaluator) asks whether to give up after a refusal.
Their deterministic defaults differ, and the differences encode a recommended posture: propose by default, and do not give up by default.

**Responding to an overture.** `EvaluateEmbargoProposal` (Evaluator) asks whether the terms are acceptable.
Its default is to accept (EMB-15-001, EMB-15-005) — the protocol's position is that a well-formed overture deserves agreement unless there is a reason otherwise.

`WillingToCounterEmbargoProposal` (Evaluator) asks whether to counter instead. Its default is *not* to counter (EMB-15-003), which is the same recommendation in a different form: accept and then revise, rather than trade proposals. Countering introduces no new mechanism — it re-uses the ordinary proposal path and leaves the case at `PROPOSED`.

**Staying in.** `CurrentEmbargoAcceptable` (Evaluator) asks whether the active embargo is still acceptable as circumstances change.

**Getting out early.** `ExitEmbargoWhenFixReady`, `ExitEmbargoWhenDeployed`, and `ExitEmbargoForOtherReason` (all Evaluators) each ask whether a condition now warrants ending the embargo.
All three default to *no*, and the defaults are ordered.
A fix being deployed is a more plausible reason to exit than a fix merely being ready, and "some other reason" is the least plausible of all.
An implementer reading only the code sees three similar nodes; the probabilities are where the editorial judgment is recorded.

**Authorizing the response.** Deciding how the *case* responds to an overture is not every Participant's call.
The response seam puts a case-owner check first: when the deciding actor holds `CVDRole.CASE_OWNER`, its stated response is authoritative and no approval is sought (EMB-15-002, EMB-15-006).
A non-owner — typically a case manager handling the overture on the owner's behalf — routes through `CaseOwnerApprovesEmbargoResponse` (Evaluator, EMB-15-007).

**Reacting to the outcome.** `OnEmbargoAccept`, `OnEmbargoReject`, and `OnEmbargoExit` are Actuators.
They are notification and integration hooks that fire after the transition and confirm a side effect, producing nothing the protocol reads.

!!! note "A default is not a requirement"

    Every "defaults to accept" above describes the stub backend a deployment gets
    when it wires nothing (BT-23-001). None of them is a protocol obligation to
    accept. The one place the protocol *does* mandate an answer is the
    public/exploit/attacks condition, and that is enforced independently of any
    call-out outcome (EMB-15-004).

---

## Inaction is an answer

An `Invite(EmbargoEvent)` carries a respond-by instant, and silence past it ends the invitation — the **pocket veto**.
A Participant whose row is `INVITED` and that does not answer within the window has that row moved to `TIMED_OUT`, not `DECLINED`: silence is not a decision, and `DECLINED` records only an explicit refusal (CM-28-004, [ADR-0118](../../../adr/0118-pec-expired-and-unbound-exited-states.md)).
The deadline belongs to one invitation and is recorded on that invitation's `INVITED` row, so a Participant can hold several open invitations with different deadlines, and one passing times out only its own row (CM-28-013).

The window has two forms and they are one mechanism, not two ([ADR-0065](../../../adr/0065-embargo-invite-rsvp-deadline.md)).
When the invitation carries an explicit `Invite.end_time`, that value governs (CM-28-002).
When it does not, the policy default applies — seven days, measured from the invitation's `published` timestamp (EP-07-001).
The case manager stamps `Invite.end_time` on every invitation it relays.
It then records the invitee's `INVITED` consent row, deadline included, as its own ledger entry right after the Invite's, and every replica copies that row from the entry (CM-28-012, CM-28-013).
A Participant that receives an invitation derives no deadline of its own.

There is a floor. An inviting actor must not send a window shorter than the configured minimum, defaulting to 72 hours (EP-07-002).
The case manager, as the actor that stamps the relayed invitation, clamps a too-short window up to the minimum and logs the clamp; it does **not** reject the proposal as malformed (EP-07-003, EP-07-004, EP-07-005).
Refusing a too-short invitation would punish the invitee for the inviter's error.

There is also a ceiling: the deadline never falls after the invited embargo ends (EP-07-006, CM-28-011).
A deadline past that end, whether sent explicitly or computed from the policy window, is lowered to the end and the clamp is logged.
The floor gives way to the ceiling: the minimum is 72 hours or the time left in the embargo, whichever is shorter (EP-07-002).
On day 28 of a 30-day embargo, the invitee has until day 30 to answer, not seven days.

The case manager runs no timer; it notices a passed deadline the next time it handles an embargo activity for the case.
At that point it moves each overdue `INVITED` row on an open proposal or the embargo in force to `TIMED_OUT`, and records each move in the case ledger (CM-28-015).
It does so before it records the case owner's decision on a proposal, and before every other embargo activity it receives or sends.
The case owner learns of each expiry from that ledger entry, so it decides on the embargo knowing who never answered.
The case manager checks only once it knows the sender may send the activity, and before it judges the activity itself, so the expiry is recorded even when the activity is then refused.
One exception: when the case manager refuses an Invite or an `Accept` because the vulnerability is already public, exploited or attacked (EMB-02-002), it does not check for overdue invitations; the next embargo activity it admits does.

A late `Accept` is never refused merely for being late (EMB-17-001).
The case manager instead asks whether the accepted embargo is still the case's current one, and the three answers are all different:

| What the late Accept refers to | What the case manager does |
|---|---|
| The case's current embargo | Honor it; record the Participant's consent row as `AGREED`, exactly as for an on-time Accept, directly from `TIMED_OUT` or `DECLINED` (EMB-17-002) |
| A superseded embargo | Send a fresh invitation carrying the current terms. Do **not** record consent to terms the actor never saw (EMB-17-003, EMB-17-005) |
| An embargo the case no longer has | Acknowledge as a no-op: record its own `Ignore` of the late `Accept`, and change no consent. Do not invite, and do not remove the actor from the case (EMB-17-004, EMB-17-007, EMB-17-008, EMB-17-010) |

Note what none of the three rows does: remove the accepting actor.
Answering late is not a protocol violation.

---

## What the case learns

Embargo messages route through the case manager like every other case-scoped message (PCR-08-001).
A Participant does not announce its embargo stance to the other Participants itself.

Teardown is the exception worth naming, because its addressing is prescribed.
The `Announce(EmbargoEvent)` that follows a teardown must be authored by the actor holding `CVDRole.CASE_MANAGER` and addressed to every Participant *except* the announcing actor — never to the case manager itself (EMB-19-001).
When the case manager is the only Participant, the announcement is skipped rather than sent with an empty recipient list (EMB-19-002).

On entering `EM.EXITED`, no Participant is bound by an embargo any more, and no later invitation can bind one (EMB-13-001, MSM-07-006).
No consent row is written for this: the register holds no `ACTIVE` entry, and the register is the fact.
The embargo is over for everyone at once, which is the one thing about the EM scope that is genuinely global.

### The case status EM copy is read-only

A `CaseStatus` carries one EM copy — a stamped read of the case's embargo register.
That copy is **read-only**: `CaseStatus.em` is a frozen field and `EmDimension` is a frozen model (SDO-03-006, EMB-18-001).
Every in-place write path raises a `ValidationError` at runtime: `status.em = …`, `status.em.state = …`, and the retired flat spelling `status.em_state = …`, which `CaseStatus` no longer defines (SDO-03-003).

The only writer is the case itself.
When its embargo register changes — through any `EmbargoLifecycle` operation or the function that applies a committed entry — the case replaces its current status with a `model_copy` carrying the new `EmDimension`.
Nothing else may write that copy.
A status with a different EM state is built by construction or by `model_copy(update={"em": EmDimension(state=…)})`; assignment through an existing instance always raises.

---

## What conformance requires

| Requirement | Obligation |
|---|---|
| [EMB-01-002](../../../reference/specs/protocol.md#emb-01-002) | A proposal MUST be refused with ER when the case is public, exploited, or attacked |
| [EMB-02-002](../../../reference/specs/protocol.md#emb-02-002) | An EA MUST NOT activate an embargo on a public case; emit ER |
| [EMB-03-001](../../../reference/specs/protocol.md#emb-03-001) | An EV in `EM.ACTIVE` MUST move to `EM.REVISE`, leaving the active embargo in force |
| [EMB-06-001](../../../reference/specs/protocol.md#emb-06-001) | An ER in `EM.PROPOSED` MUST return the case to `EM.NONE` when it rejects the last open proposal, and leave it `PROPOSED` while another is open |
| [EMB-13-002](../../../reference/specs/protocol.md#emb-13-002) | An actor at `EM.EXITED` MUST NOT accept a new embargo for a public case |
| [EMB-15-002](../../../reference/specs/protocol.md#emb-15-002) | The response seam MUST bypass approval when the deciding actor is the case owner |
| [EMB-16-001](../../../reference/specs/protocol.md#emb-16-001) | An actor at `EM.PROPOSED` observing the case go public MUST abandon the proposal and emit ER |
| [EMB-16-002](../../../reference/specs/protocol.md#emb-16-002) | A participant that is not the case manager MUST NOT emit ER as that abandonment or write it itself; it still answers what it receives under EMB-01-002 |
| [EMB-17-001](../../../reference/specs/protocol.md#emb-17-001) | A late `Accept` MUST NOT be refused solely because the deadline passed |
| [EMB-18-001](../../../reference/specs/architecture.md#emb-18-001) | Every EM transition MUST route through the embargo lifecycle service or the function that applies a committed entry |
| [EMB-18-003](../../../reference/specs/architecture.md#emb-18-003) | A case MUST NOT name an embargo whose record its store does not hold |
| [EMB-19-001](../../../reference/specs/protocol.md#emb-19-001) | A teardown announcement MUST be authored by the case manager and exclude it from the recipients |
| [EP-04-001](../../../reference/specs/protocol.md#ep-04-001) | A default embargo applied at case creation MUST produce `EM.ACTIVE`, not `EM.PROPOSED` |
| [EP-07-003](../../../reference/specs/protocol.md#ep-07-003) | A sub-minimum RSVP deadline MUST be clamped up, not rejected |

---

## Further reading

- [Embargo Management Behaviors](../em_bt.md) — the original design trees for proposal, evaluation, and termination
- [Propose case](propose-case.md) — where the default embargo comes from
- [Embargo Management Handlers](../../../reference/behaviors/em_handlers.md) — the trees the reference implementation builds today
- [EM Process Model](../../process_models/em/index.md) — the case-level embargo model, with its [formal definition](../../process_models/em/formal_model.md)
- [Glossary](../../../reference/glossary.md) — Participant, call-out point, capability shape, embargo consent
